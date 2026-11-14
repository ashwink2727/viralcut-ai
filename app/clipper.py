import os
import subprocess


def get_video_duration(video_path):
    """Get video duration using FFprobe."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def ass_time(seconds):
    """Convert seconds into ASS subtitle timestamp."""
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    centiseconds = int((seconds - int(seconds)) * 100)
    return (
        f"{hours}:{minutes:02d}:"
        f"{whole_seconds:02d}.{centiseconds:02d}"
    )


def escape_ass_text(text):
    """Escape special ASS subtitle characters."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


def get_all_words(segments):
    """Collect timestamped words from transcript segments."""
    words = []
    for segment in segments:
        for word in segment.get("words", []):
            start = word.get("start")
            end = word.get("end")
            text = word.get("word", "").strip()
            if start is None or end is None or not text:
                continue
            if end <= start:
                continue
            words.append({
                "start": float(start),
                "end": float(end),
                "word": text,
            })
    words.sort(key=lambda item: item["start"])
    return words


def find_story_boundaries(
    highlight,
    all_segments,
    video_duration,
    clip_length,
):
    """
    Expand a highlight to nearby sentence boundaries.

    Word-level punctuation is used when available, otherwise transcript
    segment boundaries are used. Snapping is limited to +/- 6 seconds
    around the computed window so a highlight does not drift.
    """
    anchor_start = max(0.0, float(highlight["start"]))
    anchor_end = min(video_duration, float(highlight["end"]))

    if anchor_end <= anchor_start:
        return anchor_start, anchor_start

    target_length = max(
        float(clip_length),
        anchor_end - anchor_start,
    )

    center = (anchor_start + anchor_end) / 2
    start = max(0.0, center - target_length / 2)
    end = min(video_duration, start + target_length)
    start = max(0.0, end - target_length)

    if start > anchor_start:
        start = anchor_start
    if end < anchor_end:
        end = anchor_end

    words = get_all_words(all_segments)

    if words:
        sentence_endings = (".", "!", "?", ";")

        # Move start backwards to the nearest sentence boundary, but never
        # further than 6 seconds and never past anchor_start.
        snap_min = max(0.0, start - 6.0)
        best_start = None
        for word in words:
            if snap_min <= word["start"] <= anchor_start:
                if word["word"].endswith(sentence_endings):
                    if best_start is None or word["start"] < best_start:
                        best_start = word["start"]
        if best_start is not None and best_start <= start:
            start = best_start

        # Move end forwards to the next sentence boundary after anchor_end,
        # again limited to a 6 second forward snap.
        snap_max = min(video_duration, anchor_end + 6.0)
        for word in words:
            if anchor_end <= word["end"] <= snap_max:
                if word["word"].endswith(sentence_endings):
                    end = max(end, word["end"])
                    break

    else:
        # Fallback when word timestamps are unavailable.
        for segment in all_segments:
            segment_start = float(segment.get("start", 0))
            segment_end = float(segment.get("end", 0))
            if segment_start <= start <= segment_end:
                start = segment_start
            if segment_start <= end <= segment_end:
                end = segment_end
                break

    start = max(0.0, min(start, anchor_start))
    end = min(video_duration, max(end, anchor_end))
    return start, end


def build_caption_groups(segments, clip_start, clip_end):
    """Group timestamped words into short caption lines."""
    words = []
    for segment in segments:
        for word in segment.get("words", []):
            start = word.get("start")
            end = word.get("end")
            text = word.get("word", "").strip()
            if start is None or end is None or not text:
                continue
            if end <= clip_start or start >= clip_end:
                continue
            words.append({
                "start": max(start, clip_start),
                "end": min(end, clip_end),
                "word": text,
            })
    words.sort(key=lambda item: item["start"])

    groups = []
    current_group = []
    for word in words:
        current_group.append(word)
        punctuation = word["word"].endswith(
            (".", "!", "?", ",", ";", ":")
        )
        if len(current_group) >= 4 or punctuation:
            groups.append(current_group)
            current_group = []
    if current_group:
        groups.append(current_group)
    return groups


def create_ass_file(segments, clip_start, clip_end, output_path):
    """Create animated karaoke-style ASS captions."""
    groups = build_caption_groups(segments, clip_start, clip_end)

    header = """[Script Info]
Title: ViralCut AI Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,70,70,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []
    for group in groups:
        group_start = max(0, group[0]["start"] - clip_start)
        group_end = max(
            group_start + 0.1,
            group[-1]["end"] - clip_start,
        )
        caption_text = r"{\an2\pos(540,1650)}"
        for word in group:
            duration = max(
                1,
                round((word["end"] - word["start"]) * 100),
            )
            caption_text += (
                f"{{\\k{duration}}}"
                f"{escape_ass_text(word['word'])} "
            )
        dialogue_lines.append(
            "Dialogue: 0,"
            + ass_time(group_start)
            + ","
            + ass_time(group_end)
            + ",Default,,0,0,0,,"
            + caption_text.strip()
        )

    with open(output_path, "w", encoding="utf-8-sig") as file:
        file.write(header)
        file.write("\n".join(dialogue_lines))


def _ffmpeg_subtitle_path(path):
    """
    Escape a subtitle path for FFmpeg's subtitles filter.

    FFmpeg's filter parser needs forward slashes and escaped colons
    (Windows drive letters) and quotes.
    """
    absolute = os.path.abspath(path).replace("\\", "/")
    absolute = absolute.replace(":", r"\:")
    absolute = absolute.replace("'", r"\'")
    return absolute


def create_clip(
    video_path,
    start_time,
    end_time,
    output_path,
    caption_path=None,
):
    """Create vertical video with blurred background."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    video_filter = (
        "[0:v]split=2[bgsrc][fg];"
        "[bgsrc]scale=270:480:force_original_aspect_ratio=increase,"
        "crop=270:480,boxblur=8:2,scale=1080:1920[background];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[foreground];"
        "[background][foreground]overlay=(W-w)/2:(H-h)/2,"
        "setsar=1"
    )

    if caption_path and os.path.exists(caption_path):
        safe_subtitle_path = _ffmpeg_subtitle_path(caption_path)
        video_filter += f",subtitles='{safe_subtitle_path}'"

    video_filter += ",format=yuv420p[video]"

    command = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(end_time - start_time),
        "-filter_complex", video_filter,
        "-map", "[video]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-threads", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    return output_path


def create_highlight_clips(
    video_path,
    highlights,
    clip_length=30,
    all_segments=None,
):
    """Create vertical clips with story-aware boundaries."""
    duration = get_video_duration(video_path)

    output_folder = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "outputs",
    )
    os.makedirs(output_folder, exist_ok=True)

    if all_segments is None:
        all_segments = highlights

    created_clips = []

    for index, moment in enumerate(highlights, 1):
        start, end = find_story_boundaries(
            moment,
            all_segments,
            duration,
            clip_length,
        )

        output_path = os.path.join(
            output_folder,
            f"vertical_highlight_{index}.mp4",
        )
        caption_path = os.path.join(
            output_folder,
            f"captions_{index}.ass",
        )

        create_ass_file(
            all_segments,
            start,
            end,
            caption_path,
        )
        create_clip(
            video_path,
            start,
            end,
            output_path,
            caption_path,
        )
        created_clips.append(output_path)

    return created_clips