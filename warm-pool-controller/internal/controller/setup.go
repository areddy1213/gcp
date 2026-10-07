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
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/selection"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"

	takehomev1alpha1 "github.com/areddy1213/warm-pool-controller/api/v1alpha1"
)

// CacheOptions limits the Pod informer to Pods that carry the pool label, so
// the controller does not cache every Pod in the cluster.
func CacheOptions() cache.Options {
	req, err := labels.NewRequirement(takehomev1alpha1.LabelPool, selection.Exists, nil)
	if err != nil {
		panic(err)
	}
	return cache.Options{ByObject: map[client.Object]cache.ByObject{
		&corev1.Pod{}: {Label: labels.NewSelector().Add(*req)},
	}}
}

// SetupWithManager registers both reconcilers. main.go and the tests share it
// so the tests run exactly the wiring that ships.
func SetupWithManager(mgr ctrl.Manager, claimWorkers int) error {
	recorder := mgr.GetEventRecorder("warm-pool-controller")
	if err := (&WorkerPoolReconciler{
		Client:    mgr.GetClient(),
		APIReader: mgr.GetAPIReader(),
		Scheme:    mgr.GetScheme(),
		Recorder:  recorder,
	}).SetupWithManager(mgr); err != nil {
		return err
	}
	return (&WorkerClaimReconciler{
		Client:                  mgr.GetClient(),
		APIReader:               mgr.GetAPIReader(),
		Scheme:                  mgr.GetScheme(),
		Recorder:                recorder,
		MaxConcurrentReconciles: claimWorkers,
	}).SetupWithManager(mgr)
}
