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
	"k8s.io/api/core/v1"
	"math"
	"sort"
)

// Memory Controller
type MemController struct {
}

type By func(p1, p2 *v1.Pod) bool

func (by By) Sort(pods []*v1.Pod) {
	ps := &podSorter{
		pods: pods,
		by:   by,
	}
	sort.Sort(ps)
}

type podSorter struct {
	pods []*v1.Pod
	by   func(p1, p2 *v1.Pod) bool
}

func (s *podSorter) Len() int {
	return len(s.pods)
}

func (s *podSorter) Swap(i, j int) {
	s.pods[i], s.pods[j] = s.pods[j], s.pods[i]
}

func (s *podSorter) Less(i, j int) bool {
	return s.by(s.pods[i], s.pods[j])
}

//Function to sort secondary/best effort pod list based on memory Usage
func sortPodListMemoryUsage(qosResourceStatus *QosResourceStatus, pods []*v1.Pod) {
	By(func(p1, p2 *v1.Pod) bool {
		p1ID := p1.UID
		_, ok1 := qosResourceStatus.podResourceSummary[p1ID]
		p2ID := p2.UID
		_, ok2 := qosResourceStatus.podResourceSummary[p2ID]
		if !ok1 || !ok2 {
			glog.Errorf("Cannot obtain pod IDs during pod sorting")
			return false
		}
		p1MemoryUsage := qosResourceStatus.podResourceSummary[p1ID].memoryResourceUsage.currentUsage
		p2MemoryUsage := qosResourceStatus.podResourceSummary[p2ID].memoryResourceUsage.currentUsage
		return p1MemoryUsage > p2MemoryUsage
	}).Sort(pods)
	return
}

// initialize of QosController is implemented by MemController and does all the initialization works
func (mc *MemController) initialize(qosResourceStatus *QosResourceStatus) *QosResourceStatus {
	return qosResourceStatus
}

// process of QosController is implemented by MemController and does all what a memory controller has to do
func (mc *MemController) process(qosResourceStatus *QosResourceStatus) *QosResourceStatus {

	var podRequestedMemory uint64
	var podMemoryThreshold float64

	sortedSecondaryList := false
	secondaryPods := qosResourceStatus.secondaryPodList
	//Check the memory usage for each primary pod
	for _, pod := range qosResourceStatus.primaryPodList {
		podID := (*pod).UID
		_, ok := qosResourceStatus.podResourceSummary[podID]
		if !ok {
			continue
		}
		podRequestedMemory = 0

		//Calculate the pod requested memory using the requested memory for each container
		for _, container := range pod.Spec.Containers {
			podRequestedMemory += uint64(container.Resources.Requests.Memory().Value())
		}

		//Calculate the pod memory threshold based on the configured threshold rate
		thresholdRate := 1 - qosResourceStatus.QosConfig.MemoryConfig.PodMemoryThresholdRate
		podMemoryThreshold = float64(podRequestedMemory) * thresholdRate

		//Get the pod ID and use it to obtain the acquired memory statistics for last N samples
		podMemoryUsage := qosResourceStatus.podResourceSummary[podID].memoryResourceUsage.currentUsage
		podMemoryUsageSamples := qosResourceStatus.podResourceSummary[podID].memoryResourceUsage.samples
		monitoringInterval := float64(qosResourceStatus.QosConfig.MonitoringInterval)

		//Calculate predicted memory usage
		predictedMemoryUsage := calculatePredictedUsage(podMemoryUsage, podMemoryUsageSamples, monitoringInterval)
		glog.Infof("pod=%v Current usage = %v predicted usage =%v threshold=%v", pod.Name, podMemoryUsage, predictedMemoryUsage, podMemoryThreshold)
		//Check if the current pod memory usage is greater than the pod memory threshold
		if float64(podMemoryUsage) > podMemoryThreshold && predictedMemoryUsage > podMemoryThreshold {

			if sortedSecondaryList == false {
				//Sort the secondary pod list based on decreasing usage of memory
				sortPodListMemoryUsage(qosResourceStatus, secondaryPods)
				sortedSecondaryList = true
			}
			//Update the action list with the secondary pods to be killed
			secondaryPods = updateActionList(podMemoryUsage,
				podRequestedMemory,
				&(qosResourceStatus.ActionList),
				secondaryPods,
				qosResourceStatus.QosConfig.MemoryConfig.ProcessMultiPod)
		}
	}
	return qosResourceStatus
}

//Function to calculate the predicted usage for the pod based on the rate of increase/decrease using N samples
func calculatePredictedUsage(currentUsage uint64, usageSamples []uint64, monitoringInterval float64) (predictedUsage float64) {

	var aggregateRate, averageRate, actualSamples, actualUsage float64
	var currentSample, previousSample float64

	currentSample = float64(currentUsage)
	aggregateRate = 0
	actualSamples = 0
	actualUsage = currentSample

	//Calculate the rate of increase for last N samples
	for i := len(usageSamples); i > 1; i-- {
		previousSample = float64(usageSamples[i-2])
		actualUsage += previousSample
		if currentSample > previousSample {
			if previousSample > 0 {
				aggregateRate += (currentSample - previousSample) / previousSample
				actualSamples++
			}
		} else {
			if currentSample > 0 {
				aggregateRate -= (previousSample - currentSample) / currentSample
				actualSamples++
			}
		}
		currentSample = previousSample
	}

	//Calculate the average Usage and rate of increase
	averageRate = aggregateRate / actualSamples
	actualUsage = actualUsage / actualSamples
	//Calculate the predicted usage in the next monitoring interval based on the increase/decrease rate
	rate := math.Pow((1 + averageRate), monitoringInterval)
	predictedUsage = actualUsage * rate

	return predictedUsage

}

func updateActionList(podMemoryUsage uint64,
	primaryPodRequestedMemory uint64,
	actionList *[]*Action,
	secondaryPods []*v1.Pod,
	processMultiPod bool) []*v1.Pod {

	var secondaryPodRequestedMemory uint64
	var revocableMemory uint64
	revocableMemory = 0

	i := 0
	//Check the secondary pods to be killed
	for _, pod := range secondaryPods {
		//Populate the action list with the secondary pod to be killed
		var action Action
		action.Target = pod
		action.ActionType = KillPod
		*actionList = append(*actionList, &action)
		i++
		glog.Infof("Secondary Pod %v added to action list", pod.Name)
		//Check if the option of killing multiple secondary pods is enabled
		if processMultiPod == false {
			return secondaryPods[i:]
		}

		//Consider the memory that will be released by killing the secondary pod
		secondaryPodRequestedMemory = 0
		for _, container := range pod.Spec.Containers {
			secondaryPodRequestedMemory += uint64(container.Resources.Requests.Memory().Value())
		}

		//Calculate the total revocable memory corresponding to secondary pods
		revocableMemory += secondaryPodRequestedMemory

		//Check if the memory revoked meets the primary pods requested memory
		//Some threshold of requested memory like 95% can be considered if required
		if (podMemoryUsage + revocableMemory) > primaryPodRequestedMemory {
			return secondaryPods[i:]
		}
	}
	return secondaryPods[i:]
}
