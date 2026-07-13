# Pithon Agent

Pithon is a dependency-free Python coding-agent harness for constrained environments. It runs with the standard library on ordinary macOS/Linux Python and targets [a-Shell](https://github.com/holzschu/a-shell) on iOS; the real-device port is not yet verified.

It is an independent project inspired by [Pi](https://github.com/earendil-works/pi): a small provider loop, explicit tools, append-only messages, and repository-local control. Pithon does not currently claim Pi extension, configuration, or session-format compatibility.

## Why

Most coding agents assume Node, native wheels, a desktop shell, or a large dependency graph. Pithon asks a narrower question: how much useful coding-agent machinery can fit in Python's standard library and still survive a hostile runtime?

Current scope:

- DeepSeek Chat Completions with thinking-mode tool calls;
- automatic DeepSeek prefix-cache accounting;
- confined `list_files`, `read_file`, and literal `search_text` tools;
- diff-reviewed `edit_file` and `write_file` tools;
- opt-in mode-`0600` JSONL sessions;
- a non-destructive a-Shell capability probe;
- no autonomous command execution.

## Run

Requires Python 3.9 or newer and a DeepSeek API key. From a clone:

```sh
python3 -m pithon --workspace /path/to/project
```

If `DEEPSEEK_API_KEY` is absent in an interactive terminal, Pithon asks for it without storing it.

For terminals whose hidden-input mode is incompatible with `getpass`, use
`--consume-api-key-file PATH`. Pithon opens the file without following
symlinks, requires current-user ownership with no group/other permissions,
reads it once, and deletes it before the first provider request. Keep this
temporary file outside the workspace.

Environment configuration is also supported:

```sh
export DEEPSEEK_API_KEY='...'
python3 -m pithon --model deepseek-v4-flash --workspace .
```

Avoid placing the key in a committed `.env` or repository file. Pithon deliberately does not load dotenv files.

One-shot mode:

```sh
python3 -m pithon --workspace . 'inspect this project and identify the smallest useful next change'
```

Opt-in continuity:

```sh
python3 -m pithon --workspace . --session ~/.pithon/sessions/project.jsonl
```

## a-Shell

Clone or copy the repository into an a-Shell-accessible directory, then run:

```sh
python3 -m pithon.probe
python3 -m pithon --workspace .
```

The probe reports whether the device Python can bind a loopback listening socket, invoke a-Shell commands through `subprocess`, and whether the bundled SSH client advertises `-R`. Those capabilities and one foreground reverse-tunnel round trip are verified on an iPhone 13 running iOS 26.5.2 with a-Shell's Python 3.13/OpenSSH 8.5. Background survival remains unverified because iOS may suspend a-Shell.

The real-device reverse-tunnel probe keeps both loopback listener and outbound
SSH client under one Python process:

```sh
python3 -m pithon.tunnel_probe --reverse-to cjv@MAC_TAILNET_IP --identity .ssh/pithon_mac
```

It exposes only a fixed success string on phone loopback; it is not a
remote-control service. Keep a-Shell foregrounded. Do not treat the tunnel as
persistent.

## Security model

At startup, Pithon displays and asks approval for one workspace. After approval, the model may read non-blocked files within that root. Common credential paths and names are denied; symlinks and parent traversal are rejected. Provider-bound tool output receives best-effort redaction. Every write displays its complete bounded diff and requires a separate `y` confirmation.

Redaction is not an authorization boundary. Do not point Pithon at workspaces containing secrets or sensitive personal material. See [SECURITY.md](SECURITY.md).

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m pithon.probe
```

Start with [AGENTS.md](AGENTS.md) for the repository map and [ARCHITECTURE.md](ARCHITECTURE.md) for enforced boundaries.

## License

AGPL-3.0-only. See [LICENSE](LICENSE).
