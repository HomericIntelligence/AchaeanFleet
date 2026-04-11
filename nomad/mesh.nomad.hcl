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
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "claude-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "claude-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
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
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "aider-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "aider-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
        AIDER_MODEL       = "claude-3-5-sonnet-20241022"
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
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "worker-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "worker-${NOMAD_ALLOC_INDEX}"
        AGAMEMNON_URL     = var.agamemnon_url
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
