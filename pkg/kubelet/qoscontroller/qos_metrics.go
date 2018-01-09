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
	"fmt"
	"github.com/golang/glog"
	cadvisorapiv1 "github.com/google/cadvisor/info/v1"
	cadvisorapiv2 "github.com/google/cadvisor/info/v2"
	"k8s.io/api/core/v1"
	kubelettypes "k8s.io/kubernetes/pkg/kubelet/types"
	"k8s.io/apimachinery/pkg/types"
)

const MaxSamples int = 10

// ResourceSummary contains all the usage details of various resources
type ResourceSummary struct {
	// for memory controller
	memoryResourceUsage ResourceUsage
	// for network IO controller
	networkIOResourceUsage ResourceUsage
	// for disk IO controller
	diskIOResourceUsage ResourceUsage
}

// ResourceUsage contains parameters pertaining in general to resources
type ResourceUsage struct {
	threshold      uint64
	currentUsage   uint64
	predictedUsage uint64
	numSamples     int
	samples        []uint64
}

// delete the metrics entries  collected for the pod which are not currently in active pod list
func (*ResourceSummary) cleanUp(qosResourceStatus *QosResourceStatus) error {
	for podId := range qosResourceStatus.podResourceSummary {
		exists := false
		for _, activePod := range qosResourceStatus.activePods {
			if podId == activePod.ObjectMeta.UID {
				exists = true
				break
			}
		}
		if !exists {
			delete(qosResourceStatus.podResourceSummary, podId)
		}
	}
	return nil
}

// qosAcquireMetrics calculates/gathers all resources
func (rs *ResourceSummary) qosAcquireMetrics(qosResourceStatus *QosResourceStatus) error {
	qosAcquireNodeMetrics(qosResourceStatus)
	// loop each pod in the node and collect the pod level metrics
NextActivePod:
	for _, pod := range qosResourceStatus.activePods {
		//Do not collect metrics for frozen pods
		for _, frozenPod := range qosResourceStatus.FrozenPodList {
			if frozenPod == pod {
				continue NextActivePod
			}
		}
		qosAcquirePodMetrics(pod, qosResourceStatus)
	}
	err := rs.cleanUp(qosResourceStatus)
	return err
}

// qosAcquireNodeMetrics calculates/gathers all resources for the node
func qosAcquireNodeMetrics(qosResourceStatus *QosResourceStatus) error {
	cadvisorOptions := cadvisorapiv2.RequestOptions{
		IdType:    cadvisorapiv2.TypeName,
		Count:     1,
		Recursive: false,
	}

	//calculate node memory usage
	nodeMemoryResourceUsage := qosResourceStatus.nodeResourceSummary.memoryResourceUsage
	numMemorySamples := nodeMemoryResourceUsage.numSamples
	if MaxSamples == numMemorySamples {
		for i := 0; i < (MaxSamples - 1); i++ {
			nodeMemoryResourceUsage.samples[i] = nodeMemoryResourceUsage.samples[i+1]
		}
		nodeMemoryResourceUsage.samples[numMemorySamples-1] = 0
	} else if numMemorySamples < MaxSamples {
		nodeMemoryResourceUsage.samples = append(nodeMemoryResourceUsage.samples, 0)
		numMemorySamples += 1
	}

	derivedStatsMap, err := qosResourceStatus.cadvisor.DerivedStats("/", cadvisorOptions)
	if err != nil {
		return fmt.Errorf("Get DerivedStats error:%v", err)
	}

	latestMemoryIOUsage := derivedStatsMap["/"].LatestUsage.Memory
	nodeMemoryResourceUsage.numSamples = numMemorySamples
	nodeMemoryResourceUsage.samples[numMemorySamples-1] = latestMemoryIOUsage
	nodeMemoryResourceUsage.currentUsage = latestMemoryIOUsage
	qosResourceStatus.nodeResourceSummary.memoryResourceUsage = nodeMemoryResourceUsage

	glog.Infof("--Acquired %d samples for Memory IO metrics for Node . Latest usage %v --", nodeMemoryResourceUsage.numSamples, nodeMemoryResourceUsage.currentUsage)

	// calculate network IO usage
	nodeNetworkIOResourceUsage := qosResourceStatus.nodeResourceSummary.networkIOResourceUsage
	numNetworkIOSamples := nodeNetworkIOResourceUsage.numSamples

	if MaxSamples == numNetworkIOSamples {
		for i := 0; i < (MaxSamples - 1); i++ {
			nodeNetworkIOResourceUsage.samples[i] = nodeNetworkIOResourceUsage.samples[i+1]
		}
		nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-1] = 0
	} else if numNetworkIOSamples < MaxSamples {
		nodeNetworkIOResourceUsage.samples = append(nodeNetworkIOResourceUsage.samples, 0)
		numNetworkIOSamples += 1
	}

	derivedStatsNetworkIOMap, err := qosResourceStatus.cadvisor.DerivedStats("/", cadvisorOptions)
	if err != nil {
		return fmt.Errorf("Get DerivedStats error:%v", err)
	}

	latestNetworkIOUsage := derivedStatsNetworkIOMap["/"].LatestUsage.Network
	nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-1] = latestNetworkIOUsage
	if numNetworkIOSamples > 1 {
		latestNetworkIOUsage -= nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-2]
		nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-2] = latestNetworkIOUsage
		nodeNetworkIOResourceUsage.currentUsage = latestNetworkIOUsage
	}

	nodeNetworkIOResourceUsage.numSamples = numNetworkIOSamples
	//nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-1] = latestNetworkIOUsage
	//nodeNetworkIOResourceUsage.currentUsage = latestNetworkIOUsage
	qosResourceStatus.nodeResourceSummary.networkIOResourceUsage = nodeNetworkIOResourceUsage

	glog.Infof("--Acquired %d samples for Network IO metrics for Node . Value read = %v Latest usage %v --",
		nodeNetworkIOResourceUsage.numSamples, nodeNetworkIOResourceUsage.samples[numNetworkIOSamples-1],nodeNetworkIOResourceUsage.currentUsage)

	return nil
}

// qosAcquirePodMetrics calculates/gathers all resources for each of the pod and fills up the map
func qosAcquirePodMetrics(pod *v1.Pod, qosResourceStatus *QosResourceStatus) error {
	acquireMemoryMetrics(pod, qosResourceStatus)
	acquireDiskIOMetrics(pod, qosResourceStatus)
	acquireNetworkIOMetrics(pod, qosResourceStatus)
	return nil
}

// acquireMemoryMetrics calculates/gathers memory related resources for each of the pod and fills up the map
func acquireMemoryMetrics(pod *v1.Pod, qosResourceStatus *QosResourceStatus) error {
	var resourceSummary *ResourceSummary
	cadvisorOptions := cadvisorapiv2.RequestOptions{
		IdType:    cadvisorapiv2.TypeName,
		Count:     1,
		Recursive: false,
	}

	podId := pod.ObjectMeta.UID
	nameToId := make(map[string]string)

	//check if there is an entry in the map, if it doesn't exist we end up creating one towards the end
	//of this function
	_, ok := qosResourceStatus.podResourceSummary[podId]
	if ok {
		resourceSummary = qosResourceStatus.podResourceSummary[podId]
	} else {
		resourceSummary = new(ResourceSummary)
	}
	resourceUsage := resourceSummary.memoryResourceUsage
	numSamples := resourceUsage.numSamples
	if MaxSamples == numSamples {
		for i := 0; i < (MaxSamples - 1); i++ {
			resourceUsage.samples[i] = resourceUsage.samples[i+1]
		}
		resourceUsage.samples[numSamples-1] = 0
	} else if numSamples < MaxSamples {
		resourceUsage.samples = append(resourceUsage.samples, 0)
		numSamples += 1
	}

	//get mappings from containers' Names to Ids
	for _, containerStatus := range pod.Status.ContainerStatuses {
		if len(containerStatus.Name) > 0 && len(containerStatus.ContainerID) >= 9 {
			nameToId[containerStatus.Name] = containerStatus.ContainerID[9:]
		}
	}

	for _, container := range pod.Spec.Containers {
		containerId, ok := nameToId[container.Name]
		//glog.Infof("-----------------containerName:%v containerId:%v", container.Name, containerId)
		if !ok {

			return fmt.Errorf("could not found the ContainerId of container: %v", container.Name)
		}

		derivedStatsMap, err := qosResourceStatus.cadvisor.DerivedStats("/"+containerId, cadvisorOptions)
		if err != nil {
			return fmt.Errorf("Get DerivedStats error:%v", err)
		}
		latestUsage := derivedStatsMap["/"+containerId].LatestUsage.Memory
		resourceUsage.samples[numSamples-1] += latestUsage

	}
	resourceUsage.numSamples = numSamples
	resourceUsage.currentUsage = resourceUsage.samples[numSamples-1]
	resourceSummary.memoryResourceUsage = resourceUsage
	qosResourceStatus.podResourceSummary[podId] = resourceSummary

	glog.Infof("-----Acquired %d samples for memory metrics for Pod:%v PodId:%v Latest usage %v----------", resourceUsage.numSamples, pod.Name, podId, resourceUsage.currentUsage)
	/*
	   for i:=0;i<resourceUsage.numSamples;i++{
	           glog.Infof("Memory usage sample %d value:%d",i,resourceUsage.samples[i])
	   }
	*/

	return nil
}

// acquireDiskIOMetrics calculates/gathers disk IO related resources for each of the pod and fills up the map
func acquireDiskIOMetrics(pod *v1.Pod, qosResourceStatus *QosResourceStatus) error {
	return nil
}

// acquireNetworkIOMetrics calculates/gathers network IO related resources for each of the pod and fills up the map
func acquireNetworkIOMetrics(pod *v1.Pod, qosResourceStatus *QosResourceStatus) error {

	var resourceSummary *ResourceSummary
	cadvisorOptions := cadvisorapiv2.RequestOptions{
		IdType:    cadvisorapiv2.TypeName,
		Count:     1,
		Recursive: false,
	}

	podId := pod.ObjectMeta.UID
	var pauseContainerId string

	podToPauseContainerIdMap := make(map[types.UID]string)

	//check if there is an entry in the map, if it doesn't exist we end up creating one towards the end
	//of this function
	_, ok := qosResourceStatus.podResourceSummary[podId]
	if ok {
		resourceSummary = qosResourceStatus.podResourceSummary[podId]
	} else {
		resourceSummary = new(ResourceSummary)
	}
	resourceUsage := resourceSummary.networkIOResourceUsage
	numSamples := resourceUsage.numSamples
	if MaxSamples == numSamples {
		for i := 0; i < (MaxSamples - 1); i++ {
			resourceUsage.samples[i] = resourceUsage.samples[i+1]
		}
		resourceUsage.samples[numSamples-1] = 0
	} else if numSamples < MaxSamples {
		resourceUsage.samples = append(resourceUsage.samples, 0)
		numSamples += 1
	}

	// get pause container id for the pod
	_, pauseContainerIdOk := podToPauseContainerIdMap[podId]
	// check if we already have it in the map , else retrieve from cadvisor
	if pauseContainerIdOk {
		pauseContainerId = podToPauseContainerIdMap[podId]
	} else {
		pauseContainerId = getPauseContainerIdForPod(pod.Name, qosResourceStatus)
		podToPauseContainerIdMap[podId] = pauseContainerId
	}

	// Get the derived stats for the pause container
	derivedStatsMap, err := qosResourceStatus.cadvisor.DerivedStats("/"+pauseContainerId, cadvisorOptions)
	if err != nil {
		return fmt.Errorf("Error while retrieving derived stats %v", err)
	}

	latestUsage := derivedStatsMap["/"+pauseContainerId].LatestUsage.Network
	resourceUsage.samples[numSamples-1] = latestUsage
	if numSamples > 1 {
		latestUsage -= resourceUsage.samples[numSamples-2]
		resourceUsage.samples[numSamples-2] = latestUsage
		resourceUsage.currentUsage = resourceUsage.samples[numSamples-2]
	}

	//resourceUsage.samples[numSamples-1] = latestUsage

	resourceUsage.numSamples = numSamples
	//resourceUsage.currentUsage = resourceUsage.samples[numSamples-1]
	resourceSummary.networkIOResourceUsage = resourceUsage
	qosResourceStatus.podResourceSummary[podId] = resourceSummary

	glog.Infof("-----Acquired %d samples for network IO stats for Pod:%v PodId:%v Latest usage %v----------", resourceUsage.numSamples, pod.Name, podId, resourceUsage.currentUsage)

	//for i:=0;i<resourceUsage.numSamples;i++{
	//           glog.Infof("Network IO usage sample %d value:%d",i,resourceUsage.samples[i])
	//   }
	return nil

}

// Retrives the pause container associated with the pod from cadvisor
func getPauseContainerIdForPod(podName string, qosResourceStatus *QosResourceStatus) string {

	cadvisorReq := &cadvisorapiv1.ContainerInfoRequest{}

	containerInfoMap, error := qosResourceStatus.cadvisor.SubcontainerInfo("/", cadvisorReq)
	if error != nil {
		glog.Infof("Error occurred while fetching paused container from cAdvisor %v", error)
		return ""
	} else {
		for _, container := range containerInfoMap {
			if container.Spec.HasNetwork {
				pausedContainerPodName := container.Labels[kubelettypes.KubernetesPodNameLabel]
				if podName == pausedContainerPodName {
					return container.Id
				}
			}
		}
	}
	return ""
}
