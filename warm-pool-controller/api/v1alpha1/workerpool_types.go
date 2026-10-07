/*
Copyright 2026.

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

package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// WorkerPoolSpec defines the desired state of WorkerPool.
type WorkerPoolSpec struct {
	// replicas is the number of warm Pods to keep: Pods that are Ready and not
	// assigned to any WorkerClaim. Claimed Pods do not count toward it, so the
	// total number of Pods grows with the number of claims.
	// +kubebuilder:validation:Minimum=0
	// +required
	Replicas int32 `json:"replicas"`

	// template describes the Pods the pool creates. Edits apply only to Pods
	// created after the edit; existing Pods are not rolled.
	// Labels and annotations under the takehome.replit.com/ prefix are reserved
	// for the controller and are dropped from the template.
	// +required
	Template corev1.PodTemplateSpec `json:"template"`
}

// WorkerPoolStatus is recomputed from the pool's Pods on every reconcile.
type WorkerPoolStatus struct {
	// observedGeneration is the spec generation this status was computed for.
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`

	// replicas counts every live Pod of the pool (warm, starting and claimed).
	// Terminating, Failed and Succeeded Pods are not counted.
	// +optional
	Replicas int32 `json:"replicas"`

	// readyReplicas counts live Pods that are Ready, claimed or not.
	// +optional
	ReadyReplicas int32 `json:"readyReplicas"`

	// availableReplicas counts warm Pods: Ready and unclaimed. This is the
	// number the controller drives toward spec.replicas.
	// +optional
	AvailableReplicas int32 `json:"availableReplicas"`

	// claimedReplicas counts live Pods assigned to a WorkerClaim.
	// +optional
	ClaimedReplicas int32 `json:"claimedReplicas"`

	// pendingReplicas counts unclaimed Pods that exist but are not Ready yet.
	// +optional
	PendingReplicas int32 `json:"pendingReplicas"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=wp
// +kubebuilder:validation:XValidation:rule="size(self.metadata.name) <= 63",message="name must be at most 63 characters (it is used as a label value)"
// +kubebuilder:printcolumn:name="Desired",type=integer,JSONPath=`.spec.replicas`
// +kubebuilder:printcolumn:name="Warm",type=integer,JSONPath=`.status.availableReplicas`
// +kubebuilder:printcolumn:name="Pending",type=integer,JSONPath=`.status.pendingReplicas`
// +kubebuilder:printcolumn:name="Claimed",type=integer,JSONPath=`.status.claimedReplicas`
// +kubebuilder:printcolumn:name="Total",type=integer,JSONPath=`.status.replicas`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// WorkerPool keeps spec.replicas ready, unclaimed Pods built from spec.template.
type WorkerPool struct {
	metav1.TypeMeta `json:",inline"`

	// metadata is a standard object metadata
	// +optional
	metav1.ObjectMeta `json:"metadata,omitzero"`

	// spec defines the desired state of WorkerPool
	// +required
	Spec WorkerPoolSpec `json:"spec"`

	// status defines the observed state of WorkerPool
	// +optional
	Status WorkerPoolStatus `json:"status,omitzero"`
}

// +kubebuilder:object:root=true

// WorkerPoolList contains a list of WorkerPool
type WorkerPoolList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitzero"`
	Items           []WorkerPool `json:"items"`
}

func init() {
	SchemeBuilder.Register(func(s *runtime.Scheme) error {
		s.AddKnownTypes(SchemeGroupVersion, &WorkerPool{}, &WorkerPoolList{})
		return nil
	})
}
