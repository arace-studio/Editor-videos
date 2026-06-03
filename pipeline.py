#!/usr/bin/env python3
"""
Editor de Vídeos — Pipeline principal

Uso:
  python pipeline.py <video.mp4> [opções]

Opções:
  --no-animations          Pula geração de animações (só corta silêncios)
  --preview                Qualidade reduzida (mais rápido)
  --silence-threshold N    Limiar de silêncio em ms (padrão: 400)
  --language CODE          Código de idioma para transcrição (ex: pt, en)
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _check_deps():
    missing = []
    for tool in ("ffmpeg", "ffprobe"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            missing.append(tool)
    if missing:
        print(f"ERRO: ferramentas ausentes: {', '.join(missing)}")
        print("Instale com: brew install ffmpeg  ou  apt install ffmpeg")
        sys.exit(1)


def _get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def run(
    video_path: str,
    no_animations: bool = False,
    quality: str = "final",
    silence_threshold_ms: int = 400,
    language: str | None = None,
) -> Path:
    from helpers.transcribe import transcribe
    from helpers.pack_transcripts import pack
    from helpers.silence_cutter import build_edl
    from helpers.render import render
    from helpers.animation_generator import generate
    from helpers.compositor import composite

    video_path = Path(video_path).resolve()
    if not video_path.exists():
        print(f"ERRO: arquivo não encontrado: {video_path}")
        sys.exit(1)

    edit_dir = video_path.parent / "edit"
    edit_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Processando: {video_path.name}")
    print(f"  Saída:       {edit_dir}/")
    print(f"{'='*60}\n")

    t0 = time.time()

    # Stage 1: Transcription
    print("[ 1/5 ] Transcrevendo…")
    transcript = transcribe(video_path, edit_dir, language=language)
    original_duration = _get_video_duration(video_path)

    # Stage 2: Pack transcripts
    print("\n[ 2/5 ] Empacotando transcrição…")
    pack(transcript, edit_dir)

    # Stage 3: Build EDL
    print("\n[ 3/5 ] Detectando silêncios e repetições…")
    edl_path = build_edl(
        transcript,
        edit_dir,
        silence_threshold=silence_threshold_ms / 1000.0,
    )

    # Stage 4: Render edited video
    print("\n[ 4/5 ] Renderizando vídeo editado…")
    edited_video = render(video_path, edl_path, edit_dir, quality=quality)
    edited_duration = _get_video_duration(edited_video)

    # Stage 5: Animations + composite
    if no_animations:
        print("\n[ 5/5 ] Animações desativadas — copiando como final…")
        from helpers.compositor import composite
        final = composite(edited_video, [], edit_dir)
    else:
        print("\n[ 5/5 ] Gerando animações e compositing…")
        animations = generate(transcript, edit_dir, edited_duration)
        final = composite(edited_video, animations, edit_dir)

    elapsed = time.time() - t0
    saved = original_duration - edited_duration

    print(f"\n{'='*60}")
    print(f"  Concluído em {elapsed:.0f}s")
    print(f"  Duração original:  {original_duration:.1f}s")
    print(f"  Duração editada:   {edited_duration:.1f}s  ({saved:.1f}s removidos)")
    print(f"  Vídeo final:       {final}")
    print(f"{'='*60}\n")

    return final


if __name__ == "__main__":
    _check_deps()

    parser = argparse.ArgumentParser(description="Pipeline de edição de vídeo com IA")
    parser.add_argument("video", help="Caminho para o vídeo de entrada")
    parser.add_argument("--no-animations", action="store_true", help="Pular geração de animações")
    parser.add_argument("--preview", action="store_true", help="Qualidade preview (mais rápido)")
    parser.add_argument("--silence-threshold", type=int, default=400, metavar="MS",
                        help="Limiar de silêncio em ms (padrão: 400)")
    parser.add_argument("--language", type=str, default=None, metavar="CODE",
                        help="Código de idioma (ex: pt, en, es)")
    args = parser.parse_args()

    run(
        video_path=args.video,
        no_animations=args.no_animations,
        quality="preview" if args.preview else "final",
        silence_threshold_ms=args.silence_threshold,
        language=args.language,
    )
