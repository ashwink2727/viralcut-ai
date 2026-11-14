"""
ViralCut AI - audience comment analysis.

Offline heuristic analysis for English and common Hinglish reactions.
Includes emoji signals, duplicate filtering, like-weighted ranking, and
meaningful repeated multi-word phrases. Sentiment is approximate and can
miss sarcasm, context, and languages not covered by the keyword lists.
"""

import re
from collections import Counter
from math import log1p


POSITIVE_TERMS = {
    "amazing", "awesome", "insane", "crazy", "wow", "fire", "great",
    "best", "love", "loved", "perfect", "excellent", "brilliant",
    "hilarious", "funny", "goat", "legend", "legendary", "incredible",
    "beautiful", "epic", "respect", "underrated", "masterpiece",
    "goated", "letsgo", "let'sgo", "zabardast", "शानदार", "मस्त",
    "maza", "mazaa", "majedar", "majedaar", "sahi", "khatarnak",
    "gazab", "gajab", "banger", "jhakaas", "जबरदस्त", "वाह",
}

NEGATIVE_TERMS = {
    "boring", "bad", "worst", "hate", "hated", "trash", "garbage",
    "disappointed", "disappointing", "cringe", "lag", "lagging",
    "slow", "annoying", "problem", "issue", "broken", "terrible",
    "awful", "poor", "stupid", "waste", "scam", "glitch", "bug",
    "not good", "low quality", "bad audio", "bad video",
    "bekar", "bekaaar", "bakwas", "ghatiya", "boring hai", "time waste",
    "kharab", "problem hai", "बेकार", "बकवास", "घटिया", "खराब",
}

POSITIVE_EMOJI = set("🔥😍❤️❤😂🤣👏💯🙌🥳😁😊🤩👍")
NEGATIVE_EMOJI = set("👎😡🤬💩😒😞😢😭🤮")

# Words that usually add little meaning to a topic trend.
STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "you", "your", "are",
    "was", "but", "have", "has", "had", "not", "just", "they", "them",
    "then", "than", "from", "what", "when", "where", "who", "how",
    "all", "very", "too", "its", "it's", "his", "her", "our", "out",
    "get", "got", "can", "will", "would", "should", "could", "video",
    "watch", "youtube", "bro", "bhai", "lol", "omg", "www", "one",
    "time", "like", "really", "much", "more", "about", "after", "before",
    "thank", "thanks", "watching", "she", "he", "it", "we", "i",
    "me", "my", "mine", "us", "them", "there", "here", "also",
    "please", "sir", "mam", "maam", "okay", "ok", "yes", "no",
    "good", "nice", "great", "love", "loved", "best", "amazing",
}


def _normalized(text):
    text = (text or "").lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _term_hits(text, terms):
    padded = f" {text} "
    return [term for term in terms if term.lower() in padded]


def classify_comment(text):
    """Return a sentiment label and transparent heuristic evidence."""
    normalized = _normalized(text)
    positive_hits = _term_hits(normalized, POSITIVE_TERMS)
    negative_hits = _term_hits(normalized, NEGATIVE_TERMS)

    positive_emoji = [char for char in text if char in POSITIVE_EMOJI]
    negative_emoji = [char for char in text if char in NEGATIVE_EMOJI]

    positive_score = len(positive_hits) + min(len(positive_emoji), 3)
    negative_score = len(negative_hits) + min(len(negative_emoji), 3)

    if positive_score > negative_score:
        label = "Positive excitement"
        confidence = min(0.95, 0.55 + 0.10 * (positive_score - negative_score))
    elif negative_score > positive_score:
        label = "Negative / complaint"
        confidence = min(0.95, 0.55 + 0.10 * (negative_score - positive_score))
    else:
        label = "Other / unclear"
        confidence = 0.35

    return {
        "label": label,
        "positive_score": positive_score,
        "negative_score": negative_score,
        "confidence": round(confidence, 2),
        "positive_evidence": positive_hits + positive_emoji,
        "negative_evidence": negative_hits + negative_emoji,
    }


def _extract_phrases(comments, min_count=2, limit=15):
    """
    Find repeated two- and three-word topic phrases.
    Each phrase is counted at most once per comment. Single generic words
    are intentionally excluded so the list is more useful as topic evidence.
    """
    phrase_counts = Counter()

    for comment in comments:
        words = re.findall(r"[a-zA-Z][a-zA-Z']{2,}", _normalized(comment))
        words = [
            word for word in words
            if word not in STOP_WORDS and len(word) > 2
        ]

        phrases_in_comment = set()
        for size in (2, 3):
            for index in range(len(words) - size + 1):
                phrase = " ".join(words[index:index + size])
                phrases_in_comment.add(phrase)

        phrase_counts.update(phrases_in_comment)

    return [
        {"phrase": phrase, "count": count}
        for phrase, count in phrase_counts.most_common()
        if count >= min_count
    ][:limit]


def analyze_comments(comments):
    """
    Analyze comment dictionaries with text and optional author, likes,
    and published_at fields. Return categorized comments and phrase trends.
    """
    categorized = {
        "Positive excitement": [],
        "Negative / complaint": [],
        "Other / unclear": [],
    }

    seen = set()
    duplicate_count = 0
    unique_texts = []

    for raw in comments:
        text = (raw.get("text") or "").strip()
        if not text:
            continue

        normalized = _normalized(text)
        if normalized in seen:
            duplicate_count += 1
            continue

        seen.add(normalized)
        unique_texts.append(text)

        result = classify_comment(text)
        try:
            likes = max(0, int(raw.get("likes", 0) or 0))
        except (TypeError, ValueError):
            likes = 0

        item = {
            **raw,
            "text": text,
            "likes": likes,
            **result,
            "engagement_score": round(
                (1 + log1p(likes)) * result["confidence"], 2
            ),
        }
        categorized[result["label"]].append(item)

    for label in categorized:
        categorized[label].sort(
            key=lambda item: (item["engagement_score"], item["likes"]),
            reverse=True,
        )

    return {
        "comments_analyzed": sum(len(items) for items in categorized.values()),
        "duplicate_comments_skipped": duplicate_count,
        "positive": categorized["Positive excitement"],
        "negative": categorized["Negative / complaint"],
        "other": categorized["Other / unclear"],
        "trending_phrases": _extract_phrases(unique_texts),
    }
