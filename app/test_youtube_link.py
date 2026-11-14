
from urllib.parse import urlparse, parse_qs
from googleapiclient.errors import HttpError

from youtube_auth import get_youtube_service
from youtube_chat import (
    fetch_live_chat_messages,
    analyze_reaction_windows,
    rank_reaction_highlights
)


def extract_video_id(url):
    parsed = urlparse(url.strip())

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.strip("/").split("/")[0]

    if parsed.hostname and parsed.hostname.endswith("youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]

        parts = parsed.path.strip("/").split("/")

        if len(parts) >= 2 and parts[0] in ("live", "shorts", "embed"):
            return parts[1]

    return None


def main():
    print("\nVIRALCUT AI - TEST YOUTUBE LIVESTREAM")
    print("=" * 45)

    url = input("\nPaste YouTube livestream URL: ").strip()
    video_id = extract_video_id(url)

    if not video_id:
        print("Invalid YouTube URL.")
        return

    youtube = get_youtube_service()

    print("\nChecking livestream...")

    response = youtube.videos().list(
        part="snippet,liveStreamingDetails",
        id=video_id
    ).execute()

    videos = response.get("items", [])

    if not videos:
        print("Video not found or unavailable through the API.")
        return

    video = videos[0]
    details = video.get("liveStreamingDetails", {})
    snippet = video.get("snippet", {})

    print("Title:", snippet.get("title"))
    print("Channel:", snippet.get("channelTitle"))

    live_chat_id = details.get("activeLiveChatId")

    if not live_chat_id:
        print("\nNo active live chat found.")
        print("The video may not be live or chat may be disabled.")
        return

    print("\nLive chat found! Fetching messages...")

    try:
        batch = fetch_live_chat_messages(
            youtube,
            live_chat_id
        )

        messages = batch["messages"]

        print("Messages received:", len(messages))
        print("Next polling interval:", batch["polling_interval"], "ms")

        if not messages:
            print("No new chat messages in this batch.")
            return

        results = analyze_reaction_windows(messages)

        highlights = rank_reaction_highlights(
            results,
            limit=5
        )

        print("\nREACTION WINDOWS")
        print("=" * 45)

        for result in results:
            print(
                result["window_start"],
                "| Score:", result["reaction_score"],
                "| Messages:", result["message_count"],
                "| Spike:", result["is_spike"]
            )

        print("\nTOP AUDIENCE REACTIONS")
        print("=" * 45)

        for number, item in enumerate(highlights, 1):
            print(f"\n#{number} - {item['time']}")
            print("Score:", item["score"])
            print("Messages:", item["messages"])
            print("Words:", item["top_words"])
            print("Emojis:", item["emojis"])

    except HttpError as error:
        print("\nYouTube API error:", error)


if __name__ == "__main__":
    main()
