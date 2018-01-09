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

package qoscontroller

type QosController interface {
	process(qosResourceStatus *QosResourceStatus) error
	// Initialization function for the controllers
	initialize(qosResourceStatus *QosResourceStatus) error
}

type QosMonitor struct {
}

func NewQosMonitor() *QosMonitor {
	return &QosMonitor{}
}

func (qosMonitor QosMonitor) StartQosMonitor(qosResourceStatus *QosResourceStatus) error {
	run(qosResourceStatus)
	return nil
}

// Instance of Overall Controller
var oc OverallController

// Instance of Resource Summary
var rs ResourceSummary

// Instance of Memory Controller
var mc MemController

// Instance of Network IO Controller
var nc NetworkIOController

// Instance of Disk IO Controller
var dc DiskIOController

// Instance of SLA Controller
var sc SlaController

// function to run all the controllers sequentially and then to run the executor
func run(qosResourceStatus *QosResourceStatus) error {
	//Call Metrics Aquisition
	rs.qosAcquireMetrics(qosResourceStatus)
	// Call Overall Controller
	oc.initialize(qosResourceStatus)
	oc.process(qosResourceStatus)
	if qosResourceStatus.processNextController == false {
		return nil
	}
	// Call Memory Controller
	mc.process(qosResourceStatus)
	// Call Network IO Controller
	nc.process(qosResourceStatus)
	// Call Disk IO Controller
	dc.process(qosResourceStatus)
	// Call SLA Controller
	sc.process(qosResourceStatus)
	return nil
}
