"""Unit tests for ``server.default_classifier``.

<trl>
STAGE test_classifier SHALL VALIDATE FUNCTION default_classifier SUBJECT_TO
    ARRAY response_nodes.
FUNCTION default_classifier SHALL MAP STRING user_text AS ARRAY ids
    SORTED BY INTEGER score.
</trl>
"""

from __future__ import annotations

from noise_chatbot.server.classifier import default_classifier
from noise_chatbot.server.server import ResponseNode


def _node(node_id: str, keywords: list[str]) -> ResponseNode:
    """Build a ResponseNode with dummy response text for test brevity."""
    return ResponseNode(id=node_id, keywords=keywords, response="r")


# AGENT SHALL VALIDATE PROCESS no_match_returns_empty.
def test_no_match_returns_empty() -> None:
    """Zero keyword hits yields an empty list."""
    assert default_classifier("hello world", [_node("a", ["xyzzy"])]) == []


# AGENT SHALL VALIDATE PROCESS single_keyword_match.
def test_single_keyword_match() -> None:
    """A single keyword hit returns the node's id."""
    assert default_classifier("I want to know the price", [_node("pricing", ["price"])]) == [
        "pricing"
    ]


# AGENT SHALL VALIDATE PROCESS case_insensitive_match.
def test_case_insensitive_match() -> None:
    """Matching is case-insensitive on both sides (fixture 14 parity)."""
    nodes = [_node("hours", ["HOURS"])]
    assert default_classifier("what are your Hours?", nodes) == ["hours"]


# AGENT SHALL VALIDATE PROCESS higher_score_sorts_first.
def test_higher_score_sorts_first() -> None:
    """Nodes with more keyword hits rank before fewer-hit nodes."""
    nodes = [
        _node("single", ["pricing"]),
        _node("double", ["pricing", "cost"]),
    ]
    # "pricing cost" hits "single" once and "double" twice → double first.
    assert default_classifier("I asked about pricing and cost", nodes) == ["double", "single"]


# AGENT SHALL VALIDATE PROCESS tied_scores_preserve_input_order.
def test_tied_scores_preserve_input_order() -> None:
    """Score ties preserve input-list order (stable sort guarantee)."""
    nodes = [_node("first", ["foo"]), _node("second", ["bar"])]
    assert default_classifier("foo and bar", nodes) == ["first", "second"]


# AGENT SHALL VALIDATE PROCESS empty_node_list.
def test_empty_node_list() -> None:
    """Empty node list trivially returns empty list."""
    assert default_classifier("anything", []) == []
