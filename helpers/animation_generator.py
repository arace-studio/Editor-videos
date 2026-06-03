"""Generate hyperframes HTML compositions from transcript using Claude API."""

import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

ANIMATION_TYPES = ("keyword_highlight", "stat_callout", "chapter_card", "lower_third")


def _read_packed_transcript(edit_dir: Path) -> str:
    p = edit_dir / "takes_packed.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _ask_claude(transcript_md: str, video_duration: float) -> list[dict]:
    """
    Ask Claude to identify moments in the transcript that deserve animations.
    Returns a list of animation specs.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system = (
        "Você é um editor de vídeo especialista em motion graphics. "
        "Analise o transcript e identifique momentos que se beneficiariam de animações visuais. "
        "Retorne SOMENTE um JSON válido, sem markdown, sem explicações."
    )

    prompt = f"""Transcript do vídeo (duração total: {video_duration:.1f}s):

{transcript_md}

Identifique até 8 momentos para animações. Para cada um retorne:
{{
  "type": "keyword_highlight" | "stat_callout" | "chapter_card" | "lower_third",
  "start": <segundos float>,
  "duration": <duração em segundos, entre 2 e 5>,
  "content": {{
    "keyword_highlight": {{"word": "...", "context": "..."}},
    "stat_callout": {{"number": "...", "label": "..."}},
    "chapter_card": {{"title": "...", "subtitle": "..."}},
    "lower_third": {{"name": "...", "title": "..."}}
  }}[type]
}}

Regras:
- keyword_highlight: para termos técnicos, conceitos importantes, palavras-chave
- stat_callout: para números, percentuais, estatísticas mencionadas
- chapter_card: para transições claras de assunto (mínimo 30s entre cards)
- lower_third: apenas se houver identificação de presenter (início do vídeo ou novo speaker)
- Espaçe as animações — mínimo 8s entre cada uma
- start deve ser dentro de [{0}, {video_duration:.1f}]

Retorne JSON no formato: [{{"type":..., "start":..., "duration":..., "content":{{...}}}}, ...]"""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [anim_gen] AVISO: resposta Claude não é JSON válido, ignorando animações")
        return []


def _render_keyword_highlight(content: dict, start: float, duration: float, idx: int, compositions_dir: Path) -> Path:
    word = content.get("word", "")
    context = content.get("context", "")
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; background: transparent; font-family: 'Helvetica Neue', Arial, sans-serif; }}
.container {{
  position: absolute;
  bottom: 120px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  opacity: 0;
}}
.keyword {{
  display: inline-block;
  background: rgba(255,255,255,0.95);
  color: #111;
  font-size: 42px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 12px 32px;
  border-radius: 6px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}}
.context {{
  display: block;
  font-size: 18px;
  color: rgba(255,255,255,0.85);
  margin-top: 8px;
  font-weight: 400;
  letter-spacing: 0.03em;
}}
</style>
</head>
<body>
<div
  id="root"
  data-composition-id="keyword-{idx}"
  data-start="0"
  data-width="1920"
  data-height="1080"
>
  <div
    id="anim"
    class="container clip"
    data-start="0"
    data-duration="{duration}"
    data-track-index="1"
  >
    <span class="keyword">{word}</span>
    {"<span class='context'>" + context + "</span>" if context else ""}
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.to("#anim", {{ opacity: 1, y: -10, duration: 0.4, ease: "power2.out" }}, 0.1);
tl.to("#anim", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {duration - 0.4});
window.__timelines = window.__timelines || {{}};
window.__timelines["keyword-{idx}"] = tl;
</script>
</body>
</html>"""
    path = compositions_dir / f"keyword_{idx:04d}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _render_stat_callout(content: dict, start: float, duration: float, idx: int, compositions_dir: Path) -> Path:
    number = content.get("number", "")
    label = content.get("label", "")
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; background: transparent; font-family: 'Helvetica Neue', Arial, sans-serif; }}
.stat-box {{
  position: absolute;
  bottom: 100px;
  right: 120px;
  text-align: right;
  opacity: 0;
}}
.number {{
  font-size: 96px;
  font-weight: 900;
  color: #fff;
  line-height: 1;
  text-shadow: 0 2px 20px rgba(0,0,0,0.5);
}}
.label {{
  font-size: 22px;
  font-weight: 500;
  color: rgba(255,255,255,0.8);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 6px;
}}
.accent {{
  position: absolute;
  bottom: 100px;
  right: 118px;
  width: 4px;
  height: 130px;
  background: #fff;
  transform-origin: bottom;
  scaleY: 0;
}}
</style>
</head>
<body>
<div
  id="root"
  data-composition-id="stat-{idx}"
  data-start="0"
  data-width="1920"
  data-height="1080"
>
  <div
    id="stat"
    class="stat-box clip"
    data-start="0"
    data-duration="{duration}"
    data-track-index="1"
  >
    <div class="number" id="num">{number}</div>
    <div class="label">{label}</div>
  </div>
  <div id="accent" class="accent" data-start="0" data-duration="{duration}" data-track-index="1"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.fromTo("#accent", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.3, ease: "power3.out" }}, 0);
tl.fromTo("#stat", {{ opacity: 0, x: 30 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: "power2.out" }}, 0.1);
tl.to("#stat", {{ opacity: 0, duration: 0.3 }}, {duration - 0.4});
tl.to("#accent", {{ scaleY: 0, duration: 0.3, ease: "power3.in" }}, {duration - 0.4});
window.__timelines = window.__timelines || {{}};
window.__timelines["stat-{idx}"] = tl;
</script>
</body>
</html>"""
    path = compositions_dir / f"stat_{idx:04d}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _render_chapter_card(content: dict, start: float, duration: float, idx: int, compositions_dir: Path) -> Path:
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; background: transparent; font-family: 'Helvetica Neue', Arial, sans-serif; }}
.card {{
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  opacity: 0;
}}
.chapter-title {{
  font-size: 72px;
  font-weight: 800;
  color: #fff;
  text-shadow: 0 2px 40px rgba(0,0,0,0.6);
  letter-spacing: -0.01em;
}}
.chapter-sub {{
  font-size: 26px;
  font-weight: 400;
  color: rgba(255,255,255,0.7);
  margin-top: 14px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}}
.line {{
  width: 0;
  height: 3px;
  background: rgba(255,255,255,0.6);
  margin: 20px auto;
}}
</style>
</head>
<body>
<div
  id="root"
  data-composition-id="chapter-{idx}"
  data-start="0"
  data-width="1920"
  data-height="1080"
>
  <div
    id="card"
    class="card clip"
    data-start="0"
    data-duration="{duration}"
    data-track-index="1"
  >
    <div class="chapter-title">{title}</div>
    <div class="line" id="line"></div>
    {"<div class='chapter-sub'>" + subtitle + "</div>" if subtitle else ""}
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.to("#card", {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, 0);
tl.to("#line", {{ width: 200, duration: 0.4, ease: "power2.out" }}, 0.3);
tl.to("#card", {{ opacity: 0, duration: 0.4, ease: "power2.in" }}, {duration - 0.5});
window.__timelines = window.__timelines || {{}};
window.__timelines["chapter-{idx}"] = tl;
</script>
</body>
</html>"""
    path = compositions_dir / f"chapter_{idx:04d}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _render_lower_third(content: dict, start: float, duration: float, idx: int, compositions_dir: Path) -> Path:
    name = content.get("name", "")
    title = content.get("title", "")
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden; background: transparent; font-family: 'Helvetica Neue', Arial, sans-serif; }}
.lower-third {{
  position: absolute;
  bottom: 130px;
  left: 80px;
  opacity: 0;
}}
.bar {{
  width: 0;
  height: 3px;
  background: #fff;
  margin-bottom: 10px;
}}
.name {{
  font-size: 38px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 8px rgba(0,0,0,0.4);
}}
.role {{
  font-size: 20px;
  font-weight: 400;
  color: rgba(255,255,255,0.8);
  letter-spacing: 0.05em;
  margin-top: 4px;
}}
</style>
</head>
<body>
<div
  id="root"
  data-composition-id="lower-{idx}"
  data-start="0"
  data-width="1920"
  data-height="1080"
>
  <div
    id="lt"
    class="lower-third clip"
    data-start="0"
    data-duration="{duration}"
    data-track-index="1"
  >
    <div class="bar" id="bar"></div>
    <div class="name">{name}</div>
    {"<div class='role'>" + title + "</div>" if title else ""}
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.to("#lt", {{ opacity: 1, x: 0, duration: 0.3, ease: "power2.out" }}, 0);
tl.fromTo("#lt", {{ x: -20 }}, {{ x: 0, duration: 0.3 }}, 0);
tl.to("#bar", {{ width: 200, duration: 0.4, ease: "power2.out" }}, 0.1);
tl.to("#lt", {{ opacity: 0, x: -20, duration: 0.3, ease: "power2.in" }}, {duration - 0.4});
window.__timelines = window.__timelines || {{}};
window.__timelines["lower-{idx}"] = tl;
</script>
</body>
</html>"""
    path = compositions_dir / f"lower_{idx:04d}.html"
    path.write_text(html, encoding="utf-8")
    return path


_RENDERERS = {
    "keyword_highlight": _render_keyword_highlight,
    "stat_callout": _render_stat_callout,
    "chapter_card": _render_chapter_card,
    "lower_third": _render_lower_third,
}


def generate(transcript: dict, edit_dir: Path, edited_duration: float) -> list[dict]:
    """
    Return list of animation specs: [{html_path, start, duration, type}, ...]
    HTMLs are written to edit_dir/compositions/.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("  [anim_gen] ANTHROPIC_API_KEY não definida — pulando animações")
        return []

    packed_md = _read_packed_transcript(edit_dir)
    if not packed_md:
        print("  [anim_gen] takes_packed.md não encontrado — pulando animações")
        return []

    print("  [anim_gen] analisando conteúdo com Claude…")
    specs = _ask_claude(packed_md, edited_duration)

    if not specs:
        return []

    compositions_dir = edit_dir / "compositions"
    compositions_dir.mkdir(parents=True, exist_ok=True)

    animations = []
    for idx, spec in enumerate(specs):
        anim_type = spec.get("type")
        start = float(spec.get("start", 0))
        duration = float(spec.get("duration", 3))
        content = spec.get("content", {})

        if anim_type not in _RENDERERS:
            continue
        if start + duration > edited_duration:
            duration = max(1.0, edited_duration - start - 0.5)

        renderer = _RENDERERS[anim_type]
        html_path = renderer(content, start, duration, idx, compositions_dir)
        animations.append({
            "html_path": str(html_path),
            "start": start,
            "duration": duration,
            "type": anim_type,
        })
        print(f"  [anim_gen] {anim_type} @ {start:.1f}s ({duration:.1f}s) → {html_path.name}")

    return animations
