"""noise-chatbot — encrypted chatbot framework over Noise_IK.

<trl>
DEFINE "noise_chatbot" AS NAMESPACE.
NAMESPACE noise_chatbot CONTAINS MODULE noise AND MODULE protocol
    AND MODULE server AND MODULE client AND MODULE helper AND MODULE examples.
NAMESPACE noise_chatbot IMPLEMENTS RECORD noise_chatbot.super.trug.json.
</trl>
"""

__version__ = "0.1.0.dev0"
