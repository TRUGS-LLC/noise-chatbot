"""Anthropic selection backend — forced tool-choice over the menu enum (ADR-003).

<trl>
FUNCTION selector SHALL RECEIVE RECORD menu THEN RETURN SOLE RECORD choice.
ASSERT PROCESS engine SHALL VALIDATE EACH RECORD choice BY RECORD menu.
</trl>

The strongest constraint a hosted API offers: a forced tool call whose input schema
``enum``-erates exactly the legal menu node-ids (``strict: true``), so the model returns
one member of the menu — never free text. Safety does not depend on that conformance
(B2): the engine re-validates membership regardless, and a timeout / rate-limit / off-menu
return routes to ⊥. On any backend failure this selector returns the empty string, which
the loader guarantees is never a legal node-id, so the engine's off-menu → RETRY BOUNDED
1 → ⊥ path fires deterministically.

This module imports the ``anthropic`` SDK (the ``[anthropic]`` extra) and is therefore
**never imported by** ``engine`` / ``engine.select`` package ``__init__`` — the base
install stays dependency-free (ADR-002). Import it explicitly:
``from noise_chatbot.engine.select.anthropic import AnthropicSelector``.
"""

from __future__ import annotations

from typing import Any, Final, Protocol, cast

import anthropic

from noise_chatbot.engine.select.port import Menu

#: Default backend model — the cheap tier (D2 cost decoupling); operator-overridable.
DEFAULT_MODEL: Final = "claude-haiku-4-5-20251001"

#: The forced tool the model must call; its single ``choice`` param enumerates the menu.
SELECT_TOOL_NAME: Final = "select_menu_option"

#: Returned on any backend failure — never a legal node-id (loader forbids empty ids),
#: so the engine's off-menu → ⊥ path fires.
_NO_SELECTION: Final = ""


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _AnthropicClient(Protocol):
    @property
    def messages(self) -> _Messages: ...


class AnthropicSelector:
    """A constrained-selection backend backed by Anthropic forced tool choice.

    ``client`` is injectable (tests pass a fake — no network / key); the default builds a
    real ``anthropic.Anthropic`` with a bounded timeout and exactly one retry (ADR-003).
    """

    __slots__ = ("_client", "_max_tokens", "_model", "_tool_name")

    def __init__(
        self,
        *,
        client: _AnthropicClient | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        max_retries: int = 1,
        max_tokens: int = 1024,
        tool_name: str = SELECT_TOOL_NAME,
    ) -> None:
        # The real SDK client's typed `create` doesn't structurally match the loose
        # `**kwargs` Protocol; cast at the construction boundary.
        self._client: _AnthropicClient = (
            client
            if client is not None
            else cast(
                "_AnthropicClient", anthropic.Anthropic(timeout=timeout, max_retries=max_retries)
            )
        )
        self._model = model
        self._max_tokens = max_tokens
        self._tool_name = tool_name

    def select(self, query: str, menu: Menu) -> str:
        """Return the model's chosen node-id, or ``""`` on any backend failure."""
        legal_ids = [option.node_id for option in menu]
        tool = {
            "name": self._tool_name,
            "description": (
                "Choose the single menu option that best answers the user's question. "
                "You MUST call this tool with exactly one of the enumerated ids."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": legal_ids,
                        "description": "The id of the chosen option (see the prompt for id → label).",
                    }
                },
                "required": ["choice"],
                "additionalProperties": False,
            },
        }
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                tools=[tool],
                tool_choice={"type": "tool", "name": self._tool_name},
                messages=[{"role": "user", "content": self._prompt(query, menu)}],
            )
        except anthropic.APIError:
            # Timeout / rate-limit / any API error → signal ⊥ (B2 / ADR-003). The engine
            # never crashes on a misbehaving backend; the miss is located, not silent.
            return _NO_SELECTION
        return self._extract_choice(response)

    def _prompt(self, query: str, menu: Menu) -> str:
        options = "\n".join(f"- {option.node_id}: {option.menu_label}" for option in menu)
        return (
            f"User question:\n{query}\n\n"
            f"Options (id: label):\n{options}\n\n"
            f"Call {self._tool_name!r} with the id of the single best option."
        )

    def _extract_choice(self, response: Any) -> str:
        for block in getattr(response, "content", []):
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == self._tool_name
            ):
                choice = block.input.get("choice") if isinstance(block.input, dict) else None
                if isinstance(choice, str):
                    return choice
        return _NO_SELECTION
