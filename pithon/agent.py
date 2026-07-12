"""The provider-independent tool-calling loop."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .provider import ChatProvider
from .session import SessionLog
from .tools import TOOL_SCHEMAS, ToolRegistry

SYSTEM_PROMPT = """You are Pithon, a careful coding agent operating in one confined workspace.
Use tools to inspect real files before making claims about them. Paths are relative to the workspace.
Prefer small, exact edits. Never request credentials or attempt to access blocked paths.
File mutations require user approval. If a tool returns an error or a declined mutation, adapt rather than claiming success.
There is no command-execution tool: tell the user exactly which focused check to run when verification is needed.
"""

UsageReporter = Callable[[dict[str, int]], None]


@dataclass
class UsageLedger:
    totals: dict[str, int] = field(default_factory=dict)

    def add(self, usage: dict[str, int]) -> None:
        for name, value in usage.items():
            self.totals[name] = self.totals.get(name, 0) + value


class AgentError(RuntimeError):
    """The agent could not safely complete its turn."""


class Agent:
    def __init__(
        self,
        provider: ChatProvider,
        tools: ToolRegistry,
        *,
        messages: list[dict[str, Any]] | None = None,
        max_rounds: int = 16,
        session: SessionLog | None = None,
        report_usage: UsageReporter | None = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be positive")
        self.provider = provider
        self.tools = tools
        self.max_rounds = max_rounds
        self.session = session
        self.report_usage = report_usage or (lambda usage: None)
        self.usage = UsageLedger()
        if messages:
            self.messages = list(messages)
        else:
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if self.session is not None:
                self.session.append(self.messages[0])
        if self.messages[0] != {"role": "system", "content": SYSTEM_PROMPT}:
            raise ValueError("session must begin with the current stable system prompt")

    def run(self, user_text: str) -> str:
        if not user_text.strip():
            raise ValueError("user message must not be empty")
        self._append({"role": "user", "content": user_text})

        for _ in range(self.max_rounds):
            completion = self.provider.complete(self.messages, TOOL_SCHEMAS)
            self.usage.add(completion.usage)
            self.report_usage(completion.usage)
            assistant = dict(completion.message)
            tool_calls = assistant.get("tool_calls") or []
            if not tool_calls:
                assistant.pop("reasoning_content", None)
                self._append(assistant)
                return assistant.get("content") or ""

            self._append(assistant)
            for tool_call in tool_calls:
                tool_message = self._execute_tool_call(tool_call)
                self._append(tool_message)

        raise AgentError(f"agent exceeded {self.max_rounds} provider rounds")

    def _execute_tool_call(self, tool_call: Any) -> dict[str, Any]:
        call_id = "unknown"
        try:
            if not isinstance(tool_call, dict):
                raise ValueError("tool call is not an object")
            call_id = tool_call["id"]
            function = tool_call["function"]
            name = function["name"]
            raw_arguments = function["arguments"]
            if not all(isinstance(value, str) for value in (call_id, name, raw_arguments)):
                raise ValueError("tool call fields must be strings")
            arguments = json.loads(raw_arguments)
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be an object")
            content = self.tools.execute(name, arguments)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            content = json.dumps({"ok": False, "error": f"invalid tool call: {error}"})
        return {"role": "tool", "tool_call_id": call_id, "content": content}

    def _append(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        if self.session is not None:
            self.session.append(message)
