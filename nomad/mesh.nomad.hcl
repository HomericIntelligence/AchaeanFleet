# AchaeanFleet: Nomad Job Specification (Phase 6)
#
# Manages the full heterogeneous agent mesh in Nomad.
# Features: health checks, auto-restart, rolling updates, GPU scheduling.
#
# Usage:
#   nomad job plan nomad/mesh.nomad.hcl
#   nomad job run nomad/mesh.nomad.hcl
#
# Override variables at run time:
#   nomad job run -var="agamemnon_url=http://192.168.1.10:8080" nomad/mesh.nomad.hcl
#
# SECRETS MANAGEMENT (Phase 6):
# API keys and dynamic secrets are injected via Nomad's Vault integration.
# See nomad/PATTERNS.md § 5 for the template stanza pattern and anti-patterns to avoid.
# Never pass secrets as inline env vars or store them in HCL.

# =============================================================================
# Variables (override via -var or .nomadvar files)
# =============================================================================

variable "agamemnon_url" {
  description = "URL of the ProjectAgamemnon coordinator"
  type        = string
  default     = "http://172.20.0.1:8080"
}

variable "agamemnon_sidecar_path" {
  description = "Absolute path to Agamemnon sidecar binary on the Nomad client host"
  type        = string
  default     = "/home/mvillmow/ProjectAgamemnon/agent-sidecar/agent-sidecar"
}

variable "workspace_root" {
  description = "Absolute path to the workspace root on the Nomad client host"
  type        = string
  default     = "/home/mvillmow"
}

variable "tls_cert_dir" {
  description = "Absolute path to TLS certificate directory on Nomad client hosts (populated by .github/workflows/certs.yml)"
  type        = string
  default     = "/etc/achaean/certs"
}


# =============================================================================
# Job
# =============================================================================

job "achaean-mesh" {
  datacenters = ["dc1"]
  type        = "service"

  # Update strategy: rolling updates, no service disruption
  update {
    max_parallel     = 2
    min_healthy_time = "30s"
    healthy_deadline = "5m"
    auto_revert      = true
    canary           = 0
  }

  # -------------------------------------------------------------------------
  # Claude agents group
  # -------------------------------------------------------------------------
  group "claude-agents" {
    count = 2  # Scale by increasing count

    network {
      port "agent" {
        # Nomad assigns a dynamic host port mapped to 23001 in container
        to = 23001
      }
    }

    task "claude" {
      driver = "docker"

      config {
        image        = "achaean-claude:latest"
        ports        = ["agent"]
        cap_drop     = ["ALL"]
        no_new_privs = true
        # Note: cap_drop ALL compatibility with Claude Code CLI is unverified.
        # If Claude Code requires specific capabilities (e.g. NET_BIND_SERVICE),
        # add cap_add = ["NET_BIND_SERVICE"] here after validating with a live run.

        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
          "${var.tls_cert_dir}:/certs:ro",
        ]
      }

      env {
        AGENT_PORT    = "23001"
        AGAMEMNON_URL = var.agamemnon_url
      }

      # NOMAD_ALLOC_INDEX is only available via Consul Template — see nomad/PATTERNS.md
      template {
        data        = <<EOT
TMUX_SESSION_NAME="claude-{{ env "NOMAD_ALLOC_INDEX" }}"
AGENT_ID="claude-{{ env "NOMAD_ALLOC_INDEX" }}"
EOT
        destination = "local/runtime-env.env"
        env         = true
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/claude" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 2000  # MHz
        memory = 4096  # MB
      }
      logs {
        max_files     = 3
        max_file_size = 10
      }

      service {
        name = "achaean-claude-${NOMAD_ALLOC_INDEX}"
        port = "agent"

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "5s"
        }
      }
    }
  }

  # -------------------------------------------------------------------------
  # Aider agents group (Python)
  # -------------------------------------------------------------------------
  group "aider-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "aider" {
      driver = "docker"

      config {
        image        = "achaean-aider:latest"
        ports        = ["agent"]
        cap_drop     = ["ALL"]
        no_new_privs = true
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
          "${var.tls_cert_dir}:/certs:ro",
        ]
      }

      env {
        AGENT_PORT  = "23001"
        AGAMEMNON_URL = var.agamemnon_url
        AIDER_MODEL = "claude-3-5-sonnet-20241022"
      }

      # NOMAD_ALLOC_INDEX is only available via Consul Template — see nomad/PATTERNS.md
      template {
        data        = <<EOT
TMUX_SESSION_NAME="aider-{{ env "NOMAD_ALLOC_INDEX" }}"
AGENT_ID="aider-{{ env "NOMAD_ALLOC_INDEX" }}"
EOT
        destination = "local/runtime-env.env"
        env         = true
      }

      resources {
        cpu    = 2000  # MHz
        memory = 4096  # MB
      }
      logs {
        max_files     = 3
        max_file_size = 10
      }

      service {
        name = "achaean-aider-${NOMAD_ALLOC_INDEX}"
        port = "agent"

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "5s"
        }
      }
    }
  }

  # -------------------------------------------------------------------------
  # Shell Worker group
  # -------------------------------------------------------------------------
  group "worker-agents" {
    count = 2

    network {
      port "agent" { to = 23001 }
    }

    task "worker" {
      driver = "docker"

      config {
        image        = "achaean-worker:latest"
        ports        = ["agent"]
        cap_drop     = ["ALL"]
        no_new_privs = true
        volumes = [
          "/tmp/ci-workspace:/workspace",
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
          "${var.tls_cert_dir}:/certs:ro",
        ]
      }

      env {
        AGENT_PORT    = "23001"
        AGAMEMNON_URL = var.agamemnon_url
      }

      # NOMAD_ALLOC_INDEX is only available via Consul Template — see nomad/PATTERNS.md
      template {
        data        = <<EOT
TMUX_SESSION_NAME="worker-{{ env "NOMAD_ALLOC_INDEX" }}"
AGENT_ID="worker-{{ env "NOMAD_ALLOC_INDEX" }}"
EOT
        destination = "local/runtime-env.env"
        env         = true
      }

      resources {
        cpu    = 1000  # MHz
        memory = 1024  # MB
      }
      logs {
        max_files     = 3
        max_file_size = 10
      }

      service {
        name = "achaean-worker-${NOMAD_ALLOC_INDEX}"
        port = "agent"

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "5s"
        }
      }
    }
  }

  # -------------------------------------------------------------------------
  # GPU-accelerated group (Phase 6: ProjectOdyssey workloads)
  # -------------------------------------------------------------------------
  # group "gpu-agents" {
  #   count = 1
  #
  #   constraint {
  #     attribute = "${attr.unique.platform.aws.instance-type}"
  #     operator  = "set_contains_any"
  #     value     = "g4dn.xlarge,g5.xlarge"
  #   }
  #
  #   task "claude-gpu" {
  #     driver = "docker"
  #     config {
  #       image = "achaean-claude:latest"
  #       devices = [{
  #         Name = "nvidia"
  #       }]
  #       cap_drop     = ["ALL"]
  #       no_new_privs = true
  #     }
  #     resources {
  #       device "nvidia/gpu" {
  #         count = 1
  #       }
  #     }
  #   }
  # }
}
