# Security

Pithon sends approved prompts and file excerpts to a remote model and lets that model propose local filesystem operations. Treat the provider and all repository content as untrusted.

## Current guarantees

- One canonical workspace root per process.
- Relative paths only; no parent traversal or symlink following.
- Common credential, VCS metadata, and secret filenames are blocked.
- Provider-bound tool text is bounded and receives best-effort redaction.
- Writes use same-directory temporary files plus atomic replacement.
- Complete diffs are displayed before mutation; oversized diffs fail closed.
- Every mutation requires a fresh user confirmation.
- API keys are read from an interactive hidden prompt or process environment.
- No shell/command tool, inbound server, plugin loading, or autonomous network fetch tool.
- Session persistence is opt-in, mode `0600`, and ignored by Git.
- Provider output and rounds are bounded.

## Non-guarantees

Redaction cannot recognize every credential. Workspace approval is not a sandbox against files that are sensitive but do not match blocked patterns. A model may misunderstand code, propose destructive edits, or reproduce provider-visible data in its response. Atomic replacement does not provide multi-file transactions.

Do not use Pithon on secret-bearing or regulated workspaces. Review every mutation. Keep version-control recovery available.

## DeepSeek boundary

Direct DeepSeek use is a deliberate data-export decision. Its published policy permits collection and retention of inputs and describes storage in China. Pithon displays this boundary before workspace approval and exposes cache hit/miss metrics, but cannot control provider retention.

## Reverse-tunnel experiment

The a-Shell reverse-tunnel experiment is not part of the trusted runtime. If device probes prove it viable, any prototype must:

- initiate outbound from the phone;
- bind both local service and Mac reverse listener to loopback;
- use a random one-session capability token;
- expose structured bounded operations, not a raw shell;
- retain local write/command confirmations;
- assume immediate failure when iOS backgrounds the app.

## Reporting

Open a GitHub security advisory rather than a public issue for vulnerabilities that could expose credentials or bypass workspace/mutation policy.
