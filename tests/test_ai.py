import json
from types import SimpleNamespace as NS

import pytest

from neuranova.ai import ClaudeLLM, ModelRefused, OpenAILLM, build_llm
from neuranova.config import load_settings

TOOLS = [{"name": "add", "description": "add numbers", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}}]


class FakeOpenAI:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        message = self.replies.pop(0)
        return NS(choices=[NS(message=message, finish_reason="stop")])


def oa_msg(content=None, tool_calls=None, refusal=None):
    return NS(content=content, tool_calls=tool_calls, refusal=refusal)


def test_openai_json_and_tool_loop():
    client = FakeOpenAI([oa_msg(content='{"ok": true}')])
    llm = OpenAILLM("gpt-x", client=client)
    assert llm.json("sys", "user", {"type": "object"}) == {"ok": True}
    fmt = client.calls[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True

    call = NS(id="c1", function=NS(name="add", arguments='{"a": 2, "b": 3}'))
    bad = NS(id="c2", function=NS(name="add", arguments='not json'))
    client = FakeOpenAI([oa_msg(tool_calls=[call, bad]), oa_msg(content="The answer is 5.")])
    llm = OpenAILLM("gpt-x", client=client)
    seen = []
    answer = llm.chat("sys", "what is 2+3", TOOLS, lambda name, args: seen.append(args) or args["a"] + args["b"])
    assert answer == "The answer is 5." and seen == [{"a": 2, "b": 3}]
    tool_msgs = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "5" and tool_msgs[1]["content"].startswith("Error")
    params = client.calls[0]["tools"][0]["function"]
    assert params["strict"] is True and params["parameters"]["required"] == ["a", "b"]
    assert params["parameters"]["additionalProperties"] is False


def test_openai_refusal():
    llm = OpenAILLM("gpt-x", client=FakeOpenAI([oa_msg(refusal="no")]))
    with pytest.raises(ModelRefused):
        llm.text("s", "u")


class FakeClaude:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return self.responses.pop(0)


def test_claude_tool_loop_appends_and_reports_errors():
    use = NS(type="tool_use", id="t1", name="add", input={"a": 1, "b": "x"})
    client = FakeClaude([NS(stop_reason="tool_use", content=[use], stop_details=None),
                         NS(stop_reason="end_turn", content=[NS(type="text", text="Done")], stop_details=None)])
    llm = ClaudeLLM("claude-opus-5-5", client=client)
    assert llm.chat("s", "u", TOOLS, lambda n, a: a["a"] + a["b"]) == "Done"
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and result["tool_use_id"] == "t1"
    tool = client.calls[0]["tools"][0]
    assert tool["strict"] is True and tool["input_schema"]["required"] == ["a", "b"]
    assert client.calls[0]["fallbacks"] == "default"


def test_build_llm_picks_provider(tmp_path):
    cfg = tmp_path / "x.toml"
    s = lambda **env: load_settings(cfg, env=env)  # noqa: E731
    assert build_llm(s(ANTHROPIC_API_KEY="a"), client=object()).provider == "claude"
    assert build_llm(s(OPENAI_API_KEY="o"), client=object()).provider == "openai"
    assert build_llm(s(ANTHROPIC_API_KEY="a", OPENAI_API_KEY="o"), client=object()).provider == "claude"
    chosen = build_llm(s(ANTHROPIC_API_KEY="a", OPENAI_API_KEY="o", AI_PROVIDER="openai", OPENAI_MODEL="m1"),
                       client=object())
    assert chosen.provider == "openai" and chosen.model == "m1"
