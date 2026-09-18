# Cline vessel dependency closure

This legacy sidecar vessel retains Cline 2.14.0 and the Node base's existing
entrypoint, agent user and health check. Its executable is linked from the
private installation prefix `/opt/achaean-cline` into `/usr/local/bin/cline`.
It does not implement the standalone Fleet worker protocol.

Cline depends on `ink-picture` 1.3.x, whose Sharp dependency range selects
0.34.x. [GHSA-rgj7-g3m4-5g8c](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c)
requires Sharp 0.35.4, with the corrected libheif 1.23.2. The root package
override selects exactly that version while retaining the existing Cline CLI.
`package-lock.json` records the complete npm dependency closure, including the
amd64 and arm64 native payloads. `npm ci` checks the recorded integrity values.

The Docker build runs `cline --version` and `verify-runtime.cjs`. The latter
checks the installed native Sharp/libheif versions and exercises the
metadata, resize and raw-buffer operations used by `ink-picture`. It uses only
a small generated image. No model, account, filesystem input or network request
is needed for this probe.

Run `just build-vessel cline`, then the repository's normal image smoke and
Trivy gates. A passing lockfile audit does not replace a scan of the actual
image or the runtime probe. Keep the existing scanner severity, exception and
enabled-vessel policies. Remove the override only after the selected upstream
Cline dependency closure includes the fix and those same gates pass.
