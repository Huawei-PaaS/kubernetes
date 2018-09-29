/*
Copyright 2015 The Kubernetes Authors.

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

package cache

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/util/wait"
	utilfeature "k8s.io/apiserver/pkg/util/feature"
	"k8s.io/kubernetes/pkg/features"
	"k8s.io/kubernetes/pkg/scheduler/api"

	"github.com/golang/glog"
	policy "k8s.io/api/policy/v1beta1"
)

var (
	cleanAssumedPeriod = 1 * time.Second
)

// New returns a Cache implementation.
// It automatically starts a go routine that manages expiration of assumed pods.
// "ttl" is how long the assumed pod will get expired.
// "stop" is the channel that would close the background goroutine.
func New(ttl time.Duration, stop <-chan struct{}) Cache {
	cache := newSchedulerCache(ttl, cleanAssumedPeriod, stop)
	cache.run()
	return cache
}

type schedulerCache struct {
	stop   <-chan struct{}
	ttl    time.Duration
	period time.Duration

	// This mutex guards all fields within this cache struct.
	mu sync.Mutex
	// a set of assumed pod keys.
	// The key could further be used to get an entry in podStates.
	assumedPods map[string]bool
	// a map from pod key to podState.
	podStates map[string]*podState
	nodes     map[string]*NodeInfo
	pdbs      map[string]*policy.PodDisruptionBudget
}

type podState struct {
	pod *v1.Pod
	// Used by assumedPod to determinate expiration.
	deadline *time.Time
	// Used to block cache from expiring assumedPod if binding still runs
	bindingFinished bool
}

func newSchedulerCache(ttl, period time.Duration, stop <-chan struct{}) *schedulerCache {
	return &schedulerCache{
		ttl:    ttl,
		period: period,
		stop:   stop,

		nodes:       make(map[string]*NodeInfo),
		assumedPods: make(map[string]bool),
		podStates:   make(map[string]*podState),
		pdbs:        make(map[string]*policy.PodDisruptionBudget),
	}
}

// Snapshot takes a snapshot of the current schedulerCache. The method has performance impact,
// and should be only used in non-critical path.
func (cache *schedulerCache) Snapshot() *Snapshot {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	nodes := make(map[string]*NodeInfo)
	for k, v := range cache.nodes {
		nodes[k] = v.Clone()
	}

	assumedPods := make(map[string]bool)
	for k, v := range cache.assumedPods {
		assumedPods[k] = v
	}

	pdbs := make(map[string]*policy.PodDisruptionBudget)
	for k, v := range cache.pdbs {
		pdbs[k] = v.DeepCopy()
	}

	return &Snapshot{
		Nodes:       nodes,
		AssumedPods: assumedPods,
		Pdbs:        pdbs,
	}
}

func (cache *schedulerCache) UpdateNodeNameToInfoMap(nodeNameToInfo map[string]*NodeInfo) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	for name, info := range cache.nodes {
		if utilfeature.DefaultFeatureGate.Enabled(features.BalanceAttachedNodeVolumes) && info.TransientInfo != nil {
			// Transient scheduler info is reset here.
			info.TransientInfo.resetTransientSchedulerInfo()
		}
		if current, ok := nodeNameToInfo[name]; !ok || current.generation != info.generation {
			nodeNameToInfo[name] = info.Clone()
		}
	}
	for name := range nodeNameToInfo {
		if _, ok := cache.nodes[name]; !ok {
			delete(nodeNameToInfo, name)
		}
	}
	return nil
}

func (cache *schedulerCache) List(selector labels.Selector) ([]*v1.Pod, error) {
	alwaysTrue := func(p *v1.Pod) bool { return true }
	return cache.FilteredList(alwaysTrue, selector)
}

func (cache *schedulerCache) FilteredList(podFilter PodFilter, selector labels.Selector) ([]*v1.Pod, error) {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	// podFilter is expected to return true for most or all of the pods. We
	// can avoid expensive array growth without wasting too much memory by
	// pre-allocating capacity.
	maxSize := 0
	for _, info := range cache.nodes {
		maxSize += len(info.pods)
	}
	pods := make([]*v1.Pod, 0, maxSize)
	for _, info := range cache.nodes {
		for _, pod := range info.pods {
			if podFilter(pod) && selector.Matches(labels.Set(pod.Labels)) {
				pods = append(pods, pod)
			}
		}
	}
	return pods, nil
}

func (cache *schedulerCache) AssumePod(pod *v1.Pod) error {
	key, err := getPodKey(pod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()
	if _, ok := cache.podStates[key]; ok {
		return fmt.Errorf("pod %v is in the cache, so can't be assumed", key)
	}

	cache.addPod(pod)
	ps := &podState{
		pod: pod,
	}
	cache.podStates[key] = ps
	cache.assumedPods[key] = true
	return nil
}

func (cache *schedulerCache) FinishBinding(pod *v1.Pod) error {
	return cache.finishBinding(pod, time.Now())
}

// finishBinding exists to make tests determinitistic by injecting now as an argument
func (cache *schedulerCache) finishBinding(pod *v1.Pod, now time.Time) error {
	key, err := getPodKey(pod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	glog.V(5).Infof("Finished binding for pod %v. Can be expired.", key)
	currState, ok := cache.podStates[key]
	if ok && cache.assumedPods[key] {
		dl := now.Add(cache.ttl)
		currState.bindingFinished = true
		currState.deadline = &dl
	}
	return nil
}

func (cache *schedulerCache) ForgetPod(pod *v1.Pod) error {
	key, err := getPodKey(pod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	currState, ok := cache.podStates[key]
	if ok && currState.pod.Spec.NodeName != pod.Spec.NodeName {
		return fmt.Errorf("pod %v was assumed on %v but assigned to %v", key, pod.Spec.NodeName, currState.pod.Spec.NodeName)
	}

	switch {
	// Only assumed pod can be forgotten.
	case ok && cache.assumedPods[key]:
		err := cache.removePod(pod)
		if err != nil {
			return err
		}
		delete(cache.assumedPods, key)
		delete(cache.podStates, key)
	default:
		return fmt.Errorf("pod %v wasn't assumed so cannot be forgotten", key)
	}
	return nil
}

// Assumes that lock is already acquired.
func (cache *schedulerCache) addPod(pod *v1.Pod) {
	n, ok := cache.nodes[pod.Spec.NodeName]
	if !ok {
		n = NewNodeInfo()
		cache.nodes[pod.Spec.NodeName] = n
	}
glog.Warningf("VDBG-cache-addPod: Pod: %v", pod.Name)
	n.AddPod(pod)
}

// this function expects valid pod, and valid, non-empty resizeRequestAnnotation json string
func (cache *schedulerCache) getPodResizeRequirements(pod *v1.Pod, resizeRequestAnnotation string) (map[string]v1.Container, *Resource, error) {
	var resizeContainers []v1.Container

	if err := json.Unmarshal([]byte(resizeRequestAnnotation), &resizeContainers); err != nil {
		return nil, nil, err
	}
//fmt.Printf("VDBGGG: ANNO: %s. resizeContainers: %#v\n", resizeRequestAnnotation, resizeContainers)
	resizeContainersMap := make(map[string]v1.Container)
	for _, resizeContainer := range resizeContainers {
		resizeContainersMap[resizeContainer.Name] = resizeContainer
	}

	podResource := &Resource{}
	for _, container := range pod.Spec.Containers {
		containerResourcesRequests := v1.ResourceList {
							v1.ResourceCPU:    container.Resources.Requests[v1.ResourceCPU],
							v1.ResourceMemory: container.Resources.Requests[v1.ResourceMemory],
						}
//fmt.Printf("VDBGGG22: containerResourceRequests: %#v\n", containerResourcesRequests)
		if resizeContainer, ok := resizeContainersMap[container.Name]; ok {
			for k, v := range resizeContainer.Resources.Requests {
				containerResourcesRequests[k] = v
			}
		}
glog.Warningf("VDBG-cache-getPodResizeRequirements: Pod: %s. Container: %s. CtrRESOURCEREQUESTS: %+v", pod.Name, container.Name, containerResourcesRequests)
		podResource.Add(containerResourcesRequests)
	}

glog.Warningf("VDBG-cache-getPodResizeRequirements: Pod: %s podResource: %+v", pod.Name, podResource)
	return resizeContainersMap, podResource, nil
}

func (cache *schedulerCache) processPodResourcesResizeRequest(oldPod, newPod *v1.Pod) error {
	node, ok := cache.nodes[newPod.Spec.NodeName]
	if !ok {
		errMsg := fmt.Sprintf("Node %s not found for pod %s", newPod.Spec.NodeName, newPod.Name)
		glog.Errorf(errMsg)
		return fmt.Errorf(errMsg)
	}
glog.Warningf("VDBG-cache-processVSCALE: Pod: %s. NodeINFO: %+v.", newPod.Name, node)

	resizeResourcesPolicy := api.ResizePolicyInPlacePreferred
	if _, ok := newPod.ObjectMeta.Annotations[api.AnnotationResizeResourcesPolicy]; ok {
		resizeResourcesPolicy = api.ResizePolicy(newPod.ObjectMeta.Annotations[api.AnnotationResizeResourcesPolicy])
	}

	if resizeRequestAnnotation, ok := newPod.ObjectMeta.Annotations[api.AnnotationResizeResources]; ok {
glog.Warningf("VDBG-cache-processVSCALE: Pod: %s. Policy: %+v. Annot: %v.", newPod.Name, resizeResourcesPolicy, resizeRequestAnnotation)
		if resizeRequestAnnotation == "" {
			return nil
		}

		if resizeResourcesPolicy == api.ResizePolicyRestart {
			newPod.ObjectMeta.Annotations[api.AnnotationResizeResources] = api.ResizeActionReschedule
			return nil
		}

		if resizeContainersMap, podResource, err := cache.getPodResizeRequirements(newPod, resizeRequestAnnotation); err == nil {
			// Remove oldPod from node for resizing calculations with newPod
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-BEFORE_REMOVE_POD: NAAR: %#v NRRR: %#v\n", node.AllocatableResource(), node.RequestedResource())
			if err := node.RemovePod(oldPod); err != nil {
				return err
			}
			allocatable := node.AllocatableResource()
			nodeMilliCPU := node.RequestedResource().MilliCPU
			nodeMemory := node.RequestedResource().Memory
glog.Warningf("VDBG-cache-processVSCALE: NODE-INFO: NODE_ALLOCATABLE_RESOURCE: %+v (CPU: %d . MEM: %d)", node.allocatableResource, allocatable.MilliCPU, allocatable.Memory)
glog.Warningf("VDBG-cache-processVSCALE: NODE-INFO: NODE_REQUESTED_RESOURCE: %+v (CPU: %d . MEM: %d)", node.requestedResource, nodeMilliCPU, nodeMemory)
glog.Warningf("VDBG-cache-processVSCALE: NODE-INFO: NODE_NONZERO-REQUEST: %+v", node.nonzeroRequest)
fmt.Printf("VDBG-cache-processVSCALE: NODE-INFO: NODE_ALLOCATABLE_RESOURCE: %+v (CPU: %d . MEM: %d)\n", node.allocatableResource, allocatable.MilliCPU, allocatable.Memory)
fmt.Printf("VDBG-cache-processVSCALE: NODE-INFO: NODE_REQUESTED_RESOURCE: %+v (CPU: %d . MEM: %d)\n", node.requestedResource, nodeMilliCPU, nodeMemory)
fmt.Printf("VDBG-cache-processVSCALE: NEWPod: podResource: %#v\n", podResource)
			node.AddPod(oldPod)
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-AFTER_ADD_POD_POD: NAAR: %#v NRRR: %#v\n", node.AllocatableResource(), node.RequestedResource())

			if ((allocatable.MilliCPU > (podResource.MilliCPU + nodeMilliCPU)) &&
				(allocatable.Memory > (podResource.Memory + nodeMemory))) {
				// InPlace resizing is possible
				for i, container := range newPod.Spec.Containers {
					resizeContainer, ok := resizeContainersMap[container.Name]
					if ok {
fmt.Printf("VDBGVDBG: RESIZE_CONTAINER: %#v\n",resizeContainer)
						// Controller checks ensure pod QoS invariance, just update changed values
						if (resizeContainer.Resources.Requests != nil) {
							for k, v := range resizeContainer.Resources.Requests {
								newPod.Spec.Containers[i].Resources.Requests[k] = v
							}
						}
						if (resizeContainer.Resources.Limits != nil) {
							for k, v := range resizeContainer.Resources.Limits {
								newPod.Spec.Containers[i].Resources.Limits[k] = v
							}
						}
					}
				}
				newPod.ObjectMeta.Annotations[api.AnnotationResizeResources] = api.ResizeActionUpdate
			} else {
				// InPlace resizing is not possible, restart if allowed by policy
				if resizeResourcesPolicy == api.ResizePolicyInPlaceOnly {
					newPod.ObjectMeta.Annotations[api.AnnotationResizeResources] = api.ResizeActionNonePerPolicy
					glog.Infof("In-place resizing of pod %s on node %s rejected by policy (%s). Allocatable CPU: %d, Memory: %d. Requested: CPU: %d, Memory %d.",
							newPod.Name, newPod.Spec.NodeName, resizeResourcesPolicy, allocatable.MilliCPU, allocatable.Memory,
							podResource.MilliCPU, podResource.Memory)
					return nil
				}
				newPod.ObjectMeta.Annotations[api.AnnotationResizeResources] = api.ResizeActionReschedule
			}
		} else {
			return err
		}
	}
	return nil
}

// Assumes that lock is already acquired.
func (cache *schedulerCache) updatePod(oldPod, newPod *v1.Pod) error {
glog.Warningf("VDBG-cache-updatePod: OLD_POD: %s (%s)\n   ===>  OLD_POD_ANNOT: %+v\n   ===>  OLD_POD_RES: %+v\n   ===>  STS: %+v\n", oldPod.Name, oldPod.ObjectMeta.ResourceVersion, oldPod.ObjectMeta.Annotations, oldPod.Spec.Containers, oldPod.Status)
glog.Warningf("VDBG-cache-updatePod: NEW_POD: %s (%s)\n   ===>  NEW_POD_ANNOT: %+v\n   ===>  NEW_POD_RES: %+v\n   ===>  STS: %+v\n", newPod.Name, newPod.ObjectMeta.ResourceVersion, newPod.ObjectMeta.Annotations, newPod.Spec.Containers, newPod.Status)
fmt.Printf("VDBG-cache-updatePod: OLD_POD: %s (%s)\n=======================\n   ===>  OLD_POD_ANNOT: %+v\n   ===>  OLD_POD_RES: %+v\n", oldPod.Name, oldPod.ObjectMeta.ResourceVersion, oldPod.ObjectMeta.Annotations, oldPod.Spec.Containers)
fmt.Printf("VDBG-cache-updatePod: NEW_POD: %s (%s)\n   ===>  NEW_POD_ANNOT: %+v\n   ===>  NEW_POD_RES: %+v\n", newPod.Name, newPod.ObjectMeta.ResourceVersion, newPod.ObjectMeta.Annotations, newPod.Spec.Containers)
node, _ := cache.nodes[newPod.Spec.NodeName]
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-1111: NAAR: %#v NRRR: %#v\n", node.AllocatableResource(), node.RequestedResource())
	if err := cache.processPodResourcesResizeRequest(oldPod, newPod); err != nil {
		return err
	}
node2, _ := cache.nodes[newPod.Spec.NodeName]
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-2222: NAAR: %#v NRRR: %#v\n", node2.AllocatableResource(), node2.RequestedResource())
	if err := cache.removePod(oldPod); err != nil {
		return err
	}
fmt.Printf("VDBG-cache-updatePod: PROCESSED_NEW_POD: %s\n   ===>  PROCESSED_NEW_POD_ANNOT: %+v\n   ===>  PROCESSED_NEW_POD_RES: %+v\n=======================\n", newPod.Name, newPod.ObjectMeta.Annotations, newPod.Spec.Containers)
node3, _ := cache.nodes[newPod.Spec.NodeName]
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-3333: NAAR: %#v NRRR: %#v\n", node3.AllocatableResource(), node3.RequestedResource())
	cache.addPod(newPod)
node4, _ := cache.nodes[newPod.Spec.NodeName]
fmt.Printf("VDBG-cache-updatePOD: NODE-INFO-4444: NAAR: %#v NRRR: %#v\n", node4.AllocatableResource(), node4.RequestedResource())
	return nil
}

// Assumes that lock is already acquired.
func (cache *schedulerCache) removePod(pod *v1.Pod) error {
	n := cache.nodes[pod.Spec.NodeName]
glog.Warningf("VDBG-cache-removePod: Pod: %s , NodeInfo: %+v", pod.Name, n)
	if err := n.RemovePod(pod); err != nil {
		return err
	}
	if len(n.pods) == 0 && n.node == nil {
		delete(cache.nodes, pod.Spec.NodeName)
	}
	return nil
}

func (cache *schedulerCache) AddPod(pod *v1.Pod) error {
glog.Warningf("VDBG-cache-AddPod: Pod: %v", pod.Name)
	key, err := getPodKey(pod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	currState, ok := cache.podStates[key]
	switch {
	case ok && cache.assumedPods[key]:
		if currState.pod.Spec.NodeName != pod.Spec.NodeName {
			// The pod was added to a different node than it was assumed to.
			glog.Warningf("Pod %v was assumed to be on %v but got added to %v", key, pod.Spec.NodeName, currState.pod.Spec.NodeName)
			// Clean this up.
			cache.removePod(currState.pod)
			cache.addPod(pod)
		}
		delete(cache.assumedPods, key)
		cache.podStates[key].deadline = nil
		cache.podStates[key].pod = pod
	case !ok:
		// Pod was expired. We should add it back.
		cache.addPod(pod)
		ps := &podState{
			pod: pod,
		}
		cache.podStates[key] = ps
	default:
		return fmt.Errorf("pod %v was already in added state", key)
	}
	return nil
}

func (cache *schedulerCache) UpdatePod(oldPod, newPod *v1.Pod) error {
//glog.Warningf("VDBG-cache-UpdatePod: OLDPod: %v", oldPod.Name)
//glog.Warningf("VDBG-cache-UpdatePod: NEWPod: %v", newPod.Name)
	key, err := getPodKey(oldPod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	currState, ok := cache.podStates[key]
	switch {
	// An assumed pod won't have Update/Remove event. It needs to have Add event
	// before Update event, in which case the state would change from Assumed to Added.
	case ok && !cache.assumedPods[key]:
		if currState.pod.Spec.NodeName != newPod.Spec.NodeName {
			glog.Errorf("Pod %v updated on a different node than previously added to.", key)
			glog.Fatalf("Schedulercache is corrupted and can badly affect scheduling decisions")
		}
		if err := cache.updatePod(oldPod, newPod); err != nil {
			return err
		}
	default:
		return fmt.Errorf("pod %v is not added to scheduler cache, so cannot be updated", key)
	}
	return nil
}

func (cache *schedulerCache) RemovePod(pod *v1.Pod) error {
glog.Warningf("VDBG-cache-RemovePod: Pod: %v", pod.Name)
	key, err := getPodKey(pod)
	if err != nil {
		return err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	currState, ok := cache.podStates[key]
	switch {
	// An assumed pod won't have Delete/Remove event. It needs to have Add event
	// before Remove event, in which case the state would change from Assumed to Added.
	case ok && !cache.assumedPods[key]:
		if currState.pod.Spec.NodeName != pod.Spec.NodeName {
			glog.Errorf("Pod %v was assumed to be on %v but got added to %v", key, pod.Spec.NodeName, currState.pod.Spec.NodeName)
			glog.Fatalf("Schedulercache is corrupted and can badly affect scheduling decisions")
		}
		err := cache.removePod(currState.pod)
		if err != nil {
			return err
		}
		delete(cache.podStates, key)
	default:
		return fmt.Errorf("pod %v is not found in scheduler cache, so cannot be removed from it", key)
	}
	return nil
}

func (cache *schedulerCache) IsAssumedPod(pod *v1.Pod) (bool, error) {
	key, err := getPodKey(pod)
	if err != nil {
		return false, err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	b, found := cache.assumedPods[key]
	if !found {
		return false, nil
	}
	return b, nil
}

func (cache *schedulerCache) GetPod(pod *v1.Pod) (*v1.Pod, error) {
	key, err := getPodKey(pod)
	if err != nil {
		return nil, err
	}

	cache.mu.Lock()
	defer cache.mu.Unlock()

	podState, ok := cache.podStates[key]
	if !ok {
		return nil, fmt.Errorf("pod %v does not exist in scheduler cache", key)
	}

	return podState.pod, nil
}

func (cache *schedulerCache) AddNode(node *v1.Node) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	n, ok := cache.nodes[node.Name]
	if !ok {
		n = NewNodeInfo()
		cache.nodes[node.Name] = n
	}
	return n.SetNode(node)
}

func (cache *schedulerCache) UpdateNode(oldNode, newNode *v1.Node) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	n, ok := cache.nodes[newNode.Name]
	if !ok {
		n = NewNodeInfo()
		cache.nodes[newNode.Name] = n
	}
	return n.SetNode(newNode)
}

func (cache *schedulerCache) RemoveNode(node *v1.Node) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	n := cache.nodes[node.Name]
	if err := n.RemoveNode(node); err != nil {
		return err
	}
	// We remove NodeInfo for this node only if there aren't any pods on this node.
	// We can't do it unconditionally, because notifications about pods are delivered
	// in a different watch, and thus can potentially be observed later, even though
	// they happened before node removal.
	if len(n.pods) == 0 && n.node == nil {
		delete(cache.nodes, node.Name)
	}
	return nil
}

func (cache *schedulerCache) AddPDB(pdb *policy.PodDisruptionBudget) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	// Unconditionally update cache.
	cache.pdbs[string(pdb.UID)] = pdb
	return nil
}

func (cache *schedulerCache) UpdatePDB(oldPDB, newPDB *policy.PodDisruptionBudget) error {
	return cache.AddPDB(newPDB)
}

func (cache *schedulerCache) RemovePDB(pdb *policy.PodDisruptionBudget) error {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	delete(cache.pdbs, string(pdb.UID))
	return nil
}

func (cache *schedulerCache) ListPDBs(selector labels.Selector) ([]*policy.PodDisruptionBudget, error) {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	var pdbs []*policy.PodDisruptionBudget
	for _, pdb := range cache.pdbs {
		if selector.Matches(labels.Set(pdb.Labels)) {
			pdbs = append(pdbs, pdb)
		}
	}
	return pdbs, nil
}

func (cache *schedulerCache) IsUpToDate(n *NodeInfo) bool {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	node, ok := cache.nodes[n.Node().Name]
	return ok && n.generation == node.generation
}

func (cache *schedulerCache) run() {
	go wait.Until(cache.cleanupExpiredAssumedPods, cache.period, cache.stop)
}

func (cache *schedulerCache) cleanupExpiredAssumedPods() {
	cache.cleanupAssumedPods(time.Now())
}

// cleanupAssumedPods exists for making test deterministic by taking time as input argument.
func (cache *schedulerCache) cleanupAssumedPods(now time.Time) {
	cache.mu.Lock()
	defer cache.mu.Unlock()

	// The size of assumedPods should be small
	for key := range cache.assumedPods {
		ps, ok := cache.podStates[key]
		if !ok {
			panic("Key found in assumed set but not in podStates. Potentially a logical error.")
		}
		if !ps.bindingFinished {
			glog.V(3).Infof("Couldn't expire cache for pod %v/%v. Binding is still in progress.",
				ps.pod.Namespace, ps.pod.Name)
			continue
		}
		if now.After(*ps.deadline) {
			glog.Warningf("Pod %s/%s expired", ps.pod.Namespace, ps.pod.Name)
			if err := cache.expirePod(key, ps); err != nil {
				glog.Errorf("ExpirePod failed for %s: %v", key, err)
			}
		}
	}
}

func (cache *schedulerCache) expirePod(key string, ps *podState) error {
	if err := cache.removePod(ps.pod); err != nil {
		return err
	}
	delete(cache.assumedPods, key)
	delete(cache.podStates, key)
	return nil
}
