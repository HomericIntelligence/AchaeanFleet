# AGENTS.md

This repository follows the [`agents.md`](https://agents.md) convention for
AI coding agents. The full agent guidance lives in [`CLAUDE.md`](./CLAUDE.md),
which is the canonical instruction file for Claude, Codex, Cursor, and any
other agentic coding tool that operates in this repo.

Until divergent per-tool guidance is needed, treat `CLAUDE.md` as the source of
truth for:

- Project overview and architectural intent
- Commands, build/test workflows, and `just` recipes
- Coding conventions and forbidden patterns
- Vessel layout and base-image relationships
- CI/CD expectations and security guards

If you are an AI agent: read [`CLAUDE.md`](./CLAUDE.md) first, then
[`README.md`](./README.md) for human-facing context, then
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contribution workflow.
