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

If `DEEPSEEK_API_KEY` is absent in an interactive terminal, Pithon asks for it without storing it. Environment configuration is also supported:

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

The probe reports whether the device Python can bind a loopback listening socket, invoke a-Shell commands through `subprocess`, and whether the bundled SSH client advertises `-R`. Reverse tunnelling remains an experiment: iOS can suspend a-Shell whenever it leaves the foreground.

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
