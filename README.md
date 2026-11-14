# 🎬 ViralCut AI

### Turn long videos into scroll-stopping short videos with AI.

ViralCut AI is an AI-powered video clipping studio that transforms long-form videos into engaging vertical clips for YouTube Shorts, Instagram Reels, and TikTok.

## ✨ Features

- 🎙️ **AI Transcription:** Speech-to-text using Faster-Whisper.
- 🧠 **Smart Highlight Detection:** Automatically scores and ranks interesting moments.
- 📱 **Vertical Video Creation:** Generates 9:16 short-form videos.
- 💬 **Animated Captions:** Creates synchronized captions for clips.
- 🎯 **Smart Clip Boundaries:** Uses speech and sentence timing for natural cuts.
- 📊 **YouTube Analysis:** Retrieves video metadata and analyzes available audience comments.
- 🎬 **Video Preview & Export:** Preview and download generated MP4 clips.
- 🔒 **Local Processing:** Video transcription and rendering run locally.

## 🛠️ Technology

| Technology | Purpose |
|---|---|
| Python | Core application |
| Streamlit | Interactive dashboard |
| Faster-Whisper | AI transcription |
| FFmpeg | Video processing |
| OpenCV | Video handling |
| PySceneDetect | Scene analysis |
| YouTube Data API | Video metadata and comments |

## 🚀 Installation

### Requirements

- Python 3.11 recommended
- FFmpeg
- Windows, macOS, or Linux

### 1. Clone the repository

```bash
git clone https://github.com/ashwink2727/viralcut-ai.git
cd viralcut-ai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

Install FFmpeg and ensure it is available in your system PATH.

### 4. Start ViralCut AI

```bash
python -m streamlit run app/main.py --server.port 8503
```

Open your browser:

http://localhost:8503

**Windows users:** You can also double-click `Start_ViralCut.bat`.

## 📂 Project Structure

```text
viralcut-ai/
│
├── app/
│   ├── main.py
│   ├── analyzer.py
│   ├── scorer.py
│   ├── clipper.py
│   └── other application modules
│
├── models/
├── tests/
├── uploads/
├── outputs/
│
├── Start_ViralCut.bat
├── requirements.txt
├── .gitignore
└── README.md
```

## 🔐 YouTube API Configuration

YouTube metadata and comment analysis require your own Google Cloud OAuth credentials.

1. Create a Google Cloud project.
2. Enable YouTube Data API v3.
3. Configure OAuth consent.
4. Create a Desktop OAuth client.
5. Save your credentials locally as `youtube_client_secret.json`.

Never upload OAuth credentials, tokens, API keys, or passwords to GitHub.

## ⚠️ Important Notes

- Video processing is performed locally.
- YouTube metadata and comments are accessed through the YouTube Data API.
- YouTube URLs are not automatically downloadable video files. Supply an authorized video source for clipping.
- Only process videos you own or have permission to use.
- Highlight scoring is heuristic-based and cannot guarantee viral performance
