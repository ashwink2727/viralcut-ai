
from youtube_auth import get_youtube_service
from youtube_discovery import discover_live_streams

youtube = get_youtube_service()

print("\nVIRALCUT AI - YOUTUBE GAMING DISCOVERY")
print("=" * 45)

streams = discover_live_streams(
    youtube,
    query="gaming",
    max_results=10
)

if not streams:
    print("No live gaming streams found right now.")

else:
    for number, stream in enumerate(streams, 1):
        print(f"\n#{number} - {stream['title']}")
        print("Channel:", stream["channel_name"])
        print("Video:", stream["video_url"])
        print(
            "Live chat:",
            "Available" if stream["live_chat_id"] else "Unavailable"
        )
        print("Started:", stream["actual_start_time"] or "Unknown")
