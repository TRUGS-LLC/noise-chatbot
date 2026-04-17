"""Default guardrail response nodes — 15 compiled-in boundary answers.

<trl>
DEFINE RESOURCE DEFAULT_GUARDRAILS AS ARRAY OF RECORD ResponseNode CONTAINS 15 RECORD.
SERVICE Server SHALL VALIDATE EACH RECORD Message SUBJECT_TO RESOURCE DEFAULT_GUARDRAILS
    BEFORE ARRAY responses.
</trl>

The 15 entries mirror the shipped ``guardrails.trug.json`` data file.
Response text is byte-for-byte identical to the Go parity fixture 06
assertion (``REFERENCE/parity/fixtures/06_guardrail_hit_identity.yaml``).

IDs are taken from ``guardrails.trug.json``. Parity fixtures assert on
response text and guardrail precedence, not on IDs.
"""

from __future__ import annotations

from noise_chatbot.server.server import ResponseNode

DEFAULT_GUARDRAILS: list[ResponseNode] = [
    ResponseNode(
        id="identity_name",
        keywords=[
            "your name",
            "who are you",
            "what are you",
            "are you a bot",
            "are you real",
            "are you AI",
            "are you human",
        ],
        response=(
            "I'm an automated assistant for this service. I answer questions "
            "from our knowledge base. I don't have personal opinions or "
            "experiences \u2014 I find the best answer from what we've published."
        ),
    ),
    ResponseNode(
        id="identity_creator",
        keywords=[
            "who made you",
            "who built you",
            "who created you",
            "who is the developer",
            "what company",
        ],
        response=(
            "I was built using Noise Chatbot, an open-source encrypted "
            "chatbot framework. My responses come from the knowledge base "
            "maintained by the team behind this service."
        ),
    ),
    ResponseNode(
        id="admin_access",
        keywords=[
            "admin",
            "administrator",
            "admin panel",
            "admin access",
            "backend",
            "dashboard",
            "login",
        ],
        response=(
            "I'm the public-facing assistant. I don't have access to admin "
            "systems, and I can't help with internal tools or accounts. If "
            "you need admin support, please contact the team directly "
            "through our official channels."
        ),
    ),
    ResponseNode(
        id="password_request",
        keywords=[
            "password",
            "credentials",
            "login details",
            "secret",
            "auth token",
            "access code",
        ],
        response=(
            "I don't store or have access to any passwords, credentials, or "
            "authentication tokens. If you need to reset your password or "
            "access your account, please use the official login page or "
            "contact support."
        ),
    ),
    ResponseNode(
        id="api_keys",
        keywords=[
            "API key",
            "api keys",
            "secret key",
            "access key",
            "token",
            "bearer",
            "authorization",
        ],
        response=(
            "I don't have access to any API keys or service credentials. "
            "I'm a read-only assistant that answers questions from our "
            "published knowledge base. For API access, please check our "
            "developer documentation."
        ),
    ),
    ResponseNode(
        id="system_prompt",
        keywords=[
            "system prompt",
            "instructions",
            "initial prompt",
            "your prompt",
            "your instructions",
            "what were you told",
            "your rules",
        ],
        response=(
            "I match your questions to answers in our knowledge base. I "
            "don't compose responses or follow dynamic instructions \u2014 "
            "I find the closest pre-written answer and return it exactly as "
            "written."
        ),
    ),
    ResponseNode(
        id="ignore_instructions",
        keywords=[
            "ignore previous",
            "ignore all",
            "disregard",
            "forget your instructions",
            "new instructions",
            "override",
            "jailbreak",
            "DAN",
            "do anything now",
        ],
        response=(
            "I appreciate the creativity, but I work differently from most "
            "chatbots. I don't follow instructions in messages \u2014 I "
            "match your question to our knowledge base and return a "
            "pre-written answer. There's nothing to override because I "
            "don't compose responses."
        ),
    ),
    ResponseNode(
        id="personal_info",
        keywords=[
            "my data",
            "my information",
            "my records",
            "my account",
            "my profile",
            "what do you know about me",
        ],
        response=(
            "I don't store any information about you between conversations, "
            "and I can't access personal accounts or records. Each "
            "conversation starts fresh. For account-related questions, "
            "please contact our support team."
        ),
    ),
    ResponseNode(
        id="other_users",
        keywords=[
            "other users",
            "other customers",
            "someone else",
            "another person",
            "other people",
            "user data",
            "customer list",
        ],
        response=(
            "I don't have access to information about any individual users "
            "or customers. I only answer general questions from our "
            "published knowledge base."
        ),
    ),
    ResponseNode(
        id="harmful_request",
        keywords=[
            "hack",
            "exploit",
            "vulnerability",
            "break into",
            "bypass security",
            "SQL injection",
            "XSS",
        ],
        response=(
            "I'm a customer service assistant. I answer questions about "
            "our products and services. For security concerns or "
            "vulnerability reports, please contact our security team "
            "through our official responsible disclosure page."
        ),
    ),
    ResponseNode(
        id="off_topic",
        keywords=[
            "meaning of life",
            "tell me a joke",
            "write me a poem",
            "what is love",
            "political opinion",
            "who should I vote for",
        ],
        response=(
            "That's a great question, but it's outside what I can help "
            "with. I'm focused on answering questions about our products "
            "and services. Is there something specific about our service "
            "I can help you with?"
        ),
    ),
    ResponseNode(
        id="emotional_distress",
        keywords=[
            "suicide",
            "kill myself",
            "self harm",
            "depressed",
            "want to die",
            "end my life",
            "hurt myself",
        ],
        response=(
            "I'm not equipped to help with this, but please reach out to "
            "someone who can. National Suicide Prevention Lifeline: 988 "
            "(call or text). Crisis Text Line: text HOME to 741741. You "
            "matter, and help is available 24/7."
        ),
    ),
    ResponseNode(
        id="capabilities",
        keywords=[
            "what can you do",
            "help me",
            "how do you work",
            "what do you know",
            "your capabilities",
        ],
        response=(
            "I can answer questions about our products, services, pricing, "
            "hours, and policies. I work by matching your question to our "
            "knowledge base and returning the most relevant answer. If I "
            "don't have an answer, I'll let you know and suggest how to "
            "reach our team."
        ),
    ),
    ResponseNode(
        id="language",
        keywords=[
            "speak spanish",
            "habla espa\u00f1ol",
            "parlez-vous",
            "sprechen sie",
            "other language",
            "translate",
        ],
        response=(
            "I currently respond in English only. If you need assistance "
            "in another language, please contact our support team who may "
            "be able to help."
        ),
    ),
    ResponseNode(
        id="feedback",
        keywords=[
            "complaint",
            "feedback",
            "not helpful",
            "wrong answer",
            "bad answer",
            "you're wrong",
            "that's incorrect",
        ],
        response=(
            "Thank you for letting me know. I'll make sure this feedback "
            "reaches our team. If my answer wasn't helpful, please contact "
            "our support team directly \u2014 they can give you more "
            "detailed help."
        ),
    ),
]
