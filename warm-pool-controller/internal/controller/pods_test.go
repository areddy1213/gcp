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
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

var (
	t0       = time.Date(2026, 10, 6, 10, 0, 0, 0, time.UTC)
	testPool = &takehomev1alpha1.WorkerPool{ObjectMeta: metav1.ObjectMeta{
		Name: "default", Namespace: "ns", UID: types.UID("pool-uid"),
	}}
)

// podOpt mutates a test Pod.
type podOpt func(*corev1.Pod)

func makePod(name string, opts ...podOpt) corev1.Pod {
	pod := corev1.Pod{ObjectMeta: metav1.ObjectMeta{
		Name: name, Namespace: "ns",
		Labels:            map[string]string{takehomev1alpha1.LabelPool: "default"},
		CreationTimestamp: metav1.NewTime(t0),
		OwnerReferences: []metav1.OwnerReference{{
			APIVersion: takehomev1alpha1.GroupVersion.String(), Kind: "WorkerPool",
			Name: "default", UID: testPool.UID, Controller: new(true),
		}},
	}}
	for _, o := range opts {
		o(&pod)
	}
	return pod
}

func readyAt(at time.Time) podOpt {
	return func(p *corev1.Pod) {
		p.Status.Phase = corev1.PodRunning
		p.Status.Conditions = []corev1.PodCondition{{
			Type: corev1.PodReady, Status: corev1.ConditionTrue, LastTransitionTime: metav1.NewTime(at),
		}}
	}
}

var ready = readyAt(t0)

func phase(ph corev1.PodPhase) podOpt { return func(p *corev1.Pod) { p.Status.Phase = ph } }

func claimedBy(uid string) podOpt {
	return func(p *corev1.Pod) {
		p.Labels[takehomev1alpha1.LabelClaim] = "claim-" + uid
		p.Labels[takehomev1alpha1.LabelClaimUID] = uid
	}
}

func terminating(p *corev1.Pod) { p.DeletionTimestamp = new(metav1.NewTime(t0)) }

func createdAt(at time.Time) podOpt {
	return func(p *corev1.Pod) { p.CreationTimestamp = metav1.NewTime(at) }
}

func notOwned(p *corev1.Pod) { p.OwnerReferences = nil }

func names(pods []*corev1.Pod) []string {
	out := make([]string, len(pods))
	for i, p := range pods {
		out[i] = p.Name
	}
	return out
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestClassifyPod(t *testing.T) {
	notReady := func(p *corev1.Pod) {
		p.Status.Phase = corev1.PodRunning
		p.Status.Conditions = []corev1.PodCondition{{Type: corev1.PodReady, Status: corev1.ConditionFalse}}
	}
	tests := []struct {
		name string
		pod  corev1.Pod
		want podClass
	}{
		{"pending", makePod("p", phase(corev1.PodPending)), podStarting},
		{"running but not ready", makePod("p", notReady), podStarting},
		{"ready condition but not running", makePod("p", ready, phase(corev1.PodPending)), podStarting},
		{"running and ready", makePod("p", ready), podWarm},
		{"ready and claimed", makePod("p", ready, claimedBy("u1")), podClaimed},
		{"not ready and claimed", makePod("p", notReady, claimedBy("u1")), podClaimed},
		{"failed", makePod("p", phase(corev1.PodFailed)), podTerminal},
		{"succeeded", makePod("p", phase(corev1.PodSucceeded)), podTerminal},
		{"failed and claimed", makePod("p", phase(corev1.PodFailed), claimedBy("u1")), podTerminal},
		{"ready but terminating", makePod("p", ready, terminating), podTerminating},
		{"claimed and terminating", makePod("p", ready, claimedBy("u1"), terminating), podTerminating},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := classifyPod(&tc.pod); got != tc.want {
				t.Errorf("classifyPod = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestGroupPoolPods(t *testing.T) {
	pods := []corev1.Pod{
		makePod("warm", ready),
		makePod("starting"),
		makePod("claimed-ready", ready, claimedBy("u1")),
		makePod("claimed-starting", claimedBy("u2")),
		makePod("failed", phase(corev1.PodFailed)),
		makePod("failed-claimed", phase(corev1.PodFailed), claimedBy("u3")),
		makePod("terminating", ready, terminating),
		makePod("terminating-claimed", ready, claimedBy("u4"), terminating),
		makePod("foreign", ready, notOwned),
	}
	g := groupPoolPods(testPool, pods)

	checks := []struct {
		what string
		got  []*corev1.Pod
		want []string
	}{
		{"warm", g.warm, []string{"warm"}},
		{"starting", g.starting, []string{"starting"}},
		{"claimed", g.claimed, []string{"claimed-ready", "claimed-starting"}},
		{"terminalUnclaimed", g.terminalUnclaimed, []string{"failed"}},
		{"withClaimLabel", g.withClaimLabel, []string{"claimed-ready", "claimed-starting", "failed-claimed"}},
	}
	for _, c := range checks {
		if !equalStrings(names(c.got), c.want) {
			t.Errorf("%s = %v, want %v", c.what, names(c.got), c.want)
		}
	}
	if g.claimedReady != 1 {
		t.Errorf("claimedReady = %d, want 1", g.claimedReady)
	}
}

func TestScaleDelta(t *testing.T) {
	pods := func(warm, starting, claimed int) poolPods {
		var g poolPods
		for range warm {
			g.warm = append(g.warm, &corev1.Pod{})
		}
		for range starting {
			g.starting = append(g.starting, &corev1.Pod{})
		}
		for range claimed {
			g.claimed = append(g.claimed, &corev1.Pod{})
		}
		return g
	}
	tests := []struct {
		name                    string
		want                    int32
		warm, starting, claimed int
		wantDelta               int
	}{
		{"empty pool", 3, 0, 0, 0, 3},
		{"first batch still booting: do not create more", 3, 0, 3, 0, 0},
		{"one claimed: replace it", 3, 2, 0, 1, 1},
		{"claimed Pods never count", 3, 3, 0, 10, 0},
		{"surplus after scale down", 1, 2, 1, 1, -2},
		{"scale to zero", 0, 2, 1, 4, -3},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := scaleDelta(tc.want, pods(tc.warm, tc.starting, tc.claimed)); got != tc.wantDelta {
				t.Errorf("scaleDelta = %d, want %d", got, tc.wantDelta)
			}
		})
	}
}

func TestScaleDownVictims(t *testing.T) {
	all := []corev1.Pod{
		makePod("warm-old", ready, createdAt(t0)),
		makePod("warm-new", ready, createdAt(t0.Add(time.Minute))),
		makePod("starting-old", createdAt(t0)),
		makePod("starting-new", createdAt(t0.Add(time.Minute))),
		makePod("claimed", ready, claimedBy("u1"), createdAt(t0.Add(time.Hour))),
	}
	g := groupPoolPods(testPool, all)

	tests := []struct {
		n    int
		want []string
	}{
		{1, []string{"starting-new"}},
		{3, []string{"starting-new", "starting-old", "warm-new"}},
		{10, []string{"starting-new", "starting-old", "warm-new", "warm-old"}}, // never the claimed Pod
	}
	for _, tc := range tests {
		if got := names(scaleDownVictims(g, tc.n)); !equalStrings(got, tc.want) {
			t.Errorf("scaleDownVictims(%d) = %v, want %v", tc.n, got, tc.want)
		}
	}
}

func TestBindCandidates(t *testing.T) {
	pods := []corev1.Pod{
		makePod("b-ready-late", readyAt(t0.Add(2*time.Second))),
		makePod("a-ready-early", readyAt(t0)),
		makePod("c-ready-early", readyAt(t0)),
		makePod("starting"),
		makePod("claimed", ready, claimedBy("u1")),
		makePod("terminating", ready, terminating),
		makePod("foreign", ready, notOwned),
	}
	got := names(bindCandidates(testPool, pods))
	want := []string{"a-ready-early", "c-ready-early", "b-ready-late"}
	if !equalStrings(got, want) {
		t.Errorf("bindCandidates = %v, want %v", got, want)
	}
}

func TestKeeperPod(t *testing.T) {
	at := func(ts time.Time) podOpt {
		return func(p *corev1.Pod) {
			p.Annotations = map[string]string{takehomev1alpha1.AnnotationClaimedAt: ts.Format(time.RFC3339)}
		}
	}
	early := makePod("early", ready, at(t0))
	late := makePod("late", ready, at(t0.Add(time.Minute)))
	none := makePod("none", ready)
	live := []*corev1.Pod{&late, &none, &early}

	if got := keeperPod(live, "late").Name; got != "late" {
		t.Errorf("keeperPod with reported Pod = %s, want late", got)
	}
	if got := keeperPod(live, "").Name; got != "early" {
		t.Errorf("keeperPod without reported Pod = %s, want early", got)
	}
	if got := keeperPod(live, "gone").Name; got != "early" {
		t.Errorf("keeperPod with a reported Pod that is not live = %s, want early", got)
	}
}

func TestPodForPoolStripsReservedMetadata(t *testing.T) {
	pool := testPool.DeepCopy()
	pool.Spec.Template.Labels = map[string]string{
		"app":                          "worker",
		takehomev1alpha1.LabelClaimUID: "forged",
		takehomev1alpha1.LabelPool:     "other",
	}
	pool.Spec.Template.Annotations = map[string]string{
		"note":                               "kept",
		takehomev1alpha1.AnnotationClaimedAt: "forged",
	}
	pool.Spec.Template.Spec.Containers = []corev1.Container{{Name: "worker", Image: "nginx:alpine"}}

	pod := podForPool(pool)
	if pod.GenerateName != "default-" || pod.Namespace != "ns" {
		t.Errorf("name/namespace = %q/%q", pod.GenerateName, pod.Namespace)
	}
	wantLabels := map[string]string{"app": "worker", takehomev1alpha1.LabelPool: "default"}
	if len(pod.Labels) != len(wantLabels) {
		t.Errorf("labels = %v, want %v", pod.Labels, wantLabels)
	}
	for k, v := range wantLabels {
		if pod.Labels[k] != v {
			t.Errorf("label %s = %q, want %q", k, pod.Labels[k], v)
		}
	}
	if len(pod.Annotations) != 1 || pod.Annotations["note"] != "kept" {
		t.Errorf("annotations = %v", pod.Annotations)
	}
	if classifyPod(pod) == podClaimed {
		t.Error("a template must not be able to create a claimed Pod")
	}
	if len(pod.Spec.Containers) != 1 || pod.Spec.Containers[0].Image != "nginx:alpine" {
		t.Errorf("spec not copied: %+v", pod.Spec.Containers)
	}
}
