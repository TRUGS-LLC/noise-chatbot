"""Example chatbot binaries mirroring the Go ``examples/`` tree.

<trl>
DEFINE "examples" AS MODULE.
MODULE examples CONTAINS INTERFACE echo AND INTERFACE faq
    AND INTERFACE llm AND INTERFACE graph.
</trl>
"""
