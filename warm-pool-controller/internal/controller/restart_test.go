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
	"math/rand"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

var _ = Describe("Controller restart", func() {
	var ns string
	BeforeEach(func() { ns = newNamespace() })

	It("rebuilds every claim from Pod labels without losing or duplicating assignments", func() {
		stop := startManager(4)
		newPool(ns, "default", 3)
		waitWarm(ns, "default", 3)
		names := []string{"keep", "lose-pod", "deleted"}
		for _, n := range names {
			newClaim(ns, n, "default")
		}
		before := map[string]string{}
		Eventually(func(g Gomega) {
			markAllReady(ns)
			for _, n := range names {
				c := getClaim(ns, n)
				g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
				before[n] = c.Status.PodName
			}
		}).Should(Succeed())
		waitPool(ns, "default", 3, 3)
		stop()

		By("changing things while the controller is down")
		// 1. The claim's status is wiped; only the Pod label remembers it.
		keep := getClaim(ns, "keep")
		keep.Status = takehomev1alpha1.WorkerClaimStatus{}
		Expect(k8sClient.Status().Update(ctx, keep)).To(Succeed())
		// 2. A bound Pod is deleted.
		deletePodNow(ns, before["lose-pod"])
		// 3. A claim is deleted; its finalizer keeps it Terminating.
		Expect(k8sClient.Delete(ctx, getClaim(ns, "deleted"))).To(Succeed())
		Expect(getClaim(ns, "deleted").DeletionTimestamp).NotTo(BeNil())
		// 4. A claim is created.
		newClaim(ns, "created-while-down", "default")
		// 5. The previous process died right after binding a Pod and before
		// writing the claim's status: the Pod is labelled, the status is empty.
		crashed := newClaim(ns, "crashed", "default")
		controllerutil.AddFinalizer(crashed, takehomev1alpha1.ClaimFinalizer)
		Expect(k8sClient.Update(ctx, crashed)).To(Succeed())
		var victim *corev1.Pod
		for _, p := range livePods(ns) {
			if isWarm(&p) {
				victim = p.DeepCopy()
				break
			}
		}
		Expect(victim).NotTo(BeNil())
		victim.Labels[takehomev1alpha1.LabelClaim] = crashed.Name
		victim.Labels[takehomev1alpha1.LabelClaimUID] = string(crashed.UID)
		victim.Annotations = map[string]string{takehomev1alpha1.AnnotationClaimedAt: time.Now().UTC().Format(time.RFC3339)}
		Expect(k8sClient.Update(ctx, victim)).To(Succeed())

		By("starting a fresh controller")
		DeferCleanup(startManager(4))

		Eventually(func(g Gomega) {
			markAllReady(ns)
			k := getClaim(ns, "keep")
			g.Expect(k.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(k.Status.PodName).To(Equal(before["keep"]), "status rebuilt from the label")

			l := getClaim(ns, "lose-pod")
			g.Expect(l.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(l.Status.PodName).NotTo(Equal(before["lose-pod"]))
			g.Expect(l.Status.Attempts).To(Equal(int32(2)))

			err := k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: "deleted"}, &takehomev1alpha1.WorkerClaim{})
			g.Expect(apierrors.IsNotFound(err)).To(BeTrue(), "the finalizer ran after the restart")
			g.Expect(podGone(ns, before["deleted"])()).To(BeTrue())

			g.Expect(getClaim(ns, "created-while-down").Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))

			c := getClaim(ns, "crashed")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(c.Status.PodName).To(Equal(victim.Name), "the half-finished bind is completed, not repeated")
			g.Expect(c.Status.Attempts).To(Equal(int32(1)))
		}).Should(Succeed())
		Expect(podsLabelledFor(getClaim(ns, "crashed"))).To(HaveLen(1))
		Consistently(invariantsHold(ns)).Should(Succeed())
		waitPool(ns, "default", 3, 4)
	})

	It("deletes a Pod whose claim was removed without its finalizer, even if the name is reused", func() {
		stop := startManager(4)
		newPool(ns, "default", 2)
		waitWarm(ns, "default", 2)
		newClaim(ns, "claim-a", "default")
		oldPod := waitClaimed(ns, "claim-a").Status.PodName
		stop()

		By("force-removing the finalizer and recreating the claim under the same name")
		old := getClaim(ns, "claim-a")
		old.Finalizers = nil
		Expect(k8sClient.Update(ctx, old)).To(Succeed())
		Expect(k8sClient.Delete(ctx, old)).To(Succeed())
		Eventually(func() bool {
			return apierrors.IsNotFound(k8sClient.Get(ctx, client.ObjectKeyFromObject(old), &takehomev1alpha1.WorkerClaim{}))
		}).Should(BeTrue())
		newClaim(ns, "claim-a", "default")

		DeferCleanup(startManager(4))
		Eventually(podGone(ns, oldPod)).Should(BeTrue(), "the orphan is deleted: same claim name, different UID")
		Eventually(func(g Gomega) {
			markAllReady(ns)
			c := getClaim(ns, "claim-a")
			g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed))
			g.Expect(c.Status.PodName).NotTo(Equal(oldPod))
		}).Should(Succeed())
		Consistently(invariantsHold(ns)).Should(Succeed())
	})
})

var _ = Describe("Churn", func() {
	It("keeps the invariants while claims and Pods are created and deleted at random", func() {
		ns := newNamespace()
		DeferCleanup(startManager(10))
		newPool(ns, "default", 4)
		waitWarm(ns, "default", 4)

		rng := rand.New(rand.NewSource(GinkgoRandomSeed()))
		created := 0
		deadline := time.Now().Add(8 * time.Second)
		for time.Now().Before(deadline) {
			switch rng.Intn(4) {
			case 0:
				newClaim(ns, fmt.Sprintf("c-%03d", created), "default")
				created++
			case 1:
				var claims takehomev1alpha1.WorkerClaimList
				Expect(k8sClient.List(ctx, &claims, client.InNamespace(ns))).To(Succeed())
				if len(claims.Items) > 0 {
					c := claims.Items[rng.Intn(len(claims.Items))]
					Expect(client.IgnoreNotFound(k8sClient.Delete(ctx, &c))).To(Succeed())
				}
			case 2:
				var claimed []corev1.Pod
				for _, p := range livePods(ns) {
					if p.Labels[takehomev1alpha1.LabelClaimUID] != "" {
						claimed = append(claimed, p)
					}
				}
				if len(claimed) > 0 {
					p := claimed[rng.Intn(len(claimed))]
					Expect(client.IgnoreNotFound(k8sClient.Delete(ctx, &p))).To(Succeed())
				}
			case 3:
				markAllReady(ns)
			}
			checkInvariants(Default, ns)
			time.Sleep(20 * time.Millisecond)
		}

		By("settling: every remaining claim gets a Pod and the pool refills")
		Eventually(func(g Gomega) {
			markAllReady(ns)
			checkInvariants(g, ns)
			var claims takehomev1alpha1.WorkerClaimList
			g.Expect(k8sClient.List(ctx, &claims, client.InNamespace(ns))).To(Succeed())
			for _, c := range claims.Items {
				g.Expect(c.DeletionTimestamp).To(BeNil(), "deleted claim %s is released", c.Name)
				g.Expect(c.Status.Phase).To(Equal(takehomev1alpha1.ClaimClaimed), "claim %s", c.Name)
			}
			g.Expect(getPool(ns, "default").Status.AvailableReplicas).To(Equal(int32(4)))
			g.Expect(livePods(ns)).To(HaveLen(len(claims.Items) + 4))
		}).Should(Succeed())
	})
})
