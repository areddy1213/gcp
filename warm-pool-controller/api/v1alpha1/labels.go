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

// Metadata the controller writes on Pods. Together with the Pod's
// ownerReference to its WorkerPool, these are the durable record of every
// assignment: the controller keeps no other state.
const (
	// ReservedPrefix is stripped from pool templates so a template cannot
	// create Pods that look already claimed.
	ReservedPrefix = "takehome.replit.com/"

	// LabelPool names the WorkerPool that created the Pod. Set at creation.
	LabelPool = ReservedPrefix + "pool"

	// LabelClaim names the WorkerClaim the Pod is assigned to. For humans and
	// for routing Pod events to the claim; LabelClaimUID is authoritative.
	LabelClaim = ReservedPrefix + "claim"

	// LabelClaimUID holds the UID of the assigned WorkerClaim. A Pod with this
	// label is claimed. UIDs, unlike names, are never reused, so a claim that
	// is deleted and recreated under the same name does not inherit the Pod.
	LabelClaimUID = ReservedPrefix + "claim-uid"

	// AnnotationClaimedAt records when the Pod was assigned (RFC 3339).
	AnnotationClaimedAt = ReservedPrefix + "claimed-at"

	// ClaimFinalizer lets the controller delete a claim's Pod before the
	// claim disappears.
	ClaimFinalizer = ReservedPrefix + "release-pod"
)
