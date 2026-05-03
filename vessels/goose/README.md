# Goose Vessel

Goose is a Block AI agent that runs as part of the AchaeanFleet mesh.

## Version Upgrade Procedure

This vessel pins a specific Goose release version and its cryptographic checksums for both AMD64
and ARM64 architectures.

### Current Version

See `Dockerfile` for the current `GOOSE_VERSION`, `GOOSE_AMD64_SHA256`, and `GOOSE_ARM64_SHA256` values.

### Where to Find Release Checksums

Goose releases are published at: <https://github.com/block/goose/releases>

Each release includes:

- `goose-x86_64-unknown-linux-gnu.tar.gz` (AMD64)
- `goose-aarch64-unknown-linux-gnu.tar.gz` (ARM64)
- SHA256 checksums in the release notes or downloadable checksum files

### Updating to a New Version

1. Visit <https://github.com/block/goose/releases> and select the target version
1. Copy the SHA256 checksums for both AMD64 and ARM64 archives
1. Update `Dockerfile`:
   - Change `GOOSE_VERSION=X.Y.Z` to the new version
   - Update `GOOSE_AMD64_SHA256=<new-amd64-hash>`
   - Update `GOOSE_ARM64_SHA256=<new-arm64-hash>`

### Verify Locally Before PR

Build the image with the new version to ensure it installs correctly:

```bash
# From the AchaeanFleet root directory
docker build -f vessels/goose/Dockerfile \
  --build-arg BASE_IMAGE=achaean-base-minimal:latest \
  -t achaean-goose:test .
```

If the build succeeds, the checksums are correct and Goose is properly installed. You can then verify the binary:

```bash
docker run --rm achaean-goose:test goose --version
```

Once verified, open a PR with the updated `Dockerfile`.
