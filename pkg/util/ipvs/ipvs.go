/*
Copyright 2014 The Kubernetes Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package ipvs

import (
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"strconv"
	"strings"
	"sync"

	"github.com/docker/libnetwork/ipvs"
	godbus "github.com/godbus/dbus"
	"github.com/golang/glog"
	utildbus "k8s.io/kubernetes/pkg/util/dbus"
	utilexec "k8s.io/kubernetes/pkg/util/exec"
	utilsysctl "k8s.io/kubernetes/pkg/util/sysctl"

	"syscall"
)

const (
	DefaultIPVSScheduler = "rr"

	// In "ipvs" proxy mode, the following two flags need to be set
	sysctlVsConnTrack = "net/ipv4/vs/conntrack"
	sysctlForward     = "net/ipv4/ip_forward"

	ipvsSvcFlagPersist   = 0x1
	ipvsSvcFlagHashed    = 0x2
	ipvsSvcFlagOnePacket = 0x4
)

// Replica of IPVS Service.
type Service struct {
	Address   net.IP
	Protocol  string
	Port      uint16
	Scheduler string
	Flags     uint32
	Timeout   uint32
}

func (svc *Service) Equal(other *Service) bool {
	return svc.Address.Equal(other.Address) &&
		svc.Protocol == other.Protocol &&
		svc.Port == other.Port &&
		svc.Scheduler == other.Scheduler &&
		svc.Timeout == other.Timeout
}

//Replica of IPVS Destination
type Destination struct {
	Address net.IP
	Port    uint16
	Weight  int
}

var ipvsModules = []string{
	"ip_vs",
	"ip_vs_rr",
	"ip_vs_wrr",
	"ip_vs_sh",
	"nf_conntrack_ipv4",
}

const AliasDevice = "kube0"
const cmd = "ip"

const (
	SFPersistent ServiceFlags = ipvsSvcFlagPersist
	SFHashed     ServiceFlags = ipvsSvcFlagHashed
	SFOnePacket  ServiceFlags = ipvsSvcFlagOnePacket
)

// ServiceFlags specifies the flags for a IPVS service.
type ServiceFlags uint32

const DefaultIpvsScheduler = "rr"

// An injectable interface for running iptables commands.  Implementations must be goroutine-safe.
type Interface interface {
	InitIpvsInterface() error
	CreateAliasDevice(aliasDev string) error
	DeleteAliasDevice(aliasDev string) error
	SetAlias(serv *Service) error
	UnSetAlias(serv *Service) error
	AddService(*Service) error
	UpdateService(*Service) error
	DeleteService(*Service) error
	GetService(*Service) (*Service, error)
	GetServices() ([]*Service, error)
	AddReloadFunc(reloadFunc func())
	Flush() error
	Destroy()

	AddDestination(*Service, *Destination) error
	GetDestinations(*Service) ([]*Destination, error)
	UpdateDestination(*Service, *Destination) error
	DeleteDestination(*Service, *Destination) error
}

type Protocol byte

const (
	ProtocolIpv4 Protocol = iota + 1
	ProtocolIpv6
)

const (
	firewalldName      = "org.fedoraproject.FirewallD1"
	firewalldPath      = "/org/fedoraproject/FirewallD1"
	firewalldInterface = "org.fedoraproject.FirewallD1"
)

// runner implements Interface in terms of exec("ipvs").
type runner struct {
	mu          sync.Mutex
	exec        utilexec.Interface
	dbus        utildbus.Interface
	sysctl      utilsysctl.Interface
	protocol    Protocol
	reloadFuncs []func()
	signal      chan *godbus.Signal
}

// New returns a new Interface which will exec IPVS.
func New(exec utilexec.Interface, dbus utildbus.Interface) Interface {
	runner := &runner{
		exec:   exec,
		dbus:   dbus,
		sysctl: utilsysctl.New(),
	}

	// TODO this needs to be moved to a separate Start() or Run() function so that New() has zero side
	// effects.
	runner.connectToFirewallD()
	return runner
}

// Destroy is part of Interface.
func (runner *runner) Destroy() {
	if runner.signal != nil {
		runner.signal <- nil
	}
}

// Connects to D-Bus and listens for FirewallD start/restart. (On non-FirewallD-using
// systems, this is effectively a no-op; we listen for the signals, but they will never be
// emitted, so reload() will never be called.)
func (runner *runner) connectToFirewallD() {
	bus, err := runner.dbus.SystemBus()
	if err != nil {
		glog.V(1).Infof("Could not connect to D-Bus system bus: %s", err)
		return
	}

	rule := fmt.Sprintf("type='signal',sender='%s',path='%s',interface='%s',member='Reloaded'", firewalldName, firewalldPath, firewalldInterface)
	bus.BusObject().Call("org.freedesktop.DBus.AddMatch", 0, rule)

	rule = fmt.Sprintf("type='signal',interface='org.freedesktop.DBus',member='NameOwnerChanged',path='/org/freedesktop/DBus',sender='org.freedesktop.DBus',arg0='%s'", firewalldName)
	bus.BusObject().Call("org.freedesktop.DBus.AddMatch", 0, rule)

	runner.signal = make(chan *godbus.Signal, 10)
	bus.Signal(runner.signal)

	go runner.dbusSignalHandler(bus)
}

// GetVersion returns the version string.
/*func (runner *runner) GetVersion() string {
	return ipvs.Version().String()
}*/

var ipvs_handle *ipvs.Handle

type IPProto uint16

func (runner *runner) InitIpvsInterface() error {
	glog.V(6).Infof("Preparation for ipvs")

	// The system command "modeprobe" is hard coded here.
	for _, module := range ipvsModules {
		_, err := runner.exec.Command("modprobe", module).CombinedOutput()
		if err != nil {
			glog.Errorf("Error: Can not load module: %s in lvs proxier", module)
			return err
		}
	}

	// Setup ioctrl flags
	if err := runner.setSystemFlagInt(sysctlVsConnTrack, 1); err != nil {
		return err
	}
	if err := runner.setSystemFlagInt(sysctlForward, 1); err != nil {
		return err
	}

	if err := runner.CreateAliasDevice(AliasDevice); err != nil {
		glog.Errorf("createAliasDevice: Alias network device cannot be created. Error: %v", err)
		return err
	}

	var err error
	if ipvs_handle, err = ipvs.New(""); err != nil {
		glog.Errorf("InitIpvsInterface: Ipvs cannot be Inited. Error: %v", err)
		return err
	}

	return nil
}

func ToProtocolNumber(protocol string) uint16 {
	switch strings.ToLower(protocol) {
	case "tcp":
		return uint16(syscall.IPPROTO_TCP)
	case "udp":
		return uint16(syscall.IPPROTO_UDP)
	}

	return uint16(0)
}

func (runner *runner) AddService(svc *Service) error {
	if svc.Scheduler == "" {
		svc.Scheduler = DefaultIPVSScheduler
	}

	return ipvs_handle.NewService(NewIpvsService(svc))
}

//Empty Implementation
func (runner *runner) UpdateService(svc *Service) error {
	return nil
}

func (runner *runner) DeleteService(svc *Service) error {

	return ipvs_handle.DelService(NewIpvsService(svc))
}

func (runner *runner) CreateAliasDevice(aliasDev string) error {

	if aliasDev == AliasDevice {
		// Generate device alias
		args := []string{"link", "add", aliasDev, "type", "dummy"}
		if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
			// "exit status 2" is returned from the above run command if the device already exists
			if !strings.Contains(fmt.Sprintf("%v", err), "exit status 2") {
				glog.Errorf("Error: Cannot create alias network device: %s", aliasDev)
				return err
			}
			glog.V(6).Infof(" Info: Alias network device already exists and skip create: args: %s", args)
			return nil
		}
		glog.V(6).Infof(" Succeeded: Create alias device: %s", aliasDev)
	}

	return nil

}

func (runner *runner) DeleteAliasDevice(aliasDev string) error {
	if aliasDev == AliasDevice {
		// Delete device alias
		args := []string{"link", "del", aliasDev}
		if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
			// "exit status 2" is returned from the above run command if the device don't exists
			if !strings.Contains(fmt.Sprintf("%v", err), "exit status 2") {
				glog.Errorf("Error: Cannot delete alias network device: %s", aliasDev)
				return err
			}
			glog.V(6).Infof(" Info: Alias network device don't exists and skip delete: args: %s", args)
			return nil
		}
		glog.V(6).Infof(" Succeeded: Delete alias device: %s", aliasDev)
	}

	return nil
}

func (runner *runner) setSystemFlagInt(sysControl string, value int) error {
	if val, err := runner.sysctl.GetSysctl(sysControl); err == nil && val != value {
		runner.sysctl.SetSysctl(sysControl, value)
	} else if err != nil {
		glog.Errorf("Error: System control flag [%s] cannot be set", sysControl)
		return err
	}
	return nil
}

func (runner *runner) SetAlias(serv *Service) error {
	// TODO:  Hard code command to config aliases to network device

	// Generate device alias
	alias := AliasDevice + ":" + strconv.FormatUint(uint64(IPtoInt(serv.Address)), 10)
	args := []string{"addr", "add", serv.Address.String(), "dev", AliasDevice, "label", alias}
	if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
		// "exit status 2" is returned from the above run command if the alias exists
		if !strings.Contains(fmt.Sprintf("%v", err), "exit status 2") {
			glog.Errorf("Error: Cannot create alias for service : alias: %s, service: %v, error: %v", alias, serv.Address, err)
			return err
		}
	}
	glog.V(6).Infof(" Succeeded: Set ailias [%s] to network device [%s]", serv.Address.String(), alias)
	return nil
}

func (runner *runner) UnSetAlias(serv *Service) error {
	// TODO:  Hard code command to config aliases to network device

	// Unset device alias
	alias := AliasDevice + ":" + strconv.FormatUint(uint64(IPtoInt(serv.Address)), 10)
	args := []string{"addr", "del", serv.Address.String(), "dev", AliasDevice, "label", alias}
	if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
		// "exit status 2" is returned from the above run command if the alias is not exists
		if !strings.Contains(fmt.Sprintf("%v", err), "exit status 2") {
			glog.Errorf("Error: Cannot unset alias for service : alias: %s, service: %v, error: %v", alias, serv.Address, err)
			return err
		}
	}
	glog.V(6).Infof(" Succeeded: UnSet ailias [%s] to network device [%s]", serv.Address.String(), alias)
	return nil
}

func IPtoInt(ip net.IP) uint32 {
	if len(ip) == 16 {
		return binary.BigEndian.Uint32(ip[12:16])
	}
	return binary.BigEndian.Uint32(ip)
}

//// goroutine to listen for D-Bus signals
func (runner *runner) dbusSignalHandler(bus utildbus.Connection) {
	firewalld := bus.Object(firewalldName, firewalldPath)

	for s := range runner.signal {
		if s == nil {
			// Unregister
			bus.Signal(runner.signal)
			return
		}

		switch s.Name {
		case "org.freedesktop.DBus.NameOwnerChanged":
			name := s.Body[0].(string)
			new_owner := s.Body[2].(string)

			if name != firewalldName || len(new_owner) == 0 {
				continue
			}

			// FirewallD startup (specifically the part where it deletes
			// all existing iptables rules) may not yet be complete when
			// we get this signal, so make a dummy request to it to
			// synchronize.
			firewalld.Call(firewalldInterface+".getDefaultZone", 0)

			runner.reload()
		case firewalldInterface + ".Reloaded":
			runner.reload()
		}
	}
}

// AddReloadFunc is part of Interface
func (runner *runner) AddReloadFunc(reloadFunc func()) {
	runner.reloadFuncs = append(runner.reloadFuncs, reloadFunc)
}

//// runs all reload funcs to re-sync iptables rules
func (runner *runner) reload() {
	glog.V(1).Infof("reloading iptables rules")

	for _, f := range runner.reloadFuncs {
		f()
	}
}

func (runner *runner) GetService(svc *Service) (*Service, error) {
	ipvsService, err := ipvs_handle.GetService(NewIpvsService(svc))
	if err != nil {
		return nil, err
	}
	var rsvc *Service
	rsvc, err = toService(ipvsService)
	if err != nil {
		return nil, err
	}
	return rsvc, nil
}

func (runner *runner) GetServices() ([]*Service, error) {
	ipvsServices, err := ipvs_handle.GetServices()
	if err != nil {
		return nil, err
	}

	svcs := make([]*Service, 0)

	for _, ipvsService := range ipvsServices {
		svc, err := toService(ipvsService)
		if err != nil {
			return nil, err
		}
		svcs = append(svcs, svc)
	}

	return svcs, nil
}

func (runner *runner) Flush() error {
	Services, err := runner.GetServices()
	if err != nil {
		return err
	}
	for _, service := range Services {
		err := runner.DeleteService(service)
		if err != nil {
			return err
		}
	}
	return nil
}

func (runner *runner) AddDestination(svc *Service, dst *Destination) error {
	if svc == nil {
		return errors.New("Invalid Service Interface")
	}

	err := ipvs_handle.NewDestination(NewIpvsService(svc), NewIPVSDestination(dst))
	if err != nil {
		if !strings.Contains(err.Error(), "object exists") {
			glog.Errorf("Error: Cannot add destination: %v, error: %v", dst, err)
			return err
		}
	}

	glog.V(6).Infof("Endpoints: [%+v] added", dst)
	return nil
}

//Empty Implementation
func (runner *runner) UpdateDestination(svc *Service, dst *Destination) error {
	if svc == nil {
		return errors.New("Invalid Service Interface")
	}
	return nil
}

func (runner *runner) DeleteDestination(svc *Service, dst *Destination) error {
	if svc == nil {
		return errors.New("Invalid Service Interface")
	}

	return ipvs_handle.DelDestination(NewIpvsService(svc), NewIPVSDestination(dst))
}

func (runner *runner) GetDestinations(svc *Service) ([]*Destination, error) {
	if svc == nil {
		return nil, errors.New("Invalid Service Interface")
	}

	destinations := make([]*Destination, 0)

	Destinations, err := ipvs_handle.GetDestinations(NewIpvsService(svc))

	if err != nil {
		glog.Errorf("Error: Failed to  Getdestination for Service: %v, error: %v", svc, err)
		return nil, err
	}

	for _, dest := range Destinations {
		dst, err := toDestination(dest)
		if err != nil {
			return nil, err
		}
		destinations = append(destinations, dst)
	}

	glog.V(6).Infof("Destinations: [%+v] return", destinations)
	return destinations, nil
}

// toService converts a service entry from its IPVS representation to the Go
// equivalent Service structure.
func toService(svc *ipvs.Service) (*Service, error) {
	if svc == nil {
		return nil, errors.New("Invalid Service Interface")
	}

	return &Service{
		Address:   svc.Address,
		Port:      svc.Port,
		Scheduler: svc.SchedName,
		Protocol:  String(IPProto(svc.Protocol)),
		Flags:     svc.Flags,
		Timeout:   svc.Timeout,
	}, nil
}

// toDestination converts a destination entry from its IPVS representation
// to the Go equivalent Destination structure.
func toDestination(ipvsDst *ipvs.Destination) (*Destination, error) {
	if ipvsDst == nil {
		return nil, errors.New("Invalid ipvsDst Interface")
	}
	dst := &Destination{
		Address: ipvsDst.Address,
		Port:    ipvsDst.Port,
		Weight:  ipvsDst.Weight,
	}

	return dst, nil
}

// newIPVSService converts a service to its IPVS representation.
func NewIpvsService(svc *Service) *ipvs.Service {
	ipvsSvc := &ipvs.Service{
		Address:   svc.Address,
		Protocol:  ToProtocolNumber(svc.Protocol),
		Port:      svc.Port,
		SchedName: svc.Scheduler,
		Flags:     svc.Flags,
		Timeout:   svc.Timeout,
	}
	if ip4 := svc.Address.To4(); ip4 != nil {
		ipvsSvc.AddressFamily = syscall.AF_INET
		ipvsSvc.Netmask = 0xffffffff
	} else {
		ipvsSvc.AddressFamily = syscall.AF_INET6
		ipvsSvc.Netmask = 128
	}
	return ipvsSvc
}

// newIPVSDestination converts a destination to its IPVS representation.
func NewIPVSDestination(dst *Destination) *ipvs.Destination {
	return &ipvs.Destination{
		Address: dst.Address,
		Port:    dst.Port,
		Weight:  dst.Weight,
	}
}

// String returns the name for the given protocol value.
func String(proto IPProto) string {
	switch proto {
	case syscall.IPPROTO_TCP:
		return "TCP"
	case syscall.IPPROTO_UDP:
		return "UDP"
	}
	return fmt.Sprintf("IP(%d)", proto)
}
