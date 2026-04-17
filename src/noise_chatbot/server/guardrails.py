"""Default guardrail response nodes — 15 compiled-in boundary answers.

<trl>
DEFINE RESOURCE DEFAULT_GUARDRAILS AS ARRAY OF RECORD ResponseNode CONTAINS 15 RECORD.
SERVICE Server SHALL VALIDATE EACH RECORD Message SUBJECT_TO RESOURCE DEFAULT_GUARDRAILS
    BEFORE ARRAY responses.
</trl>

Mirrors Go ``server.DefaultGuardrails`` (server.go:116-132). Node IDs,
keywords, and response text are preserved byte-for-byte so parity
fixture 06 and the custom-guardrails additive test (fixture 15) match.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode


# <trl>
# EACH RECORD 'in RESOURCE DEFAULT_GUARDRAILS CONTAINS STRING id AND ARRAY keywords AND STRING response.
# </trl>
DEFAULT_GUARDRAILS: list[ResponseNode]
"""15 pre-authored boundary responses — identity, creator, admin,
password, api-key, prompt-injection, personal, others, harmful,
off-topic, distress, capabilities, language, feedback, and the
capabilities summary.

Phase C populates this with the exact Go text. The list is checked
BEFORE ``Server._responses`` so any guardrail keyword in user text
masks a business response with the same score.
"""
# Phase B placeholder — Phase C fills this with the 15 ResponseNodes from Go.
DEFAULT_GUARDRAILS = []
