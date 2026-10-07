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
	"cmp"
	"slices"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

// podClass is how both reconcilers see a Pod. The order of the checks in
// classifyPod matters: a terminating Pod is terminating even if it is claimed.
type podClass int

const (
	// podTerminating has a deletionTimestamp. Ignored everywhere.
	podTerminating podClass = iota
	// podTerminal is Failed or Succeeded and will never be Ready again.
	podTerminal
	// podClaimed carries a claim UID label.
	podClaimed
	// podWarm is Running, Ready and unclaimed: the capacity spec.replicas asks for.
	podWarm
	// podStarting is unclaimed and not Ready yet (Pending, or Running but not Ready).
	podStarting
)

func (c podClass) String() string {
	return [...]string{"terminating", "terminal", "claimed", "warm", "starting"}[c]
}

func classifyPod(pod *corev1.Pod) podClass {
	switch {
	case pod.DeletionTimestamp != nil:
		return podTerminating
	case isTerminal(pod):
		return podTerminal
	case pod.Labels[takehomev1alpha1.LabelClaimUID] != "":
		return podClaimed
	case isPodReady(pod):
		return podWarm
	default:
		return podStarting
	}
}

func isTerminal(pod *corev1.Pod) bool {
	return pod.Status.Phase == corev1.PodFailed || pod.Status.Phase == corev1.PodSucceeded
}

// isPodReady is true for a Running Pod whose Ready condition is True.
func isPodReady(pod *corev1.Pod) bool {
	if pod.Status.Phase != corev1.PodRunning {
		return false
	}
	return readyCondition(pod) != nil
}

// readyCondition returns the Pod's Ready condition if it is True.
func readyCondition(pod *corev1.Pod) *corev1.PodCondition {
	for i := range pod.Status.Conditions {
		c := &pod.Status.Conditions[i]
		if c.Type == corev1.PodReady && c.Status == corev1.ConditionTrue {
			return c
		}
	}
	return nil
}

// isLive is true for a Pod that is neither terminating nor terminal.
func isLive(pod *corev1.Pod) bool {
	return pod.DeletionTimestamp == nil && !isTerminal(pod)
}

// isWarm is true for a Pod a claim may take: Running, Ready, unclaimed and not terminating.
func isWarm(pod *corev1.Pod) bool {
	return classifyPod(pod) == podWarm
}

// poolPods is one pool's Pods, grouped by class. Only Pods controlled by the
// pool (ownerReference with the pool's UID) are included.
type poolPods struct {
	warm     []*corev1.Pod
	starting []*corev1.Pod
	// claimed holds live claimed Pods; claimedReady is how many of them are Ready.
	claimed      []*corev1.Pod
	claimedReady int
	// terminalUnclaimed are Failed/Succeeded Pods with no claim. The pool deletes them.
	// Terminal claimed Pods are left to the claim reconciler, which counts the loss.
	terminalUnclaimed []*corev1.Pod
	// withClaimLabel holds every non-terminating Pod with a claim UID label, live
	// or terminal, for the orphan check.
	withClaimLabel []*corev1.Pod
}

func groupPoolPods(pool *takehomev1alpha1.WorkerPool, pods []corev1.Pod) poolPods {
	var g poolPods
	for i := range pods {
		pod := &pods[i]
		if !metav1.IsControlledBy(pod, pool) {
			continue
		}
		claimed := pod.Labels[takehomev1alpha1.LabelClaimUID] != ""
		if claimed && pod.DeletionTimestamp == nil {
			g.withClaimLabel = append(g.withClaimLabel, pod)
		}
		switch classifyPod(pod) {
		case podTerminating:
		case podTerminal:
			if !claimed {
				g.terminalUnclaimed = append(g.terminalUnclaimed, pod)
			}
		case podClaimed:
			g.claimed = append(g.claimed, pod)
			if isPodReady(pod) {
				g.claimedReady++
			}
		case podWarm:
			g.warm = append(g.warm, pod)
		case podStarting:
			g.starting = append(g.starting, pod)
		}
	}
	return g
}

// scaleDelta is how many Pods to create (>0) or delete (<0). Starting Pods
// count toward the target so the pool does not keep creating Pods while the
// first batch boots; only warm Pods count toward status.availableReplicas.
func scaleDelta(want int32, g poolPods) int {
	return int(want) - (len(g.warm) + len(g.starting))
}

// scaleDownVictims picks n unclaimed Pods to delete: not-Ready Pods first,
// then the youngest. Claimed Pods are never candidates.
func scaleDownVictims(g poolPods, n int) []*corev1.Pod {
	candidates := make([]*corev1.Pod, 0, len(g.starting)+len(g.warm))
	candidates = append(candidates, youngestFirst(g.starting)...)
	candidates = append(candidates, youngestFirst(g.warm)...)
	if n > len(candidates) {
		n = len(candidates)
	}
	return candidates[:n]
}

func youngestFirst(pods []*corev1.Pod) []*corev1.Pod {
	out := slices.Clone(pods)
	slices.SortStableFunc(out, func(a, b *corev1.Pod) int {
		if c := b.CreationTimestamp.Compare(a.CreationTimestamp.Time); c != 0 {
			return c
		}
		return cmp.Compare(a.Name, b.Name)
	})
	return out
}

// bindCandidates returns the pool's warm Pods, longest-Ready first, so a claim
// gets the Pod that has been waiting the longest. Ties break by name so the
// order is deterministic.
func bindCandidates(pool *takehomev1alpha1.WorkerPool, pods []corev1.Pod) []*corev1.Pod {
	var out []*corev1.Pod
	for i := range pods {
		pod := &pods[i]
		if metav1.IsControlledBy(pod, pool) && isWarm(pod) {
			out = append(out, pod)
		}
	}
	slices.SortStableFunc(out, func(a, b *corev1.Pod) int {
		if c := readySince(a).Compare(readySince(b)); c != 0 {
			return c
		}
		return cmp.Compare(a.Name, b.Name)
	})
	return out
}

func readySince(pod *corev1.Pod) time.Time {
	if c := readyCondition(pod); c != nil {
		return c.LastTransitionTime.Time
	}
	return time.Time{}
}

// keeperPod chooses which Pod a claim keeps if more than one live Pod carries
// its UID (which the design prevents, but the code does not assume): the one
// the claim's status already reports, otherwise the earliest assigned.
func keeperPod(live []*corev1.Pod, reported string) *corev1.Pod {
	for _, pod := range live {
		if pod.Name == reported {
			return pod
		}
	}
	keep := live[0]
	for _, pod := range live[1:] {
		a, b := claimedAt(pod), claimedAt(keep)
		if a.Before(b) || (a.Equal(b) && pod.Name < keep.Name) {
			keep = pod
		}
	}
	return keep
}

// claimedAt parses the claimed-at annotation; a Pod without one sorts last.
func claimedAt(pod *corev1.Pod) time.Time {
	t, err := time.Parse(time.RFC3339, pod.Annotations[takehomev1alpha1.AnnotationClaimedAt])
	if err != nil {
		return time.Unix(1<<62, 0)
	}
	return t
}

// podForPool builds a new Pod from the pool's template. Reserved labels and
// annotations are dropped from the template so the template cannot create a
// Pod that looks claimed; the pool label is always set.
func podForPool(pool *takehomev1alpha1.WorkerPool) *corev1.Pod {
	tmpl := pool.Spec.Template.DeepCopy()
	labels := withoutReserved(tmpl.Labels)
	labels[takehomev1alpha1.LabelPool] = pool.Name
	return &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			GenerateName: pool.Name + "-",
			Namespace:    pool.Namespace,
			Labels:       labels,
			Annotations:  withoutReserved(tmpl.Annotations),
		},
		Spec: tmpl.Spec,
	}
}

func withoutReserved(in map[string]string) map[string]string {
	out := make(map[string]string, len(in)+1)
	for k, v := range in {
		if !strings.HasPrefix(k, takehomev1alpha1.ReservedPrefix) {
			out[k] = v
		}
	}
	return out
}
