package ipvs

//import (
//	"fmt"
//	_ "k8s.io/kubernetes/pkg/proxy"
//	utildbus "k8s.io/kubernetes/pkg/util/dbus"
//	"k8s.io/kubernetes/pkg/util/exec"
//	utilipvs "k8s.io/kubernetes/pkg/util/ipvs"
//	"net"
//	"testing"
//)
//
//const testHostname = "test-hostname"
//
//type fakePortOpener struct {
//	openPorts []*localPort
//}
//
//func NewFakeProxier(ipt utilipvs.Interface, execer exec.Interface) *Proxier {
//	// TODO: Call NewProxier after refactoring out the goroutine
//	// invocation into a Run() method.
//	ipt.InitIpvsInterface()
//	return &Proxier{
//		exec:             execer,
//		serviceMap:       make(proxyServiceMap),
//		serviceChanges:   newServiceChangeMap(),
//		endpointsMap:     make(proxyEndpointsMap),
//		endpointsChanges: newEndpointsChangeMap(),
//		ipvs:             ipt,
//		clusterCIDR:      "10.0.0.0/24",
//		hostname:         testHostname,
//		portsMap:         make(map[localPort]closeable),
//		//portMapper:       &fakePortOpener{[]*localPort{}},
//		//healthChecker:    newFakeHealthChecker(),
//	}
//}
//
//func Test_getservice(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//	Svcs, _ := prox.ipvs.GetServices()
//	for _, svc := range Svcs {
//		srv, _ := svc.GetService()
//		fmt.Println(srv.Address.String())
//	}
//}
//
//func Test_addservice(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//
//	svc := utilipvs.Service{
//		Address:   net.ParseIP("100.109.161.75"),
//		Port:      uint16(11122),
//		Protocol:  string("TCP"),
//		Scheduler: utilipvs.DefaultIPVSScheduler,
//	}
//
//	prox.ipvs.AddService(&svc)
//}
//
//func Test_delservice(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//
//	svc := utilipvs.Service{
//		Address:   net.ParseIP("192.168.222.222"),
//		Port:      uint16(11122),
//		Protocol:  string("TCP"),
//		Scheduler: utilipvs.DefaultIPVSScheduler,
//	}
//
//	prox.ipvs.DeleteService(&svc)
//}
//
//func Test_setalias(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//
//	svc := utilipvs.Service{
//		Address:   net.ParseIP("192.168.222.222"),
//		Port:      uint16(11122),
//		Protocol:  string("TCP"),
//		Scheduler: utilipvs.DefaultIPVSScheduler,
//	}
//
//	prox.ipvs.SetAlias(&svc)
//}
//
//func Test_unsetalias(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//
//	svc := utilipvs.Service{
//		Address:   net.ParseIP("192.168.222.222"),
//		Port:      uint16(11122),
//		Protocol:  string("TCP"),
//		Scheduler: utilipvs.DefaultIPVSScheduler,
//	}
//
//	prox.ipvs.UnSetAlias(&svc)
//}
//
//func Test_flush(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	//	prox := NewFakeProxier(IPVSInterface, execer)
//	IPVSInterface.InitIpvsInterface()
//	IPVSInterface.Flush()
//	//	fmt.Println(prox.ipvs.Flush())
//}
//
//func Test_createAliasDevice(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//	err := prox.ipvs.CreateAliasDevice("kube-ipvs0")
//	if err != nil {
//		fmt.Println(err.Error())
//	}
//}
//
//func Test_deleteAliasDevice(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//	err := prox.ipvs.DeleteAliasDevice("kube-ipvs0")
//	if err != nil {
//		fmt.Println("error")
//		fmt.Println(err.Error())
//	}
//
//}
//
//func Test_deleteService(t *testing.T) {
//	execer := exec.New()
//	var dbus utildbus.Interface
//	dbus = utildbus.New()
//	IPVSInterface := utilipvs.New(execer, dbus)
//	prox := NewFakeProxier(IPVSInterface, execer)
//
//	svc := utilipvs.Service{
//		Address:  net.ParseIP("192.168.11.11"),
//		Port:     uint16(11111),
//		Protocol: string("TCP"),
//		//Scheduler: utilipvs.DefaultIPVSScheduler,
//	}
//
//	err := prox.ipvs.DeleteService(&svc)
//	if err != nil {
//		fmt.Println("error")
//		fmt.Println(err.Error())
//	}
//
//}