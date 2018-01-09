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

import (
	"github.com/golang/glog"
	"github.com/google/cadvisor/machine"
	"k8s.io/api/core/v1"
	"math"

	qosUtil "k8s.io/kubernetes/pkg/apis/core/v1/helper/qos"
	"strconv"
	"sync"
)

// Overall Controller
type OverallController struct {
}

var MutexNodeStability = &sync.Mutex{}
var IsNodeUnstable bool

// initialize of QosController is implemented by OverallController and does all the initialization works
func (oc *OverallController) initialize(qosResourceStatus *QosResourceStatus) error {
	qosResourceStatus.primaryPodList = nil
	qosResourceStatus.secondaryPodList = nil
	qosResourceStatus.bestEffortPodList = nil
	qosResourceStatus.processNextController = true
	qosResourceStatus.ActionList = nil
	return nil
}

// process of QosController interface is implemented by OverallController and does all what an overall controller has to do
func (oc *OverallController) process(qosResourceStatus *QosResourceStatus) error {

	var nodeMemoryRate, nodeAverageMemoryRate float64
	var nodeMemoryCurrentSample, nodeMemoryPreviousSample float64

	nodeMemoryUsage := qosResourceStatus.nodeResourceSummary.memoryResourceUsage.currentUsage
	nodeMemoryUsageSamples := qosResourceStatus.nodeResourceSummary.memoryResourceUsage.samples
	monitoringInterval := qosResourceStatus.QosConfig.MonitoringInterval
	nodeHighMemoryThresholdRate := qosResourceStatus.QosConfig.MemoryConfig.NodeHighMemoryRequestThresholdRate
	nodeLowMemoryThresholdRate := qosResourceStatus.QosConfig.MemoryConfig.NodeLowMemoryRequestThresholdRate

	nodeMemory, err := machine.GetMachineMemoryCapacity()
	if err != nil {
		glog.Errorf("Cannot obtain Node Memory Capacity")
		return err
	}

	nodeMemoryCurrentSample = float64(nodeMemoryUsage)
	nodeMemoryRate = 0

	// Calculate the rate of increase for last N samples
	for i := 0; i < len(nodeMemoryUsageSamples); i++ {
		nodeMemoryPreviousSample = float64(nodeMemoryUsageSamples[i])
		nodeMemoryRate += (nodeMemoryCurrentSample - nodeMemoryPreviousSample) / nodeMemoryPreviousSample
		nodeMemoryCurrentSample = nodeMemoryPreviousSample
	}

	// Calculate the average rate of increase
	nodeAverageMemoryRate = nodeMemoryRate / float64(len(nodeMemoryUsageSamples))

	// Calculate the various predicted node level memory usage and node level thresholds
	// in the next monitoring interval based on the increase in memory rate
	nodeMemoryIncreaseRate := math.Pow((1 + nodeAverageMemoryRate), float64(monitoringInterval))
	nodePredictedMemoryUsage := float64(nodeMemoryUsage) * nodeMemoryIncreaseRate
	nodeHighMemoryThreshold := float64(nodeMemory) * (1 - nodeHighMemoryThresholdRate)
	nodeLowMemoryThreshold := float64(nodeMemory) * (1 - nodeLowMemoryThresholdRate)

	// Check if node memory usage greater than lower memory threshold
	if float64(nodeMemoryUsage) > nodeLowMemoryThreshold {
		// Check if predicted usage greater than high memory threshold
		if nodePredictedMemoryUsage > nodeHighMemoryThreshold {
			// Signalling Resource Estimator to stop sending resource usage to Resource Manager
			glog.Infof("Node is unstable, Signalling Resource Estimator to stop sending resource usage to Resource Manager")
			MutexNodeStability.Lock()
			IsNodeUnstable = true
			MutexNodeStability.Unlock()
		}
		// Node stable/unstable state retained when memory usage is between high and low memory threshold

	} else {
		// Signalling Resource Estimator to keep sending resource usage to Resource Manager
		MutexNodeStability.Lock()
		IsNodeUnstable = false
		MutexNodeStability.Unlock()
	}

	// classify active pods into primary, secondary and best-effort pods
NextActivePod:
	for _, pod := range qosResourceStatus.activePods {

		//Do not consider frozen pods in the active list. Ideally paused pods has to be handled with a separate state in kubelet
		for _, frozenPod := range qosResourceStatus.FrozenPodList {
			if frozenPod == pod {
				continue NextActivePod
			}
		}

		//Do not consider pods not in running state
		if pod.Status.Phase != v1.PodRunning {
			glog.Infof("Pod %v not in running state", pod.Name)
			continue NextActivePod
		}

		cpuSecondaryAmountStr, okCpu := pod.Annotations[v1.CpuSecondaryAmount]
		memSecondaryAmountStr, okMem := pod.Annotations[v1.MemSecondaryAmount]
		if okCpu == false && okMem == false {
			glog.Errorf("Annotations to classify the pod as secondary pod is not present in the pod %v", pod.UID)
		}
		cpuSecondaryAmount, _ := strconv.Atoi(cpuSecondaryAmountStr)
		memSecondaryAmount, _ := strconv.Atoi(memSecondaryAmountStr)

		qosStatus := qosUtil.GetPodQOS(pod)
		if qosStatus == v1.PodQOSBestEffort {
			qosResourceStatus.bestEffortPodList = append(qosResourceStatus.bestEffortPodList, pod)
		} else if (okMem == true && memSecondaryAmount > 0) || (okCpu == true && cpuSecondaryAmount > 0) { //Pod that consumes secondary resource is a secondary pod
			qosResourceStatus.secondaryPodList = append(qosResourceStatus.secondaryPodList, pod)
		} else {
			qosResourceStatus.primaryPodList = append(qosResourceStatus.primaryPodList, pod)
		}
	}
	//Set the unfreeze pod list to the frozen pod list
	for _, pod := range qosResourceStatus.FrozenPodList {
		qosResourceStatus.UnfreezePodList = append (qosResourceStatus.UnfreezePodList, pod)
	}


	//No need to process further if there are no secondary pods, best effort pods and unfreeze pods
	if qosResourceStatus.secondaryPodList == nil && qosResourceStatus.bestEffortPodList == nil && qosResourceStatus.UnfreezePodList == nil {
		glog.Infof("There are no secondary or best effort or unfreezable pods, so returning back to kubelet")
		qosResourceStatus.processNextController = false
	}
	return nil
}
