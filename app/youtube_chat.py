
from collections import Counter, defaultdict
from datetime import datetime
import re


def fetch_live_chat_messages(youtube, live_chat_id, page_token=None):
    """Fetch one batch of YouTube live-chat messages."""

    response = youtube.liveChatMessages().list(
        liveChatId=live_chat_id,
        part="id,snippet,authorDetails",
        pageToken=page_token
    ).execute()

    messages = []

    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        author = item.get("authorDetails", {})

        messages.append({
            "time": snippet.get("publishedAt"),
            "text": snippet.get("displayMessage", ""),
            "author": author.get("displayName", "Unknown"),
            "type": snippet.get("type", "textMessageEvent")
        })

    return {
        "messages": messages,
        "next_page_token": response.get("nextPageToken"),
        "polling_interval": response.get("pollingIntervalMillis", 5000)
    }


def analyze_reactions(messages):
    """Analyze message volume, emojis and repeated words."""

    words = []
    emojis = Counter()

    for message in messages:
        message_text = message["text"].lower()

        words.extend(re.findall(r"\b[a-z0-9]{3,}\b", message_text))

        for character in message_text:
            if (
                0x1F000 <= ord(character) <= 0x1FAFF
                or 0x2600 <= ord(character) <= 0x27BF
            ):
                emojis[character] += 1

    common_words = {
        "the", "and", "for", "you", "are", "this",
        "that", "was", "with", "have", "but", "not"
    }

    phrases = Counter(
        word for word in words if word not in common_words
    )

    return {
        "message_count": len(messages),
        "top_phrases": phrases.most_common(5),
        "emoji_counts": dict(emojis.most_common(10))
    }


def analyze_reaction_windows(messages, window_seconds=10):
    """Find periods with unusually high audience activity."""

    windows = defaultdict(list)

    for message in messages:
        timestamp = message.get("time")

        if not timestamp:
            continue

        try:
            moment = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
            seconds = int(moment.timestamp())
            window_start = seconds - (seconds % window_seconds)
            windows[window_start].append(message)
        except (ValueError, TypeError):
            continue

    if not windows:
        return []

    results = []

    for start, window_messages in sorted(windows.items()):
        analysis = analyze_reactions(window_messages)

        emoji_total = sum(analysis["emoji_counts"].values())

        unique_authors = len({
            message.get("author", "Unknown")
            for message in window_messages
        })

        # Limit the influence of repeated emoji spam.
        useful_emoji_count = min(
            emoji_total,
            unique_authors * 2
        )

        score = (
            analysis["message_count"]
            + unique_authors * 2
            + useful_emoji_count
        )

        results.append({
            "window_start": datetime.fromtimestamp(
                start
            ).strftime("%H:%M:%S"),

            "window_start_epoch": start,
            "message_count": analysis["message_count"],
            "top_phrases": analysis["top_phrases"],
            "emoji_counts": analysis["emoji_counts"],
            "reaction_score": score
        })

    average = sum(
        item["reaction_score"] for item in results
    ) / len(results)

    for item in results:
        item["is_spike"] = (
            item["reaction_score"] >= max(5, average * 1.5)
        )

    return results


def rank_reaction_highlights(results, limit=5):
    """Rank the strongest audience-reaction windows."""

    ranked = sorted(
        results,
        key=lambda item: (
            item["reaction_score"],
            item["message_count"]
        ),
        reverse=True
    )

    highlights = []

    for item in ranked[:limit]:
        highlights.append({
            "time": item["window_start"],
            "score": item["reaction_score"],
            "messages": item["message_count"],
            "top_words": item["top_phrases"],
            "emojis": item["emoji_counts"],
            "is_spike": item["is_spike"]
        })

    return highlights


def synchronize_reaction_windows(
    reaction_windows,
    recording_start_epoch
):
    """
    Convert UTC reaction timestamps into video-relative seconds.
    """

    synchronized = []

    for window in reaction_windows:
        video_time_seconds = (
            window["window_start_epoch"]
            - recording_start_epoch
        )

        if video_time_seconds < 0:
            continue

        synchronized.append({
            **window,
            "video_time_seconds": video_time_seconds
        })

    return synchronized


if __name__ == "__main__":

    demo_messages = [
        {"time": "2026-11-14T10:00:01Z", "text": "Hello everyone"},
        {"time": "2026-11-14T10:00:03Z", "text": "Nice stream"},
        {"time": "2026-11-14T10:00:05Z", "text": "Great content"},
        {"time": "2026-11-14T10:00:11Z", "text": "WOW 🔥🔥"},
        {"time": "2026-11-14T10:00:13Z", "text": "INSANE 🔥"},
        {"time": "2026-11-14T10:00:14Z", "text": "OMG 😂"},
        {"time": "2026-11-14T10:00:15Z", "text": "WOW WOW"},
        {"time": "2026-11-14T10:00:16Z", "text": "Amazing ❤️"},
        {"time": "2026-11-14T10:00:31Z", "text": "Thanks for watching"},
    ]

    print("\nVIRALCUT AI - REACTION DETECTOR")
    print("=" * 40)

    results = analyze_reaction_windows(demo_messages)

    print("\nALL REACTION WINDOWS")
    print("=" * 40)

    for result in results:
        print(
            result["window_start"],
            "| Score:", result["reaction_score"],
            "| Messages:", result["message_count"],
            "| Spike:", result["is_spike"]
        )

    print("\nTOP 5 REACTION HIGHLIGHTS")
    print("=" * 40)

    highlights = rank_reaction_highlights(results, limit=5)

    for number, highlight in enumerate(highlights, 1):
        print(f"\n#{number} - {highlight['time']}")
        print("Score:", highlight["score"])
        print("Messages:", highlight["messages"])
        print("Top words:", highlight["top_words"])
        print("Emojis:", highlight["emojis"])
        print("Spike:", highlight["is_spike"])
