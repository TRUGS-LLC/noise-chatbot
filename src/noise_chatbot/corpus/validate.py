"""The corpus validate gate — ADR-001: the published ``trug`` CLI, not a library import.

<trl>
FUNCTION loader SHALL READ FILE corpus THEN VALIDATE ALL RECORD.
FUNCTION loader SHALL_NOT LOAD ANY INVALID FILE corpus.
</trl>

The engine gates on exactly the command a corpus author runs by hand: the published
``trug`` binary from ``trugs-tools==2.1.0`` (the ``[engine]`` extra), invoked as a
subprocess. A non-zero exit, absent CLI, or non-``VALID`` output all refuse the load
with the tool's own message (ADR-001 failure mode, T1.3). No coupling to private
``trugs_tools`` internals — trivially reversible if profiling ever demands.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from noise_chatbot.corpus.errors import CorpusValidationError

__all__ = ["TRUG_BINARY", "CorpusValidationError", "trug_validate"]

#: The published console-script the gate invokes (``trug``, never the dev-only ``tg``).
TRUG_BINARY = "trug"


def trug_validate(path: Path, *, binary: str = TRUG_BINARY) -> None:
    """Refuse unless ``binary validate <path>`` exits 0 with ``VALID`` output.

    <trl>
    FUNCTION trug_validate SHALL VALIDATE FILE corpus BY SERVICE trug.
    </trl>

    Raises ``CorpusValidationError`` when the CLI is absent, exits non-zero, or does
    not report ``VALID`` — never a silent pass (ADR-001, T1.3).
    """
    exe = shutil.which(binary)
    if exe is None:
        raise CorpusValidationError(
            f"{binary!r} CLI not found on PATH — install trugs-tools==2.1.0 "
            f"(the noise-chatbot[engine] extra) so the corpus validate gate can run"
        )
    # Fixed argv, resolved absolute executable, no shell — safe subprocess.
    proc = subprocess.run(
        [exe, "validate", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    first_token = first_line.split()[0] if first_line else ""
    if proc.returncode != 0 or first_token != "VALID":
        raise CorpusValidationError(
            f"corpus at {path} failed `{binary} validate`: {first_line or 'no output'}"
        )
