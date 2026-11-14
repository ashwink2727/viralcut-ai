import os
import time
import json
import hashlib
import datetime
from urllib.parse import urlparse, parse_qs

import streamlit as st
from googleapiclient.errors import HttpError

from analyzer import transcribe_video
from scorer import rank_highlights
from clipper import create_highlight_clips
from youtube_auth import get_youtube_service
from youtube_chat import (
    fetch_live_chat_messages,
    analyze_reaction_windows,
    rank_reaction_highlights,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
OUTPUT_DIR = os.path.join(APP_DIR, "outputs")
PROJECTS_DIR = os.path.join(APP_DIR, "projects")
PROJECTS_INDEX = os.path.join(PROJECTS_DIR, "index.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PROJECTS_DIR, exist_ok=True)

st.set_page_config(
    page_title="ViralCut AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# PREMIUM DARK THEME — stable selectors only
# ============================================================

st.markdown("""
<style>
:root {
    --vc-bg: #0a0a0f;
    --vc-surface: #12121a;
    --vc-surface-2: #1a1a24;
    --vc-border: #262630;
    --vc-border-strong: #3a3a48;
    --vc-text: #f5f5f7;
    --vc-text-dim: #a0a0ab;
    --vc-accent: #8b5cf6;
    --vc-accent-hover: #a78bfa;
    --vc-success: #10b981;
    --vc-danger: #ef4444;
    --vc-warning: #f59e0b;
}

.stApp {
    background: radial-gradient(circle at 15% 0%, #1a1030 0%, transparent 40%),
                radial-gradient(circle at 85% 100%, #101a2e 0%, transparent 40%),
                var(--vc-bg);
    color: var(--vc-text);
}

/* Typography */
html, body, [class*="css"], .stMarkdown, .stText, p, span, div {
    color: var(--vc-text);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, Helvetica, Arial, sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--vc-text) !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

h1 { font-size: 2.25rem !important; line-height: 1.15 !important; }
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.15rem !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--vc-surface);
    border-right: 1px solid var(--vc-border);
}
section[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}

/* Buttons */
.stButton > button {
    background: var(--vc-accent);
    color: white;
    border-radius: 8px;
    border: 1px solid var(--vc-accent);
    padding: 0.55rem 1.1rem;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.15s ease;
    width: 100%;
}
.stButton > button:hover {
    background: var(--vc-accent-hover);
    border-color: var(--vc-accent-hover);
    color: white;
}
.stButton > button:focus {
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25) !important;
}

.stDownloadButton > button {
    background: transparent;
    color: var(--vc-text);
    border-radius: 8px;
    border: 1px solid var(--vc-border-strong);
    padding: 0.5rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    transition: all 0.15s ease;
    width: 100%;
}
.stDownloadButton > button:hover {
    background: var(--vc-surface-2);
    border-color: var(--vc-accent);
    color: var(--vc-text);
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea textarea,
.stNumberInput input {
    background: var(--vc-surface-2) !important;
    border: 1px solid var(--vc-border) !important;
    border-radius: 8px !important;
    color: var(--vc-text) !important;
    padding: 0.55rem 0.75rem !important;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: var(--vc-accent) !important;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15) !important;
}

/* File uploader */
section[data-testid="stFileUploaderDropzone"] {
    background: var(--vc-surface) !important;
    border: 2px dashed var(--vc-border-strong) !important;
    border-radius: 12px !important;
    padding: 2rem !important;
    transition: all 0.2s ease;
}
section[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--vc-accent) !important;
    background: var(--vc-surface-2) !important;
}

/* Sliders */
.stSlider > div > div > div > div {
    background: var(--vc-accent) !important;
}

/* Progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--vc-accent), var(--vc-accent-hover)) !important;
}

/* Expander */
.streamlit-expanderHeader, details summary {
    background: var(--vc-surface) !important;
    border: 1px solid var(--vc-border) !important;
    border-radius: 8px !important;
    padding: 0.6rem 0.9rem !important;
    font-weight: 500;
}

/* Alerts */
.stAlert {
    border-radius: 10px !important;
    border: 1px solid var(--vc-border) !important;
}

/* Divider */
hr {
    border-color: var(--vc-border) !important;
    margin: 1.5rem 0 !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: var(--vc-text-dim) !important;
    font-weight: 500 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--vc-text) !important;
    border-bottom-color: var(--vc-accent) !important;
}

/* Cards — custom HTML blocks I control, so no brittle Streamlit selectors */
.vc-card {
    background: var(--vc-surface);
    border: 1px solid var(--vc-border);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
}
.vc-card-elevated {
    background: linear-gradient(180deg, var(--vc-surface-2), var(--vc-surface));
    border: 1px solid var(--vc-border);
    border-radius: 14px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}
.vc-hero {
    background: linear-gradient(135deg, #1a1030 0%, #12121a 60%, #101a2e 100%);
    border: 1px solid var(--vc-border);
    border-radius: 18px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.5rem;
}
.vc-hero h1 {
    margin: 0 0 0.5rem 0 !important;
    font-size: 2rem !important;
}
.vc-hero p {
    color: var(--vc-text-dim);
    margin: 0;
    font-size: 1rem;
}
.vc-badge {
    display: inline-block;
    background: rgba(139, 92, 246, 0.15);
    color: var(--vc-accent-hover);
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 999px;
    padding: 0.2rem 0.7rem;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin-bottom: 0.75rem;
}
.vc-badge-success {
    background: rgba(16, 185, 129, 0.15);
    color: #6ee7b7;
    border-color: rgba(16, 185, 129, 0.35);
}
.vc-meta {
    color: var(--vc-text-dim);
    font-size: 0.85rem;
}
.vc-meta strong {
    color: var(--vc-text);
    font-weight: 600;
}
.vc-stat {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--vc-text);
    letter-spacing: -0.02em;
}
.vc-stat-label {
    color: var(--vc-text-dim);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background: transparent;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def extract_video_id(url):
    parsed = urlparse(url.strip())
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.strip("/").split("/")[0]
    if parsed.hostname and (
        parsed.hostname == "youtube.com"
        or parsed.hostname.endswith(".youtube.com")
    ):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] in ("live", "shorts", "embed"):
            return parts[1]
    return None


@st.cache_data(show_spinner=False)
def cached_transcription(video_path, video_hash):
    return transcribe_video(video_path)


def _cleanup_outputs():
    if not os.path.isdir(OUTPUT_DIR):
        return
    for name in os.listdir(OUTPUT_DIR):
        if name.startswith(("vertical_highlight_", "captions_")):
            try:
                os.remove(os.path.join(OUTPUT_DIR, name))
            except OSError:
                pass


def load_projects():
    if not os.path.exists(PROJECTS_INDEX):
        return []
    try:
        with open(PROJECTS_INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_project(entry):
    projects = load_projects()
    projects.insert(0, entry)
    projects = projects[:30]
    with open(PROJECTS_INDEX, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2)


def init_state():
    defaults = {
        "page": "Dashboard",
        "clips": None,
        "last_project": None,
        "yt_result": None,
        "clip_length": 30,
        "clip_count": 5,
        "whisper_model": os.getenv("VIRALCUT_WHISPER_MODEL", "base"),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_state()


def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='padding:0.5rem 0 1.5rem 0;'>"
            "<div style='font-size:1.4rem;font-weight:700;"
            "letter-spacing:-0.02em;'>🎬 ViralCut AI</div>"
            "<div class='vc-meta' style='margin-top:0.25rem;'>"
            "AI Video Clipping Studio</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        pages = [
            ("Dashboard", "🏠 Dashboard"),
            ("Create Clips", "✨ Create Clips"),
            ("My Projects", "📁 My Projects"),
            ("YouTube Analysis", "🔗 YouTube Analysis"),
            ("Settings", "⚙️ Settings"),
        ]
        for key, label in pages:
            selected = st.session_state["page"] == key
            if st.button(
                label,
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state["page"] = key
                st.rerun()

        st.markdown("---")
        st.markdown(
            "<div class='vc-meta' style='font-size:0.75rem;'>"
            "Local processing · No cloud uploads<br>"
            "Powered by Faster-Whisper + FFmpeg"
            "</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# PAGE: DASHBOARD
# ============================================================

def page_dashboard():
    st.markdown(
        "<div class='vc-hero'>"
        "<span class='vc-badge'>PREMIUM</span>"
        "<h1>Welcome to ViralCut AI</h1>"
        "<p>Turn long-form video into short, vertical, caption-perfect clips "
        "with local AI transcription and intelligent highlight detection.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    projects = load_projects()
    clips_total = sum(len(p.get("clips", [])) for p in projects)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "<div class='vc-card'>"
            "<div class='vc-stat-label'>Projects</div>"
            f"<div class='vc-stat'>{len(projects)}</div>"
            "<div class='vc-meta'>Rendered sessions</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            "<div class='vc-card'>"
            "<div class='vc-stat-label'>Clips generated</div>"
            f"<div class='vc-stat'>{clips_total}</div>"
            "<div class='vc-meta'>Across all projects</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            "<div class='vc-card'>"
            "<div class='vc-stat-label'>Transcription</div>"
            f"<div class='vc-stat' style='font-size:1.25rem;'>"
            f"{st.session_state['whisper_model'].upper()}</div>"
            "<div class='vc-meta'>Faster-Whisper on CPU</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### Quick actions")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='vc-card-elevated'>"
            "<h3 style='margin-top:0;'>✨ Create a new clip set</h3>"
            "<div class='vc-meta'>Upload a video, transcribe locally, and "
            "render 9:16 clips with captions.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Start creating", key="dash_start"):
            st.session_state["page"] = "Create Clips"
            st.rerun()
    with c2:
        st.markdown(
            "<div class='vc-card-elevated'>"
            "<h3 style='margin-top:0;'>🔗 Analyze a YouTube video</h3>"
            "<div class='vc-meta'>Inspect available chat replay reactions for a "
            "video and preview audience reaction peaks.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open YouTube analysis", key="dash_yt"):
            st.session_state["page"] = "YouTube Analysis"
            st.rerun()

    if projects:
        st.markdown("### Recent projects")
        for entry in projects[:5]:
            st.markdown(
                "<div class='vc-card'>"
                f"<div><strong>{entry.get('title', 'Untitled')}</strong></div>"
                f"<div class='vc-meta'>"
                f"{entry.get('created_at', '')} · "
                f"{entry.get('clip_count', 0)} clips · "
                f"{entry.get('duration_label', 'unknown duration')}"
                f"</div>"
                "</div>",
                unsafe_allow_html=True,
            )


# ============================================================
# PAGE: CREATE CLIPS
# ============================================================

def page_create_clips():
    st.markdown(
        "<div class='vc-hero'>"
        "<span class='vc-badge'>WORKFLOW</span>"
        "<h1>Create vertical clips</h1>"
        "<p>Upload a video, choose your target length, and let ViralCut AI "
        "find the most clip-worthy moments.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### 1 · Upload")
    uploaded_file = st.file_uploader(
        "Drag and drop your video here",
        type=["mp4", "mov", "mkv", "avi"],
        help="Supported formats: MP4, MOV, MKV, AVI.",
    )

    video_path = None
    video_hash = None
    file_size_mb = 0

    if uploaded_file is not None:
        video_bytes = uploaded_file.getvalue()
        video_hash = hashlib.sha256(video_bytes).hexdigest()
        file_size_mb = len(video_bytes) / (1024 * 1024)

        safe_name = os.path.basename(uploaded_file.name)
        video_path = os.path.join(UPLOAD_DIR, safe_name)

        needs_write = (
            not os.path.exists(video_path)
            or os.path.getsize(video_path) != len(video_bytes)
        )
        if not needs_write:
            with open(video_path, "rb") as f:
                needs_write = (
                    hashlib.sha256(f.read()).hexdigest() != video_hash
                )
        if needs_write:
            with open(video_path, "wb") as f:
                f.write(video_bytes)

        st.markdown(
            "<div class='vc-card'>"
            f"<span class='vc-badge vc-badge-success'>UPLOADED</span>"
            f"<div><strong>{safe_name}</strong></div>"
            f"<div class='vc-meta'>{file_size_mb:.1f} MB · "
            f"ready for transcription</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.video(video_path)

    st.markdown("### 2 · Settings")
    c1, c2 = st.columns(2)
    with c1:
        clip_length = st.slider(
            "Target clip length (seconds)",
            min_value=15, max_value=90,
            value=st.session_state["clip_length"], step=5,
        )
        st.session_state["clip_length"] = clip_length
    with c2:
        clip_count = st.slider(
            "Maximum number of clips",
            min_value=1, max_value=10,
            value=st.session_state["clip_count"],
        )
        st.session_state["clip_count"] = clip_count

    st.markdown("### 3 · Render")
    run = st.button(
        "🚀 Analyze & generate clips",
        use_container_width=True,
        disabled=video_path is None,
    )

    if run and video_path is not None:
        _run_pipeline(video_path, video_hash, clip_length, clip_count)

    # Persistent results — survive reruns
    if st.session_state.get("clips"):
        _render_results(st.session_state["clips"])


def _run_pipeline(video_path, video_hash, clip_length, clip_count):
    try:
        _cleanup_outputs()
        st.session_state["clips"] = None

        total_started = time.perf_counter()
        progress = st.progress(0)
        status = st.empty()

        # STAGE 1 — Transcription
        status.info("Stage 1 / 3 · Transcribing speech locally…")
        t0 = time.perf_counter()
        result = cached_transcription(video_path, video_hash)
        transcription_seconds = time.perf_counter() - t0
        segments = result["segments"]
        progress.progress(45)
        st.success(
            f"Transcription complete in {transcription_seconds/60:.1f} min "
            f"(language: {result['language']})."
        )

        if not segments:
            progress.progress(100)
            status.success("Finished.")
            st.warning("No speech was detected in this video.")
            return

        # STAGE 2 — Highlight scoring
        status.info("Stage 2 / 3 · Ranking highlight candidates…")
        t0 = time.perf_counter()
        highlights = rank_highlights(segments, limit=clip_count)
        scoring_seconds = time.perf_counter() - t0
        progress.progress(55)

        if not highlights:
            progress.progress(100)
            status.success("Analysis finished.")
            st.info(
                "No highlight candidates matched the scoring thresholds. "
                "Try a longer or more speech-dense video."
            )
            return

        st.success(
            f"Found {len(highlights)} candidate moments in "
            f"{scoring_seconds:.1f}s."
        )

        with st.expander("Detected highlights (before rendering)"):
            for i, m in enumerate(highlights, 1):
                st.write(
                    f"**#{i}** · {m['start']}s → {m['end']}s · "
                    f"score {m['score']} · {m['text'][:120]}…"
                )

        with st.expander("Full transcript"):
            for seg in segments:
                st.write(
                    f"{seg['start']}s – {seg['end']}s: {seg['text']}"
                )

        # STAGE 3 — Rendering
        status.info("Stage 3 / 3 · Rendering vertical clips with captions…")
        t0 = time.perf_counter()
        clips = create_highlight_clips(
            video_path,
            highlights,
            clip_length=clip_length,
            all_segments=segments,
        )
        rendering_seconds = time.perf_counter() - t0
        progress.progress(100)

        total_seconds = time.perf_counter() - total_started
        status.success(
            f"Done · total {total_seconds/60:.1f} min · "
            f"transcription {transcription_seconds/60:.1f} min · "
            f"rendering {rendering_seconds/60:.1f} min"
        )

        st.session_state["clips"] = clips

        # Save project metadata
        save_project({
            "title": os.path.basename(video_path),
            "created_at": datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),
            "clip_count": len(clips),
            "duration_label": f"target {clip_length}s per clip",
            "clips": [os.path.basename(c) for c in clips],
        })

    except Exception as error:
        st.error(f"Processing failed: {error}")
        st.exception(error)


def _render_results(clips):
    st.markdown("---")
    st.markdown(
        "<div class='vc-hero' style='padding:1.25rem 1.5rem;'>"
        "<span class='vc-badge vc-badge-success'>READY</span>"
        f"<h2 style='margin:0.25rem 0 0 0;font-size:1.35rem;'>"
        f"{len(clips)} clip{'s' if len(clips) != 1 else ''} generated</h2>"
        "<p style='margin-top:0.5rem;'>Preview each clip and download "
        "the MP4 files below.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    for i, clip in enumerate(clips, 1):
        if not os.path.exists(clip):
            st.warning(f"Clip {i} missing on disk: {os.path.basename(clip)}")
            continue

        size_mb = os.path.getsize(clip) / (1024 * 1024)
        st.markdown(
            "<div class='vc-card'>"
            f"<span class='vc-badge'>CLIP {i}</span>"
            f"<div><strong>{os.path.basename(clip)}</strong></div>"
            f"<div class='vc-meta'>9:16 · MP4 · H.264 · {size_mb:.1f} MB · "
            f"karaoke captions burned in</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.video(clip)
        with c_right:
            st.markdown(
                "<div class='vc-card' style='min-height:180px;'>"
                "<div class='vc-stat-label'>Ready to publish</div>"
                "<div class='vc-meta' style='margin-top:0.5rem;'>"
                "Vertical 1080×1920 with animated captions. "
                "Upload directly to Shorts, Reels, or TikTok."
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            with open(clip, "rb") as f:
                st.download_button(
                    f"⬇️ Download clip {i}",
                    data=f.read(),
                    file_name=f"viralcut_highlight_{i}.mp4",
                    mime="video/mp4",
                    key=f"dl_{i}",
                )


# ============================================================
# PAGE: MY PROJECTS
# ============================================================

def page_projects():
    st.markdown(
        "<div class='vc-hero'>"
        "<span class='vc-badge'>HISTORY</span>"
        "<h1>My projects</h1>"
        "<p>Local project history. Only metadata and file references are "
        "stored — no video content leaves your machine.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    projects = load_projects()
    if not projects:
        st.info(
            "No projects yet. Generated clip sets will appear here automatically."
        )
        if st.button("Create your first clip set"):
            st.session_state["page"] = "Create Clips"
            st.rerun()
        return

    for entry in projects:
        st.markdown(
            "<div class='vc-card'>"
            f"<div><strong>{entry.get('title', 'Untitled')}</strong></div>"
            f"<div class='vc-meta'>"
            f"Created {entry.get('created_at', 'unknown')} · "
            f"{entry.get('clip_count', 0)} clips · "
            f"{entry.get('duration_label', '')}"
            f"</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.caption(
        "Clip files from previous sessions live in the app's outputs folder "
        "and may be overwritten by newer renders. Only the most recent set is "
        "guaranteed to remain downloadable."
    )


# ============================================================
# PAGE: YOUTUBE ANALYSIS
# ============================================================

def page_youtube():
    st.markdown(
        "<div class='vc-hero'>"
        "<span class='vc-badge'>AUDIENCE SIGNAL</span>"
        "<h1>YouTube analysis</h1>"
        "<p>Inspect the audience reaction signal from a video's available "
        "chat replay. This describes chat intensity — it does not map to "
        "exact video timestamps.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    youtube_url = st.text_input(
        "YouTube video URL",
        placeholder="https://www.youtube.com/watch?v=...",
    )

    if st.button("Analyze", use_container_width=True):
        video_id = extract_video_id(youtube_url)
        if not video_id:
            st.error("Please enter a valid YouTube video URL.")
            return

        try:
            with st.spinner("Connecting to YouTube…"):
                youtube = get_youtube_service()
                response = youtube.videos().list(
                    part="snippet,liveStreamingDetails",
                    id=video_id,
                ).execute()
                videos = response.get("items", [])

                if not videos:
                    st.error("Video not found or unavailable.")
                    return

                video = videos[0]
                snippet = video.get("snippet", {})
                details = video.get("liveStreamingDetails", {})

                st.markdown(
                    "<div class='vc-card-elevated'>"
                    "<span class='vc-badge'>FOUND</span>"
                    f"<h3 style='margin:0.25rem 0;'>"
                    f"{snippet.get('title', 'Unknown title')}</h3>"
                    f"<div class='vc-meta'>"
                    f"{snippet.get('channelTitle', 'Unknown channel')} · "
                    f"ID {video_id}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

                live_chat_id = details.get("activeLiveChatId")
                if not live_chat_id:
                    st.warning(
                        "This video has no accessible chat replay. "
                        "Audience reaction analysis is unavailable."
                    )
                    return

                with st.spinner("Analyzing chat signal…"):
                    batch = fetch_live_chat_messages(youtube, live_chat_id)
                    messages = batch["messages"]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(
                            "<div class='vc-card'>"
                            "<div class='vc-stat-label'>Messages</div>"
                            f"<div class='vc-stat'>{len(messages)}</div>"
                            "</div>",
                            unsafe_allow_html=True,
                        )
                    with col2:
                        st.markdown(
                            "<div class='vc-card'>"
                            "<div class='vc-stat-label'>Polling interval</div>"
                            f"<div class='vc-stat' style='font-size:1.1rem;'>"
                            f"{batch['polling_interval']} ms</div>"
                            "</div>",
                            unsafe_allow_html=True,
                        )

                    if not messages:
                        st.warning("No chat messages were returned.")
                        return

                    results = analyze_reaction_windows(messages)
                    highlights = rank_reaction_highlights(results, limit=5)

                    st.markdown("### Reaction windows")
                    for r in results:
                        st.write(
                            f"**{r['window_start']}** · "
                            f"score {r['reaction_score']} · "
                            f"{r['message_count']} messages · "
                            f"{'spike' if r['is_spike'] else 'normal'}"
                        )

                    st.markdown("### Top reactions")
                    for i, item in enumerate(highlights, 1):
                        with st.expander(
                            f"#{i} · {item['time']} · score {item['score']}"
                        ):
                            st.write("Messages:", item["messages"])
                            st.write("Top words:", item["top_words"])
                            st.write("Emojis:", item["emojis"])
                            st.write("Spike:", item["is_spike"])

                    st.caption(
                        "Chat timestamps are UTC wall-clock times and are not "
                        "converted to video-relative seconds."
                    )

        except HttpError as error:
            st.error(f"YouTube API error: {error}")
        except Exception as error:
            st.error(f"Something went wrong: {error}")
            st.exception(error)


# ============================================================
# PAGE: SETTINGS
# ============================================================

def page_settings():
    st.markdown(
        "<div class='vc-hero'>"
        "<span class='vc-badge'>CONFIGURATION</span>"
        "<h1>Settings</h1>"
        "<p>Session preferences for this browser session. Changes apply on "
        "the next render.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Clip defaults")
    st.session_state["clip_length"] = st.slider(
        "Default clip length (seconds)",
        min_value=15, max_value=90,
        value=st.session_state["clip_length"], step=5,
        key="settings_clip_length",
    )
    st.session_state["clip_count"] = st.slider(
        "Default number of clips",
        min_value=1, max_value=10,
        value=st.session_state["clip_count"],
        key="settings_clip_count",
    )

    st.markdown("### Transcription")
    st.text_input(
        "Whisper model (read-only)",
        value=st.session_state["whisper_model"],
        disabled=True,
        help="Set the VIRALCUT_WHISPER_MODEL environment variable and "
             "restart the app to change this.",
    )

    st.markdown("### Export")
    st.markdown(
        "<div class='vc-card'>"
        "<div class='vc-meta'>"
        "Exports are fixed at 1080×1920 vertical MP4 (H.264, AAC 128 kbps) "
        "with karaoke captions burned in. Export presets are not yet "
        "configurable."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### AI API")
    st.markdown(
        "<div class='vc-card'>"
        "<div class='vc-meta'>"
        "All processing runs locally. No cloud AI APIs are configured or "
        "required. An optional DeepSeek integration is not yet implemented."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Storage locations")
    st.markdown(
        "<div class='vc-card'>"
        f"<div class='vc-meta'>Uploads: <code>{UPLOAD_DIR}</code></div>"
        f"<div class='vc-meta'>Rendered clips: <code>{OUTPUT_DIR}</code></div>"
        f"<div class='vc-meta'>Project history: <code>{PROJECTS_INDEX}</code></div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# ROUTER
# ============================================================

render_sidebar()

page = st.session_state["page"]
if page == "Dashboard":
    page_dashboard()
elif page == "Create Clips":
    page_create_clips()
elif page == "My Projects":
    page_projects()
elif page == "YouTube Analysis":
    page_youtube()
elif page == "Settings":
    page_settings()