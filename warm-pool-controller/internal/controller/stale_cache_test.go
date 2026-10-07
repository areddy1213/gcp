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

package controller

import (
	"context"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	"k8s.io/client-go/tools/events"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

// TestClaimDoesNotBindTwiceOnStaleCache reproduces the race the uncached
// "observe" step exists for. The claim was bound to pod-a by the previous
// reconcile, but the informer cache has not seen pod-a's new label yet. If the
// claim looked for its Pod in the cache it would find none and bind pod-b too.
// It must look on the API server, find pod-a, and leave pod-b alone.
func TestClaimDoesNotBindTwiceOnStaleCache(t *testing.T) {
	scheme := runtime.NewScheme()
	_ = clientgoscheme.AddToScheme(scheme)
	_ = takehomev1alpha1.AddToScheme(scheme)

	claim := &takehomev1alpha1.WorkerClaim{
		ObjectMeta: metav1.ObjectMeta{
			Name: "claim-a", Namespace: "ns", UID: types.UID("claim-uid"),
			Finalizers: []string{takehomev1alpha1.ClaimFinalizer},
		},
		Spec: takehomev1alpha1.WorkerClaimSpec{PoolName: "default"},
	}
	podA := makePod("pod-a", ready)
	// pod-b has been Ready longer, so it is the first bind candidate: a
	// reconciler that trusted the cache would pick it.
	podB := makePod("pod-b", readyAt(t0.Add(-time.Minute)))
	podAOnServer := makePod("pod-a", ready, func(p *corev1.Pod) {
		p.Labels[takehomev1alpha1.LabelClaim] = claim.Name
		p.Labels[takehomev1alpha1.LabelClaimUID] = string(claim.UID)
	})

	// "cache" is what the reconciler reads by default (and writes through);
	// "server" is what the API server really holds.
	cache := fake.NewClientBuilder().WithScheme(scheme).
		WithStatusSubresource(&takehomev1alpha1.WorkerClaim{}).
		WithObjects(claim.DeepCopy(), testPool.DeepCopy(), &podA, &podB).Build()
	server := fake.NewClientBuilder().WithScheme(scheme).
		WithObjects(claim.DeepCopy(), testPool.DeepCopy(), &podAOnServer, podB.DeepCopy()).Build()

	r := &WorkerClaimReconciler{
		Client: cache, APIReader: server, Scheme: scheme, Recorder: events.NewFakeRecorder(10),
	}
	if _, err := r.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Namespace: "ns", Name: "claim-a"},
	}); err != nil {
		t.Fatalf("Reconcile: %v", err)
	}

	var gotB corev1.Pod
	if err := cache.Get(context.Background(), client.ObjectKeyFromObject(&podB), &gotB); err != nil {
		t.Fatal(err)
	}
	if uid := gotB.Labels[takehomev1alpha1.LabelClaimUID]; uid != "" {
		t.Fatalf("pod-b was bound to %s: the claim now holds two Pods", uid)
	}
	var gotClaim takehomev1alpha1.WorkerClaim
	if err := cache.Get(context.Background(), client.ObjectKeyFromObject(claim), &gotClaim); err != nil {
		t.Fatal(err)
	}
	if gotClaim.Status.Phase != takehomev1alpha1.ClaimClaimed || gotClaim.Status.PodName != "pod-a" {
		t.Fatalf("status = %s/%s, want Claimed/pod-a", gotClaim.Status.Phase, gotClaim.Status.PodName)
	}
}
