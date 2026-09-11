# Dedicated Fleet image checks

The implementation for [issue #797](https://github.com/HomericIntelligence/AchaeanFleet/issues/797)
is wired in [fleet-images.yml](../../.github/workflows/fleet-images.yml). Its first
actual BuildKit/runtime runs remain pending. The legacy vessel matrix does not
validate Fleet images, and passing contract tests cannot substitute for this job.

## Inputs and job boundaries

1. A trusted package job checks out one reviewed, immutable Hephaestus commit,
   builds its actual worker wheel, and supplies a complete hash-locked Python
   3.13 wheelhouse for each Linux architecture. Retain the exact source manifest,
   wheel digest, and package-job evidence. An arbitrary source SHA attached to a
   wheel is insufficient evidence that the wheel came from that source.
2. An image job consumes those artifacts plus reviewed platform-specific Node,
   Python, and BuildKit scanner manifest digests. Run separate `linux/arm64` and
   `linux/amd64` jobs on supported builders. Use read-only repository permissions;
   do not supply provider, OpenBao, controller, or registry-write credentials.
3. Build only the `worker` and `build-tools` targets through the existing recipes.
   Each matrix entry owns a fresh output directory. Keep job concurrency bounded
   by runner capacity; do not assume a host can run the entire matrix at once.

The job runs on native amd64 and arm64 Linux runners. It reads the reviewed
source/base/scanner pins in `ci/inputs.json`, archives that exact Hephaestus commit,
builds its wheel with `ci/build-requirements.txt`, and downloads each platform's
hash-locked runtime closure. Worktree changes and private files are excluded from
the Hephaestus source archive. A compatible Buildx builder and native Podman
runtime are prerequisites for the local equivalent:

```bash
just test-fleet-ci
just fleet-ci run --platform "$FLEET_PLATFORM" \
  --source "$HEPHAESTUS_CHECKOUT" --output "$FLEET_CI_OUTPUT" \
  --engine /usr/bin/podman
```

## Required runtime and artifact checks

Use `plan` to inspect commands without creating output. Use `prepare` to build
only the wheel/bundle; `build` continues that prepared output through both image
targets and runtime checks. Every new preparation requires a fresh output path.
BuildKit is pinned to verified upstream v0.33.0 registry bytes and capped at two
CPUs/two GiB using its [documented driver limits](https://docs.docker.com/build/builders/drivers/docker-container/).

The runtime job consumes the exact verified OCI image configuration identity and
the [packaging probe](ci/runtime_probe.py). It checks the pinned Codex version,
worker initialization and inventory, private storage, nonroot execution, resource
limits, orderly shutdown, and refusal of admission without the required execution
boundary. It uses empty authentication storage and synthetic identities only.
It never starts a model turn or changes account authentication. Each disposable
container has one CPU, one GiB, 128 PIDs, no network, a read-only root, dropped
capabilities, and fresh workspace/state mounts. The probe checks actual effective
capabilities and no-new-privileges; the host retains engine resource inspection.
The build-tools check executes a benign `just` recipe. Cleanup requires the
persisted random ownership label, exact image/CID, and successful removal readback.

Archive the generated OCI bytes, raw builder metadata, content-verification result,
SBOM and provenance attestations, and unedited runtime output. Fail the job on
missing predicates, mismatched hashes, unexpected runtime behavior, or incomplete
cleanup. A standalone SPDX scan does not substitute for the attestation check.

The smoke-matrix test guards Fleet's separate native jobs and actual run command.
Registry promotion remains a separate approved
step that preserves the verified image and attestations. Neither these synthetic
checks nor a passing legacy matrix establishes cluster execution or Fleet capacity.
