"""Transcription via ElevenLabs Scribe — word-level timestamps, cached."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
_AUDIO_SAMPLE_RATE = 16000


def _audio_hash(video_path: Path) -> str:
    """SHA1 of first 64KB of the video file — fast cache key."""
    h = hashlib.sha1()
    with open(video_path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()[:16]


def _extract_audio(video_path: Path, out_wav: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", str(_AUDIO_SAMPLE_RATE),
            "-f", "wav", str(out_wav),
        ],
        check=True,
        capture_output=True,
    )


def transcribe(video_path: Path, edit_dir: Path, language: str | None = None) -> dict:
    """
    Return word-level transcript dict (ElevenLabs Scribe format).
    Results cached in edit_dir/transcripts/<stem>.json.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY não definida em .env")

    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    video_path = Path(video_path)
    cache_key = _audio_hash(video_path)
    cache_file = transcripts_dir / f"{video_path.stem}_{cache_key}.json"

    if cache_file.exists():
        print(f"  [transcribe] cache hit → {cache_file.name}")
        return json.loads(cache_file.read_text())

    print(f"  [transcribe] extraindo áudio de {video_path.name}…")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = Path(tmp.name)

    try:
        _extract_audio(video_path, tmp_wav)

        print(f"  [transcribe] enviando para ElevenLabs Scribe…")
        with open(tmp_wav, "rb") as audio_file:
            payload = {"model_id": "scribe_v1", "diarize": "true"}
            if language:
                payload["language_code"] = language
            resp = requests.post(
                SCRIBE_URL,
                headers={"xi-api-key": api_key},
                data=payload,
                files={"file": (video_path.stem + ".wav", audio_file, "audio/wav")},
                timeout=300,
            )
        resp.raise_for_status()
        result = resp.json()
    finally:
        tmp_wav.unlink(missing_ok=True)

    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"  [transcribe] salvo em {cache_file.name}")
    return result
