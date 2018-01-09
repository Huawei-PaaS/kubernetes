/*
Copyright 2014 The Kubernetes Authors All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http: //www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package formatdeployment

import (
	"io"
	"k8s.io/apiserver/pkg/admission"
	api "k8s.io/kubernetes/pkg/apis/core"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/kubernetes/pkg/apis/extensions"
	"strconv"

	"github.com/golang/glog"
)

const TargetLatencyField = "pod.alpha.kubernetes.io/targetlatency"

type formatdeployment struct {
	*admission.Handler
}

func (fd formatdeployment) Admit(attributes admission.Attributes) (err error) {
	// Ignore all calls to subresources or resources other than pods.
	if attributes == nil || len(attributes.GetSubresource()) != 0 || attributes.GetResource() != extensions.Resource("deployments").WithVersion(attributes.GetResource().Version) {
		return nil
	}
	deployment, ok := attributes.GetObject().(*extensions.Deployment)
	glog.V(3).Infof("Get deployment: %v when format deployment.", attributes.GetObject())
	if !ok {
		return apierrors.NewBadRequest("Resource was marked with kind Pod but was unable to be converted")
	}

	if deployment.Spec.Sla != nil && deployment.Spec.Sla.SlaSpec != nil {
		rt, ok := deployment.Spec.Sla.SlaSpec[string(api.SlaSpecRT)]
		if ok {
			if deployment.Spec.Template.ObjectMeta.Annotations == nil {
				deployment.Spec.Template.ObjectMeta.Annotations = make(map[string]string)
			}
			deployment.Spec.Template.ObjectMeta.Annotations[string(TargetLatencyField)] = strconv.FormatFloat(float64(rt), 'f', 2, 32)
		}
	}

	return nil
}

// NewAddPodAnnotations creates a new add pod annotations admission control handler
func NewFormatDeployment() admission.Interface {
	return &formatdeployment{
		Handler: admission.NewHandler(admission.Create, admission.Update),
	}
}

// Register registers a plugin
func Register(plugins *admission.Plugins) {
	plugins.Register("FormatDeployment", func(config io.Reader) (admission.Interface, error) {
		return NewFormatDeployment(), nil
	})
}
