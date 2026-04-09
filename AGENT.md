# Noise Chatbot — Agent Guide

<trl>
DEFINE "noise_chatbot" AS MODULE.
MODULE noise_chatbot CONTAINS MODULE server AND MODULE client AND MODULE noise AND MODULE protocol AND MODULE helper.
MODULE server IMPLEMENTS INTERFACE chatbot_server.
INTERFACE chatbot_server GOVERNS ALL RECORD message FROM ENTRY client TO EXIT response.
</trl>

## What This Repo Is

Noise Chatbot is an encrypted chatbot framework. Every message is end-to-end encrypted using Noise_IK (Curve25519 + ChaCha20-Poly1305 + BLAKE2b). Apache 2.0.

## Navigation

| Package | What It Does |
|---------|-------------|
| `server/` | Chatbot server — `New()`, `OnChat()`, `WithResponses()`, `ListenAndServe()` |
| `client/` | Client library — `Connect()`, `Chat()`, `Send()`, `Close()` |
| `noise/` | Noise_IK transport — handshake, encryption, key management |
| `protocol/` | Wire format — `Message` type |
| `helper/` | stdin/stdout bridge binary for non-Go clients |
| `examples/` | echo, faq, llm, graph |
| `guardrails.trug.json` | 15 default boundary responses |

## Key Design Rule

<trl>
AGENT SHALL_NOT WRITE ANY RECORD response 'that 'is NOT FROM RECORD ResponseNode.
FUNCTION classifier SHALL RETURNS_TO MODULE server RECORD node_id.
FUNCTION classifier SHALL_NOT RETURNS_TO MODULE server RECORD text.
MODULE server SHALL READ RECORD response FROM RECORD ResponseNode THEN SEND RESULT TO ENTRY client.
</trl>

The LLM classifies — picks node IDs from the TRUG. It NEVER composes response text. Every word the user sees was written by a human and stored in a ResponseNode.

## Defense System

<trl>
DEFINE "defense" AS PIPELINE.
PIPELINE defense CONTAINS STAGE guardrails AND STAGE honeypot AND STAGE wind_down AND STAGE rate_limit.
STAGE guardrails FEEDS STAGE honeypot.
EACH RECORD guardrail_hit SHALL INCREMENT RECORD counter.
IF RECORD counter EXCEEDS 12 THEN AGENT SHALL DENY RECORD connection.
IF RECORD question_count EXCEEDS 20 THEN PROCESS response SHALL TIMEOUT WITHIN 5 RECORD seconds 'per RECORD extra_question.
</trl>

- Guardrails: 15 pre-authored boundary responses (loaded by default)
- Honeypot: 4 tiers of escalating delays + different-sounding deflections
- Wind-down: 5s delay per question after 20, goodbye at 40
- Rate limit: 30 messages/minute, 200 token input limit
- Ban: permanent (honeypot tier 5) or 3-day temp (question limit)
