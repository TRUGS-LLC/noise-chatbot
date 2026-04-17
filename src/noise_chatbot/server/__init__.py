"""Chatbot server — template-mode classification + safety + honeypot + wind-down.

<trl>
DEFINE "server" AS MODULE.
MODULE server CONTAINS SERVICE Server AND RECORD ResponseNode AND RECORD SafetyConfig
    AND RECORD ConnectionStats AND RECORD LLMConfig AND RESOURCE DEFAULT_GUARDRAILS.
MODULE server DEPENDS_ON MODULE noise AND MODULE protocol.
SERVICE Server GOVERNS EACH RECORD Message FROM ENTRY client TO EXIT response.
</trl>
"""

from noise_chatbot.server.classifier import Classifier, default_classifier
from noise_chatbot.server.guardrails import DEFAULT_GUARDRAILS
from noise_chatbot.server.server import (
    ChatHandler,
    ConnectionStats,
    LLMConfig,
    MessageHandler,
    ResponseNode,
    SafetyConfig,
    Server,
)

__all__ = [
    "DEFAULT_GUARDRAILS",
    "ChatHandler",
    "Classifier",
    "ConnectionStats",
    "LLMConfig",
    "MessageHandler",
    "ResponseNode",
    "SafetyConfig",
    "Server",
    "default_classifier",
]
