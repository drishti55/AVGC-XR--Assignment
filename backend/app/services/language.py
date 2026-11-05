"""Language detection and tokenisation for Hindi (Devanagari) and English text."""
import re
import unicodedata

DEVANAGARI_LETTER = re.compile(r"[ऀ-ॿ]")
# Split on whitespace and punctuation, including the Devanagari danda (।) and double danda (॥).
# Note: we must NOT use \w+ — Python's \w excludes Devanagari vowel signs (matras), so
# "कर्म" would be broken into pieces.
SPLIT = re.compile(r"[\s\.,;:!?\"'“”‘’()\[\]{}<>/\\|\-—–*।॥0-9०-९]+")
ZERO_WIDTH = re.compile(r"[​-‍﻿]")

STOPWORDS = {
    # English
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "with", "and", "or", "is", "are", "was",
    "were", "be", "been", "does", "do", "did", "what", "which", "who", "whom", "how", "why", "when", "where",
    "it", "its", "this", "that", "these", "those", "about", "according", "text", "say", "says", "tell", "me",
    "explain", "describe", "there", "as", "from", "into", "can", "one", "his", "he", "they", "their",
    "i", "we", "you", "my", "our", "your", "us", "them", "him", "her", "she", "will", "would", "should",
    # words present in nearly every question but not informative for retrieval
    "garuda", "purana", "puran", "garud",
    # Hindi
    "के", "की", "का", "को", "में", "से", "पर", "है", "हैं", "था", "थे", "और", "या", "क्या", "कैसे", "क्यों",
    "कौन", "बारे", "बताया", "गया", "गयी", "गई", "कहा", "वर्णन", "अनुसार", "यह", "वह", "इस", "उस", "एक",
    "भी", "तो", "ही", "होता", "होती", "जाता", "जाती", "गरुड़", "गरुड", "पुराण", "गरुड़पुराण", "गरुडपुराण",
    # pronouns: frequent in the Hindi translation, carry no topic
    "मैं", "मुझे", "मुझसे", "मेरा", "मेरी", "मेरे", "हम", "हमें", "हमारा", "आप", "तुम", "तुम्हें", "अपना", "अपने", "अपनी",
}

# Gita Press Hindi joins postpositions to the noun ("कर्मोंके" = कर्मों + के). Stripping these
# common endings lets "कर्मोंके" match a question that says "कर्म".
HINDI_SUFFIXES = sorted(
    ["ोंके", "ोंकी", "ोंका", "ोंको", "ोंसे", "ोंमें", "ोंने", "ोंपर", "ों", "ें",
     "के", "की", "का", "को", "से", "में", "ने", "पर", "ाएँ", "ाओं"],
    key=len, reverse=True,
)


def detect_language(text: str) -> str:
    """'hi' if the question is mostly Devanagari, else 'en'.

    Hindi written in Latin letters ("karma ke baare mein") is treated as English; the
    multilingual embeddings still retrieve the right passages for it.
    """
    letters = [c for c in text if c.isalpha() or DEVANAGARI_LETTER.match(c)]
    if not letters:
        return "en"
    deva = sum(bool(DEVANAGARI_LETTER.match(c)) for c in letters)
    return "hi" if deva / len(letters) > 0.3 else "en"


def normalize(text: str) -> str:
    return ZERO_WIDTH.sub("", unicodedata.normalize("NFC", text)).lower()


def _stem(token: str) -> str:
    if DEVANAGARI_LETTER.match(token[0]):
        for suf in HINDI_SUFFIXES:
            if token.endswith(suf) and len(token) - len(suf) >= 2:
                return token[: -len(suf)]
        return token
    if token.endswith("'s"):
        token = token[:-2]
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]                     # suffering -> suffer
    elif len(token) > 4 and token.endswith("ed") and not token.endswith("eed"):
        token = token[:-2]                     # suffered -> suffer (deed/need untouched)
    elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]                     # karmas -> karma, deeds -> deed
    return token


def tokenize(text: str) -> list[str]:
    tokens = (t for t in SPLIT.split(normalize(text)) if t)
    return [_stem(t) for t in tokens if t not in STOPWORDS and len(t) > 1]
