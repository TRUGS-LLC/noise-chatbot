"""Corpus contract + loader for the TRUG-traced answer engine (AAA #29, SP1).

<trl>
MODULE corpus CONTAINS FUNCTION load_corpus AND RECORD Corpus AND RECORD CorpusNode.
FUNCTION loader SHALL READ FILE corpus THEN VALIDATE ALL RECORD.
FUNCTION loader SHALL_NOT LOAD ANY INVALID FILE corpus.
</trl>

A corpus is a standard ``trug validate``-VALID TRUG envelope plus the engine-level
role contract pinned in ``docs/corpus_schema.md``. This package owns *reading* a
corpus and *refusing* an invalid one; it defines **no writer** — corpora mutate only
via a human author + ``trug validate`` + a new version (capture-never-compose, D8).
"""

from __future__ import annotations

from noise_chatbot.corpus.loader import (
    Corpus,
    CorpusError,
    CorpusNode,
    CorpusSchemaError,
    CorpusValidationError,
    load_corpus,
)
from noise_chatbot.corpus.schema import (
    CORPUS_SCHEMA_VERSION,
    ROLE_ANSWER,
    ROLE_BOTTOM,
    ROLE_BRANCH,
    ROLE_PROCEDURE,
    VALID_ROLES,
    Role,
)

__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "ROLE_ANSWER",
    "ROLE_BOTTOM",
    "ROLE_BRANCH",
    "ROLE_PROCEDURE",
    "VALID_ROLES",
    "Corpus",
    "CorpusError",
    "CorpusNode",
    "CorpusSchemaError",
    "CorpusValidationError",
    "Role",
    "load_corpus",
]
