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
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/events"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

const (
	// pendingRequeue is a safety net for Pending claims; normally the Pod
	// watch wakes them as soon as a Pod in their pool turns Ready.
	pendingRequeue = 5 * time.Second
	// poolNotFoundRequeue re-checks a claim whose pool does not exist yet.
	poolNotFoundRequeue = 10 * time.Second
	// conflictRequeue retries quickly when every bind attempt lost a race:
	// the cache was stale, the pool is not empty.
	conflictRequeue = 200 * time.Millisecond
)

// WorkerClaimReconciler assigns one warm Pod to each WorkerClaim.
type WorkerClaimReconciler struct {
	client.Client
	// APIReader reads straight from the API server. The claim uses it to find
	// the Pods already labelled with its UID: a cached read can miss a label
	// written by the previous reconcile, and the claim would bind a second Pod.
	APIReader client.Reader
	Scheme    *runtime.Scheme
	Recorder  events.EventRecorder
	// MaxConcurrentReconciles > 1 lets different claims race for the same
	// Pod. Correctness does not depend on it being 1; the conditional bind
	// write decides every race.
	MaxConcurrentReconciles int
}

// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerclaims,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerclaims/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerclaims/finalizers,verbs=update
// +kubebuilder:rbac:groups=takehome.replit.com,resources=workerpools,verbs=get;list;watch
// +kubebuilder:rbac:groups="",resources=pods,verbs=get;list;watch;update;patch;delete
// +kubebuilder:rbac:groups=events.k8s.io,resources=events,verbs=create;patch

// Reconcile observes before it binds: it first looks for a Pod that already
// carries the claim's UID, and only binds a new Pod if there is none.
func (r *WorkerClaimReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	claim := &takehomev1alpha1.WorkerClaim{}
	if err := r.Get(ctx, req.NamespacedName, claim); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	if claim.DeletionTimestamp != nil {
		return ctrl.Result{}, r.release(ctx, claim)
	}

	// The finalizer goes on in its own write, before any Pod is bound, so a
	// bound Pod can never outlive a claim that was deleted without it.
	if !controllerutil.ContainsFinalizer(claim, takehomev1alpha1.ClaimFinalizer) {
		controllerutil.AddFinalizer(claim, takehomev1alpha1.ClaimFinalizer)
		if err := r.Update(ctx, claim); err != nil {
			if apierrors.IsConflict(err) {
				return ctrl.Result{RequeueAfter: conflictRequeue}, nil
			}
			return ctrl.Result{}, client.IgnoreNotFound(err)
		}
	}

	// Step 1: observe. Which Pods already carry this claim's UID?
	bound, err := r.boundPods(ctx, claim)
	if err != nil {
		return ctrl.Result{}, err
	}
	var live []*corev1.Pod
	for _, pod := range bound {
		switch {
		case pod.DeletionTimestamp != nil:
			// Going away; it still carries the label but no longer counts.
		case isTerminal(pod):
			// The sandbox exited. It is consumed, so delete it.
			if err := r.deletePod(ctx, pod); err != nil {
				return ctrl.Result{}, err
			}
		default:
			live = append(live, pod)
		}
	}
	if len(live) > 0 {
		keep := keeperPod(live, claim.Status.PodName)
		// I2 repair: one controller never binds twice, but two active
		// controllers can each bind a Pod to this claim. Keep one, delete the rest.
		for _, pod := range live {
			if pod == keep {
				continue
			}
			if err := r.deletePod(ctx, pod); err != nil {
				return ctrl.Result{}, err
			}
			r.Recorder.Eventf(claim, pod, corev1.EventTypeWarning, "DuplicateAssignment", "Delete",
				"Deleted extra Pod %s; keeping %s", pod.Name, keep.Name)
		}
		return r.setClaimed(ctx, claim, keep)
	}

	// No live Pod. If the status still names one, that Pod was lost.
	if claim.Status.PodName != "" {
		r.Recorder.Eventf(claim, nil, corev1.EventTypeWarning, takehomev1alpha1.ReasonAssignedPodLost, "Reassign",
			"Pod %s was deleted or failed; looking for another warm Pod", claim.Status.PodName)
	}

	// Step 2: bind.
	pool := &takehomev1alpha1.WorkerPool{}
	if err := r.Get(ctx, types.NamespacedName{Namespace: claim.Namespace, Name: claim.Spec.PoolName}, pool); err != nil {
		if !apierrors.IsNotFound(err) {
			return ctrl.Result{}, err
		}
		pool = nil
	}
	if pool == nil {
		return r.setPending(ctx, claim, takehomev1alpha1.ReasonPoolNotFound,
			fmt.Sprintf("WorkerPool %q does not exist in namespace %q", claim.Spec.PoolName, claim.Namespace),
			poolNotFoundRequeue)
	}
	if pool.DeletionTimestamp != nil {
		return r.setPending(ctx, claim, takehomev1alpha1.ReasonPoolNotFound,
			fmt.Sprintf("WorkerPool %q is being deleted", pool.Name), poolNotFoundRequeue)
	}

	// Candidates come from the cache. A stale entry is safe: the bind is a
	// conditional write, so a Pod that changed since the cache saw it is
	// rejected with 409 rather than double-assigned.
	var list corev1.PodList
	if err := r.List(ctx, &list, client.InNamespace(pool.Namespace),
		client.MatchingLabels{takehomev1alpha1.LabelPool: pool.Name}); err != nil {
		return ctrl.Result{}, err
	}
	lostRaces := 0
	for _, candidate := range bindCandidates(pool, list.Items) {
		pod, err := r.bind(ctx, claim, candidate)
		switch {
		case err == nil:
			r.Recorder.Eventf(claim, pod, corev1.EventTypeNormal, takehomev1alpha1.ReasonAssigned, "Assign",
				"Assigned Pod %s from pool %s", pod.Name, pool.Name)
			return r.setClaimed(ctx, claim, pod)
		case apierrors.IsConflict(err) || apierrors.IsNotFound(err):
			// Another claim took this Pod, or it changed or vanished since the
			// cache saw it. Try the next one.
			lostRaces++
		default:
			return ctrl.Result{}, err
		}
	}
	if lostRaces > 0 {
		return ctrl.Result{RequeueAfter: conflictRequeue}, nil
	}

	if claim.Status.Attempts > 0 {
		return r.setPending(ctx, claim, takehomev1alpha1.ReasonAssignedPodLost,
			fmt.Sprintf("The assigned Pod was lost (%d assigned so far); pool %q has no ready, unclaimed Pods",
				claim.Status.Attempts, pool.Name),
			pendingRequeue)
	}
	return r.setPending(ctx, claim, takehomev1alpha1.ReasonNoWarmPodsAvailable,
		fmt.Sprintf("Pool %q has no ready, unclaimed Pods", pool.Name), pendingRequeue)
}

// bind labels the Pod with the claim. This one write is the assignment.
// Update sends the resourceVersion the Pod had when we read it, so the API
// server applies it only if nobody changed the Pod since; the loser of a race
// gets 409 Conflict. A plain merge patch would be last-writer-wins and two
// claims could both believe they own the Pod.
func (r *WorkerClaimReconciler) bind(ctx context.Context, claim *takehomev1alpha1.WorkerClaim,
	candidate *corev1.Pod) (*corev1.Pod, error) {
	pod := candidate.DeepCopy()
	if pod.Labels == nil {
		pod.Labels = map[string]string{}
	}
	if pod.Annotations == nil {
		pod.Annotations = map[string]string{}
	}
	pod.Labels[takehomev1alpha1.LabelClaim] = claim.Name
	pod.Labels[takehomev1alpha1.LabelClaimUID] = string(claim.UID)
	pod.Annotations[takehomev1alpha1.AnnotationClaimedAt] = time.Now().UTC().Format(time.RFC3339)
	if err := r.Update(ctx, pod); err != nil {
		return nil, err
	}
	return pod, nil
}

// release runs when the claim is being deleted: the claim's Pod is consumed,
// so it is deleted rather than returned to the pool. The pool refills.
func (r *WorkerClaimReconciler) release(ctx context.Context, claim *takehomev1alpha1.WorkerClaim) error {
	if !controllerutil.ContainsFinalizer(claim, takehomev1alpha1.ClaimFinalizer) {
		return nil
	}
	bound, err := r.boundPods(ctx, claim)
	if err != nil {
		return err
	}
	for _, pod := range bound {
		if pod.DeletionTimestamp != nil {
			continue
		}
		if err := r.deletePod(ctx, pod); err != nil {
			return err
		}
		r.Recorder.Eventf(claim, pod, corev1.EventTypeNormal, "Released", "Delete",
			"Deleted Pod %s because the claim is being deleted", pod.Name)
	}
	// Removing the finalizer is the last write. If the process dies before
	// it, the next reconcile repeats the (idempotent) deletes above.
	controllerutil.RemoveFinalizer(claim, takehomev1alpha1.ClaimFinalizer)
	return client.IgnoreNotFound(r.Update(ctx, claim))
}

// boundPods lists, from the API server, every Pod labelled with the claim's UID.
func (r *WorkerClaimReconciler) boundPods(ctx context.Context, claim *takehomev1alpha1.WorkerClaim) ([]*corev1.Pod, error) {
	var list corev1.PodList
	if err := r.APIReader.List(ctx, &list, client.InNamespace(claim.Namespace),
		client.MatchingLabels{takehomev1alpha1.LabelClaimUID: string(claim.UID)}); err != nil {
		return nil, err
	}
	out := make([]*corev1.Pod, len(list.Items))
	for i := range list.Items {
		out[i] = &list.Items[i]
	}
	return out, nil
}

func (r *WorkerClaimReconciler) deletePod(ctx context.Context, pod *corev1.Pod) error {
	return client.IgnoreNotFound(r.Delete(ctx, pod, client.Preconditions{UID: &pod.UID}))
}

// setClaimed projects the bound Pod into the claim's status. attempts goes up
// whenever the reported Pod changes, which also counts correctly when the
// process died between binding a Pod and writing this status.
func (r *WorkerClaimReconciler) setClaimed(ctx context.Context, claim *takehomev1alpha1.WorkerClaim,
	pod *corev1.Pod) (ctrl.Result, error) {
	status := claim.Status
	if status.PodName != pod.Name {
		status.Attempts++
	}
	status.Phase = takehomev1alpha1.ClaimClaimed
	status.PodName = pod.Name
	status.PodIP = pod.Status.PodIP
	status.Reason = takehomev1alpha1.ReasonAssigned
	status.Message = fmt.Sprintf("Assigned Pod %s from pool %s", pod.Name, claim.Spec.PoolName)
	status.AssignedAt = nil
	if t, err := time.Parse(time.RFC3339, pod.Annotations[takehomev1alpha1.AnnotationClaimedAt]); err == nil {
		at := metav1.NewTime(t)
		status.AssignedAt = &at
	}
	return r.writeStatus(ctx, claim, status, 0)
}

func (r *WorkerClaimReconciler) setPending(ctx context.Context, claim *takehomev1alpha1.WorkerClaim,
	reason, message string, requeue time.Duration) (ctrl.Result, error) {
	status := claim.Status
	status.Phase = takehomev1alpha1.ClaimPending
	status.PodName = ""
	status.PodIP = ""
	status.AssignedAt = nil
	status.Reason = reason
	status.Message = message
	return r.writeStatus(ctx, claim, status, requeue)
}

// writeStatus writes only when something changed, so a reconcile that finds
// nothing new is a no-op and the claim's own status events do not loop.
func (r *WorkerClaimReconciler) writeStatus(ctx context.Context, claim *takehomev1alpha1.WorkerClaim,
	status takehomev1alpha1.WorkerClaimStatus, requeue time.Duration) (ctrl.Result, error) {
	if equality.Semantic.DeepEqual(claim.Status, status) {
		return ctrl.Result{RequeueAfter: requeue}, nil
	}
	claim.Status = status
	if err := r.Status().Update(ctx, claim); err != nil {
		if apierrors.IsConflict(err) {
			// The claim changed under us; recompute from fresh state.
			return ctrl.Result{RequeueAfter: conflictRequeue}, nil
		}
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	logf.FromContext(ctx).V(1).Info("claim status", "phase", status.Phase, "pod", status.PodName, "reason", status.Reason)
	return ctrl.Result{RequeueAfter: requeue}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *WorkerClaimReconciler) SetupWithManager(mgr ctrl.Manager) error {
	workers := max(r.MaxConcurrentReconciles, 1)
	return ctrl.NewControllerManagedBy(mgr).
		For(&takehomev1alpha1.WorkerClaim{}).
		Watches(&corev1.Pod{}, handler.EnqueueRequestsFromMapFunc(r.podToClaims)).
		WithOptions(controller.Options{MaxConcurrentReconciles: workers}).
		Named("workerclaim").
		Complete(r)
}

// podToClaims routes Pod events to claims. A claimed Pod wakes its claim
// (so a deleted or failed Pod is noticed). An unclaimed Pod that is warm
// wakes every claim of its pool that is still waiting.
func (r *WorkerClaimReconciler) podToClaims(ctx context.Context, obj client.Object) []reconcile.Request {
	pod, ok := obj.(*corev1.Pod)
	if !ok {
		return nil
	}
	if name := pod.Labels[takehomev1alpha1.LabelClaim]; name != "" {
		return []reconcile.Request{{NamespacedName: types.NamespacedName{Namespace: pod.Namespace, Name: name}}}
	}
	poolName := pod.Labels[takehomev1alpha1.LabelPool]
	if poolName == "" || !isWarm(pod) {
		return nil
	}
	var claims takehomev1alpha1.WorkerClaimList
	if err := r.List(ctx, &claims, client.InNamespace(pod.Namespace)); err != nil {
		logf.FromContext(ctx).Error(err, "listing claims for Pod event", "pod", pod.Name)
		return nil
	}
	var reqs []reconcile.Request
	for i := range claims.Items {
		c := &claims.Items[i]
		if c.Spec.PoolName == poolName && c.Status.Phase != takehomev1alpha1.ClaimClaimed && c.DeletionTimestamp == nil {
			reqs = append(reqs, reconcile.Request{NamespacedName: types.NamespacedName{Namespace: c.Namespace, Name: c.Name}})
		}
	}
	return reqs
}
