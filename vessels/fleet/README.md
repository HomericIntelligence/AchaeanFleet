# Fleet worker and build-tool images

These image sources implement the AchaeanFleet part of the
[Fleet plan](https://github.com/HomericIntelligence/Odysseus/blob/main/docs/homeric-fleet-plan.md).
They do not provision workers, manage authentication, or admit work.

`worker` contains Codex **0.153.4** and an explicitly supplied Hephaestus wheel.
`build-tools` contains the same Python toolchain and Hephaestus package without
Codex. Both targets use UID/GID 1000 and support `linux/amd64` and `linux/arm64`.
Build each architecture with its own compatible wheel bundle.

## Inputs and reproducibility

The build requires three actual registry digest references:

- `--node-base`: a compatible Debian-based Node image, used only to install the
  locked Codex platform package. The final image preserves its platform binaries
  and bundled sandbox resources in their upstream directory layout.
- `--runtime-base`: **Python 3.13 slim bookworm**, including its manifest digest.
  The Dockerfile checks Python and Debian versions. Its toolchain stage installs
  Git/compiler packages from the fixed Debian snapshot `20260909T000000Z`.
- `--sbom-generator`: a digest-pinned BuildKit-compatible SBOM scanner, such as the
  BuildKit Syft scanner. Resolve and review this digest before building.

The toolchain installs just **1.51.0** and pixi **0.70.2**, checking the per-platform
release archive SHA256 before extracting only the named executable. The recorded
checksums came from the upstream release checksum files:
[just](https://github.com/casey/just/releases/download/1.51.0/SHA256SUMS),
[pixi amd64](https://github.com/prefix-dev/pixi/releases/download/v0.70.2/pixi-x86_64-unknown-linux-musl.tar.gz.sha256),
[pixi arm64](https://github.com/prefix-dev/pixi/releases/download/v0.70.2/pixi-aarch64-unknown-linux-musl.tar.gz.sha256).

Codex npm dependency integrity comes from `package-lock.json`. Regenerate lock
metadata with `just fleet-lock-codex`; that command does not install node_modules.
All build inputs are pinned, but bit-for-bit image reproducibility remains a
separate measured gate. Do not treat a source commit alone as evidence for a dirty
checkout. Build inputs record file hashes and the dirty state.

## Hephaestus wheel contract

Build the actual Fleet-capable Hephaestus source through that repository's package
recipe. Resolve its complete Python 3.13 dependency closure for the target Linux
architecture. Include the `automation` extra for issue-stage execution. Do not
substitute a published version that does not contain `hephaestus-fleet-worker`.

The wheelhouse must contain the built Hephaestus wheel and every dependency wheel.
Supply a requirements file with one exact package pin and SHA256 hash per line:

```text
package-name==exact-version --hash=sha256:actual-wheel-sha256
```

The line above describes the format; it is not an installable requirement.
Multiple hashes on one line are supported. Direct URLs, source distributions,
editable installs, index options, environment markers, and continued lines are
rejected. Produce one resolved requirements file per target. Wheel installation
uses `--no-index --require-hashes --only-binary=:all:` and then `pip check`.

Prepare the bundle from existing artifacts:

```bash
just fleet-image-bundle \
  --platform linux/arm64 \
  --wheelhouse "$FLEET_WHEELHOUSE" \
  --requirements "$FLEET_REQUIREMENTS" \
  --hephaestus-revision "$HEPHAESTUS_SOURCE_REVISION" \
  --output "$FLEET_BUNDLE"
```

The output directory must not exist. The helper copies only wheels and the lock,
computes their hashes, and writes `bundle.json`. The source revision is a declared
build input, not a source-provenance attestation. Retain the wheel build's actual
source/snapshot evidence separately. Image installation verifies that the worker
entrypoint exists. Extra context files, changed bytes, and symlinks block a build.

## Build and evidence gate

Use Docker Buildx with a compatible BuildKit builder and OCI attestation support.
This explicit recipe does not require the repository's legacy Podman selection.
No container engine socket is copied into an image.

First review the exact command without creating images or output directories:

```bash
just fleet-image-plan \
  --platform linux/arm64 --target worker \
  --bundle "$FLEET_BUNDLE" \
  --node-base "$FLEET_NODE_BASE" \
  --runtime-base "$FLEET_PYTHON_BASE" \
  --sbom-generator "$FLEET_SBOM_GENERATOR" \
  --output "$FLEET_IMAGE_OUTPUT"
```

Run the same arguments with `just fleet-image-build` after a builder is available.
The output directory must not exist. Use `--target build-tools` for the tool image.
Repeat for `linux/amd64` with its wheel bundle and a different output directory.

The recipe freezes an allowlisted source context and a verified wheel context.
BuildKit exports `image.oci.tar` with SPDX SBOM and provenance attestations.
The helper preserves raw BuildKit metadata and verifies metadata, configuration,
and filesystem-layer hashes, image subjects, and required predicate types before writing
`build-result.json`. This is content binding, not signature verification or SLSA
certification. A failed build/verification retains diagnostic artifacts without
writing a successful result. No recipe pushes, loads, starts, or registers an image.

Keep admission disabled and image references unset until actual builds, scanner
review, image startup, worker protocol checks, and the approved registry process
supply usable digests. An OCI export digest is not a promise that the registry has
that image. Preserve attestations during publication.

## Runtime contract

The supervisor supplies private writable mounts for `/home/agent`,
`/var/lib/fleet`, `/workspace`, and `/tmp`. It owns their permissions and lifecycle.
Each worker has its own authentication directory; never mount the operator's home,
SSH material, OpenBao token, container socket, or a shared Codex authentication home.
Apply a read-only root filesystem, explicit resource limits, and supported sandbox
controls when starting containers. These are supervisor responsibilities, not
properties established by a Dockerfile.

The worker entrypoint rejects root and an unexpected Codex version, then delegates
arguments without shell reinterpretation:

```text
serve --state-dir /var/lib/fleet/state --workspace-root /workspace
  --codex-home /var/lib/fleet/codex --worker-id WORKER --pool-id POOL
  --host-id HOST --generation GENERATION --capacity CAPACITY
  --codex-bin /opt/codex-bin/codex
```

Before startup, the supervisor creates `/var/lib/fleet/codex` and
`/var/lib/fleet/state` with mode `0700`, owned by UID 1000. The Codex directory
must already exist. The absolute binary path is required because the provider
uses a restricted PATH that does not include `/opt/codex-bin`.

Use `--allocation-id` on Slurm when available. Identity, admission, credentials,
Unix-socket attachment, and the worker protocol belong to Hephaestus/Agamemnon.
Logical conversations share one managed runtime. Any separate tool containers
belong to the supervisor; this image does not provision them. The build-tool target
defaults to `just`; the admitted recipe can explicitly select `pixi run` through
the supervisor.

## Local checks and current limits

Run `just test-fleet-images` for daemon-free contract tests. These use synthetic
dependency/OCI fixtures, never live provider credentials. They cover offline input
validation, command generation, checksums, entrypoint dispatch/version checks, and
attestation binding.

Fleet is intentionally absent from the legacy vessel smoke matrix while its
explicit wheel contexts and digest inputs await dedicated CI wiring, tracked in
[issue #797](https://github.com/HomericIntelligence/AchaeanFleet/issues/797).
The daemon-free tests run with the existing pytest suite. They do not replace
the required CI image build and runtime smoke checks before activation.
The [dedicated CI proposal](ci-proposal.md) records the concrete inputs, commands,
and remaining runtime-probe contract for human review.

Local arm64 and amd64 image builds were exercised on 2026-09-11 with an existing
rootless Podman engine. The amd64 build used its pre-existing QEMU handler; this
does not establish execution on M1 or M2. The arm64 startup probe confirmed
UID 1000, a 2-CPU/2-GiB cgroup limit, zero sessions, zero active reservations,
and clean shutdown. It used a read-only root filesystem, no network, no added
capabilities, and private disposable volumes. This does not establish session
isolation: after correcting omitted bundled resources, the separate Linux probe
failed when bubblewrap attempted to mount `devpts`. Admission remains blocked.

A subsequent pair of isolated arm64 containers passed direct `exec-server` file
and process checks with synthetic markers and empty authentication storage.
Each endpoint had a separate workspace and a 1-CPU/1-GiB limit. Positive fixture
readbacks established the peer and authority markers before the checks. Neither
endpoint could read those other markers. Detached synthetic children survived
stdio shutdown. The harness then cleaned its synthetic children before external
cleanup removed the owning containers and confirmed absence of their observed
cgroup leaves. This does not prove that container removal killed a live detached
child or that the enclosing cgroup scope disappeared.
These checks used `sandbox: null` inside the external container boundary. They do
not establish normal model-tool routing, nested sandbox compatibility, or admission.

A separate lifecycle probe identified a live detached synthetic child by its
nonce, PID, and kernel start time immediately before removing its container.
It did not signal the child first. After removal, both recorded process identities,
the cgroup leaf, and its enclosing scope were absent. This establishes that bounded
container lifecycle check; production supervisor integration remains untested.

Both private images were then refreshed from the current Hephaestus snapshot.
The installed workers started with empty authentication storage and rejected a
synthetic session-start command over their actual Unix sockets with
`linux_execution_requires_verified_boundary`. Each retained zero sessions and
reservations and shut down cleanly. The earlier image artifacts remain as test
history; they predate this admission guard and must not be deployed.

The capped Podman path produces a local OCI archive. Its export can have a
different manifest digest from the engine's stored image; retain both identities
and the archive checksum. It does not satisfy the BuildKit SBOM/provenance
attestation gate above. Do not create a successful BuildKit result record for
such an export. Raw local artifacts remain outside the repository.

Native cluster execution, session isolation, BuildKit attestations, approved
registry publication, and Fleet workloads remain required gates. No image has
been published or admitted. These local builds do not establish account capacity
or the 108-agent acceptance run. Future worker changes require another source
snapshot, wheel build, image build, and installed-worker check.
