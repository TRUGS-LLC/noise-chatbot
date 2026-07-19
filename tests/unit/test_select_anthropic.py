"""SP3 Anthropic backend tests (T3.1 / T3.2) — fake client, no network / key.

Verifies ADR-003: the request forces a tool call whose ``choice`` enum is exactly the menu
node-ids (T3.1), and a backend failure returns ``""`` so the engine's off-menu → RETRY
BOUNDED 1 → ⊥ chain fires (T3.2). Engine safety does not depend on backend conformance (B2).
"""

from __future__ import annotations

from typing import Any

import anthropic
import httpx

from noise_chatbot.engine import Engine
from noise_chatbot.engine.select import MenuOption
from noise_chatbot.engine.select.anthropic import DEFAULT_MODEL, AnthropicSelector
from tests.unit._engine_helpers import faq_corpus


class _FakeBlock:
    def __init__(self, block_type: str, name: str | None = None, input_: Any = None) -> None:
        self.type = block_type
        self.name = name
        self.input = input_


class _FakeResponse:
    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(
        self, *, response: _FakeResponse | None = None, error: Exception | None = None
    ) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class _FakeClient:
    def __init__(self, messages: _FakeMessages) -> None:
        self.messages = messages


def _api_error() -> anthropic.APIError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message="simulated timeout", request=request)


_MENU = [MenuOption("about", "What is TRUGS?"), MenuOption("none", "None of these")]


# ── T3.1 — forced tool-choice request shape ────────────────────────────────────


def test_forced_tool_enumerates_exactly_the_menu_ids() -> None:
    messages = _FakeMessages(
        response=_FakeResponse([_FakeBlock("tool_use", "select_menu_option", {"choice": "about"})])
    )
    selector = AnthropicSelector(client=_FakeClient(messages))

    assert selector.select("what is trugs?", _MENU) == "about"

    call = messages.calls[0]
    assert call["model"] == DEFAULT_MODEL == "claude-haiku-4-5-20251001"
    assert call["tool_choice"] == {"type": "tool", "name": "select_menu_option"}
    tool = call["tools"][0]
    assert tool["name"] == "select_menu_option"
    assert tool["strict"] is True
    schema = tool["input_schema"]
    assert schema["properties"]["choice"]["enum"] == ["about", "none"]  # exactly the menu ids
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["choice"]


def test_off_menu_return_is_passed_through_for_the_engine_to_reject() -> None:
    # a (non-conforming) backend returning an off-menu id is returned verbatim; the engine
    # enforces membership (B2) — the selector does not silently repair it.
    messages = _FakeMessages(
        response=_FakeResponse(
            [_FakeBlock("tool_use", "select_menu_option", {"choice": "not-a-node"})]
        )
    )
    selector = AnthropicSelector(client=_FakeClient(messages))
    assert selector.select("q", _MENU) == "not-a-node"


def test_missing_tool_use_block_returns_no_selection() -> None:
    messages = _FakeMessages(response=_FakeResponse([_FakeBlock("text")]))
    selector = AnthropicSelector(client=_FakeClient(messages))
    assert selector.select("q", _MENU) == ""


# ── T3.2 — backend failure path ────────────────────────────────────────────────


def test_backend_failure_returns_empty_string() -> None:
    selector = AnthropicSelector(client=_FakeClient(_FakeMessages(error=_api_error())))
    assert selector.select("q", _MENU) == ""  # never a legal node-id


def test_failing_backend_routes_the_walk_to_bottom(tmp_path: Any) -> None:
    corpus = faq_corpus(tmp_path)
    selector = AnthropicSelector(client=_FakeClient(_FakeMessages(error=_api_error())))
    answer = Engine(corpus, selector).answer("anything")
    assert answer.is_bottom is True  # off-menu ("") → RETRY BOUNDED 1 → ⊥
    assert answer.gap is not None
