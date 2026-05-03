# AchaeanFleet — Pinned Tool Versions

All agent tool versions are pinned in their respective Dockerfiles for
reproducible builds. Update the version here and in the Dockerfile together.

Versions verified: **2026-04-10**

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

1. Update the version in the relevant Dockerfile (`vessels/<name>/Dockerfile` or `bases/Dockerfile.<name>`).
2. Update the table in this file.
3. Run `python3 -m pytest tests/ -v` — all tests should still pass.
4. Open a PR with the bump.
