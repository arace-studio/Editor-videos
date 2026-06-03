"""Render edited video from EDL using ffmpeg."""

import json
import subprocess
import tempfile
from pathlib import Path

QUALITY_PRESETS = {
    "final":   {"crf": "20", "scale": "1920:-2"},
    "preview": {"crf": "26", "scale": "1280:-2"},
    "draft":   {"crf": "32", "scale": "854:-2"},
}


def _probe(video_path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name",
            "-of", "json", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return data["streams"][0] if data.get("streams") else {}


def _extract_segment(
    video_path: Path,
    start: float,
    end: float,
    out_path: Path,
    quality: str = "final",
) -> None:
    preset = QUALITY_PRESETS[quality]
    duration = end - start
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start), "-i", str(video_path), "-t", str(duration),
            "-vf", f"scale={preset['scale']}",
            "-c:v", "libx264", "-crf", preset["crf"], "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-af", "afade=t=in:st=0:d=0.03,afade=t=out:st=" + str(max(0, duration - 0.03)) + ":d=0.03",
            str(out_path),
        ],
        check=True, capture_output=True,
    )


def render(
    video_path: Path,
    edl_path: Path,
    edit_dir: Path,
    quality: str = "final",
) -> Path:
    """
    Extract segments defined in edl.json, concatenate, normalize audio.
    Returns path to edited.mp4.
    """
    video_path = Path(video_path)
    edl = json.loads(Path(edl_path).read_text())
    segments = edl["segments"]

    if not segments:
        raise ValueError("EDL sem segmentos — nada a renderizar")

    clips_dir = edit_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, seg in enumerate(segments):
        clip_path = clips_dir / f"seg_{i:04d}.mp4"
        print(f"  [render] segmento {i+1}/{len(segments)} [{seg['start']:.2f}s → {seg['end']:.2f}s]")
        _extract_segment(video_path, seg["start"], seg["end"], clip_path, quality)
        clip_paths.append(clip_path)

    # Write concat list
    concat_list = edit_dir / "concat_list.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths)
    )

    # Concatenate
    concat_output = edit_dir / "concat.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(concat_output),
        ],
        check=True, capture_output=True,
    )

    # Normalize audio to -14 LUFS
    edited_output = edit_dir / "edited.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(concat_output),
            "-af", "loudnorm=I=-14:TP=-1:LRA=11",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(edited_output),
        ],
        check=True, capture_output=True,
    )

    concat_output.unlink(missing_ok=True)
    print(f"  [render] → {edited_output.name}")
    return edited_output
