# Network Topology

AchaeanFleet uses two named Docker bridge networks to limit the blast radius of a compromised agent
container (defense-in-depth, zero-trust principles).

## Networks

| Network | Driver | Purpose |
|---------|--------|---------|
| `agamemnon-frontend` | bridge | All agent vessels; ProjectAgamemnon reaches agents here |
| `agent-backend` | bridge | Opt-in lateral traffic between agents |

## Diagram

```
  Host
  ├─ ProjectAgamemnon (port 8080)
  │   └─ reaches agents via Docker bridge gateway: 172.20.0.1
  │
  ├─ agamemnon-frontend (bridge)
  │   ├─ hi-aindrea   :23001
  │   ├─ hi-baird     :23003
  │   ├─ hi-vegai     :23004
  │   ├─ hi-codex-1   :23010
  │   ├─ hi-aider-1   :23020
  │   ├─ hi-goose-1   :23030
  │   ├─ hi-cline-1   :23040
  │   ├─ hi-opencode-1 :23050
  │   ├─ hi-codebuff-1 :23060
  │   ├─ hi-ampcode-1  :23070
  │   └─ hi-worker-1  :23080  ──┐
  │                              │ (spans both networks)
  └─ agent-backend (bridge)      │
      └─ hi-worker-1  ───────────┘
```

## Service network membership

| Service | agamemnon-frontend | agent-backend |
|---------|:-----------------:|:-------------:|
| hi-aindrea | ✓ | |
| hi-baird | ✓ | |
| hi-vegai | ✓ | |
| hi-codex-1 | ✓ | |
| hi-aider-1 | ✓ | |
| hi-goose-1 | ✓ | |
| hi-cline-1 | ✓ | |
| hi-opencode-1 | ✓ | |
| hi-codebuff-1 | ✓ | |
| hi-ampcode-1 | ✓ | |
| hi-worker-1 | ✓ | ✓ |

## Design decisions

**Why two networks instead of one?**
Previously all containers shared a single flat `homeric-mesh` network. Any compromised agent could
reach every other agent on any port. Splitting into frontend/backend limits lateral movement: a
compromised AI agent on `agamemnon-frontend` cannot directly probe the `agent-backend` subnet.

**Why is `agent-backend` currently sparse?**
No current agent-to-agent protocol requires direct container-to-container communication. The network
exists as infrastructure ready for future use (e.g., a pipeline where one agent hands off work to
another). `hi-worker-1` is the natural bridge because it is the orchestration primitive with no AI
tool dependency.

**Why are network names hard-coded instead of env-var-driven?**
The two networks have architectural meaning — `agamemnon-frontend` always connects to Agamemnon,
`agent-backend` always carries lateral traffic. Allowing arbitrary runtime renaming would make the
topology ambiguous. The former `MESH_NETWORK` env var has been removed.

**How does ProjectAgamemnon reach agents?**
ProjectAgamemnon runs on the host (not in a container). It connects to agent HTTP endpoints via the
Docker bridge gateway IP `172.20.0.1`, which is the host-side address of the `agamemnon-frontend`
bridge. No Compose-internal DNS is needed for host → container communication.

**How do agents resolve each other?**
Agents on the same network (`agamemnon-frontend`) resolve each other by hostname via Docker's
embedded DNS. For example, `hi-aindrea` can reach `hi-baird` at `http://hi-baird:23001`. This is
standard Docker Compose DNS — no IP injection needed (that workaround is Podman-specific).

## Adding a new agent

New agent vessels should join `agamemnon-frontend` only:

```yaml
services:
  hi-myagent:
    networks: [agamemnon-frontend]
```

To also participate in direct agent-to-agent coordination, add `agent-backend` as well:

```yaml
services:
  hi-myagent:
    networks:
      agamemnon-frontend:
        aliases: [hi-myagent]
      agent-backend:
        aliases: [hi-myagent]
```

## Manual isolation verification

```bash
# Start the test containers
docker compose -f compose/docker-compose.network-test.yml up -d

# frontend container should NOT reach backend-only container
docker exec netshoot-frontend ping -c 1 netshoot-backend   # expect: unreachable

# backend container should NOT reach frontend-only container
docker exec netshoot-backend ping -c 1 netshoot-frontend   # expect: unreachable

# worker (spans both) should reach both
docker exec hi-worker-1 ping -c 1 netshoot-frontend        # expect: reachable
docker exec hi-worker-1 ping -c 1 netshoot-backend         # expect: reachable

# Cleanup
docker compose -f compose/docker-compose.network-test.yml down
```
