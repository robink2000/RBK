"""One interface over the AI providers the PA can use: Claude (default) or OpenAI.

    llm.json(system, user, schema)          -> dict    (structured output)
    llm.text(system, user)                  -> str
    llm.chat(system, user, tools, run_tool) -> str     (tool-using conversation, append-only)

Tools are described once in a neutral form ({"name", "description", "properties"}) and converted
for each provider. Every tool is strict: all properties required, optional ones nullable.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOOL_STEPS = 8


class ModelRefused(RuntimeError):
    pass


def _schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


class ClaudeLLM:
    provider = "claude"

    def __init__(self, model: str, client=None, api_key: str | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key or None)
        self.client, self.model = client, model

    def _create(self, system: str, messages: list, *, effort: str, max_tokens: int, schema: dict | None = None,
                tools: list | None = None):
        output_config: dict = {"effort": effort}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        kwargs = {"tools": tools} if tools else {}
        response = self.client.beta.messages.create(
            model=self.model, max_tokens=max_tokens, system=system, messages=messages,
            output_config=output_config, betas=[FALLBACK_BETA], fallbacks="default", **kwargs,
        )
        if response.stop_reason == "refusal":
            raise ModelRefused(str(response.stop_details))
        return response

    @staticmethod
    def _text(response) -> str:
        return "".join(b.text for b in response.content if b.type == "text")

    def text(self, system: str, user: str, *, effort: str = "medium", max_tokens: int = 8000) -> str:
        response = self._create(system, [{"role": "user", "content": user}], effort=effort, max_tokens=max_tokens)
        if response.stop_reason == "max_tokens":
            raise RuntimeError("The AI response was cut off (max_tokens)")
        return self._text(response).strip()

    def json(self, system: str, user: str, schema: dict, *, effort: str = "low", max_tokens: int = 16000) -> dict:
        response = self._create(system, [{"role": "user", "content": user}], effort=effort, max_tokens=max_tokens,
                                schema=schema)
        if response.stop_reason == "max_tokens":
            raise RuntimeError("The AI response was cut off (max_tokens)")
        return json.loads(self._text(response))

    def chat(self, system: str, user: str, tools: list[dict], run_tool: Callable[[str, dict], object], *,
             effort: str = "medium") -> str:
        claude_tools = [{"name": t["name"], "description": t["description"], "strict": True,
                         "input_schema": _schema(t["properties"])} for t in tools]
        messages: list = [{"role": "user", "content": user}]
        for _ in range(MAX_TOOL_STEPS):
            response = self._create(system, messages, effort=effort, max_tokens=16000, tools=claude_tools)
            calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not calls:
                return self._text(response).strip()
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in calls:
                ok, out = _run(run_tool, call.name, dict(call.input))
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": out,
                                **({} if ok else {"is_error": True})})
            messages.append({"role": "user", "content": results})
        return ""


class OpenAILLM:
    provider = "openai"

    def __init__(self, model: str, client=None, api_key: str | None = None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key or None)
        self.client, self.model = client, model

    def _create(self, messages: list, **kwargs):
        response = self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
        choice = response.choices[0]
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            raise ModelRefused(refusal)
        if choice.finish_reason == "length":
            raise RuntimeError("The AI response was cut off (length)")
        return choice.message

    def text(self, system: str, user: str, *, effort: str = "medium", max_tokens: int = 8000) -> str:
        msg = self._create([{"role": "system", "content": system}, {"role": "user", "content": user}],
                           max_completion_tokens=max_tokens)
        return (msg.content or "").strip()

    def json(self, system: str, user: str, schema: dict, *, effort: str = "low", max_tokens: int = 16000) -> dict:
        msg = self._create([{"role": "system", "content": system}, {"role": "user", "content": user}],
                           max_completion_tokens=max_tokens,
                           response_format={"type": "json_schema",
                                            "json_schema": {"name": "result", "strict": True, "schema": schema}})
        return json.loads(msg.content or "{}")

    def chat(self, system: str, user: str, tools: list[dict], run_tool: Callable[[str, dict], object], *,
             effort: str = "medium") -> str:
        oa_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                      "parameters": _schema(t["properties"]), "strict": True}}
                    for t in tools]
        messages: list = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for _ in range(MAX_TOOL_STEPS):
            msg = self._create(messages, tools=oa_tools, max_completion_tokens=16000)
            calls = msg.tool_calls or []
            if not calls:
                return (msg.content or "").strip()
            messages.append({"role": "assistant", "content": msg.content,
                             "tool_calls": [{"id": c.id, "type": "function",
                                             "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                            for c in calls]})
            for call in calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except ValueError:
                    args = None
                ok, out = (False, "Error: arguments were not valid JSON") if args is None else \
                    _run(run_tool, call.function.name, args)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": out})
        return ""


def _run(run_tool, name: str, args: dict) -> tuple[bool, str]:
    try:
        return True, json.dumps(run_tool(name, args), default=str)
    except Exception as exc:  # the model sees the error and can recover
        log.warning("Tool %s failed: %s", name, exc)
        return False, f"Error: {exc}"


def build_llm(settings, client=None):
    """The configured provider. AI_PROVIDER chooses; otherwise whichever key is present (Claude first)."""
    provider = (settings.secret("AI_PROVIDER") or "").lower()
    if not provider:
        provider = "openai" if settings.secret("OPENAI_API_KEY") and not settings.secret("ANTHROPIC_API_KEY") else "claude"
    if provider == "openai":
        return OpenAILLM(settings.secret("OPENAI_MODEL") or "gpt-4.1", client=client,
                         api_key=settings.secret("OPENAI_API_KEY"))
    return ClaudeLLM(settings.model, client=client, api_key=settings.secret("ANTHROPIC_API_KEY"))
