"""Wire envelope type.

<trl>
DEFINE "protocol" AS MODULE.
MODULE protocol CONTAINS RECORD Message.
</trl>
"""

from noise_chatbot.protocol.message import Message

__all__ = ["Message"]
