# Prepare and distribute a Fleet image

This runbook prepares an artifact for reviewed promotion. It does not authorize a
registry push, Slurm allocation, pool enablement, or agent task. Follow the
[architecture boundary](../fleet-images.md) and
[image build contract](../../vessels/fleet/README.md).

1. Select reviewed immutable AchaeanFleet and Hephaestus sources. Record file hashes
   for any intentionally dirty snapshot. Build the actual Hephaestus wheel with
   its package recipe and retain the build output, source manifest, wheel SHA256,
   and complete target-specific Python 3.13 dependency closure. Inspect the wheel's
   installed entrypoint rather than reusing an old editable script.
2. Resolve compatible platform-specific Node, Python 3.13 slim-bookworm, and
   BuildKit scanner manifests. Retain upstream metadata and actual digest
   verification. Prepare a closed bundle and review the build command:

   ```bash
   just fleet-image-bundle \
     --platform "$FLEET_PLATFORM" --wheelhouse "$FLEET_WHEELHOUSE" \
     --requirements "$FLEET_REQUIREMENTS" \
     --hephaestus-revision "$HEPHAESTUS_SOURCE_REVISION" \
     --output "$FLEET_BUNDLE"
   just fleet-image-plan \
     --platform "$FLEET_PLATFORM" --target worker \
     --bundle "$FLEET_BUNDLE" --node-base "$FLEET_NODE_BASE" \
     --runtime-base "$FLEET_PYTHON_BASE" \
     --sbom-generator "$FLEET_SBOM_GENERATOR" --output "$FLEET_IMAGE_OUTPUT"
   ```

3. Check builder disk, memory, and concurrent work before running the same image
   arguments with `just fleet-image-build`. Use a fresh output directory for every
   target/platform. Retain raw failures. Require generated OCI bytes, verified
   content, and actual SBOM/provenance predicates before treating the BuildKit gate
   as passed. A standalone Syft SPDX scan of a Podman export records useful package
   evidence but cannot replace those predicates.
4. Run the reviewed no-auth runtime checks against that exact image. Verify Codex
   0.153.4, the installed worker entrypoint, nonroot execution, private storage,
   initialization/inventory, current admission refusal, resource limits, and
   orderly cleanup. Inspect the source checkpoint: an older image's successful
   check does not cover later supervisor changes. Retain actual commands and raw
   output independently from source documentation.
5. Scan the actual final image and review its dependency findings. When changing a
   vulnerability suppression, confirm the binary present in the built image, not
   only the downloaded release. The legacy worker's conditional `yq` installation
   can retain an inherited executable. Expired exceptions must not silently renew.
6. Choose the approved distribution path. For a registry, preserve the verified
   manifests and attestations during publication and read the remote digest back.
   For HPC file staging, first generate a real compatible SquashFS artifact using
   an inspected Enroot converter and the exact source image. Record converter
   revision, any patch, executed arguments, entrypoint/environment mapping, and
   resulting file checksum. M1/M2 Enroot 3.5.0 does not accept `oci-archive://` or a
   Docker archive file as an import scheme. Do not present an archive as a `.sqsh`.
7. Transfer only approved artifact files to a dedicated staging directory. The HPC
   operator verifies checksums after transfer, source-image linkage, and explicit
   Pyxis launch requirements: nonroot identity, private mounts, declared CPU/memory
   and zero-GPU requests where required, network/namespace policy, timeout, and
   cleanup. OCI `USER` metadata alone does not establish these properties. Keep
   login-node commands transient; no permanent Fleet service belongs there.
8. Supply the verified distribution reference and evidence to the approved
   reconciliation process. Myrmidons records desired configuration; Agamemnon
   decides admission. Worker journals cannot enable their own pool. Keep missing
   image references unset and pools disabled while runtime, transport, or ownership
   checks remain unresolved. Performance testing starts only through the planned
   Scylla/Argus gates; a successful packaging check does not count as issue work.

## Existing private packaging checkpoint

The 2026-09-11 local checkpoint contains arm64 and amd64 OCI exports and independent
SPDX scans. An amd64 SquashFS conversion and separately packaged Keystone gateway
were also built. These artifacts remain private and were not pushed or admitted.
Their source/receipt inventory must accompany any later promotion proposal.

The first Enroot conversion returned failure after generating a filesystem because
upstream cleanup removed its current directory before deleting its temporary
container. The preserved second capture used a recorded cleanup-order correction
and completed successfully. That correction is part of its converter identity.

The separately built gateway carries its `libnats` dependency and uses
`$ORIGIN/../lib` for both binary and library RUNPATH, without an empty current-directory
entry. Its remaining OpenSSL/glibc/C++ runtime dependencies were checked in the
declared worker base. This does not establish compatibility with an arbitrary login
host or prove an authenticated Keystone connection. Neither that gateway nor the
NATS test fixture is included in the Fleet worker image by the present Dockerfile.
