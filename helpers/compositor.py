"""Composite hyperframes animation overlays onto the edited video."""

import json
import subprocess
import tempfile
from pathlib import Path


def _get_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _render_overlay(html_path: Path, duration: float, width: int, height: int, out_webm: Path) -> bool:
    """Render HTML composition to transparent WebM using hyperframes CLI."""
    try:
        subprocess.run(
            [
                "npx", "--yes", "hyperframes", "render",
                str(html_path),
                "--format", "webm",
                "--output", str(out_webm),
                "--width", str(width),
                "--height", str(height),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return out_webm.exists() and out_webm.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  [compositor] AVISO: falha ao renderizar {html_path.name}: {e}")
        return False


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0] if data.get("streams") else {}
    return stream.get("width", 1920), stream.get("height", 1080)


def composite(
    edited_video: Path,
    animations: list[dict],
    edit_dir: Path,
) -> Path:
    """
    Render each animation as transparent WebM then overlay onto edited video.
    Returns path to final.mp4.
    """
    final_path = edit_dir / "final.mp4"

    if not animations:
        print("  [compositor] sem animações — copiando vídeo editado como final")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(edited_video), "-c", "copy", str(final_path)],
            check=True, capture_output=True,
        )
        return final_path

    width, height = _get_video_dimensions(edited_video)
    overlays_dir = edit_dir / "overlays"
    overlays_dir.mkdir(exist_ok=True)

    # Render each animation to WebM
    rendered = []
    for anim in animations:
        html_path = Path(anim["html_path"])
        out_webm = overlays_dir / (html_path.stem + ".webm")
        print(f"  [compositor] renderizando {html_path.name}…")
        ok = _render_overlay(html_path, anim["duration"], width, height, out_webm)
        if ok:
            rendered.append({**anim, "webm_path": str(out_webm)})

    if not rendered:
        print("  [compositor] nenhum overlay renderizado — copiando vídeo editado")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(edited_video), "-c", "copy", str(final_path)],
            check=True, capture_output=True,
        )
        return final_path

    # Build ffmpeg overlay filter chain
    # Inputs: [0] = base video, [1..N] = overlay webms
    inputs = ["-i", str(edited_video)]
    for r in rendered:
        inputs += ["-i", str(r["webm_path"])]

    # Filter: overlay each webm at its start time
    filter_parts = []
    prev_label = "0:v"
    for i, r in enumerate(rendered, start=1):
        in_label = f"[{i}:v]"
        out_label = f"[v{i}]" if i < len(rendered) else "[vout]"
        start_ms = int(r["start"] * 1000)
        filter_parts.append(
            f"[{prev_label}]{in_label}overlay=0:0:enable='between(t,{r['start']},{r['start'] + r['duration']})'{out_label}"
        )
        prev_label = f"v{i}"

    filter_complex = ";".join(filter_parts)

    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a",
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-c:a", "copy",
            str(final_path),
        ]
    )

    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  [compositor] → {final_path.name}")
    return final_path
