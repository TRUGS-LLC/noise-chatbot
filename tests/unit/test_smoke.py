"""Phase B smoke tests: import graph is clean.

<trl>
STAGE test_smoke SHALL VALIDATE MODULE noise_chatbot CAN BE IMPORTED.
</trl>
"""

from __future__ import annotations

import importlib


def test_package_imports() -> None:
    """The top-level package imports cleanly."""
    mod = importlib.import_module("noise_chatbot")
    assert hasattr(mod, "__version__")
    assert mod.__version__.startswith("0.1.0")


def test_submodules_import() -> None:
    """Every documented submodule imports cleanly."""
    for name in (
        "noise_chatbot.noise",
        "noise_chatbot.protocol",
        "noise_chatbot.server",
        "noise_chatbot.client",
        "noise_chatbot.helper",
        "noise_chatbot.examples",
    ):
        importlib.import_module(name)


def test_public_api_surface_declared() -> None:
    """Each subpackage exposes its __all__ list."""
    for name, expected_min_size in (
        ("noise_chatbot.noise", 8),
        ("noise_chatbot.protocol", 1),
        ("noise_chatbot.server", 8),
        ("noise_chatbot.client", 2),
    ):
        mod = importlib.import_module(name)
        assert hasattr(mod, "__all__"), f"{name} missing __all__"
        assert len(mod.__all__) >= expected_min_size, f"{name}.__all__ too small"
