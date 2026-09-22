# Day 2, written by hand: the bucket that holds every other layer's state.
# This one layer uses local state (chicken-and-egg). Apply it once, then leave it alone.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate" {
  name     = "${var.project_id}-tfstate"
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # State history lets you recover from a bad apply or a corrupted state file.
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }

  # Sandbox convenience. In prod: false, plus prevent_destroy.
  force_destroy = true

  labels = {
    managed-by = "terraform"
    purpose    = "tfstate"
  }

  depends_on = [google_project_service.storage]
}

output "state_bucket" {
  value = google_storage_bucket.tfstate.name
}
