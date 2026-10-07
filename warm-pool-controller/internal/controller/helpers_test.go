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
	"fmt"
	"sync/atomic"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/util/retry"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

// All helpers use k8sClient, which talks to the API server directly (no
// cache), so assertions see authoritative state.

const (
	// holdFinalizer keeps a deleted test Pod in Terminating. Without a
	// kubelet, envtest otherwise removes unscheduled Pods immediately.
	holdFinalizer = "test.takehome.replit.com/hold"
	// notReadyLabel stops markAllReady from making a Pod Ready.
	notReadyLabel = "test.takehome.replit.com/not-ready"
)

var podIPs atomic.Uint32

func newNamespace() string {
	ns := &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{GenerateName: "test-"}}
	Expect(k8sClient.Create(ctx, ns)).To(Succeed())
	return ns.Name
}

func newPool(ns, name string, replicas int32) {
	pool := &takehomev1alpha1.WorkerPool{
		ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: name},
		Spec: takehomev1alpha1.WorkerPoolSpec{
			Replicas: replicas,
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": "worker"}},
				Spec: corev1.PodSpec{Containers: []corev1.Container{{
					Name: "worker", Image: "nginx:alpine",
				}}},
			},
		},
	}
	Expect(k8sClient.Create(ctx, pool)).To(Succeed())
}

// setReplicas changes spec.replicas with a merge patch, which does not
// conflict with the controller's concurrent status writes.
func setReplicas(ns, name string, n int32) {
	pool := &takehomev1alpha1.WorkerPool{ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: name}}
	patch := []byte(fmt.Sprintf(`{"spec":{"replicas":%d}}`, n))
	Expect(k8sClient.Patch(ctx, pool, client.RawPatch(types.MergePatchType, patch))).To(Succeed())
}

func newClaim(ns, name, pool string) *takehomev1alpha1.WorkerClaim {
	claim := &takehomev1alpha1.WorkerClaim{
		ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: name},
		Spec:       takehomev1alpha1.WorkerClaimSpec{PoolName: pool},
	}
	Expect(k8sClient.Create(ctx, claim)).To(Succeed())
	return claim
}

func getClaim(ns, name string) *takehomev1alpha1.WorkerClaim {
	claim := &takehomev1alpha1.WorkerClaim{}
	Expect(k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: name}, claim)).To(Succeed())
	return claim
}

func getPool(ns, name string) *takehomev1alpha1.WorkerPool {
	pool := &takehomev1alpha1.WorkerPool{}
	Expect(k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: name}, pool)).To(Succeed())
	return pool
}

func listPods(ns string) []corev1.Pod {
	var list corev1.PodList
	Expect(k8sClient.List(ctx, &list, client.InNamespace(ns))).To(Succeed())
	return list.Items
}

// livePods are the namespace's Pods that are neither terminating nor terminal.
func livePods(ns string) []corev1.Pod {
	var out []corev1.Pod
	for _, p := range listPods(ns) {
		if isLive(&p) {
			out = append(out, p)
		}
	}
	return out
}

// podsLabelledFor returns the live Pods that carry the claim's UID.
func podsLabelledFor(claim *takehomev1alpha1.WorkerClaim) []corev1.Pod {
	var out []corev1.Pod
	for _, p := range livePods(claim.Namespace) {
		if p.Labels[takehomev1alpha1.LabelClaimUID] == string(claim.UID) {
			out = append(out, p)
		}
	}
	return out
}

func getPod(ns, name string) (*corev1.Pod, error) {
	pod := &corev1.Pod{}
	err := k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: name}, pod)
	return pod, err
}

func podGone(ns, name string) func() bool {
	return func() bool {
		_, err := getPod(ns, name)
		return apierrors.IsNotFound(err)
	}
}

// setPodStatus plays the kubelet: it rewrites a Pod's status.
func setPodStatus(ns, name string, mutate func(*corev1.PodStatus)) {
	err := retry.RetryOnConflict(retry.DefaultRetry, func() error {
		pod, err := getPod(ns, name)
		if err != nil {
			return err
		}
		mutate(&pod.Status)
		return k8sClient.Status().Update(ctx, pod)
	})
	Expect(client.IgnoreNotFound(err)).To(Succeed())
}

func markReady(ns, name string) {
	n := podIPs.Add(1)
	ip := fmt.Sprintf("10.244.%d.%d", (n>>8)&0xff, n&0xff)
	setPodStatus(ns, name, func(s *corev1.PodStatus) {
		s.Phase = corev1.PodRunning
		s.PodIP = ip
		s.PodIPs = []corev1.PodIP{{IP: ip}}
		s.Conditions = []corev1.PodCondition{{
			Type: corev1.PodReady, Status: corev1.ConditionTrue, LastTransitionTime: metav1.Now(),
		}}
	})
}

func markNotReady(ns, name string) {
	setPodStatus(ns, name, func(s *corev1.PodStatus) {
		s.Phase = corev1.PodRunning
		s.Conditions = []corev1.PodCondition{{
			Type: corev1.PodReady, Status: corev1.ConditionFalse, LastTransitionTime: metav1.Now(),
		}}
	})
}

func markPhase(ns, name string, phase corev1.PodPhase) {
	setPodStatus(ns, name, func(s *corev1.PodStatus) {
		s.Phase = phase
		s.Conditions = nil
	})
}

// markAllReady makes every live, not-yet-Ready Pod in the namespace Ready,
// except Pods labelled notReadyLabel. Calling it inside Eventually acts as a
// kubelet that boots each new Pod.
func markAllReady(ns string) {
	for _, p := range livePods(ns) {
		if !isPodReady(&p) && p.Labels[notReadyLabel] == "" {
			markReady(ns, p.Name)
		}
	}
}

// holdAndDelete deletes a Pod but keeps it in Terminating with a test finalizer.
func holdAndDelete(ns, name string) {
	Expect(retry.RetryOnConflict(retry.DefaultRetry, func() error {
		pod, err := getPod(ns, name)
		if err != nil {
			return err
		}
		controllerutil.AddFinalizer(pod, holdFinalizer)
		return k8sClient.Update(ctx, pod)
	})).To(Succeed())
	pod, err := getPod(ns, name)
	Expect(err).NotTo(HaveOccurred())
	Expect(k8sClient.Delete(ctx, pod)).To(Succeed())
}

func releaseHold(ns, name string) {
	Expect(client.IgnoreNotFound(retry.RetryOnConflict(retry.DefaultRetry, func() error {
		pod, err := getPod(ns, name)
		if err != nil {
			return err
		}
		controllerutil.RemoveFinalizer(pod, holdFinalizer)
		return k8sClient.Update(ctx, pod)
	}))).To(Succeed())
}

func deletePodNow(ns, name string) {
	pod, err := getPod(ns, name)
	Expect(err).NotTo(HaveOccurred())
	Expect(k8sClient.Delete(ctx, pod)).To(Succeed())
}

// waitWarm waits until the pool reports n warm Pods, booting Pods as it goes.
func waitWarm(ns, pool string, n int32) {
	GinkgoHelper()
	Eventually(func(g Gomega) {
		markAllReady(ns)
		g.Expect(getPool(ns, pool).Status.AvailableReplicas).To(Equal(n))
	}).Should(Succeed())
}

// waitPool waits until the pool reports warm warm Pods and claimed claimed
// Pods, booting Pods as it goes. Checking both counts matters: a status
// written before a claim took its Pod also reports the old warm count.
func waitPool(ns, pool string, warm, claimed int32) {
	GinkgoHelper()
	Eventually(func(g Gomega) {
		markAllReady(ns)
		s := getPool(ns, pool).Status
		g.Expect(s.AvailableReplicas).To(Equal(warm))
		g.Expect(s.ClaimedReplicas).To(Equal(claimed))
	}).Should(Succeed())
}

// waitClaimed waits until the claim is Claimed and returns it.
func waitClaimed(ns, name string) *takehomev1alpha1.WorkerClaim {
	GinkgoHelper()
	var claim *takehomev1alpha1.WorkerClaim
	Eventually(func(g Gomega) {
		claim = getClaim(ns, name)
		g.Expect(claim.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
	}).Should(Succeed())
	return claim
}

// checkInvariants asserts what must hold at every instant, not only
// eventually. It reads claims before Pods: a claim reports a Pod only after
// the Pod's label is written, so a later Pod read always sees that label.
//
//   - I1: no two claims report the same Pod.
//   - I2: no claim UID is on more than one live Pod.
//   - A claim's status never names a Pod labelled for a different claim.
func checkInvariants(g Gomega, ns string) {
	var claims takehomev1alpha1.WorkerClaimList
	g.Expect(k8sClient.List(ctx, &claims, client.InNamespace(ns))).To(Succeed())
	pods := listPods(ns)

	byName := map[string]*corev1.Pod{}
	liveByClaim := map[string][]string{}
	for i := range pods {
		p := &pods[i]
		byName[p.Name] = p
		if uid := p.Labels[takehomev1alpha1.LabelClaimUID]; uid != "" && isLive(p) {
			liveByClaim[uid] = append(liveByClaim[uid], p.Name)
		}
	}
	for uid, names := range liveByClaim {
		g.Expect(names).To(HaveLen(1), "claim UID %s is on several live Pods", uid)
	}
	reportedBy := map[string]string{}
	for _, c := range claims.Items {
		if c.Status.Phase != takehomev1alpha1.ClaimClaimed {
			continue
		}
		g.Expect(reportedBy).NotTo(HaveKey(c.Status.PodName),
			"Pod %s is reported by claims %s and %s", c.Status.PodName, reportedBy[c.Status.PodName], c.Name)
		reportedBy[c.Status.PodName] = c.Name
		if p, ok := byName[c.Status.PodName]; ok {
			g.Expect(p.Labels[takehomev1alpha1.LabelClaimUID]).To(Equal(string(c.UID)),
				"claim %s reports Pod %s, which is labelled for another claim", c.Name, p.Name)
		}
	}
}

func invariantsHold(ns string) func(Gomega) {
	return func(g Gomega) { checkInvariants(g, ns) }
}
