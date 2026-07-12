from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pithon.agent import Agent, SYSTEM_PROMPT
from pithon.provider import Completion, DeepSeekProvider
from pithon.session import SessionLog


class FakeResponse:
    def __init__(self, document: dict) -> None:
        self.body = json.dumps(document).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class SequenceProvider:
    def __init__(self, completions: list[Completion]) -> None:
        self.completions = completions
        self.requests: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> Completion:
        self.requests.append(list(messages))
        return self.completions.pop(0)


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, name: str, arguments: dict) -> str:
        self.calls.append((name, arguments))
        return '{"ok":true,"result":"file body"}'


class ProviderAndAgentTests(unittest.TestCase):
    def test_deepseek_payload_and_cache_metrics(self) -> None:
        document = {
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 2,
            },
        }
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(document)

        provider = DeepSeekProvider("test-key", max_tokens=2048)
        with patch("urllib.request.urlopen", fake_urlopen):
            completion = provider.complete([{"role": "user", "content": "hi"}], [])

        payload = json.loads(captured["request"].data)
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(completion.message["content"], "done")
        self.assertEqual(completion.usage["prompt_cache_hit_tokens"], 8)

    def test_agent_preserves_tool_reasoning_and_executes_call(self) -> None:
        provider = SequenceProvider([
            Completion(
                message={
                    "role": "assistant",
                    "content": "I will read it.",
                    "reasoning_content": "Need the file.",
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"a.py"}'},
                    }],
                },
                usage={"total_tokens": 5},
            ),
            Completion(
                message={
                    "role": "assistant",
                    "content": "The file is small.",
                    "reasoning_content": "Finished.",
                },
                usage={"total_tokens": 4},
            ),
        ])
        tools = FakeTools()
        agent = Agent(provider, tools)
        answer = agent.run("inspect a.py")

        self.assertEqual(answer, "The file is small.")
        self.assertEqual(tools.calls, [("read_file", {"path": "a.py"})])
        second_request = provider.requests[1]
        self.assertEqual(second_request[-2]["reasoning_content"], "Need the file.")
        self.assertEqual(second_request[-1]["tool_call_id"], "call-1")
        self.assertNotIn("reasoning_content", agent.messages[-1])
        self.assertEqual(agent.usage.totals["total_tokens"], 9)

    def test_malformed_tool_call_becomes_bounded_tool_error(self) -> None:
        provider = SequenceProvider([
            Completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-bad",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "not-json"},
                    }],
                },
                {},
            ),
            Completion({"role": "assistant", "content": "recovered"}, {}),
        ])
        tools = FakeTools()
        agent = Agent(provider, tools)
        self.assertEqual(agent.run("inspect"), "recovered")
        self.assertEqual(tools.calls, [])
        error = json.loads(provider.requests[1][-1]["content"])
        self.assertFalse(error["ok"])
        self.assertIn("invalid tool call", error["error"])

    def test_session_round_trip_starts_with_stable_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            log = SessionLog(path)
            provider = SequenceProvider([
                Completion({"role": "assistant", "content": "hello"}, {})
            ])
            agent = Agent(provider, FakeTools(), session=log)
            agent.run("hi")
            messages = log.load()
            self.assertEqual(messages[0], {"role": "system", "content": SYSTEM_PROMPT})
            self.assertEqual(messages[-1]["content"], "hello")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            resumed_provider = SequenceProvider([
                Completion({"role": "assistant", "content": "resumed"}, {})
            ])
            resumed = Agent(resumed_provider, FakeTools(), messages=messages, session=log)
            self.assertEqual(resumed.run("continue"), "resumed")
            self.assertEqual(resumed_provider.requests[0][0]["content"], SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
