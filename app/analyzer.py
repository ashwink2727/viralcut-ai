import os
from functools import lru_cache

from faster_whisper import WhisperModel


MODEL_SIZE = os.getenv("VIRALCUT_WHISPER_MODEL", "base")


@lru_cache(maxsize=1)
def get_transcription_model():
    """Create and reuse the local CPU transcription model."""
    cpu_count = os.cpu_count() or 4
    cpu_threads = max(1, cpu_count - 1)

    print(f"Loading Whisper {MODEL_SIZE} model...")
    return WhisperModel(
        MODEL_SIZE,
        device="cpu",
        compute_type="int8",
        cpu_threads=cpu_threads,
        num_workers=1,
    )


def transcribe_video(video_path):
    """
    Transcribe speech and preserve word-level timestamps for captions.

    Uses a cached model and a smaller beam search than the original
    configuration to reduce CPU processing time.
    """
    model = get_transcription_model()

    print("Analyzing video audio...")
    segments, info = model.transcribe(
        video_path,
        beam_size=3,
        best_of=1,
        patience=1,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
    )

    results = []
    for segment in segments:
        word_results = []

        if segment.words:
            for word in segment.words:
                word_results.append({
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                    "word": word.word.strip(),
                })

        results.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": word_results,
        })

    return {
        "language": info.language,
        "segments": results,
    }