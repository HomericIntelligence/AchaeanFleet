# AchaeanFleet: Nomad Job Specification (Phase 6)
#
# Manages the full heterogeneous agent mesh in Nomad.
# Features: health checks, auto-restart, rolling updates, GPU scheduling.
#
# Usage:
#   nomad job plan nomad/mesh.nomad.hcl
#   nomad job run nomad/mesh.nomad.hcl

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
          "/home/mvillmow/ai-maestro/agent-container/agent-server.js:/app/agent-server.js:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "claude-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "claude-${NOMAD_ALLOC_INDEX}"
        AIM_HOST          = "http://172.20.0.1:23000"
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
          "/home/mvillmow/ai-maestro/agent-container/agent-server.js:/app/agent-server.js:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "aider-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "aider-${NOMAD_ALLOC_INDEX}"
        AIM_HOST          = "http://172.20.0.1:23000"
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
          "/home/mvillmow/ai-maestro/agent-container/agent-server.js:/app/agent-server.js:ro",
        ]
      }

      env {
        AGENT_PORT        = "23001"
        TMUX_SESSION_NAME = "worker-${NOMAD_ALLOC_INDEX}"
        AGENT_ID          = "worker-${NOMAD_ALLOC_INDEX}"
        AIM_HOST          = "http://172.20.0.1:23000"
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
