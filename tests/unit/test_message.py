"""Unit tests for ``protocol.Message`` JSON envelope.

<trl>
STAGE test_message SHALL VALIDATE RECORD Message SUBJECT_TO DATA json_fixture.
EACH RECORD Message SHALL MAP AS STRING json THEN MAP STRING json AS RECORD Message.
</trl>
"""

from __future__ import annotations

import json

from noise_chatbot.protocol.message import Message


# AGENT SHALL VALIDATE PROCESS to_json_includes_required_fields.
def test_to_json_includes_required_fields() -> None:
    """``type``/``payload``/``id`` always present in the encoded JSON."""
    msg = Message(type="CHAT", payload={"text": "hi"}, id="msg-1")
    doc = json.loads(msg.to_json())
    assert doc["type"] == "CHAT"
    assert doc["payload"] == {"text": "hi"}
    assert doc["id"] == "msg-1"


# AGENT SHALL VALIDATE PROCESS to_json_omits_empty_reply_to.
def test_to_json_omits_empty_reply_to() -> None:
    """``reply_to`` key elided when empty (Go ``omitempty`` parity)."""
    msg = Message(type="CHAT", payload={}, id="msg-1")
    doc = json.loads(msg.to_json())
    assert "reply_to" not in doc


# AGENT SHALL VALIDATE PROCESS to_json_includes_reply_to_when_set.
def test_to_json_includes_reply_to_when_set() -> None:
    """``reply_to`` key present and accurate when non-empty."""
    msg = Message(type="CHAT", payload={}, id="msg-2", reply_to="msg-1")
    doc = json.loads(msg.to_json())
    assert doc["reply_to"] == "msg-1"


# AGENT SHALL VALIDATE PROCESS from_json_accepts_bytes.
def test_from_json_accepts_bytes() -> None:
    """UTF-8 bytes input decodes into a Message."""
    raw = b'{"type":"CHAT","payload":{"text":"hi"},"id":"m-1"}'
    msg = Message.from_json(raw)
    assert msg.type == "CHAT"
    assert msg.payload == {"text": "hi"}
    assert msg.id == "m-1"
    assert msg.reply_to == ""


# AGENT SHALL VALIDATE PROCESS from_json_accepts_str.
def test_from_json_accepts_str() -> None:
    """String input also decodes into a Message."""
    msg = Message.from_json('{"type":"ERROR","payload":{"error":"x"},"id":"e-1"}')
    assert msg.type == "ERROR"
    assert msg.payload == {"error": "x"}


# AGENT SHALL VALIDATE PROCESS from_json_tolerates_missing_fields.
def test_from_json_tolerates_missing_fields() -> None:
    """Missing fields default to empty values (Go parity with zero-value struct)."""
    msg = Message.from_json("{}")
    assert msg.type == ""
    assert msg.payload == {}
    assert msg.id == ""
    assert msg.reply_to == ""


# AGENT SHALL VALIDATE PROCESS round_trip_preserves_content.
def test_round_trip_preserves_content() -> None:
    """``from_json(to_json(m))`` recovers the original Message fields."""
    original = Message(type="CHAT", payload={"text": "hello", "n": 3}, id="m-x", reply_to="m-y")
    recovered = Message.from_json(original.to_json())
    assert recovered.type == original.type
    assert recovered.payload == original.payload
    assert recovered.id == original.id
    assert recovered.reply_to == original.reply_to
