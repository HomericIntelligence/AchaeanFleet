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
#   nomad job run -var="agamemnon_url=https://caddy:8443" nomad/mesh.nomad.hcl
#
# TLS prerequisites:
#   Run bash tls/generate-certs.sh and distribute certs to var.tls_cert_dir
#   on each Nomad client host before running this job.

# =============================================================================
# Variables (override via -var or .nomadvar files)
# =============================================================================

variable "agamemnon_url" {
  description = "URL of the ProjectAgamemnon coordinator (TLS via Caddy)"
  type        = string
  default     = "https://caddy:8443"
}

variable "tls_cert_dir" {
  description = "Absolute path to TLS certs directory on the Nomad client host"
  type        = string
  default     = "/etc/achaean/certs"
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

variable "anthropic_api_key" {
  description = "Anthropic API key (for claude, aider, goose, cline, opencode, codebuff, ampcode)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key (for codex)"
  type        = string
  default     = ""
  sensitive   = true
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
        image = "achaean-claude:latest"
        ports = ["agent"]

        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
          "${var.tls_cert_dir}:/certs:ro",
        ]
      }

      env {
        AGENT_PORT    = "23001"
        AGAMEMNON_URL = var.agamemnon_url
      }

      template {
        data        = <<EOH
AGENT_ID=claude-{{ env "NOMAD_ALLOC_INDEX" }}
TMUX_SESSION_NAME=claude-{{ env "NOMAD_ALLOC_INDEX" }}
EOH
        destination = "local/agent-env"
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
        cpu    = 500   # MHz
        memory = 2048  # MB
      }

      service {
        name = "achaean-claude-${NOMAD_ALLOC_INDEX}"
        port = "agent"

        # Health check hits the Caddy TLS proxy's plain-HTTP health endpoint.
        # Caddy exposes :2019/health on its internal port; agents reach it via
        # the Nomad service name. When Consul Connect is enabled, switch to
        # type = "grpc" or use sidecar proxy checks.
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
        image   = "achaean-aider:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
          "${var.tls_cert_dir}:/certs:ro",
        ]
      }

      env {
        AGENT_PORT    = "23001"
        AGAMEMNON_URL = var.agamemnon_url
        AIDER_MODEL   = "claude-3-5-sonnet-20241022"
      }

      template {
        data        = <<EOH
AGENT_ID=aider-{{ env "NOMAD_ALLOC_INDEX" }}
TMUX_SESSION_NAME=aider-{{ env "NOMAD_ALLOC_INDEX" }}
EOH
        destination = "local/agent-env"
        env         = true
      }

      resources {
        cpu    = 500
        memory = 2048
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
  # Codex agents group (OpenAI)
  # -------------------------------------------------------------------------
  group "codex-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "codex" {
      driver = "docker"

      config {
        image   = "achaean-codex:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "codex-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "codex-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        OPENAI_API_KEY    = var.openai_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/codex" }}
      #   OPENAI_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-codex-${NOMAD_ALLOC_INDEX}"
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
  # Goose agents group (Python)
  # -------------------------------------------------------------------------
  group "goose-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "goose" {
      driver = "docker"

      config {
        image   = "achaean-goose:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "goose-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "goose-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        ANTHROPIC_API_KEY = var.anthropic_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/goose" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-goose-${NOMAD_ALLOC_INDEX}"
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
  # Cline agents group (Node)
  # -------------------------------------------------------------------------
  group "cline-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "cline" {
      driver = "docker"

      config {
        image   = "achaean-cline:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "cline-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "cline-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        ANTHROPIC_API_KEY = var.anthropic_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/cline" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-cline-${NOMAD_ALLOC_INDEX}"
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
  # Opencode agents group (Node)
  # -------------------------------------------------------------------------
  group "opencode-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "opencode" {
      driver = "docker"

      config {
        image   = "achaean-opencode:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "opencode-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "opencode-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        ANTHROPIC_API_KEY = var.anthropic_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/opencode" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-opencode-${NOMAD_ALLOC_INDEX}"
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
  # Codebuff agents group (Node)
  # -------------------------------------------------------------------------
  group "codebuff-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "codebuff" {
      driver = "docker"

      config {
        image   = "achaean-codebuff:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "codebuff-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "codebuff-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        ANTHROPIC_API_KEY = var.anthropic_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/codebuff" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-codebuff-${NOMAD_ALLOC_INDEX}"
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
  # Ampcode agents group (Node)
  # -------------------------------------------------------------------------
  group "ampcode-agents" {
    count = 1

    network {
      port "agent" { to = 23001 }
    }

    task "ampcode" {
      driver = "docker"

      config {
        image   = "achaean-ampcode:latest"
        ports   = ["agent"]
        volumes = [
          "${var.agamemnon_sidecar_path}:/app/agent-sidecar:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "ampcode-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "ampcode-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        ANTHROPIC_API_KEY = var.anthropic_api_key
      }

      # Secrets via Nomad Vault integration (Phase 6)
      # template {
      #   data = <<EOH
      #   {{ with secret "secret/achaean/ampcode" }}
      #   ANTHROPIC_API_KEY={{ .Data.api_key }}
      #   {{ end }}
      #   EOH
      #   destination = "secrets/env"
      #   env         = true
      # }

      resources {
        cpu    = 500
        memory = 2048
      }

      service {
        name = "achaean-ampcode-${NOMAD_ALLOC_INDEX}"
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
        image   = "achaean-worker:latest"
        ports   = ["agent"]
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

      template {
        data        = <<EOH
AGENT_ID=worker-{{ env "NOMAD_ALLOC_INDEX" }}
TMUX_SESSION_NAME=worker-{{ env "NOMAD_ALLOC_INDEX" }}
EOH
        destination = "local/agent-env"
        env         = true
      }

      resources {
        cpu    = 250
        memory = 512
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
  #     }
  #     resources {
  #       device "nvidia/gpu" {
  #         count = 1
  #       }
  #     }
  #   }
  # }
}
