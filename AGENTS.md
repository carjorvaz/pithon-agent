# Agent Guide

Pithon is a standard-library-only Python coding-agent harness. Correctness, confinement, and portability outrank feature count.

## Map

- `pithon/agent.py`: provider-independent message/tool loop and stable system prefix.
- `pithon/provider.py`: HTTP/API boundary and DeepSeek response parsing.
- `pithon/policy.py`: workspace confinement and blocked paths.
- `pithon/tools.py`: tool schemas and filesystem implementations.
- `pithon/redaction.py`: defense-in-depth provider-output redaction.
- `pithon/session.py`: opt-in local JSONL persistence.
- `pithon/cli.py`: human approvals and process wiring.
- `pithon/probe.py`: non-destructive constrained-runtime characterization.
- `ARCHITECTURE.md`: dependency direction and invariants.
- `SECURITY.md`: threat model and non-goals.
- `docs/`: design decisions and explicitly marked drafts.

## Invariants

1. Runtime imports remain Python standard library only.
2. Provider data is parsed at the boundary; guessed response shapes are bugs.
3. Tools cannot escape the selected workspace or follow symlinks.
4. Reads never bypass blocked secret paths. Redaction is only defense in depth.
5. A mutation is applied only after its entire diff was displayed and approved.
6. API keys come from process input/environment, never repository files.
7. Provider messages remain append-only within a turn so prefix caching works.
8. DeepSeek reasoning content is retained for tool-call turns and dropped from final non-tool turns.
9. Session transcripts remain opt-in and ignored by Git.
10. No command-execution tool lands without a separate policy and platform contract.

## Checks

Run focused tests after every behavioral change:

```sh
python3 -m unittest discover -s tests -v
```

Run `python3 -m pithon.probe` when changing portability or subprocess assumptions. Add a regression test for each boundary bug. Keep documentation short and point to the owning source rather than duplicating it.
