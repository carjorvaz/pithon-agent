"""Small interactive CLI shared by macOS, Linux, and a-Shell."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import stat
from pathlib import Path
from typing import Sequence

from .agent import Agent, AgentError
from .policy import PolicyError, WorkspacePolicy
from .provider import DeepSeekProvider, ProviderError
from .session import SessionError, SessionLog
from .tools import ToolRegistry


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _report_usage(usage: dict[str, int]) -> None:
    if not usage:
        return
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", 0)
    total = usage.get("total_tokens", 0)
    print(f"[usage total={total} cache_hit={hit} cache_miss={miss}]", file=sys.stderr)


def _consume_api_key_file(path: Path) -> str:
    expanded = path.expanduser()
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise ValueError("this platform cannot safely consume a key file without following symlinks")
    flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(expanded, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("API key file must be a regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ValueError("API key file must not be readable or writable by group/others")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ValueError("API key file must be owned by the current user")
        if not 1 <= metadata.st_size <= 4096:
            raise ValueError("API key file has an invalid size")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            api_key = handle.read(4097).strip()
        if not api_key:
            raise ValueError("API key file is empty")
        current = expanded.lstat()
        if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError("API key file changed while it was being consumed")
        expanded.unlink()
        return api_key
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pithon",
        description="Dependency-free coding-agent harness for constrained environments.",
    )
    parser.add_argument("prompt", nargs="?", help="run one turn instead of opening the prompt loop")
    parser.add_argument("--workspace", default=".", help="confined workspace root (default: current directory)")
    parser.add_argument("--model", default=os.environ.get("PITHON_MODEL", "deepseek-v4-flash"))
    parser.add_argument("--base-url", default=os.environ.get("PITHON_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--no-thinking", action="store_true", help="disable DeepSeek thinking mode")
    parser.add_argument("--max-effort", action="store_true", help="request max rather than high reasoning effort")
    parser.add_argument("--max-rounds", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=8192, help="maximum output tokens per provider call")
    parser.add_argument("--session", type=Path, help="opt in to a local mode-0600 JSONL session")
    parser.add_argument(
        "--consume-api-key-file",
        type=Path,
        help="read a mode-0600 API key file once and delete it before the provider call",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        api_key = (
            _consume_api_key_file(args.consume_api_key_file)
            if args.consume_api_key_file
            else os.environ.get("DEEPSEEK_API_KEY")
        )
    except (OSError, ValueError) as error:
        print(f"API key file rejected: {error}", file=sys.stderr)
        return 2
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("DeepSeek API key (used for this process only): ").strip()
    if not api_key:
        print(
            "No DeepSeek API key was provided.",
            file=sys.stderr,
        )
        return 2

    try:
        workspace = Path(args.workspace).expanduser().resolve(strict=True)
        print(f"Workspace: {workspace}")
        print("Provider: file excerpts and prompts approved for this session will be sent to DeepSeek.")
        if not _confirm("Allow model tools to read non-secret files under this workspace? [y/N] "):
            print("Read access declined.", file=sys.stderr)
            return 3
        policy = WorkspacePolicy(workspace, _confirm)
        registry = ToolRegistry(policy)
        session = SessionLog(args.session) if args.session else None
        messages = session.load() if session else None
        provider = DeepSeekProvider(
            api_key,
            model=args.model,
            base_url=args.base_url,
            thinking=not args.no_thinking,
            reasoning_effort="max" if args.max_effort else "high",
            max_tokens=args.max_tokens,
        )
        agent = Agent(
            provider,
            registry,
            messages=messages,
            max_rounds=args.max_rounds,
            session=session,
            report_usage=_report_usage,
        )
    except (OSError, PolicyError, SessionError, ValueError) as error:
        print(f"startup failed: {error}", file=sys.stderr)
        return 2

    if args.prompt:
        return _run_turn(agent, args.prompt)

    print("Pithon ready. /exit quits. No command-execution tool is enabled.")
    while True:
        try:
            prompt = input("pithon> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if prompt.strip() in {"/exit", "/quit"}:
            return 0
        if not prompt.strip():
            continue
        status = _run_turn(agent, prompt)
        if status != 0:
            return status


def _run_turn(agent: Agent, prompt: str) -> int:
    try:
        answer = agent.run(prompt)
    except (AgentError, ProviderError, OSError, ValueError) as error:
        print(f"turn failed: {error}", file=sys.stderr)
        return 1
    print(answer)
    return 0
