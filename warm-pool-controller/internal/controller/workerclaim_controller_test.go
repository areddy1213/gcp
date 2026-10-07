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

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"sigs.k8s.io/controller-runtime/pkg/client"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

var _ = Describe("WorkerClaim", func() {
	var ns string

	BeforeEach(func() {
		ns = newNamespace()
		// Ten claim workers: claims really do race for the same Pods.
		DeferCleanup(startManager(10))
	})

	It("assigns exactly one ready Pod, and the pool refills", func() {
		newPool(ns, "default", 3)
		waitWarm(ns, "default", 3)

		newClaim(ns, "claim-a", "default")
		claim := waitClaimed(ns, "claim-a")
		Expect(claim.Finalizers).To(ContainElement(takehomev1alpha1.ClaimFinalizer))
		Expect(claim.Status.Reason).To(Equal(takehomev1alpha1.ReasonAssigned))
		Expect(claim.Status.Attempts).To(Equal(int32(1)))
		Expect(claim.Status.AssignedAt).NotTo(BeNil())

		bound := podsLabelledFor(claim)
		Expect(bound).To(HaveLen(1))
		Expect(bound[0].Name).To(Equal(claim.Status.PodName))
		Expect(bound[0].Status.PodIP).To(Equal(claim.Status.PodIP))
		Expect(bound[0].Labels).To(HaveKeyWithValue(takehomev1alpha1.LabelClaim, "claim-a"))
		Expect(bound[0].Annotations).To(HaveKey(takehomev1alpha1.AnnotationClaimedAt))

		By("refilling to three warm Pods plus the claimed one")
		waitWarm(ns, "default", 3)
		Eventually(func(g Gomega) {
			s := getPool(ns, "default").Status
			g.Expect(s.ClaimedReplicas).To(Equal(int32(1)))
			g.Expect(s.Replicas).To(Equal(int32(4)))
		}).Should(Succeed())
		Consistently(func() string { return getClaim(ns, "claim-a").Status.PodName }).Should(Equal(bound[0].Name))
	})

	It("never gives the same Pod to two claims", func() {
		newPool(ns, "default", 3)
		waitWarm(ns, "default", 3)

		By("creating 20 claims against 3 warm Pods")
		for i := range 20 {
			newClaim(ns, fmt.Sprintf("claim-%02d", i), "default")
		}
		countPhases := func() (claimed, pending int) {
			var list takehomev1alpha1.WorkerClaimList
			Expect(k8sClient.List(ctx, &list, client.InNamespace(ns))).To(Succeed())
			for _, c := range list.Items {
				switch c.Status.Phase {
				case takehomev1alpha1.ClaimClaimed:
					claimed++
				case takehomev1alpha1.ClaimPending:
					pending++
				}
			}
			return claimed, pending
		}
		Eventually(func(g Gomega) {
			claimed, pending := countPhases()
			g.Expect(claimed).To(Equal(3))
			g.Expect(pending).To(Equal(17))
		}).Should(Succeed())
		Consistently(func(g Gomega) {
			checkInvariants(g, ns)
			claimed, _ := countPhases()
			g.Expect(claimed).To(Equal(3), "no new Pod is Ready, so nobody else can be assigned")
		}).Should(Succeed())
		Expect(getClaim(ns, "claim-19").Status.Reason).To(SatisfyAny(
			Equal(takehomev1alpha1.ReasonNoWarmPodsAvailable), Equal(takehomev1alpha1.ReasonAssigned)))

		By("booting replacement Pods until every claim has one")
		Eventually(func(g Gomega) {
			markAllReady(ns)
			checkInvariants(g, ns)
			claimed, _ := countPhases()
			g.Expect(claimed).To(Equal(20))
		}).Should(Succeed())
		Consistently(invariantsHold(ns)).Should(Succeed())
		waitPool(ns, "default", 3, 20)
	})

	It("waits with PoolNotFound until the pool exists", func() {
		newClaim(ns, "claim-a", "late")
		Eventually(func(g Gomega) {
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimPending))
			g.Expect(c.Status.Reason).To(Equal(takehomev1alpha1.ReasonPoolNotFound))
		}).Should(Succeed())

		newPool(ns, "late", 1)
		Eventually(func(g Gomega) {
			markAllReady(ns)
			g.Expect(getClaim(ns, "claim-a").Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
		}).Should(Succeed())
	})

	It("re-assigns a claim whose Pod is deleted", func() {
		newPool(ns, "default", 1)
		waitWarm(ns, "default", 1)
		newClaim(ns, "claim-a", "default")
		first := waitClaimed(ns, "claim-a").Status.PodName
		// The pool creates a replacement; it stays not Ready so we can see Pending.
		Eventually(func() []corev1.Pod { return livePods(ns) }).Should(HaveLen(2))

		deletePodNow(ns, first)
		Eventually(func(g Gomega) {
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimPending))
			g.Expect(c.Status.Reason).To(Equal(takehomev1alpha1.ReasonAssignedPodLost))
			g.Expect(c.Status.PodName).To(BeEmpty())
			g.Expect(c.Status.Attempts).To(Equal(int32(1)))
		}).Should(Succeed())

		Eventually(func(g Gomega) {
			markAllReady(ns)
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(c.Status.PodName).NotTo(Equal(first))
			g.Expect(c.Status.Attempts).To(Equal(int32(2)))
		}).Should(Succeed())
		Consistently(invariantsHold(ns)).Should(Succeed())
	})

	It("treats a terminating or failed Pod as lost", func() {
		newPool(ns, "default", 1)
		waitWarm(ns, "default", 1)
		newClaim(ns, "claim-a", "default")
		first := waitClaimed(ns, "claim-a").Status.PodName

		By("deleting the Pod but keeping it Terminating")
		holdAndDelete(ns, first)
		DeferCleanup(releaseHold, ns, first)
		Eventually(func(g Gomega) {
			markAllReady(ns)
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(c.Status.PodName).NotTo(Equal(first))
		}).Should(Succeed())
		second := getClaim(ns, "claim-a").Status.PodName
		Consistently(invariantsHold(ns)).Should(Succeed())
		Expect(getClaim(ns, "claim-a").Status.PodName).To(Equal(second),
			"the Terminating Pod still carries the claim label but must not win back the claim")

		By("failing the second Pod")
		markPhase(ns, second, corev1.PodFailed)
		Eventually(podGone(ns, second)).Should(BeTrue(), "the claim deletes its failed Pod")
		Eventually(func(g Gomega) {
			markAllReady(ns)
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(c.Status.PodName).NotTo(BeElementOf(first, second))
			g.Expect(c.Status.Attempts).To(Equal(int32(3)))
		}).Should(Succeed())
	})

	It("deletes the Pod when the claim is deleted", func() {
		newPool(ns, "default", 2)
		waitWarm(ns, "default", 2)
		claim := newClaim(ns, "claim-a", "default")
		pod := waitClaimed(ns, "claim-a").Status.PodName
		waitPool(ns, "default", 2, 1)

		Expect(k8sClient.Delete(ctx, claim)).To(Succeed())
		Eventually(func() bool {
			err := k8sClient.Get(ctx, client.ObjectKeyFromObject(claim), &takehomev1alpha1.WorkerClaim{})
			return apierrors.IsNotFound(err)
		}).Should(BeTrue(), "the finalizer is removed")
		Eventually(podGone(ns, pod)).Should(BeTrue())
		waitPool(ns, "default", 2, 0)
		Expect(livePods(ns)).To(HaveLen(2), "the consumed Pod is not returned to the pool")
	})
})
