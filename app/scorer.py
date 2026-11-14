
import re


HIGH_IMPACT_WORDS = {
    "wow", "unbelievable", "insane", "crazy",
    "amazing", "incredible", "shocking",
    "secret", "never", "impossible",
    "dangerous", "destroyed", "winning",
    "winner", "fail", "success", "surprise",
    "love", "hate", "best", "worst",
    "actually", "truth", "mistake",
    "important", "powerful", "beautiful",
    "terrible", "perfect", "unexpected",
    "massive", "brilliant", "ridiculous",
    "genius", "hilarious", "exposed"
}

HOOK_PHRASES = [
    "you won't believe",
    "this is why",
    "the truth is",
    "what happened next",
    "here's the secret",
    "i can't believe",
    "wait for it",
    "this changes everything",
    "let me explain",
    "the reason is",
    "here's what happened",
    "you need to see this",
    "the biggest mistake",
    "nobody talks about",
    "listen to this",
    "watch what happens",
    "the problem is",
    "i was shocked"
]

CURIOSITY_PHRASES = [
    "but then",
    "until one day",
    "little did i know",
    "the surprising part",
    "what i discovered",
    "turns out",
    "believe it or not",
    "the crazy thing",
    "here's the thing",
    "the real reason"
]

EMOTION_WORDS = {
    "angry", "excited", "scared", "happy",
    "sad", "furious", "shocked", "confused",
    "frustrated", "proud", "disappointed",
    "terrified", "thrilled", "emotional"
}

FILLER_PHRASES = [
    "um", "uh", "you know", "i mean",
    "kind of", "sort of"
]


def score_segment(text):
    """Score one transcript segment."""

    text_lower = text.lower().strip()
    words = re.findall(r"\b[\w']+\b", text_lower)

    if not words:
        return 0

    score = 1

    score += sum(
        2 for word in words
        if word in HIGH_IMPACT_WORDS
    )

    score += sum(
        5 for phrase in HOOK_PHRASES
        if phrase in text_lower
    )

    score += sum(
        3 for phrase in CURIOSITY_PHRASES
        if phrase in text_lower
    )

    score += sum(
        2 for word in words
        if word in EMOTION_WORDS
    )

    score += min(text.count("?") * 2, 4)
    score += min(text.count("!"), 3)

    if re.search(r"\b(you|your|yourself)\b", text_lower):
        score += 2

    if re.search(r"\b\d+(?:\.\d+)?%?\b", text_lower):
        score += 2

    if len(words) >= 8:
        score += 1

    if len(words) >= 15:
        score += 2

    if len(words) >= 25:
        score += 1

    if len(words) <= 2:
        score -= 2

    for phrase in FILLER_PHRASES:
        if phrase in text_lower:
            score -= 1

    return max(0, score)


def get_context_score(segments, index, radius=2):
    """
    Score a segment using nearby transcript segments.

    The current segment receives the highest weight.
    Nearby segments add context without overpowering it.
    """

    total = 0

    start_index = max(0, index - radius)
    end_index = min(len(segments), index + radius + 1)

    for nearby_index in range(start_index, end_index):
        nearby_text = segments[nearby_index].get("text", "")

        distance = abs(nearby_index - index)

        if distance == 0:
            weight = 1.0
        elif distance == 1:
            weight = 0.5
        else:
            weight = 0.25

        total += score_segment(nearby_text) * weight

    return round(total, 2)


def rank_highlights(segments, limit=5):
    """
    Rank highlights using individual and surrounding context scores.
    Preserve the original segment structure for app compatibility.
    """

    if not segments or limit <= 0:
        return []

    highlights = []

    for index, segment in enumerate(segments):

        text = segment.get("text", "").strip()

        individual_score = score_segment(text)

        if individual_score <= 0:
            continue

        context_score = get_context_score(
            segments,
            index,
            radius=2
        )

        combined_score = round(
            individual_score * 0.7 + context_score * 0.3,
            2
        )

        highlights.append({
            **segment,
            "score": combined_score,
            "individual_score": individual_score,
            "context_score": context_score,
            "context_text": " ".join(
                item.get("text", "").strip()
                for item in segments[
                    max(0, index - 2):min(len(segments), index + 3)
                ]
                if item.get("text", "").strip()
            )
        })

    highlights.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    selected = []
    MIN_GAP = 30

    for candidate in highlights:

        candidate_start = candidate["start"]
        candidate_end = candidate["end"]

        too_close = False

        for chosen in selected:

            chosen_start = chosen["start"]
            chosen_end = chosen["end"]

            if (
                candidate_start < chosen_end + MIN_GAP
                and candidate_end > chosen_start - MIN_GAP
            ):
                too_close = True
                break

        if not too_close:
            selected.append(candidate)

        if len(selected) >= limit:
            break

    selected.sort(
        key=lambda item: item["start"]
    )

    return selected

def rank_highlights_with_reactions(
    segments,
    reaction_windows,
    limit=5,
    reaction_weight=0.30
):
    """
    Combine transcript scores with audience reaction scores.

    Each reaction window must contain video_time_seconds,
    representing its start time on the actual video timeline.
    """

    if not segments or limit <= 0:
        return []

    if not 0 <= reaction_weight <= 1:
        raise ValueError("reaction_weight must be between 0 and 1")

    # First calculate the existing transcript rankings.
    highlights = rank_highlights(
        segments,
        limit=len(segments)
    )

    if not highlights:
        return []

    if not reaction_windows:
        return highlights[:limit]

    max_reaction = max(
        (
            window.get("reaction_score", 0)
            for window in reaction_windows
        ),
        default=0
    )

    max_transcript = max(
        (item["score"] for item in highlights),
        default=0
    )

    for highlight in highlights:

        start = highlight["start"]
        end = highlight["end"]

        # Find audience reactions near this transcript segment.
        nearby_reactions = [
            window
            for window in reaction_windows
            if start - 10 <= window.get("video_time_seconds", -9999) <= end + 10
        ]

        reaction_score = max(
            (
                window.get("reaction_score", 0)
                for window in nearby_reactions
            ),
            default=0
        )

        # Normalize audience reaction strength to transcript scale.
        reaction_strength = (
            reaction_score / max_reaction * max_transcript
            if max_reaction > 0 else 0
        )

        highlight["reaction_score"] = reaction_score
        highlight["reaction_strength"] = round(
            reaction_strength, 2
        )

        highlight["transcript_score"] = highlight["score"]

        highlight["score"] = round(
            highlight["transcript_score"] * (1 - reaction_weight)
            + reaction_strength * reaction_weight,
            2
        )

    highlights.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    selected = []
    min_gap = 30

    for candidate in highlights:

        too_close = any(
            candidate["start"] < chosen["end"] + min_gap
            and candidate["end"] > chosen["start"] - min_gap
            for chosen in selected
        )

        if not too_close:
            selected.append(candidate)

        if len(selected) >= limit:
            break

    selected.sort(key=lambda item: item["start"])

    return selected
