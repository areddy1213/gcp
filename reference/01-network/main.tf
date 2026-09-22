# Day 2, written by hand: a custom-mode VPC ready for Cloud Run (Direct VPC
# egress), Cloud SQL (Private Services Access), and private VMs/GKE (Cloud NAT).

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Backend blocks can't use variables. Pass the bucket at init time:
  #   terraform init -backend-config="bucket=<project>-tfstate"
  backend "gcs" {
    prefix = "network"
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

variable "name" {
  type    = string
  default = "app"
}

locals {
  apis = [
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "vpc" {
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false # custom mode: we choose every range
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "app" {
  name          = "${var.name}-${var.region}"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = "10.10.0.0/24"

  # Lets workloads with no external IP reach Google APIs (GCS, Secret Manager...).
  private_ip_google_access = true

  # Secondary ranges are only needed for GKE (pods/services); harmless otherwise.
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.30.0.0/20"
  }

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
  }
}

# Outbound internet for private resources (package installs, external APIs),
# without giving anything a public IP.
resource "google_compute_router" "router" {
  name    = "${var.name}-router"
  network = google_compute_network.vpc.id
  region  = var.region
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.name}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# IAP TCP forwarding is the only way in to private VMs. There is no 0.0.0.0/0 SSH rule.
resource "google_compute_firewall" "allow_iap_ssh" {
  name          = "${var.name}-allow-iap-ssh"
  network       = google_compute_network.vpc.id
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Private Services Access: a range Google peers into, so Cloud SQL (and
# Memorystore, etc.) can get a private IP inside this VPC.
resource "google_compute_global_address" "psa" {
  name          = "${var.name}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "psa" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]

  depends_on = [google_project_service.apis]
}

output "network_id" {
  value = google_compute_network.vpc.id
}

output "subnet_id" {
  value = google_compute_subnetwork.app.id
}

output "psa_connection" {
  value = google_service_networking_connection.psa.id
}
