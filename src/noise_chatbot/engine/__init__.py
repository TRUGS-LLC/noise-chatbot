"""The TRUG-traced answer engine — a generic corpus interpreter (AAA #29, SP2).

<trl>
MODULE engine CONTAINS RECORD Engine AND RECORD Answer AND RECORD Session.
PROCESS engine SHALL RECEIVE MESSAGE query THEN RETURN RECORD answer AND RECORD trace.
</trl>

The engine executes a ``trug validate``-VALID corpus as a program: it enumerates each
node's legal, session-gated moves, hands the menu to a bounded selection backend, and
delivers the pre-authored leaf verbatim with its path as a provenance address. It owns
legality; the backend owns one choice per fork. No generation step exists between source
and delivery.
"""

from __future__ import annotations

from noise_chatbot.engine.core import Answer, Engine, EngineError
from noise_chatbot.engine.legal_menu import legal_menu
from noise_chatbot.engine.select import (
    KeywordSelector,
    Menu,
    MenuOption,
    ScriptedSelector,
    Selector,
)
from noise_chatbot.engine.session import Session
from noise_chatbot.engine.trace import (
    TRACE_SCHEMA_VERSION,
    TraceAttempt,
    TraceLog,
    TraceStep,
    TraceTerminal,
)

__all__ = [
    "TRACE_SCHEMA_VERSION",
    "Answer",
    "Engine",
    "EngineError",
    "KeywordSelector",
    "Menu",
    "MenuOption",
    "ScriptedSelector",
    "Selector",
    "Session",
    "TraceAttempt",
    "TraceLog",
    "TraceStep",
    "TraceTerminal",
    "legal_menu",
]
