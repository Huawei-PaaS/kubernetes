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
	"fmt"
	"net"
	"testing"

	utildbus "k8s.io/kubernetes/pkg/util/dbus"
	"k8s.io/kubernetes/pkg/util/exec"
)

func Test_SetAlias(t *testing.T) {
	execer := exec.New()
	var dbus utildbus.Interface
	dbus = utildbus.New()
	IPVSInterface := New(execer, dbus)
	svc := Service{
		Address:  net.ParseIP("10.103.71.71"),
		Port:     uint16(11122),
		Protocol: string("TCP"),
	}
	err := IPVSInterface.SetAlias(&svc)
	if err != nil {
		fmt.Println(err)
	}
}

func Test_UnSetAlias(t *testing.T) {
	execer := exec.New()
	var dbus utildbus.Interface
	dbus = utildbus.New()
	IPVSInterface := New(execer, dbus)
	svc := Service{
		Address:  net.ParseIP("10.103.71.71"),
		Port:     uint16(11122),
		Protocol: string("TCP"),
	}
	err := IPVSInterface.UnSetAlias(&svc)
	if err != nil {
		fmt.Println(err)
	}
}
