
def discover_live_streams(youtube, query="", max_results=10):
    """
    Discover currently live public YouTube videos.

    Uses the authenticated YouTube Data API client.
    Returns metadata and live chat IDs where available.
    """

    max_results = max(1, min(int(max_results), 50))

    search_params = {
        "part": "snippet",
        "type": "video",
        "eventType": "live",
        "order": "viewCount",
        "maxResults": max_results
    }

    if query.strip():
        search_params["q"] = query.strip()

    response = youtube.search().list(
        **search_params
    ).execute()

    search_items = response.get("items", [])

    if not search_items:
        return []

    video_ids = [
        item["id"]["videoId"]
        for item in search_items
        if item.get("id", {}).get("videoId")
    ]

    if not video_ids:
        return []

    details_response = youtube.videos().list(
        part="snippet,liveStreamingDetails",
        id=",".join(video_ids)
    ).execute()

    details_by_id = {
        item["id"]: item
        for item in details_response.get("items", [])
    }

    live_streams = []

    for item in search_items:
        video_id = item.get("id", {}).get("videoId")

        if not video_id:
            continue

        details = details_by_id.get(video_id, {})
        snippet = details.get("snippet", item.get("snippet", {}))
        live_details = details.get("liveStreamingDetails", {})

        live_streams.append({
            "video_id": video_id,
            "title": snippet.get("title", "Untitled"),
            "channel_name": snippet.get("channelTitle", "Unknown"),
            "channel_id": snippet.get("channelId"),
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "live_chat_id": live_details.get("activeLiveChatId"),
            "actual_start_time": live_details.get("actualStartTime")
        })

    return live_streams
