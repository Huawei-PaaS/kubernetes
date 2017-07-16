// +build linux

/*
Copyright 2017 The Kubernetes Authors.

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
	"net"
	"reflect"
	"syscall"
	"testing"

	"k8s.io/apimachinery/pkg/util/sets"
	"k8s.io/utils/exec"
	fakeexec "k8s.io/utils/exec/testing"

	"github.com/docker/libnetwork/ipvs"
)

const dummyDevice = "kube-ipvs0"

func TestEnsureDummyDevice(t *testing.T) {
	fcmd := fakeexec.FakeCmd{
		CombinedOutputScript: []fakeexec.FakeCombinedOutputAction{
			// Success.
			func() ([]byte, error) { return []byte{}, nil },
			// Exists.
			func() ([]byte, error) { return nil, &fakeexec.FakeExitError{Status: 2} },
		},
	}
	fexec := fakeexec.FakeExec{
		CommandScript: []fakeexec.FakeCommandAction{
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
		},
	}
	runner := New(&fexec)
	// Success.
	exists, err := runner.EnsureDummyDevice(dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if exists {
		t.Errorf("expected exists = false")
	}
	if fcmd.CombinedOutputCalls != 1 {
		t.Errorf("expected 1 CombinedOutput() calls, got %d", fcmd.CombinedOutputCalls)
	}
	if !sets.NewString(fcmd.CombinedOutputLog[0]...).HasAll("ip", "link", "add", "kube-ipvs0", "type", "dummy") {
		t.Errorf("wrong CombinedOutput() log, got %s", fcmd.CombinedOutputLog[0])
	}
	// Exists.
	exists, err = runner.EnsureDummyDevice(dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if !exists {
		t.Errorf("expected exists = true")
	}
}

func TestDeleteDummyDevice(t *testing.T) {
	fcmd := fakeexec.FakeCmd{
		CombinedOutputScript: []fakeexec.FakeCombinedOutputAction{
			// Success.
			func() ([]byte, error) { return []byte{}, nil },
			// Failure.
			func() ([]byte, error) { return nil, &fakeexec.FakeExitError{Status: 1} },
		},
	}
	fexec := fakeexec.FakeExec{
		CommandScript: []fakeexec.FakeCommandAction{
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
		},
	}
	runner := New(&fexec)
	// Success.
	err := runner.DeleteDummyDevice(dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if fcmd.CombinedOutputCalls != 1 {
		t.Errorf("expected 1 CombinedOutput() calls, got %d", fcmd.CombinedOutputCalls)
	}
	if !sets.NewString(fcmd.CombinedOutputLog[0]...).HasAll("ip", "link", "del", "kube-ipvs0") {
		t.Errorf("wrong CombinedOutput() log, got %s", fcmd.CombinedOutputLog[0])
	}
	// Failure.
	err = runner.DeleteDummyDevice(dummyDevice)
	if err == nil {
		t.Errorf("expected failure")
	}
}

func TestEnsureServiceAddressBind(t *testing.T) {
	svc := &InternalService{
		Address:  net.ParseIP("10.20.30.40"),
		Port:     uint16(1234),
		Protocol: string("TCP"),
	}
	fcmd := fakeexec.FakeCmd{
		CombinedOutputScript: []fakeexec.FakeCombinedOutputAction{
			// Success.
			func() ([]byte, error) { return []byte{}, nil },
			// Exists.
			func() ([]byte, error) { return nil, &fakeexec.FakeExitError{Status: 2} },
		},
	}
	fexec := fakeexec.FakeExec{
		CommandScript: []fakeexec.FakeCommandAction{
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
		},
	}
	runner := New(&fexec)
	// Success.
	exists, err := runner.EnsureServiceAddressBind(svc, dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if exists {
		t.Errorf("expected exists = false")
	}
	if fcmd.CombinedOutputCalls != 1 {
		t.Errorf("expected 1 CombinedOutput() calls, got %d", fcmd.CombinedOutputCalls)
	}
	if !sets.NewString(fcmd.CombinedOutputLog[0]...).HasAll("ip", "addr", "add", "10.20.30.40/32", "dev", "kube-ipvs0") {
		t.Errorf("wrong CombinedOutput() log, got %s", fcmd.CombinedOutputLog[0])
	}
	// Exists.
	exists, err = runner.EnsureServiceAddressBind(svc, dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if !exists {
		t.Errorf("expected exists = true")
	}
}

func TestUnBindServiceAddress(t *testing.T) {
	svc := &InternalService{
		Address:  net.ParseIP("10.20.30.41"),
		Port:     uint16(80),
		Protocol: string("TCP"),
	}
	fcmd := fakeexec.FakeCmd{
		CombinedOutputScript: []fakeexec.FakeCombinedOutputAction{
			// Success.
			func() ([]byte, error) { return []byte{}, nil },
			// Failure.
			func() ([]byte, error) { return nil, &fakeexec.FakeExitError{Status: 2} },
		},
	}
	fexec := fakeexec.FakeExec{
		CommandScript: []fakeexec.FakeCommandAction{
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
			func(cmd string, args ...string) exec.Cmd { return fakeexec.InitFakeCmd(&fcmd, cmd, args...) },
		},
	}
	runner := New(&fexec)
	// Success.
	err := runner.UnBindServiceAddress(svc, dummyDevice)
	if err != nil {
		t.Errorf("expected success, got %v", err)
	}
	if fcmd.CombinedOutputCalls != 1 {
		t.Errorf("expected 1 CombinedOutput() calls, got %d", fcmd.CombinedOutputCalls)
	}
	if !sets.NewString(fcmd.CombinedOutputLog[0]...).HasAll("ip", "addr", "del", "10.20.30.41/32", "dev", "kube-ipvs0") {
		t.Errorf("wrong CombinedOutput() log, got %s", fcmd.CombinedOutputLog[0])
	}
	// Failure.
	err = runner.UnBindServiceAddress(svc, dummyDevice)
	if err == nil {
		t.Errorf("expected failure")
	}
}

func Test_toInternalService(t *testing.T) {
	Tests := []struct {
		ipvsService     ipvs.Service
		internalService InternalService
	}{
		{
			ipvs.Service{
				Protocol:      syscall.IPPROTO_TCP,
				Port:          80,
				FWMark:        0,
				SchedName:     "",
				Flags:         0,
				Timeout:       0,
				Netmask:       0xffffffff,
				AddressFamily: syscall.AF_INET,
				Address:       nil,
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("0.0.0.0"),
				Protocol:  "TCP",
				Port:      80,
				Scheduler: "",
				Flags:     0,
				Timeout:   0,
			},
		},
		{
			ipvs.Service{
				Protocol:      syscall.IPPROTO_UDP,
				Port:          33434,
				FWMark:        0,
				SchedName:     "wlc",
				Flags:         1234,
				Timeout:       100,
				Netmask:       128,
				AddressFamily: syscall.AF_INET6,
				Address:       net.ParseIP("2012::beef"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("2012::beef"),
				Protocol:  "UDP",
				Port:      33434,
				Scheduler: "wlc",
				Flags:     1234,
				Timeout:   100,
			},
		},
		{
			ipvs.Service{
				Protocol:      0,
				Port:          0,
				FWMark:        0,
				SchedName:     "lc",
				Flags:         0,
				Timeout:       0,
				Netmask:       0xffffffff,
				AddressFamily: syscall.AF_INET,
				Address:       net.ParseIP("1.2.3.4"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("1.2.3.4"),
				Protocol:  "",
				Port:      0,
				Scheduler: "lc",
				Flags:     0,
				Timeout:   0,
			},
		},
		{
			ipvs.Service{
				Protocol:      0,
				Port:          0,
				FWMark:        0,
				SchedName:     "wrr",
				Flags:         0,
				Timeout:       0,
				Netmask:       128,
				AddressFamily: syscall.AF_INET6,
				Address:       nil,
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("::0"),
				Protocol:  "",
				Port:      0,
				Scheduler: "wrr",
				Flags:     0,
				Timeout:   0,
			},
		},
	}

	for i := range Tests {
		got, err := toInternalService(&Tests[i].ipvsService)
		if err != nil {
			t.Errorf("case: %d, unexpected error: %v", i, err)
		}
		if !reflect.DeepEqual(*got, Tests[i].internalService) {
			t.Errorf("case: %d, got %#v, want %#v", i, *got, Tests[i].internalService)
		}
	}
}

func Test_toExternalService(t *testing.T) {
	Tests := []struct {
		ipvsService     ipvs.Service
		internalService InternalService
	}{
		{
			ipvs.Service{
				Protocol:      syscall.IPPROTO_TCP,
				Port:          80,
				FWMark:        0,
				SchedName:     "",
				Flags:         0,
				Timeout:       0,
				Netmask:       0xffffffff,
				AddressFamily: syscall.AF_INET,
				Address:       net.ParseIP("0.0.0.0"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("0.0.0.0"),
				Protocol:  "TCP",
				Port:      80,
				Scheduler: "",
				Flags:     0,
				Timeout:   0,
			},
		},
		{
			ipvs.Service{
				Protocol:      syscall.IPPROTO_UDP,
				Port:          33434,
				FWMark:        0,
				SchedName:     "wlc",
				Flags:         1234,
				Timeout:       100,
				Netmask:       128,
				AddressFamily: syscall.AF_INET6,
				Address:       net.ParseIP("2012::beef"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("2012::beef"),
				Protocol:  "UDP",
				Port:      33434,
				Scheduler: "wlc",
				Flags:     1234,
				Timeout:   100,
			},
		},
		{
			ipvs.Service{
				Protocol:      0,
				Port:          0,
				FWMark:        0,
				SchedName:     "lc",
				Flags:         0,
				Timeout:       0,
				Netmask:       0xffffffff,
				AddressFamily: syscall.AF_INET,
				Address:       net.ParseIP("1.2.3.4"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("1.2.3.4"),
				Protocol:  "",
				Port:      0,
				Scheduler: "lc",
				Flags:     0,
				Timeout:   0,
			},
		},
		{
			ipvs.Service{
				Protocol:      0,
				Port:          0,
				FWMark:        0,
				SchedName:     "wrr",
				Flags:         0,
				Timeout:       0,
				Netmask:       128,
				AddressFamily: syscall.AF_INET6,
				Address:       net.ParseIP("::0"),
				PEName:        "",
			},
			InternalService{
				Address:   net.ParseIP("::0"),
				Protocol:  "",
				Port:      0,
				Scheduler: "wrr",
				Flags:     0,
				Timeout:   0,
			},
		},
	}

	for i := range Tests {
		got, err := toExternalService(&Tests[i].internalService)
		if err != nil {
			t.Errorf("case: %d, unexpected error: %v", i, err)
		}
		if !reflect.DeepEqual(*got, Tests[i].ipvsService) {
			t.Errorf("case: %d - got %#v, want %#v", i, *got, Tests[i].ipvsService)
		}
	}
}

func Test_toInternalDestination(t *testing.T) {
	Tests := []struct {
		ipvsDestination     ipvs.Destination
		internalDestination InternalDestination
	}{
		{
			ipvs.Destination{
				Port:            54321,
				ConnectionFlags: 0,
				Weight:          1,
				Address:         net.ParseIP("1.2.3.4"),
			},
			InternalDestination{
				Address: net.ParseIP("1.2.3.4"),
				Port:    54321,
				Weight:  1,
			},
		},
		{
			ipvs.Destination{
				Port:            53,
				ConnectionFlags: 0,
				Weight:          1,
				Address:         net.ParseIP("2002::cafe"),
			},
			InternalDestination{
				Address: net.ParseIP("2002::cafe"),
				Port:    53,
				Weight:  1,
			},
		},
	}
	for i := range Tests {
		got, err := toInternalDestination(&Tests[i].ipvsDestination)
		if err != nil {
			t.Errorf("case %d unexpected error: %d", i, err)
		}
		if !reflect.DeepEqual(*got, Tests[i].internalDestination) {
			t.Errorf("case %d Failed to translate Destination - got %#v, want %#v", i, *got, Tests[i].internalDestination)
		}
	}
}

func Test_toExternalDestination(t *testing.T) {
	Tests := []struct {
		internalDestination InternalDestination
		ipvsDestination     ipvs.Destination
	}{
		{
			InternalDestination{
				Address: net.ParseIP("1.2.3.4"),
				Port:    54321,
				Weight:  1,
			},
			ipvs.Destination{
				Port:            54321,
				ConnectionFlags: 0,
				Weight:          1,
				Address:         net.ParseIP("1.2.3.4"),
			},
		},
		{
			InternalDestination{
				Address: net.ParseIP("2002::cafe"),
				Port:    53,
				Weight:  1,
			},
			ipvs.Destination{
				Port:            53,
				ConnectionFlags: 0,
				Weight:          1,
				Address:         net.ParseIP("2002::cafe"),
			},
		},
	}
	for i := range Tests {
		got, err := toExternalDestination(&Tests[i].internalDestination)
		if err != nil {
			t.Errorf("case %d unexpected error: %d", i, err)
		}
		if !reflect.DeepEqual(*got, Tests[i].ipvsDestination) {
			t.Errorf("case %d Failed to translate Destination - got %#v, want %#v", i, *got, Tests[i].ipvsDestination)
		}
	}
}

func Test_stringToProtocolNumber(t *testing.T) {
	tests := []string{
		"TCP", "UDP", "ICMP",
	}
	expecteds := []uint16{
		uint16(syscall.IPPROTO_TCP), uint16(syscall.IPPROTO_UDP), uint16(0),
	}
	for i := range tests {
		got := stringToProtocolNumber(tests[i])
		if got != expecteds[i] {
			t.Errorf("stringToProtocolNumber() failed - got %#v, want %#v",
				got, expecteds[i])
		}
	}
}

func Test_protocolNumberToString(t *testing.T) {
	tests := []ProtoType{
		syscall.IPPROTO_TCP, syscall.IPPROTO_UDP, ProtoType(0),
	}
	expecteds := []string{
		"TCP", "UDP", "",
	}
	for i := range tests {
		got := protocolNumbeToString(tests[i])
		if got != expecteds[i] {
			t.Errorf("protocolNumbeToString() failed - got %#v, want %#v",
				got, expecteds[i])
		}
	}
}
