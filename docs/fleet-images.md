# Fleet image architecture

AchaeanFleet supplies pinned executable images and verifiable build artifacts.
Hephaestus owns the worker and execution supervisor. Agamemnon owns admission and
durable work decisions; Myrmidons holds desired pool configuration; Proteus applies
approved image reconciliation. Odysseus presents their status. An image build or
checksum does not grant authority to start work.

## Build boundary

The [Fleet image contract](../vessels/fleet/README.md) is separate from the legacy
vessel matrix. It consumes a real Hephaestus wheel, the target platform's complete
hash-locked dependency closure, reviewed base-image digests, and the pinned Codex
0.153.4 package. `worker` and `build-tools` support Linux amd64 and arm64. Source
snapshots include relevant uncommitted files through explicit file hashes; a Git
revision alone cannot identify a dirty build.

The image helper validates and freezes those inputs. Its BuildKit path exports
OCI bytes with SBOM and provenance attestations and checks their content binding.
It does not publish images, register pools, create credentials, or start workers.
The existing capped Podman builds produced real private images, OCI exports, and
separately generated SPDX documents. They did not satisfy the BuildKit attestation
gate. The [dedicated CI proposal](../vessels/fleet/ci-proposal.md) remains unwired.

## Artifact identity and distribution

Keep these identities separate in the artifact manifest:

| Identity | Meaning |
| --- | --- |
| Source snapshot and wheel SHA256 | Exact source inputs and installed package bytes |
| Engine image ID | Local engine configuration identity; not a registry location |
| OCI manifest digest | Content-addressed exported manifest and referenced image bytes |
| OCI archive SHA256 | Exact transport archive, including its tar representation |
| Registry digest | Manifest actually retrieved from an approved registry after publication |
| SPDX/attestation digest | Exact scanner output or attestation bound to its declared subject |
| SquashFS SHA256 | Exact converted filesystem supplied to Pyxis/Enroot |

An engine can serialize an export with a different manifest digest. Record both
and verify their actual configuration and layer content. A SquashFS conversion is
another artifact with its own checksum and converter/source mapping; it does not
inherit OCI attestations as if it were the same manifest.

Distribution can use an approved registry or an approved immutable file transfer.
Neither path is implemented by `fleet-image-build`. Registry publication must
preserve attestations and verify remote digest readback. File transfer must verify
the destination checksum before the consumer uses the artifact. The operational
steps and remaining gates are in the [promotion runbook](runbooks/fleet-image-promotion.md).

## Runtime boundary

The worker target runs as UID/GID 1000. Private authentication and worker state
belong to its supervisor and remain separate from task workspaces. Tool containers
receive only their own workspace and declared scratch storage. They must not
receive the controller socket, provider authentication, host home, or OpenBao
credentials. OpenBao manages Fleet service secrets; native Codex authentication
remains private runtime storage.

Dockerfile metadata cannot prove mount isolation, resource enforcement, process
cleanup, or a task claim. Hephaestus must inspect the actual execution environment
and reconcile durable ownership. Five managed app-server runtimes are the planned
capacity for 108 logical agents; additional contained tool endpoints do not replace
those identities or authorize more conversations.

Externally managed Slurm/Pyxis clusters are an additive execution environment.
They do not change existing Nomad scheduling or mesh topology. Installed Enroot
3.5.0 on M1/M2 accepts registry/daemon import schemes, not an OCI-archive URI. A
local conversion has produced a genuine amd64 SquashFS file, but no transfer or
cluster launch has validated it. Enroot does not turn OCI `User`, cgroup limits,
or security flags into a launch policy; the allocation adapter must enforce them.

## Measured checkpoint and limits

On 2026-09-11, private arm64 and emulated amd64 worker images initialized with empty
authentication storage. Their installed Unix-socket interfaces refused a synthetic
session start with `linux_execution_requires_verified_boundary` and retained zero
sessions. The wheel snapshot predates subsequent Hephaestus changes, including its
production contained-exec supervisor. It is a packaging checkpoint, not a current
deployable worker release.

Separate synthetic arm64 probes established direct contained exec-server file and
process behavior and one causal live-child disposal. They used no model turns.
The native nested sandbox probe failed at a bubblewrap `devpts` mount. Normal model
tool routing, supervisor integration, account capacity, actual HPC execution, and
the combined 108-agent acceptance remain independent gates. Image references must
remain disabled for admission until their required gates pass.
