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
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

var _ = Describe("WorkerPool", func() {
	var ns string

	BeforeEach(func() {
		ns = newNamespace()
		DeferCleanup(startManager(4))
	})

	It("creates exactly spec.replicas Pods and reports them warm once Ready", func() {
		newPool(ns, "default", 3)

		By("creating three Pods, and no more while they boot")
		Eventually(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(3))
		Consistently(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(3))
		Eventually(func(g Gomega) {
			s := getPool(ns, "default").Status
			g.Expect(s.PendingReplicas).To(Equal(int32(3)))
			g.Expect(s.AvailableReplicas).To(BeZero())
		}).Should(Succeed())

		By("reporting them warm once the kubelet marks them Ready")
		for _, p := range livePods(ns) {
			Expect(p.Labels).To(HaveKeyWithValue(takehomev1alpha1.LabelPool, "default"))
			Expect(p.Labels).To(HaveKeyWithValue("app", "worker"))
			Expect(metav1.GetControllerOf(&p).Name).To(Equal("default"))
			markReady(ns, p.Name)
		}
		Eventually(func(g Gomega) {
			pool := getPool(ns, "default")
			g.Expect(pool.Status).To(Equal(takehomev1alpha1.WorkerPoolStatus{
				ObservedGeneration: pool.Generation,
				Replicas:           3, ReadyReplicas: 3, AvailableReplicas: 3,
			}))
		}).Should(Succeed())
		Consistently(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(3))
	})

	It("does not count terminating, failed, succeeded, not-ready or foreign Pods as warm", func() {
		newPool(ns, "default", 3)
		waitWarm(ns, "default", 3)
		pods := livePods(ns)

		By("injecting one failure of each kind")
		markPhase(ns, pods[0].Name, corev1.PodFailed)
		markPhase(ns, pods[1].Name, corev1.PodSucceeded)
		holdAndDelete(ns, pods[2].Name)
		DeferCleanup(releaseHold, ns, pods[2].Name)

		foreign := &corev1.Pod{
			ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: "foreign",
				Labels: map[string]string{takehomev1alpha1.LabelPool: "default"}},
			Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "c", Image: "nginx:alpine"}}},
		}
		Expect(k8sClient.Create(ctx, foreign)).To(Succeed())
		markReady(ns, "foreign")

		By("deleting the terminal Pods and replacing all three")
		Eventually(podGone(ns, pods[0].Name)).Should(BeTrue())
		Eventually(podGone(ns, pods[1].Name)).Should(BeTrue())
		Eventually(func(g Gomega) {
			markAllReady(ns)
			s := getPool(ns, "default").Status
			g.Expect(s.AvailableReplicas).To(Equal(int32(3)))
			g.Expect(s.Replicas).To(Equal(int32(3)), "the terminating Pod is not counted")
		}).Should(Succeed())

		By("counting a Pod that stops being Ready as pending, not warm")
		var owned []corev1.Pod
		for _, p := range livePods(ns) {
			if metav1.IsControlledBy(&p, getPool(ns, "default")) {
				owned = append(owned, p)
			}
		}
		Expect(owned).To(HaveLen(3))
		flaky := owned[0].Name
		Expect(k8sClient.Patch(ctx, &owned[0], client.RawPatch("application/merge-patch+json",
			[]byte(`{"metadata":{"labels":{"`+notReadyLabel+`":"true"}}}`)))).To(Succeed())
		markNotReady(ns, flaky)
		Eventually(func(g Gomega) {
			s := getPool(ns, "default").Status
			g.Expect(s.AvailableReplicas).To(Equal(int32(2)))
			g.Expect(s.PendingReplicas).To(Equal(int32(1)))
		}).Should(Succeed())
		Consistently(func() int32 { return getPool(ns, "default").Status.Replicas }).Should(Equal(int32(3)),
			"a not-ready Pod still counts toward the target, so no extra Pod is created")

		By("never touching the foreign Pod")
		_, err := getPod(ns, "foreign")
		Expect(err).NotTo(HaveOccurred())
	})

	It("scales down only unclaimed Pods", func() {
		newPool(ns, "default", 3)
		waitWarm(ns, "default", 3)
		newClaim(ns, "claim-a", "default")
		claimed := waitClaimed(ns, "claim-a").Status.PodName
		waitPool(ns, "default", 3, 1)
		Expect(livePods(ns)).To(HaveLen(4))

		setReplicas(ns, "default", 1)
		Eventually(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(2))

		setReplicas(ns, "default", 0)
		Eventually(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(1))
		Consistently(func() string { return livePods(ns)[0].Name }).Should(Equal(claimed))
		Eventually(func(g Gomega) {
			s := getPool(ns, "default").Status
			g.Expect(s.ClaimedReplicas).To(Equal(int32(1)))
			g.Expect(s.AvailableReplicas).To(BeZero())
		}).Should(Succeed())
		Expect(getClaim(ns, "claim-a").Status.PodName).To(Equal(claimed))
	})
})

var _ = Describe("API validation", func() {
	var ns string
	BeforeEach(func() { ns = newNamespace() })

	It("rejects negative replicas", func() {
		pool := &takehomev1alpha1.WorkerPool{
			ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: "bad"},
			Spec: takehomev1alpha1.WorkerPoolSpec{Replicas: -1, Template: corev1.PodTemplateSpec{
				Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "c", Image: "nginx"}}},
			}},
		}
		Expect(k8sClient.Create(ctx, pool)).To(MatchError(ContainSubstring("spec.replicas")))
	})

	It("rejects names that do not fit in a label value", func() {
		long := "a123456789b123456789c123456789d123456789e123456789f123456789g1234"
		Expect(k8sClient.Create(ctx, &takehomev1alpha1.WorkerClaim{
			ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: long},
			Spec:       takehomev1alpha1.WorkerClaimSpec{PoolName: "default"},
		})).To(MatchError(ContainSubstring("at most 63 characters")))
	})

	It("makes poolName immutable", func() {
		claim := newClaim(ns, "claim-a", "default")
		claim.Spec.PoolName = "other"
		Expect(k8sClient.Update(ctx, claim)).To(MatchError(ContainSubstring("poolName is immutable")))
	})

	It("requires a poolName", func() {
		Expect(k8sClient.Create(ctx, &takehomev1alpha1.WorkerClaim{
			ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: "claim-b"},
		})).NotTo(Succeed())
	})
})
