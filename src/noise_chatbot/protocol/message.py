"""The JSON wire-envelope for every client↔server message.

<trl>
DEFINE RECORD Message CONTAINS STRING type AND DATA payload
    AND STRING id AND OPTIONAL STRING reply_to.
</trl>
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Message:
    """Wire envelope for all Noise Chatbot communication.

    <trl>
    DEFINE RECORD Message CONTAINS STRING type AND DATA payload
        AND STRING id AND OPTIONAL STRING reply_to.
    EACH RECORD Message 'with STRING type EQUALS CHAT SHALL CONTAIN STRING text IN payload.
    EACH RECORD Message 'with STRING type EQUALS ERROR SHALL CONTAIN STRING error IN payload.
    </trl>

    JSON keys (from Go ``protocol.Message`` struct tags):
        - ``type``       : ``str``
        - ``payload``    : ``dict`` / ``list`` / raw JSON (unparsed)
        - ``id``         : ``str``
        - ``reply_to``   : ``str`` (omitted when empty, via ``omitempty`` in Go)

    Known ``type`` values observed in the Go suite:
        - ``"CHAT"``     : payload = ``{"text": str}``
        - ``"ERROR"``    : payload = ``{"error": str}``
        Arbitrary custom types are echoed verbatim by the server default path.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    reply_to: str = ""

    def to_json(self) -> str:
        """Serialise to JSON with ``reply_to`` omitted when empty.

        <trl>
        FUNCTION Message.to_json SHALL MAP RECORD SELF AS STRING json
            THEN SKIP STRING reply_to IF STRING reply_to EQUALS "".
        </trl>

        Go parity: ``json.Marshal(protocol.Message)`` — ``omitempty`` on ``ReplyTo``.
        """
        doc: dict[str, Any] = {
            "type": self.type,
            "payload": self.payload,
            "id": self.id,
        }
        if self.reply_to:
            doc["reply_to"] = self.reply_to
        return json.dumps(doc)

    @classmethod
    def from_json(cls, data: bytes | str) -> Message:
        """Parse a JSON payload into a Message.

        <trl>
        FUNCTION Message.from_json SHALL MAP STRING data AS RECORD Message
            THEN RETURNS_TO SOURCE.
        </trl>

        Go parity: ``json.Unmarshal(data, &msg)``.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        doc = json.loads(data)
        return cls(
            type=doc.get("type", ""),
            payload=doc.get("payload", {}),
            id=doc.get("id", ""),
            reply_to=doc.get("reply_to", ""),
        )
