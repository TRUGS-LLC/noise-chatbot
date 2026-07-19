"""Corpus-load exception hierarchy — one base so a single ``except`` catches any refusal.

<trl>
MODULE errors CONTAINS RECORD CorpusError AND RECORD CorpusValidationError
    AND RECORD CorpusSchemaError.
</trl>
"""

from __future__ import annotations


class CorpusError(Exception):
    """Base class for every corpus-load refusal."""


class CorpusValidationError(CorpusError):
    """Raised when a corpus fails (or cannot reach) the ``trug validate`` gate (ADR-001)."""


class CorpusSchemaError(CorpusError):
    """Raised when a ``trug``-VALID file violates the engine-level role contract."""
