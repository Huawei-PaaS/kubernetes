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
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	extensions "k8s.io/api/extensions/v1beta1"
	"k8s.io/kubernetes/plugin/pkg/admission/formatdeployment"
	"net/http"
	"fmt"
	"io/ioutil"
	"encoding/json"
	"strconv"
)

// SLA Controller
type SlaController struct {
}

type NodeMetricPoint struct {
	Value     interface{}       `json:"value"`
	Tags      map[string]string `json:"tags"`
	Timestamp int64             `json:"timestamp"`
}

type NodeMetricResp struct {
	MetricName  string                       `json:"metric_name"`
	MetricValue map[string][]*NodeMetricPoint `json:"metric_value"`
}

func (sc *SlaController) GetPodTargetLatency(pod *v1.Pod, qosResourceStatus *QosResourceStatus) (float64, error) {
	podDeployment, err := sc.GetPodDeploymentFromApiServer(pod, qosResourceStatus)

	if err != nil || podDeployment == nil || podDeployment.Spec.Sla == nil ||
		podDeployment.Spec.Sla.SlaSpec == nil {
		//glog.Infof("Failed get pod target latency: %v", err)
		return 0, fmt.Errorf("Failed get pod target latency: %v", err)
	}

	podTargetLatency, ok := podDeployment.Spec.Sla.SlaSpec[string(v1.SlaSpecRT)]

	if ok {
		glog.Infof("Get pod target latency from api server: %v", podTargetLatency)
		return float64(podTargetLatency), nil
	} else {
		return 0, fmt.Errorf("Failed get pod target latency: %v", err)
	}
}

func (sc *SlaController) GetPodTargetLatencyFromAnnotation(pod *v1.Pod) (float64, error) {
	if pod.Annotations == nil {
		//glog.Info("Failed get pod target latency from pod annotation: %v", pod.Annotations)
		return 0, fmt.Errorf("Failed get pod annotation for pod target latency: %v", pod.Annotations)
	}

	targetLatency, ok := pod.Annotations[string(formatdeployment.TargetLatencyField)]

	if !ok {
		//glog.Info("Failed get pod target latency from pod annotation: %v", ok)
		return 0, fmt.Errorf("Failed get pod target latency from pod annotation: %v", ok)
	}

	podTargetLatency, err := strconv.ParseFloat(targetLatency, 64)

	if err != nil {
		//glog.Infof("Failed convert target latency from string to float: %v", targetLatency)
		return 0, fmt.Errorf("Failed convert pod target latency from string to float: %v", targetLatency)
	}

	glog.Infof("Get pod target latency from annotation: %v", podTargetLatency)
	return float64(podTargetLatency), nil
}

func (sc *SlaController) GetPodRealLatencyFromOpsAgent(nodeMetricResp *NodeMetricResp, podIP string) (float64, error) {

	podMetricValue := nodeMetricResp.MetricValue[podIP]

	if podMetricValue == nil || len(podMetricValue) == 0 {
		//glog.Infof("No pod metric value from pod %v ", podIP)
		return 0, fmt.Errorf("No pod metric value from pod %v ", podIP)
	}

	podRealLatency := podMetricValue[0].Value.(float64)

	for _, v := range podMetricValue {
		if v.Value.(float64) > podRealLatency {
			podRealLatency = v.Value.(float64)
		}
	}

	//podRealLatency := podMetricValue[len(podMetricValue)-1].Value.(float64)
	glog.Infof("Get pod real latency from ops agent: %v", podRealLatency)
	return float64(podRealLatency), nil
}

func (sc *SlaController) GetPodDeploymentFromReplicaSet(rs *extensions.ReplicaSet,
qosResourceStatus *QosResourceStatus) ([]extensions.Deployment, error) {

	var deployments []extensions.Deployment

	if len(rs.Labels) == 0 {
		//glog.Infof("No deployments found for ReplicaSet %v because it has no labels", rs.Name)
		return nil, fmt.Errorf("No deployments found for ReplicaSet %v because it has no labels", rs.Name)
	}

	ds, err := qosResourceStatus.kubeClient.Extensions().Deployments(rs.Namespace).List(metav1.ListOptions{})

	if err != nil {
		//glog.Infof("Failed list deployments for pod target latency: %v", err)
		return nil, fmt.Errorf("Failed list deployments for pod target latency: %v", err)
	}

	for _, d := range ds.Items {

		/*
		if d.Namespace != rs.Namespace {
			glog.Infof("Deployment namespace: %v is not the same as replica set namespace: %v, so skip. ",
				d.Namespace, rs.Namespace)
			continue
		}
		*/

		selector, err := metav1.LabelSelectorAsSelector(d.Spec.Selector)

		if err != nil {
			//glog.Infof("Invalid label selector for pod target latency: %v", err)
			return nil, fmt.Errorf("Invalid label selector for pod target latency: %v", err)
		} else {
			glog.Infof("Deployment selector for pod target latency: %v ", selector)
		}

		// If a deployment with a nil or empty selector creeps in, it should match nothing, not everything.
		if selector.Empty() || !selector.Matches(labels.Set(rs.Labels)){
			glog.Infoln("Replica set labels: ", rs.Labels)
			glog.Infoln("Deployment selector is empty or not mathc to replica set label, so skip")
			continue
		}

		deployments = append(deployments, d)
	}

	if len(deployments) == 0 {
		return nil, fmt.Errorf("could not find deployments for ReplicaSet %v in namespace %v with labels: %v",
			rs.Name, rs.Namespace, rs.Labels)
	} else {
		//glog.Infof("Get pod deployments from replca set: %v", deployments)
		return deployments, nil
	}
}

func (sc *SlaController) GetPodDeploymentFromApiServer(pod *v1.Pod,
qosResourceStatus *QosResourceStatus) (*extensions.Deployment, error) {
	var selector labels.Selector
	rss, err := qosResourceStatus.kubeClient.Extensions().ReplicaSets(pod.Namespace).List(metav1.ListOptions{})

	if err != nil {
		return nil, fmt.Errorf("Failed list replica sets for pod target latency: %v", err)
	}

	for _, rs := range rss.Items {

		/*
		if rs.Namespace != pod.Namespace {
			glog.Infof("Replica set namespace: %v is not the same as pod namespace: %v, so skip. ",
				rs.Namespace, pod.Namespace)
			continue
		}
		*/

		selector, err = metav1.LabelSelectorAsSelector(rs.Spec.Selector)

		if err != nil {
			return nil, fmt.Errorf("Failed get selector for pod target latency: %v", err)
		} else {
			glog.Infof("Replica set selector for pod target latency: %v ", selector)
		}

		// If a ReplicaSet with a nil or empty selector creeps in, it should match nothing, not everything.
		if selector.Empty() || !selector.Matches(labels.Set(pod.Labels)) {
			glog.Infoln("pod labels: ", pod.Labels)
			glog.Infoln("Replica set selector is empty or not match to pod lable, so skip")
			continue
		}

		deployments, err := sc.GetPodDeploymentFromReplicaSet(&rs, qosResourceStatus)

		if err == nil && len(deployments) > 0 {
			//glog.Infof("Get pod deployment for pod target latency: %v ", deployments[0])
			return &deployments[0], nil
		}
	}

	return nil, fmt.Errorf("Failed get pod deployment from api server for pod target latency: %v", err)
}

func (sc *SlaController) GetNodeMetricRespFromOpsAgent(opsAgentEndpoint string) (*NodeMetricResp, error) {
	var nodeMetricResp *NodeMetricResp
	req, err := http.NewRequest("GET", opsAgentEndpoint, nil)

	if err != nil {
		//glog.Infof("Failed http NewRequest to ops agent for node real latency: %v", err)
		return nodeMetricResp, fmt.Errorf("Failed http NewRequest to ops agent for node real latency: %v", err)
	}

	//glog.Infof("Http request to ops agent for node real latency: %v ", req)
	httpClient := &http.Client{}
	resp, err := httpClient.Do(req)

	if err != nil {
		//glog.Infof("Failed httpClient.Do for node real latency: %v", err)
		return nodeMetricResp, fmt.Errorf("Failed httpClient.Do for node real latency: %v", err)
	}

	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		errInfo, _ := ioutil.ReadAll(resp.Body)
		//glog.Infof("Failed get node real latency with code: %d and info: %s", resp.StatusCode, string(errInfo))
		return nodeMetricResp, fmt.Errorf("Failed get node real latency with code: %d and info: %v",
			resp.StatusCode, string(errInfo))
	}

	//glog.Infof("Http response body from ops agent for node real latency: %v ", resp.Body)
	err = json.NewDecoder(resp.Body).Decode(&nodeMetricResp)

	if err != nil {
		//glog.Infof("Failed decode node real latency from ops agent: %v", err)
		return nodeMetricResp, fmt.Errorf("Failed decode node real latency from ops agent: %v", err)
	}

	//glog.Infof("Node real latency returned from ops agent: %v ", *nodeMetricResp)
	return nodeMetricResp, nil
}

func (sc *SlaController) process(qosResourceStatus *QosResourceStatus) *QosResourceStatus {

	var podTargetLatency float64
	var podLatencyThreshold float64
	var podRealLatency float64
	var opsAgentEndpoint string
	opsAgentApiPath := qosResourceStatus.QosConfig.SlaConfig.OpsAgentApiPath
	defalutOpsAgentApiPath := ":11808/api/v1/pod-metrics/latency"
	sortedSecondaryList := false

	if qosResourceStatus.primaryPodList == nil || len(qosResourceStatus.primaryPodList) == 0 {
		glog.Infoln("Primary pod list is empty, no action from SLA controller")
		return qosResourceStatus
	}

	if qosResourceStatus.secondaryPodList == nil || len(qosResourceStatus.secondaryPodList) == 0 {
		glog.Infoln("Secondary pod list is empty, no action from SLA controller")
		return qosResourceStatus
	}

	actionListSize := len(qosResourceStatus.ActionList)
	glog.Infoln("Current action list size: ", actionListSize)

	if actionListSize != 0 {
		glog.Infof("Action list is not empty, the first action is: %v, skip processing primary pods",
			qosResourceStatus.ActionList[0])
		return qosResourceStatus
	}

	hostIP := qosResourceStatus.primaryPodList[0].Status.HostIP

	if opsAgentApiPath == "" {
		glog.Infof("OpsAgentApiPath is nil or empty, use the default one: %v", defalutOpsAgentApiPath)
		opsAgentEndpoint = "http://" + hostIP + defalutOpsAgentApiPath
	} else {
		opsAgentEndpoint = "http://" + hostIP + opsAgentApiPath
	}

	//glog.Infof("endpoint for ops-agent %s", opsAgentEndpoint)
	nodeMetricResp, err := sc.GetNodeMetricRespFromOpsAgent(opsAgentEndpoint)

	if err != nil {
		glog.Infof("Failed get node real latency from ops agent: %v ", err)
		return qosResourceStatus
	}

	//Check the SLA status for each primary pod
	glog.Infoln("Start processing each primary pod")

	for _, pod := range qosResourceStatus.primaryPodList {
		podID := pod.UID
		podIP := pod.Status.PodIP
		glog.Infof("SLA controller is processing primary pod with ID: %v at IP: %v ", podID, podIP)

		//Calculate the pod latency threshold based on the configured threshold rate
		//podTargetLatency, err = sc.GetPodTargetLatency(pod, qosResourceStatus)
		podTargetLatency, err = sc.GetPodTargetLatencyFromAnnotation(pod)

		if err != nil || podTargetLatency == 0 {
			glog.Infof("No target latency for primary pod at IP: %v with error: %v, skip it", podIP, err)
			continue
		}

		thresholdRate := 1 + qosResourceStatus.QosConfig.SlaConfig.PodLatencyThresholdRate
		podLatencyThreshold = podTargetLatency * thresholdRate
		podRealLatency, err = sc.GetPodRealLatencyFromOpsAgent(nodeMetricResp, podIP)

		if err != nil || podRealLatency == 0 {
			glog.Infof("No real latency for primary pod at IP: %v with error: %v, skip it", podIP, err)
			continue
		}

		//Check if the current latency is greater than the pod latency threshold or the action list is empty
		if podRealLatency <= podLatencyThreshold {
			glog.Infof("Real latency: %v < target latency: %v for primary pod at IP: %v, skip it",
				podRealLatency, podTargetLatency, podIP)
			continue
		}

		glog.Infof("Real latency: %v > target latency: %v for primary pod at IP: %v, kill it",
			podRealLatency, podTargetLatency, podIP)

		if sortedSecondaryList == false && len(qosResourceStatus.secondaryPodList) > 1 {
			//Sort the secondary pod list based on decreasing start time
			sortPodListStartTime(qosResourceStatus.secondaryPodList)
			sortedSecondaryList = true
		}

		//Update the action list with the secondary pods to be killed
		qosResourceStatus.secondaryPodList = slaUpdateActionList(&(qosResourceStatus.ActionList),
			qosResourceStatus.secondaryPodList, qosResourceStatus.QosConfig.SlaConfig.ProcessMultiPod)

		IsNodeUnstable = true
		glog.Infoln("SLA controller set IsNodeUnstable to true when checking primary pods")
		return qosResourceStatus
	}

	glog.Infoln("Start processing each secondary pod")

	//Check the SLA status for each secondary pod
	for _, pod := range qosResourceStatus.secondaryPodList {
		podID := pod.UID
		podIP := pod.Status.PodIP
		glog.Infof("SLA controller is processing secondary pod with ID: %v at IP: %v ", podID, podIP)

		//Calculate the pod latency threshold based on the configured threshold rate
		//podTargetLatency, err = sc.GetPodTargetLatency(pod, qosResourceStatus)
		podTargetLatency, err = sc.GetPodTargetLatencyFromAnnotation(pod)

		if err != nil || podTargetLatency == 0 {
			glog.Infof("No target latency for secondary pod at IP: %v with error: %v, skip it", podIP, err)
			continue
		}

		thresholdRate := 1 + qosResourceStatus.QosConfig.SlaConfig.PodLatencyThresholdRate
		podLatencyThreshold = podTargetLatency * thresholdRate
		podRealLatency, err = sc.GetPodRealLatencyFromOpsAgent(nodeMetricResp, podIP)

		if err != nil || podRealLatency == 0 {
			glog.Infof("No real latency for secondary pod at IP: %v with error: %v, skip it", podIP, err)
			continue
		}

		//Check if the current latency is greater than the pod latency threshold or the action list is empty
		if podRealLatency <= podLatencyThreshold {
			glog.Infof("Real latency: %v < target latency: %v for secondary pod at IP: %v, skip it",
				podRealLatency, podTargetLatency, podIP)
			continue
		}

		glog.Infof("Real latency: %v > target latency: %v for secondary pod at IP: %v, kill it",
			podRealLatency, podTargetLatency, podIP)

		if sortedSecondaryList == false && len(qosResourceStatus.secondaryPodList) > 1 {
			//Sort the secondary pod list based on decreasing start time
			sortPodListStartTime(qosResourceStatus.secondaryPodList)
			sortedSecondaryList = true
		}

		//Update the action list with the secondary pods to be killed
		qosResourceStatus.secondaryPodList = slaUpdateActionList(&(qosResourceStatus.ActionList),
			qosResourceStatus.secondaryPodList, qosResourceStatus.QosConfig.SlaConfig.ProcessMultiPod)

		IsNodeUnstable = true
		glog.Infoln("SLA controller set IsNodeUnstable to true when checking secondary pods")
		return qosResourceStatus
	}

	return qosResourceStatus
}

func slaUpdateActionList(actionList *[]*Action, secondaryPods []*v1.Pod, processMultiPod bool) []*v1.Pod {

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
			glog.Infof("processMultiPod is: ", processMultiPod)
			return secondaryPods[i:]
		}
	}

	return secondaryPods[i:]
}

//Function to sort secondary/best effort pod list based on start time
func sortPodListStartTime(pods []*v1.Pod) {
	By(func(p1, p2 *v1.Pod) bool {
		p1StartTime := p1.Status.StartTime.Time
		p2StartTime := p2.Status.StartTime.Time
		return p1StartTime.After(p2StartTime)
	}).Sort(pods)
	return
}
