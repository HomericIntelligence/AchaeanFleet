# Invoke through the admitted Hephaestus tool route, with its fixed environment.
prepare SNAPSHOT IMAGE:
    python3 -I -B {{quote(justfile_directory() + "/prepare_workspace.py")}} --snapshot-sha256 {{quote(SNAPSHOT)}} --image-digest {{quote(IMAGE)}}

# Preparation and normal repository checks share the same private environment.
check SNAPSHOT IMAGE: (prepare SNAPSHOT IMAGE)
    #!/bin/sh
    set -eu
    env -i PATH=/usr/bin:/bin HOME="$HOME" \
        XDG_CONFIG_HOME="$XDG_CONFIG_HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" \
        XDG_DATA_HOME="$XDG_DATA_HOME" TMPDIR="$TMPDIR" TMP="$TMP" \
        UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/bin/python3 \
        UV_CACHE_DIR="$XDG_CACHE_HOME/athena-uv" UV_PROJECT_ENVIRONMENT=/workspace/.venv \
        UV_LINK_MODE=copy RAYON_NUM_THREADS=1 \
        just --working-directory /workspace --justfile /workspace/justfile all
