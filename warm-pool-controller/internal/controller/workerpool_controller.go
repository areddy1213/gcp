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
	"fmt"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/events"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/event"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/predicate"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

// WorkerPoolReconciler keeps spec.replicas warm Pods per WorkerPool.
type WorkerPoolReconciler struct {
	client.Client
	// APIReader reads straight from the API server, bypassing the informer
	// cache. The pool lists its Pods with it so the create decision is made on
	// authoritative state: a cached list can miss Pods created a moment ago and
	// the pool would create them again.
	APIReader client.Reader
	Scheme    *runtime.Scheme
	Recorder  events.EventRecorder
}

// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerpools,verbs=get;list;watch
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerpools/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerpools/finalizers,verbs=update
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerclaims,verbs=get;list;watch
// +kubebuilder:rbac:groups="",resources=pods,verbs=get;list;watch;create;delete
// +kubebuilder:rbac:groups=events.k8s.io,resources=events,verbs=create;patch

// Reconcile recomputes everything from a fresh list of the pool's Pods. It
// keeps no state between runs, so a restart loses nothing.
func (r *WorkerPoolReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := logf.FromContext(ctx)

	pool := &takehomev1alpha1.WorkerPool{}
	if err := r.Get(ctx, req.NamespacedName, pool); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	if pool.DeletionTimestamp != nil {
		// The garbage collector deletes the Pods through their ownerReference.
		return ctrl.Result{}, nil
	}

	var list corev1.PodList
	if err := r.APIReader.List(ctx, &list, client.InNamespace(pool.Namespace),
		client.MatchingLabels{takehomev1alpha1.LabelPool: pool.Name}); err != nil {
		return ctrl.Result{}, err
	}
	g := groupPoolPods(pool, list.Items)

	// I4: a claimed Pod whose claim no longer exists is an orphan. This only
	// happens when the claim's finalizer was removed by hand.
	for _, pod := range g.withClaimLabel {
		orphan, err := r.isOrphan(ctx, pod)
		if err != nil {
			return ctrl.Result{}, err
		}
		if orphan {
			if err := r.deletePod(ctx, pod, false); err != nil {
				return ctrl.Result{}, err
			}
			log.Info("deleted orphaned Pod", "pod", pod.Name, "claim", pod.Labels[takehomev1alpha1.LabelClaim])
			r.Recorder.Eventf(pool, pod, corev1.EventTypeNormal, "OrphanPodDeleted", "Delete",
				"Deleted Pod %s: its claim %s no longer exists", pod.Name, pod.Labels[takehomev1alpha1.LabelClaim])
		}
	}

	// Failed or Succeeded unclaimed Pods will never be warm again.
	for _, pod := range g.terminalUnclaimed {
		if err := r.deletePod(ctx, pod, false); err != nil {
			return ctrl.Result{}, err
		}
	}

	delta := scaleDelta(pool.Spec.Replicas, g)
	switch {
	case delta > 0:
		for range delta {
			pod := podForPool(pool)
			if err := controllerutil.SetControllerReference(pool, pod, r.Scheme); err != nil {
				return ctrl.Result{}, err
			}
			if err := r.Create(ctx, pod); err != nil {
				return ctrl.Result{}, fmt.Errorf("creating Pod: %w", err)
			}
		}
		r.Recorder.Eventf(pool, nil, corev1.EventTypeNormal, "ScaledUp", "Create",
			"Created %d Pod(s): %d warm, %d starting, want %d warm", delta, len(g.warm), len(g.starting), pool.Spec.Replicas)
	case delta < 0:
		deleted := 0
		for _, pod := range scaleDownVictims(g, -delta) {
			// I5: delete only if the Pod is unchanged since we listed it. If a
			// claim labelled it in the meantime, the API server rejects the
			// delete with 409 and the claimed Pod survives.
			if err := r.deletePod(ctx, pod, true); err != nil {
				if apierrors.IsConflict(err) {
					continue
				}
				return ctrl.Result{}, err
			}
			deleted++
		}
		if deleted > 0 {
			r.Recorder.Eventf(pool, nil, corev1.EventTypeNormal, "ScaledDown", "Delete",
				"Deleted %d unclaimed Pod(s), want %d warm", deleted, pool.Spec.Replicas)
		}
	}

	// Status describes what this reconcile observed. Pods created or deleted
	// above show up in the next reconcile, which their events trigger.
	status := takehomev1alpha1.WorkerPoolStatus{
		ObservedGeneration: pool.Generation,
		Replicas:           int32(len(g.warm) + len(g.starting) + len(g.claimed)),
		ReadyReplicas:      int32(len(g.warm) + g.claimedReady),
		AvailableReplicas:  int32(len(g.warm)),
		ClaimedReplicas:    int32(len(g.claimed)),
		PendingReplicas:    int32(len(g.starting)),
	}
	if !equality.Semantic.DeepEqual(pool.Status, status) {
		patch := client.MergeFrom(pool.DeepCopy())
		pool.Status = status
		if err := r.Status().Patch(ctx, pool, patch); err != nil {
			return ctrl.Result{}, client.IgnoreNotFound(err)
		}
	}
	return ctrl.Result{}, nil
}

// isOrphan reports whether the claim named on a Pod is gone. It reads the
// claim from the API server, not the cache, and compares UIDs: a claim
// recreated under the same name is a different claim.
func (r *WorkerPoolReconciler) isOrphan(ctx context.Context, pod *corev1.Pod) (bool, error) {
	claim := &takehomev1alpha1.WorkerClaim{}
	key := types.NamespacedName{Namespace: pod.Namespace, Name: pod.Labels[takehomev1alpha1.LabelClaim]}
	if key.Name == "" {
		return true, nil
	}
	if err := r.APIReader.Get(ctx, key, claim); err != nil {
		if apierrors.IsNotFound(err) {
			return true, nil
		}
		return false, err
	}
	return string(claim.UID) != pod.Labels[takehomev1alpha1.LabelClaimUID], nil
}

// deletePod deletes a Pod by UID, and also by resourceVersion when
// ifUnchanged is set. NotFound is success.
func (r *WorkerPoolReconciler) deletePod(ctx context.Context, pod *corev1.Pod, ifUnchanged bool) error {
	pre := client.Preconditions{UID: &pod.UID}
	if ifUnchanged {
		pre.ResourceVersion = &pod.ResourceVersion
	}
	return client.IgnoreNotFound(r.Delete(ctx, pod, pre))
}

// SetupWithManager sets up the controller with the Manager.
func (r *WorkerPoolReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		// Spec changes only; the pool's own status writes do not retrigger it.
		For(&takehomev1alpha1.WorkerPool{}, builder.WithPredicates(predicate.GenerationChangedPredicate{})).
		// Any change to a Pod the pool controls (created, Ready, claimed, deleted).
		Owns(&corev1.Pod{}).
		// A deleted claim may leave an orphaned Pod behind if its finalizer was
		// removed by hand; re-check the claim's pool.
		Watches(&takehomev1alpha1.WorkerClaim{}, handler.EnqueueRequestsFromMapFunc(claimToPool),
			builder.WithPredicates(predicate.Funcs{
				CreateFunc:  func(event.CreateEvent) bool { return false },
				UpdateFunc:  func(event.UpdateEvent) bool { return false },
				GenericFunc: func(event.GenericEvent) bool { return false },
			})).
		Named("workerpool").
		Complete(r)
}

func claimToPool(_ context.Context, obj client.Object) []reconcile.Request {
	claim, ok := obj.(*takehomev1alpha1.WorkerClaim)
	if !ok {
		return nil
	}
	return []reconcile.Request{{NamespacedName: types.NamespacedName{
		Namespace: claim.Namespace, Name: claim.Spec.PoolName,
	}}}
}
