# Proposed dedicated Fleet image checks

Status: Proposed. This is the review input for
[issue #797](https://github.com/HomericIntelligence/AchaeanFleet/issues/797),
not an installed workflow. Changes under `.github/workflows/` require human
review before editing. The legacy vessel matrix does not validate Fleet images.

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

The image job executes these existing commands with its reviewed input paths:

```bash
just test-fleet-images
just fleet-image-bundle \
  --platform "$FLEET_PLATFORM" --wheelhouse "$FLEET_WHEELHOUSE" \
  --requirements "$FLEET_REQUIREMENTS" \
  --hephaestus-revision "$HEPHAESTUS_SOURCE_REVISION" \
  --output "$FLEET_BUNDLE"
just fleet-image-build \
  --platform "$FLEET_PLATFORM" --target "$FLEET_TARGET" \
  --bundle "$FLEET_BUNDLE" --node-base "$FLEET_NODE_BASE" \
  --runtime-base "$FLEET_PYTHON_BASE" \
  --sbom-generator "$FLEET_SBOM_GENERATOR" --output "$FLEET_IMAGE_OUTPUT"
```

## Required runtime and artifact checks

The runtime job consumes the exact built image identity and a reviewed Hephaestus
probe from the same source checkpoint. It must check the pinned Codex version,
worker initialization and inventory, private storage, nonroot execution, resource
limits, orderly shutdown, and refusal of admission without the required execution
boundary. It uses empty authentication storage and synthetic identities only.
It must neither start model work nor change account authentication. The reviewed
probe and isolated launch recipe are still required implementation inputs; the
image helper does not currently implement this job.

Archive the generated OCI bytes, raw builder metadata, content-verification result,
SBOM and provenance attestations, and unedited runtime output. Fail the job on
missing predicates, mismatched hashes, unexpected runtime behavior, or incomplete
cleanup. A standalone SPDX scan does not substitute for the attestation check.

Replace Fleet's pending legacy-matrix exclusion with a guard for its dedicated
jobs when reviewed CI wiring covers these build and runtime contracts.
Registry promotion remains a separate approved
step that preserves the verified image and attestations. Neither these synthetic
checks nor a passing legacy matrix establishes cluster execution or Fleet capacity.
