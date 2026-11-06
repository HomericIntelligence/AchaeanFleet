# AchaeanFleet — Pinned Tool Versions

All agent tool versions are pinned for reproducible builds. Base-image pins
(`bases/Dockerfile.*`) live in `versions.yml` and are written into each
Dockerfile's generated `ENV <TOOL>_VERSION` block by
`scripts/render_version_pins.py`; `tests/test_version_pins.py` fails if the two
drift. Vessel pins are still declared inline in their Dockerfile.

Versions verified: **2026-11-06**

---

## Vessel tool versions

| Vessel | Package / Binary | Pinned version | Registry / Releases |
|--------|-----------------|----------------|---------------------|
| `claude` | `@anthropic-ai/claude-code` | `2.1.101` | <https://www.npmjs.com/package/@anthropic-ai/claude-code> |
| `claude` | `gh` (GitHub CLI) | `v2.89.0` | <https://github.com/cli/cli/releases> |
| `aider` | `aider-chat` | `0.82.3` | <https://pypi.org/project/aider-chat/> |
| `ampcode` | `@sourcegraph/amp` | `0.0.1775866026-gd3abf3` | <https://www.npmjs.com/package/@sourcegraph/amp> |
| `cline` | `cline` | `2.14.0` | <https://www.npmjs.com/package/cline> |
| `codebuff` | `codebuff` | `1.0.638` | <https://www.npmjs.com/package/codebuff> |
| `codex` | `@openai/codex` | `0.120.0` | <https://www.npmjs.com/package/@openai/codex> |
| `goose` | Goose CLI binary | `v1.30.0` | <https://github.com/block/goose/releases> |
| `opencode` | OpenCode binary | `v1.4.3` | <https://github.com/sst/opencode/releases> |
| `worker` | `yq` binary | `v4.52.5` | <https://github.com/mikefarah/yq/releases> |

## Base image tool versions

| Base image | Package | Pinned version | Registry |
|-----------|---------|----------------|----------|
| `minimal`, `python` | `yarn` | `1.22.22` | <https://www.npmjs.com/package/yarn> |
| `python` | `pip` | `26.0.1` | <https://pypi.org/project/pip/> |

---

## How to check for updates

```bash
# npm packages
npm show @anthropic-ai/claude-code version
npm show @sourcegraph/amp version
npm show @openai/codex version
npm show cline version
npm show codebuff version
npm show yarn version

# pip packages
pip index versions aider-chat
pip index versions pip

# GitHub release binaries
# Replace <owner>/<repo> with the values in the table above
curl -sL https://api.github.com/repos/<owner>/<repo>/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])"
```

## How to bump a version

1. Update `tools.<name>.version` in `versions.yml`.
2. For a base-image tool, run `pixi run python scripts/render_version_pins.py`
   to rewrite the generated blocks; for a vessel tool, edit that Dockerfile.
3. Update the table in this file.
4. Run `python3 -m pytest tests/ -v` — all tests should still pass.
5. Open a PR with the bump.
