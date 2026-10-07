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
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// WorkerClaimSpec defines the desired state of WorkerClaim.
type WorkerClaimSpec struct {
	// poolName is the WorkerPool, in the claim's namespace, to take a Pod from.
	// It cannot be changed after creation.
	// +kubebuilder:validation:MinLength=1
	// +kubebuilder:validation:MaxLength=63
	// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="poolName is immutable"
	// +required
	PoolName string `json:"poolName"`
}

// ClaimPhase is the coarse state of a WorkerClaim.
// +kubebuilder:validation:Enum=Pending;Claimed
type ClaimPhase string

const (
	// ClaimPending means the claim has no Pod and is waiting for a warm one.
	ClaimPending ClaimPhase = "Pending"
	// ClaimClaimed means a Pod carries this claim's UID label.
	ClaimClaimed ClaimPhase = "Claimed"
)

// Reasons reported in WorkerClaimStatus.Reason and in Events.
const (
	ReasonAssigned            = "Assigned"
	ReasonNoWarmPodsAvailable = "NoWarmPodsAvailable"
	ReasonPoolNotFound        = "PoolNotFound"
	ReasonAssignedPodLost     = "AssignedPodLost"
)

// WorkerClaimStatus is a projection of the Pod labelled with this claim's UID.
// The Pod labels are the source of truth; this status is rebuilt from them.
type WorkerClaimStatus struct {
	// phase is Pending or Claimed.
	// +optional
	Phase ClaimPhase `json:"phase,omitempty"`

	// podName is the assigned Pod. It can change: if the Pod is lost, the claim
	// goes back to Pending and is later assigned a different Pod.
	// +optional
	PodName string `json:"podName,omitempty"`

	// podIP is the assigned Pod's IP.
	// +optional
	PodIP string `json:"podIP,omitempty"`

	// reason is a machine-readable explanation of the phase:
	// Assigned, NoWarmPodsAvailable, PoolNotFound or AssignedPodLost.
	// +optional
	Reason string `json:"reason,omitempty"`

	// message is a human-readable explanation of the phase.
	// +optional
	Message string `json:"message,omitempty"`

	// assignedAt is when the current Pod was assigned (copied from the Pod's
	// takehome.replit.com/claimed-at annotation).
	// +optional
	AssignedAt *metav1.Time `json:"assignedAt,omitempty"`

	// attempts counts the Pods assigned over the claim's life. A value above 1
	// means earlier Pods were lost. It is informational only.
	// +optional
	Attempts int32 `json:"attempts,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=wc
// +kubebuilder:validation:XValidation:rule="size(self.metadata.name) <= 63",message="name must be at most 63 characters (it is used as a label value)"
// +kubebuilder:printcolumn:name="Pool",type=string,JSONPath=`.spec.poolName`
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Pod",type=string,JSONPath=`.status.podName`
// +kubebuilder:printcolumn:name="IP",type=string,JSONPath=`.status.podIP`
// +kubebuilder:printcolumn:name="Reason",type=string,JSONPath=`.status.reason`
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// WorkerClaim asks for one ready Pod from a WorkerPool.
type WorkerClaim struct {
	metav1.TypeMeta `json:",inline"`

	// metadata is a standard object metadata
	// +optional
	metav1.ObjectMeta `json:"metadata,omitzero"`

	// spec defines the desired state of WorkerClaim
	// +required
	Spec WorkerClaimSpec `json:"spec"`

	// status defines the observed state of WorkerClaim
	// +optional
	Status WorkerClaimStatus `json:"status,omitzero"`
}

// +kubebuilder:object:root=true

// WorkerClaimList contains a list of WorkerClaim
type WorkerClaimList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitzero"`
	Items           []WorkerClaim `json:"items"`
}

func init() {
	SchemeBuilder.Register(func(s *runtime.Scheme) error {
		s.AddKnownTypes(SchemeGroupVersion, &WorkerClaim{}, &WorkerClaimList{})
		return nil
	})
}
