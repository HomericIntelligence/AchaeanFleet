# Rebuild the Claude vessel's GitHub CLI

The Claude vessel builds GitHub CLI from upstream commit
`45437bc7eeeb3359bbfddd1742f79de7652fd3e2` (version 2.100.0), with
`golang.org/x/mod` updated to 0.40.0. Its version is `2.100.0-fleet.1` to identify
this dependency change. The upstream release still contains version 0.39.0.

[GO-2026-6180](https://pkg.go.dev/vuln/GO-2026-6180) and
[GO-2026-6179](https://pkg.go.dev/vuln/GO-2026-6179) identify the module fixes and
also require a corrected Go toolchain. The build uses Go 1.26.8. The builder
downloads fresh, checksum-verified toolchain and source archives; Go verifies
module content against the declared `go.sum` hashes. The final vessel receives
only the executable and its actual `go version -m` inventory.

1. Review the upstream source commit and the required dependency correction.
   Keep the source archive SHA256, both Linux toolchain SHA256 values, and both
   module hashes in `vessels/claude/Dockerfile` aligned with the actual downloaded
   bytes. The official toolchain checksums are in the
   [Go release metadata](https://go.dev/dl/?mode=json); module records come from
   the [Go checksum database](https://sum.golang.org/lookup/golang.org/x/mod@v0.40.0).
2. Build the base images with `just build-bases`, then the Claude vessel with
   `just build-vessel claude`, under the operator's resource limits. The build
   must retain the fixed module in the compiled executable and successfully run
   `gh --version`. The embedded module inventory is available at
   `/usr/share/doc/gh/fleet.buildinfo` in the resulting image.
3. Run the existing required image scan and smoke jobs against that actual image.
   Preserve the complete inventory and scanner output. A successful compilation
   does not establish a clean vulnerability scan. The two findings do not have
   an exception, and the scanner policy remains unchanged.
4. Build the remaining enabled vessels with `just build-all` and run
   `just verify`. That recipe checks the presence of all nine legacy vessel
   images, including aider; the required scan and smoke jobs provide separate
   runtime and vulnerability evidence.

Remove the local dependency patch only after an upstream release includes the
fix and the replacement executable passes the same image gates. Do not copy a
developer's authenticated CLI configuration or its host home into either stage.
