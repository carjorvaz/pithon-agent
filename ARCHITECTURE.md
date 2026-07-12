# Architecture

Pithon is a small control system around an untrusted probabilistic planner. Its architecture makes provider, policy, and side-effect boundaries visible and testable.

```text
CLI/user approval
      │
      ▼
Agent loop ───────────────► ChatProvider
      │                       │
      ▼                       ▼
ToolRegistry              DeepSeek HTTP
      │
      ▼
WorkspacePolicy ─────────► confined filesystem
```

Dependency direction is one-way:

```text
redaction  policy  provider  session
     ▲       ▲        ▲        ▲
     └── tools ───────┘        │
           ▲                   │
           └──── agent ────────┘
                    ▲
                    └── cli
```

`probe` is independent diagnostic code and must not become a runtime prerequisite.

## Boundaries

### Provider

`ChatProvider.complete(messages, tools)` is the only model boundary. `DeepSeekProvider` owns HTTP, authentication, request limits, response-shape parsing, and normalized usage metrics. The agent loop does not import networking code.

The system prompt and ordered tool schemas are stable prefixes. Conversation messages append in order. DeepSeek's server-side prefix cache is observed through hit/miss metrics; Pithon does not maintain a client response cache.

### Policy

All model-proposed paths pass through `WorkspacePolicy`. It canonicalizes relative paths, rejects traversal and symlinks, denies common secret/metadata paths, and verifies containment. Filesystem tools never reconstruct their own path rules.

Workspace-level read approval is explicit at startup. Each mutation has a second approval after the complete diff is rendered. Oversized diffs are rejected rather than partially displayed.

### Tools

Tool schemas and implementations live together. Outputs are bounded JSON envelopes. Expected policy, decoding, and filesystem failures return tool errors so the model can adapt; unexpected programming errors remain visible during development.

There is intentionally no command tool. Adding one requires a separate design for argv-only execution, timeouts, output limits, platform capability differences, and confirmation semantics.

### Sessions

Sessions are opt-in append-only JSONL files outside the repository by default. They preserve exact provider messages needed for tool-call continuation, but are not a compatibility promise with Pi. Secret/session patterns are ignored by Git.

## Compatibility direction

Pithon follows Pi's useful conceptual seams: provider abstraction, agent loop, tools, append-only state, and a small interactive frontend. Compatibility should be earned with executable fixtures rather than claimed by naming. TypeScript extensions and Pi's TUI are explicit non-goals for the initial constrained runtime.

## Harness-engineering application

The repository applies the useful small-project subset of OpenAI's harness-engineering principles:

- `AGENTS.md` is a map, not an encyclopedia;
- durable decisions live beside executable code;
- boundaries are mechanical and regression-tested;
- diagnostics make platform capabilities legible;
- user-visible failures should identify the missing capability;
- new taste rules graduate into tests or policy rather than prompt bulk.
