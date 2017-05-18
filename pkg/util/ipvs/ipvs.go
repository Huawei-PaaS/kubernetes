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

	godbus "github.com/godbus/dbus"
	"github.com/golang/glog"
	"github.com/google/seesaw/ipvs"
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

	SFPersistent uint32 = ipvsSvcFlagPersist
	SFHashed     uint32 = ipvsSvcFlagHashed
	SFOnePacket  uint32 = ipvsSvcFlagOnePacket
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
		svc.Flags == other.Flags &&
		svc.Timeout == other.Timeout
}

type ipvsServiceHandler struct {
	*ipvs.Service
}

type ServiceInterface interface {
	GetService() (*Service, error)
	AddDestination(*Destination) error
	GetDestinations() ([]*Destination, error)
	UpdateDestination(*Destination) error
	DeleteDestination(*Destination) error
}

//Replica of IPVS Destination
type Destination struct {
	Address net.IP
	Port    uint16
	Weight  int32
}

var ipvsModules = []string{
	"ip_vs",
	"ip_vs_rr",
	"ip_vs_wrr",
	"ip_vs_sh",
	"nf_conntrack_ipv4",
}

var aliasDevice string = "ipvs0"

// An injectable interface for running iptables commands.  Implementations must be goroutine-safe.
type Interface interface {
	InitIpvsInterface() error
	CreateAliasDevice(aliasDev string) error
	DeleteAliasDevice(aliasDev string) error
	SetAlias(serv *Service) error
	UnSetAlias(serv *Service) error
	GetVersion() string
	AddService(*Service) error
	UpdateService(*Service) error
	DeleteService(*Service) error
	GetService(*Service) (ServiceInterface, error)
	GetServices() ([]ServiceInterface, error)
	AddReloadFunc(reloadFunc func())
	Flush() error
	Destroy()
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
func (runner *runner) GetVersion() string {
	return ipvs.Version().String()
}

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

	if err := runner.CreateAliasDevice(aliasDevice); err != nil {
		glog.Errorf("createAliasDevice: Alias network device cannot be created. Error: %v", err)
		return err
	}

	if err := ipvs.Init(); err != nil {
		return err

	}

	return nil
}

func ToProtocolNumber(protocol string) ipvs.IPProto {
	switch strings.ToLower(protocol) {
	case "tcp":
		return ipvs.IPProto(syscall.IPPROTO_TCP)
	case "udp":
		return ipvs.IPProto(syscall.IPPROTO_UDP)
	}

	return ipvs.IPProto(0)
}

func (runner *runner) AddService(svc *Service) error {
	if svc.Scheduler == "" {
		svc.Scheduler = DefaultIPVSScheduler
	}

	return ipvs.AddService(ipvs.Service{
		Address:   svc.Address,
		Port:      svc.Port,
		Protocol:  ToProtocolNumber(svc.Protocol),
		Scheduler: svc.Scheduler,
		Flags:     ipvs.ServiceFlags(svc.Flags),
	})
}

//Empty Implementation
func (runner *runner) UpdateService(svc *Service) error {
	return nil
}

func (runner *runner) DeleteService(svc *Service) error {
	return ipvs.DeleteService(ipvs.Service{
		Address:  svc.Address,
		Port:     svc.Port,
		Protocol: ToProtocolNumber(svc.Protocol),
	})
}

func (runner *runner) CreateAliasDevice(aliasDev string) error {

	if aliasDev == aliasDevice {
		cmd := "ip"

		//
		// Generate device alias
		//
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
	if aliasDev == aliasDevice {
		cmd := "ip"

		//
		// Delete device alias
		//
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
	//
	cmd := "ifconfig"

	//
	// Generate device alias
	//
	alias := aliasDevice + ":" + strconv.FormatUint(uint64(IPtoInt(serv.Address)), 10)
	args := []string{alias, serv.Address.String(), "up"}
	if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
		// "exit status 255" is returned from the above run command if the alias exists
		if !strings.Contains(fmt.Sprintf("%v", err), "exit status 255") {
			glog.Errorf("Error: Cannot create alias for service : alias: %s, service: %v, error: %v", alias, serv.Address, err)
			return err
		}
	}
	glog.V(6).Infof(" Succeeded: Set ailias [%s] to network device [%s]", serv.Address.String(), alias)
	return nil
}

func (runner *runner) UnSetAlias(serv *Service) error {
	// TODO:  Hard code command to config aliases to network device
	//
	cmd := "ifconfig"

	//
	// Unset device alias
	//
	alias := aliasDevice + ":" + strconv.FormatUint(uint64(IPtoInt(serv.Address)), 10)
	args := []string{alias, "down"}
	if _, err := runner.exec.Command(cmd, args...).CombinedOutput(); err != nil {
		// "exit status 255" is returned from the above run command if the alias is not exists
		if !strings.Contains(fmt.Sprintf("%v", err), "exit status 255") {
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

func (runner *runner) GetService(svc *Service) (ServiceInterface, error) {
	ipvsService, err := ipvs.GetService(&ipvs.Service{
		Address:  svc.Address,
		Port:     svc.Port,
		Protocol: ToProtocolNumber(svc.Protocol),
	})
	if err != nil {
		return nil, err
	}

	return &ipvsServiceHandler{Service: ipvsService}, nil
}

func (runner *runner) GetServices() ([]ServiceInterface, error) {
	ipvsServices, err := ipvs.GetServices()
	if err != nil {
		return nil, err
	}

	svcs := make([]ServiceInterface, 0)
	for _, svc := range ipvsServices {
		svcs = append(svcs, &ipvsServiceHandler{Service: svc})
	}

	return svcs, nil
}

func (runner *runner) Flush() error {
	return ipvs.Flush()
}

func (svcHandler *ipvsServiceHandler) AddDestination(dst *Destination) error {
	if svcHandler.Service == nil {
		return errors.New("Invalid Service Interface")
	}

	err := ipvs.AddDestination(*svcHandler.Service, ipvs.Destination{
		Address: dst.Address,
		Port:    dst.Port,
		Weight:  dst.Weight,
	})
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
func (svcHandler *ipvsServiceHandler) UpdateDestination(dst *Destination) error {
	if svcHandler.Service == nil {
		return errors.New("Invalid Service Interface")
	}
	return nil
}

func (svcHandler *ipvsServiceHandler) DeleteDestination(dst *Destination) error {
	if svcHandler.Service == nil {
		return errors.New("Invalid Service Interface")
	}

	return ipvs.DeleteDestination(*svcHandler.Service, ipvs.Destination{
		Address: dst.Address,
		Port:    dst.Port,
		Weight:  dst.Weight,
	})
}

func (svcHandler *ipvsServiceHandler) GetDestinations() ([]*Destination, error) {
	if svcHandler.Service == nil {
		return nil, errors.New("Invalid Service Interface")
	}

	destinations := make([]*Destination, 0)

	for _, dest := range svcHandler.Destinations {
		destinations = append(destinations, &Destination{
			Address: dest.Address,
			Port:    dest.Port,
			Weight:  dest.Weight,
		})
	}

	glog.V(6).Infof("Destinations: [%+v] return", destinations)
	return destinations, nil
}

func (svcHandler *ipvsServiceHandler) GetService() (*Service, error) {
	if svcHandler.Service == nil {
		return nil, errors.New("Invalid Service Interface")
	}

	return &Service{
		Address:   svcHandler.Address,
		Port:      svcHandler.Port,
		Scheduler: svcHandler.Scheduler,
		Protocol:  svcHandler.Protocol.String(),
	}, nil
}
