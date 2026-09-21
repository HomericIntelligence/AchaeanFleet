# Athena offline tool image

`achaean-athena-tools` supplies the contained tools for a Hephaestus worker
handling Athena work. It targets **Linux ARM64**. It does not provide a worker,
an authenticated app-server, or a running agent service. Cluster support requires
verification of each execution host's architecture and resources.

AchaeanFleet owns the image definition, scan and publication. Hephaestus owns
the worker, authenticated Codex app-server, workspace admission and execution
lifecycle. Agamemnon retains task decisions; Odysseus displays observed work and
logs. This image adds no queue, claim, credentials or orchestration authority.

The [central pins](../../versions.yml) bind Python 3.13.15, Git, just 1.51.0,
uv 0.12.10, Codex 0.153.4 and Athena's dependency files at
`3ba737517e2234729bcc7eb45b6ec0e3531efdf0`. Existing Codex and Python vessels
retain their own versions.

## Execution contract

The existing worker starts `/opt/codex-bin/codex exec-server --listen stdio`.
The official Codex payload and its resources are retained for that endpoint;
there is no app-server or authentication home in the image. The image's default
`env` entrypoint also permits explicit tool commands for isolated CI checks.
Hephaestus supplies its fixed exec-server entrypoint during environment attachment.

Python, Git, just and uv are available on the unchanged `/usr/bin:/bin` PATH.
Image ENV values are not required for execution: the worker clears them and
provides private HOME, XDG and temporary directories below `/workspace/.fleet-runtime`.
Keep its read-only root, no network, UID 1000, capabilities, permissions, mount
allowlist and initial 1 CPU / 1 GiB / 128 PID limits unchanged.

## Build and qualification

1. Prepare only public inputs in an explicit context directory:

   ```bash
   just athena-tools-inputs /tmp/athena-tools-build
   ```

   The script verifies each cached or downloaded archive and dependency file.
   A wrong cached digest fails. It never silently replaces an unexpected input.
   Each download has a 180-second deadline; no image or environment starts here.
   Existing verified inputs can be placed in the context's `inputs/` directory.

2. Obtain an exclusive Linux ARM64 build slot. Check the actual engine storage
   and context filesystems: initially require 14 GiB free, stop at 10 GiB free
   or 4 GiB growth. These are initial operating budgets, not measured guarantees.
   Then use the bounded build recipe:

   ```bash
   CONTAINER_CMD=podman just athena-tools-build /tmp/athena-tools-build
   ```

   The image build has a 30-minute deadline, 2 CPU quota, 2 GiB memory with no
   additional swap, and a requested `nproc=512` limit. Verify the effective
   builder controls: an nproc limit alone is not a cgroup PID cap for a root
   build process. The operator owns the VM, storage
   monitoring and confirmation that timeout cleanup has stopped the build.
   An unsupported resource flag or Python link collision fails the build.
   No limit is weakened automatically.

3. Complete the repository CI and image scanner gates. The image builder
   requires wheels with `uv sync --locked --no-build`; it cannot resolve an
   unrecorded source-build toolchain. It records the complete cache digest,
   dependency hashes, platform and observed Python/uv/Git versions in
   `/opt/athena/inputs.json`. Ordinary apt signature and expiry checks remain
   enabled for the pinned Debian snapshot. Update expired or vulnerable pins
   through review; do not disable their gates.

4. Supply a fresh admitted validation workspace and the actual source snapshot
   SHA-256 and selected image digest. Through the unchanged Hephaestus tool
   route, execute:

   ```bash
   just --justfile /opt/athena/workspace.just check SNAPSHOT_SHA256 IMAGE_DIGEST
   ```

   `prepare` is available separately if validation will follow in another
   command. It verifies all dependency files and the immutable cache seed,
   copies that seed into `$XDG_CACHE_HOME/athena-uv`, and runs a real locked
   offline sync into `/workspace/.venv`. The cache copy is private and writable;
   the image seed stays unchanged. Existing outputs require reconciliation in
   a new workspace; preparation never deletes them to conceal a partial run.

5. Retain the preparation receipt at
   `/workspace/.fleet-runtime/athena-preparation.json`. It binds the supplied
   snapshot and image identifiers, upstream revision, dependency hashes, cache
   and environment paths. The trusted outer worker must bind those identifiers
   to the actual admission and image. This receipt grants no authority and is
   not an independent validation result.

6. Run the unchanged Athena `just all` with the same explicit private offline
   environment; the `check` recipe performs both steps. Subsequent validation
   commands must retain `UV_OFFLINE=1`, `UV_PYTHON_DOWNLOADS=never`,
   `UV_PYTHON=/usr/bin/python3`, `UV_PROJECT_ENVIRONMENT=/workspace/.venv` and
   `UV_CACHE_DIR=$XDG_CACHE_HOME/athena-uv`. Do not use `--no-sync`, a lock bypass
   or another environment to make validation pass. Publication stays outside
   the container. Athena #265 implementation and review remain a separate task.

## Repository registration and evidence

The image has rows in the existing build, smoke and publication matrices.
They use native ARM64 runners. The build job scans and exports one artifact;
the smoke job loads that artifact, runs the binary check and unchanged Athena
`just all` with a fresh private environment and no network; publication loads
the same artifact after both jobs pass. Registry tag verification includes it.

This is a standalone tool image, following the standalone build distinction
already used by `hello-world`. The agent-type Compose service, workspace mapping
and Dagger agent matrix instructions do not apply: no new agent service is
created. Use `just athena-tools-build` for this explicitly admitted ARM64 build;
the existing `build-all`/Dagger agent set remains separate. The smoke drift guard
still covers this vessel; it is not added to an exclusion list.

`just athena-tools-test` runs the real offline workspace tests. The existing
Python suite also collects them. Missing uv fails visibly. Hosted tests install
checksum-verified uv 0.12.10 for AMD64; the canonical CI Containerfile provides
the same version at `/usr/local/bin/uv` within its existing AMD64 environment.
The tool image supplies the separately verified ARM64 binary at `/usr/bin/uv`.
Native tests with another host uv or pytest version must disclose that limit
and cannot replace the pinned CI environment.

CI tool commands alone do not qualify Hephaestus attachment, exec-server traffic
or causal disposal. Those require an independent run through the unchanged
worker route before issue admission. No native test count establishes an image,
provider, dashboard or cluster acceptance result.
