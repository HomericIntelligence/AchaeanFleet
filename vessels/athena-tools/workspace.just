# Invoke through the admitted Hephaestus tool route, with its fixed environment.
prepare SNAPSHOT IMAGE:
    python3 -I -B {{quote(justfile_directory() + "/prepare_workspace.py")}} --snapshot-sha256 {{quote(SNAPSHOT)}} --image-digest {{quote(IMAGE)}}

# Preparation and normal repository checks share the same private environment.
#
# Scope: this recipe asserts that the image's offline environment is sound — the
# snapshot and digest bindings match the image, `uv sync --locked --offline`
# resolves from the baked cache, and Athena validates its own content on the
# prepared tree. That is what the image is responsible for.
#
# It deliberately does not run Athena's `test`, `static`, `markdownlint`,
# `workflow-check`, or `package`. Those run in Athena's own required checks on
# every change to Athena, and `all` aggregates them into one suite that cannot
# finish here: this job gives the container --cpus 1 --memory 1g --pids-limit
# 128 --network none on an emulated ARM64 runner, where the suite reached 19% in
# 16.6 minutes against a 20-minute step budget. Re-running it would be a slower,
# weaker duplicate of Athena's CI.
check SNAPSHOT IMAGE: (prepare SNAPSHOT IMAGE)
    #!/bin/sh
    set -eu
    # .fleet-runtime holds the offline uv cache that preparation copies here. Athena's
    # validator walks the workspace and reads every file it is not told to skip, so
    # without this it descends into that cache and fails on undecodable .so/.exe/.whl
    # payloads and on vendored library source it cannot reword. The setting names only
    # this runtime directory; authored content stays in scope.
    env -i PATH=/usr/bin:/bin HOME="$HOME" \
        XDG_CONFIG_HOME="$XDG_CONFIG_HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" \
        XDG_DATA_HOME="$XDG_DATA_HOME" TMPDIR="$TMPDIR" TMP="$TMP" \
        UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/bin/python3 \
        UV_CACHE_DIR="$XDG_CACHE_HOME/athena-uv" UV_PROJECT_ENVIRONMENT=/workspace/.venv \
        UV_LINK_MODE=copy RAYON_NUM_THREADS=1 \
        ATHENA_VALIDATE_IGNORED_PATHS=".fleet-runtime" \
        just --working-directory /workspace --justfile /workspace/justfile validate uv-pins
