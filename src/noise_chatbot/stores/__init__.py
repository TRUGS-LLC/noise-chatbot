"""Pluggable stores for noise-chatbot persistent state.

<trl>
MODULE stores CONTAINS PROCESS GuardrailStore AND PROCESS ResponseStore
    AND PROCESS BannedKeyStore AND PROCESS KnowledgeBaseStore.
EACH PROCESS SHALL DEFINE RECORD.
AGENT claude SHALL_NOT WRITE ANY DATA primitive TO RESOURCE trugs_store
    WHEN MODULE stores CONTAINS RECORD default.
</trl>

Four protocols, three implementation layers:

- ``protocols`` — Protocol classes (type-only contracts)
- ``memory`` — ``InMemory*`` defaults for all four (zero external deps)
- ``json_file`` — ``JsonFile*`` defaults for the three read-only loaders + ``BannedKeyStore``
- ``trugs`` — ``Trugs*`` adapters, only importable when the ``[trugs]`` extra
  is installed (``pip install noise-chatbot[trugs]``)

See ``REFERENCE/LAB_1596_noise_chatbot_extras.md`` for the architecture decision log.
"""

from __future__ import annotations

from noise_chatbot.stores.json_file import (
    JsonFileBannedKeyStore,
    JsonFileKnowledgeBaseStore,
    JsonFileResponseStore,
)

# ``noise_chatbot.stores.trugs`` is intentionally NOT imported here — it
# depends on the ``[trugs]`` optional extra. Callers opt in via:
#     from noise_chatbot.stores.trugs import TrugsGuardrailStore
# ImportError is raised at that point if the extra is absent, with a clear
# install hint.
from noise_chatbot.stores.memory import (
    InMemoryBannedKeyStore,
    InMemoryGuardrailStore,
    InMemoryKnowledgeBaseStore,
    InMemoryResponseStore,
)
from noise_chatbot.stores.protocols import (
    BannedKeyStore,
    GuardrailStore,
    KnowledgeBaseStore,
    ResponseStore,
)

__all__ = [
    "BannedKeyStore",
    "GuardrailStore",
    "InMemoryBannedKeyStore",
    "InMemoryGuardrailStore",
    "InMemoryKnowledgeBaseStore",
    "InMemoryResponseStore",
    "JsonFileBannedKeyStore",
    "JsonFileKnowledgeBaseStore",
    "JsonFileResponseStore",
    "KnowledgeBaseStore",
    "ResponseStore",
]
