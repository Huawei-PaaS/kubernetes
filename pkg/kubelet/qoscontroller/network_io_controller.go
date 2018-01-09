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
	qosUtil "k8s.io/kubernetes/pkg/apis/core/v1/helper/qos"
	"strconv"
)

// Network I/O Controller
type NetworkIOController struct {
}

//Function to sort secondary/best effort pod list based on network IO Usage
func sortPodListNetworkUsage(qosResourceStatus *QosResourceStatus, pods []*v1.Pod) {
	By(func(p1, p2 *v1.Pod) bool {
		p1ID := p1.UID
		_, ok1 := qosResourceStatus.podResourceSummary[p1ID]
		p2ID := p2.UID
		_, ok2 := qosResourceStatus.podResourceSummary[p2ID]
		if !ok1 || !ok2 {
			glog.Errorf("Cannot obtain pod IDs during pod sorting")
			return false
		}
		p1NetworkIOUsage := qosResourceStatus.podResourceSummary[p1ID].networkIOResourceUsage.currentUsage
		p2NetworkIOUsage := qosResourceStatus.podResourceSummary[p2ID].networkIOResourceUsage.currentUsage
		return p1NetworkIOUsage > p2NetworkIOUsage
	}).Sort(pods)
	return
}

// initialize of QosController is implemented by NetworkIOController and does all the initialization works
func (nc *NetworkIOController) initialize(qosResourceStatus *QosResourceStatus) error {
	return nil
}

// process of QosController is implemented by NetworkIOController and does all what a network I/O controller has to do
func (nc *NetworkIOController) process(qosResourceStatus *QosResourceStatus) *QosResourceStatus {

	processUnfreezable := true
	//sortedSecondaryList := false
	secondaryPods := qosResourceStatus.secondaryPodList
	bestEffortPods := qosResourceStatus.bestEffortPodList

	//Currently the network IO capacity of node is obtained from configuration file
	nodeNetworkIO := uint64(qosResourceStatus.QosConfig.NetworkIOConfig.NodeNetworkIOCapacity)
	//TBD to get the network IO capacity of node based on the network interface card
	//nodeNetworkIO, err := machine.GetMachineNetworkIOCapacity()
	//if err != nil {
	//	glog.Errorf("Cannot obtain Node Network IO Capacity")
	//	return err
	//}

	//First check the network IO usage of the node
	//Calculate the node network IO threshold based on the node configured threshold rate
	nodeThresholdRate := 1 - qosResourceStatus.QosConfig.NetworkIOConfig.NodeNetworkIOThresholdRate
	nodeNetworkIOThreshold := float64(nodeNetworkIO) * nodeThresholdRate

	//Get the acquired network statistics for last N samples
	nodeNetworkIOUsage := qosResourceStatus.nodeResourceSummary.networkIOResourceUsage.currentUsage
	nodeNetworkIOUsageSamples := qosResourceStatus.nodeResourceSummary.networkIOResourceUsage.samples
	monitoringInterval := float64(qosResourceStatus.QosConfig.MonitoringInterval)

	//Calculate predicted network usage
	predictedNodeNetworkIOUsage := calculatePredictedUsage(nodeNetworkIOUsage, nodeNetworkIOUsageSamples, monitoringInterval)
	glog.Infof("Node Network IO usage = %v Node Threshold = %v Predicted Usage = %v",nodeNetworkIOUsage,nodeNetworkIOThreshold,predictedNodeNetworkIOUsage)
	//Check if the current/predicted node network IO usage is greater than the node network IO threshold
	if float64(nodeNetworkIOUsage) > nodeNetworkIOThreshold && predictedNodeNetworkIOUsage > nodeNetworkIOThreshold {

		if predictedNodeNetworkIOUsage > float64(nodeNetworkIOUsage) {
			nodeNetworkIOUsage = uint64(predictedNodeNetworkIOUsage)
		}
		revocableNetworkIO := uint64(0)

		if bestEffortPods != nil {
			//Sort the best effort pod list based on decreasing usage of network IO
			sortPodListNetworkUsage(qosResourceStatus, bestEffortPods)

			//Update the action list with the best effort pods to be freezed
			bestEffortPods, revocableNetworkIO = updateActionListForNetworkIOController(nodeNetworkIOUsage,
				nodeNetworkIO,
				&(qosResourceStatus.ActionList),
				bestEffortPods,
				qosResourceStatus.QosConfig.NetworkIOConfig.ProcessMultiPod)
			processUnfreezable = false
		}
		// Consider freezing secondary pods if there are no besteffort pods to freeze OR
		// network IO usage will be above threshold even after freezing best effort pods
		if secondaryPods != nil && (processUnfreezable == true ||
			((float64(nodeNetworkIOUsage - revocableNetworkIO) > nodeNetworkIOThreshold) &&
				qosResourceStatus.QosConfig.NetworkIOConfig.ProcessMultiPod == true )) {
			//Sort the secondary pod list based on decreasing usage of network IO
			sortPodListNetworkUsage(qosResourceStatus, secondaryPods)
			nodeNetworkIOUsage -= revocableNetworkIO
			//Update the action list with the secondary pods to be freezed
			secondaryPods, revocableNetworkIO = updateActionListForNetworkIOController(nodeNetworkIOUsage,
				nodeNetworkIO,
				&(qosResourceStatus.ActionList),
				secondaryPods,
				qosResourceStatus.QosConfig.NetworkIOConfig.ProcessMultiPod)
		}
		// Set flag to NOT unfreeze any pods
		processUnfreezable = false
	}

	//To be included/considered after Network IO is consider reclaimable by scheduler
	//Check the network usage for each primary pod.
	/*for _, pod := range qosResourceStatus.primaryPodList {
		podID := (*pod).UID
		_, ok := qosResourceStatus.podResourceSummary[podID]
		if !ok {
			continue
		}

		//Get the pod requested network IO
		desiredNetworkIORateStr, _ := pod.Annotations[api.DesiredNetworkIORate]
		podRequestedNetworkIO, _ := strconv.Atoi (desiredNetworkIORateStr)

		//Do not consider pods that do not specify the network IO
		if podRequestedNetworkIO == 0 {
			continue
		}

		//Calculate the pod network IO threshold based on the configured threshold rate
		thresholdRate := 1 - qosResourceStatus.QosConfig.NetworkIOConfig.PodNetworkIOThresholdRate
		podNetworkIOThreshold := float64(podRequestedNetworkIO) * thresholdRate

		//Get the pod ID and use it to obtain the acquired network statistics for last N samples
		podNetworkIOUsage := qosResourceStatus.podResourceSummary[podID].networkIOResourceUsage.currentUsage
		podNetworkIOUsageSamples := qosResourceStatus.podResourceSummary[podID].networkIOResourceUsage.samples
		monitoringInterval := float64(qosResourceStatus.QosConfig.MonitoringInterval)

		glog.Infof("Pod Network IO usage = %v Pod Threshold = %v",podNetworkIOUsage,podNetworkIOThreshold)
		//Check if the current pod network IO usage is less than the pod network IO threshold
		if float64(podNetworkIOUsage) < podNetworkIOThreshold {

			//Calculate predicted network usage
			predictedNetworkIOUsage := calculatePredictedUsage(podNetworkIOUsage, podNetworkIOUsageSamples, monitoringInterval)

			//Check if predicted usage is less than the pod network IO threshold
			if predictedNetworkIOUsage < podNetworkIOThreshold {
				//No action wrt the current primary pod, continue to next primary pod
				continue
			}
		}
		processUnfreezable = false
		//Sort the secondary pod list based on decreasing usage of network IO
		if sortedSecondaryList == false {
			sortPodListNetworkUsage(qosResourceStatus, secondaryPods)
			sortedSecondaryList = true
		}
		//Update the action list with the secondary pods to be killed
		secondaryPods = updateActionListForNetworkIOController(podNetworkIOUsage,
			uint64(podRequestedNetworkIO),
			&(qosResourceStatus.ActionList),
			secondaryPods,
			qosResourceStatus.QosConfig.NetworkIOConfig.ProcessMultiPod)
	}*/

	//Process the unfreeze pod list if both node usage and pod level usages are within thresholds
	if processUnfreezable == true {
		processUnfreezePodList(qosResourceStatus)
	}else {
		qosResourceStatus.UnfreezePodList = nil
	}
	return qosResourceStatus
}

//Function to update the action list with best effort/secondary pods
func updateActionListForNetworkIOController(networkIOUsage uint64,
	networkIOThreshold uint64,
	actionList *[]*Action,
	pods []*v1.Pod,
	processMultiPod bool) ([]*v1.Pod, uint64) {

	var revocableNetworkIO uint64
	revocableNetworkIO = 0

	i := 0
	//Check the pods to be frozen
	for _, pod := range pods {
		//Populate the action list with the pod to be frozen
		var action Action
		action.Target = pod
		action.ActionType = FreezePod
		*actionList = append(*actionList, &action)
		i++
		glog.Infof("Pod %v added to action list", pod.Name)
		//Check if the option of freezing multiple pods is enabled
		if processMultiPod == false {
			return pods[i:], revocableNetworkIO
		}

		//Consider the networkIO that will be released by freezing the pod
		desiredNetworkIORateStr, _ := pod.Annotations[v1.DesiredNetworkIORate]
		podRequestedNetworkIO, _ := strconv.Atoi(desiredNetworkIORateStr)

		//Calculate the total revocable networkIO corresponding to pods
		revocableNetworkIO += uint64(podRequestedNetworkIO)

		//Check if the networkIO revoked meets the requested pod/node networkIO
		//Some threshold of requested networkIO like 95% can be considered if required
		if (networkIOUsage - revocableNetworkIO) < networkIOThreshold {
			return pods[i:],revocableNetworkIO
		}
	}
	return pods[i:], revocableNetworkIO
}

//Function to process unfreeze list
func processUnfreezePodList(qosResourceStatus *QosResourceStatus) {
	requiredNodeNetworkIO := float64(0)
	//var unfreezeSecondaryPodList []*api.Pod
	var unfreezeBesteffortPodList []*v1.Pod

	//Currently the network IO capacity of node is obtained from configuration file
	nodeNetworkIO := uint64(qosResourceStatus.QosConfig.NetworkIOConfig.NodeNetworkIOCapacity)

	//Calculate the node threshold
	nodeThresholdRate := 1 - qosResourceStatus.QosConfig.NetworkIOConfig.NodeNetworkIOThresholdRate
	nodeNetworkIOThreshold := float64(nodeNetworkIO) * nodeThresholdRate

	//Get the current node network usage
	nodeNetworkIOUsage := float64(qosResourceStatus.nodeResourceSummary.networkIOResourceUsage.currentUsage)

	// Process the unfreeze pod list
	for i := len (qosResourceStatus.UnfreezePodList) ;i > 0  ; i-- {
		pod := qosResourceStatus.UnfreezePodList [i-1]
		podID := (*pod).UID
		_, ok := qosResourceStatus.podResourceSummary[podID]
		if !ok {
			continue
		}
		//Get the last network IO usage
		unfreezePodNetworkIO := float64(qosResourceStatus.podResourceSummary[podID].networkIOResourceUsage.currentUsage)
		qosStatus := qosUtil.GetPodQOS(pod)

		//Consider unfreeze of the Secondary pods on priority
		if qosStatus != v1.PodQOSBestEffort {
			//To unfreeze secondary pod check if resources are available in the node
			availableNetworkIO := float64(nodeNetworkIOThreshold) - nodeNetworkIOUsage - requiredNodeNetworkIO
			if unfreezePodNetworkIO < availableNetworkIO {
				glog.Infof("Pod %v in unfreeze list", pod.Name)
				requiredNodeNetworkIO += unfreezePodNetworkIO
			} else {
				// Remove pod from unfreeze list
				qosResourceStatus.UnfreezePodList = append(qosResourceStatus.UnfreezePodList[:i-1],qosResourceStatus.UnfreezePodList[i:]...)
			}
		} else {
			// Create list of best effort pods to consider for unfreeze later
			unfreezeBesteffortPodList = append(unfreezeBesteffortPodList, pod)
			qosResourceStatus.UnfreezePodList = append(qosResourceStatus.UnfreezePodList[:i-1],qosResourceStatus.UnfreezePodList[i:]...)
		}
	}

	// Process the best effort pods now
	for _, besteffortPod := range unfreezeBesteffortPodList {
		podID := (*besteffortPod).UID
		//Get the last network IO usage
		unfreezePodNetworkIO := float64(qosResourceStatus.podResourceSummary[podID].networkIOResourceUsage.currentUsage)
		availableNetworkIO := float64(nodeNetworkIOThreshold) - nodeNetworkIOUsage - requiredNodeNetworkIO
		if unfreezePodNetworkIO < availableNetworkIO {
			requiredNodeNetworkIO += unfreezePodNetworkIO
			qosResourceStatus.UnfreezePodList = append(qosResourceStatus.UnfreezePodList, besteffortPod)
			glog.Infof("Pod %v in unfreeze list",  besteffortPod.Name)
		}
	}

	//To be included/considered after Network IO is consider reclaimable by scheduler
	//To unfreeze secondary pods check if reclaimable resource is available with primary pods
	/*for _, primaryPod := range qosResourceStatus.primaryPodList {
		primaryPodID := (*primaryPod).UID
		_, ok := qosResourceStatus.podResourceSummary[primaryPodID]
		if !ok {
			continue
		}

		//Get the pod requested network IO
		desiredNetworkIORateStr, _ := primaryPod.Annotations[api.DesiredNetworkIORate]
		podRequestedNetworkIO, _ := strconv.Atoi(desiredNetworkIORateStr)

		//Calculate the pod network IO threshold based on the configured threshold rate
		thresholdRate := 1 - qosResourceStatus.QosConfig.NetworkIOConfig.PodNetworkIOThresholdRate
		podNetworkIOThreshold := float64(podRequestedNetworkIO) * thresholdRate
		podNetworkIOUsage := float64(qosResourceStatus.podResourceSummary[primaryPodID].networkIOResourceUsage.currentUsage)

		requiredPodNetworkIO := float64(0)
		for i := len(unfreezeSecondaryPodList); i > 0 ; i--  {
			pod := unfreezeSecondaryPodList[i-1]
			podID := (*pod).UID
			_, ok := qosResourceStatus.podResourceSummary[podID]
			if !ok {
				continue
			}
			//Get the last network IO usage
			unfreezePodNetworkIO := float64(qosResourceStatus.podResourceSummary[podID].networkIOResourceUsage.currentUsage)
			availablePodNetworkIO := podNetworkIOThreshold - podNetworkIOUsage - requiredPodNetworkIO
			if unfreezePodNetworkIO < availablePodNetworkIO {
				requiredPodNetworkIO += unfreezePodNetworkIO
				unfreezeSecondaryPodList = append(unfreezeSecondaryPodList[:i-1],unfreezeSecondaryPodList[i:]...)
			}
		}
	}
	RemovePod:
	for _, pod := range unfreezeSecondaryPodList {
		//Remove pod from unfreeze list
		for i := len(qosResourceStatus.UnfreezePodList) ; i > 0 ; i-- {
			unfreezePod := qosResourceStatus.UnfreezePodList[i-1]
			if pod == unfreezePod {
				qosResourceStatus.UnfreezePodList = append(qosResourceStatus.UnfreezePodList[:i-1],qosResourceStatus.UnfreezePodList[i:]...)
				continue RemovePod
			}
		}
	}*/
}
