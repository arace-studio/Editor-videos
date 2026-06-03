"""Pack word-level transcript JSON into editorial-friendly markdown."""

from pathlib import Path


def pack(transcript: dict, edit_dir: Path) -> Path:
    """
    Group words into phrases, write takes_packed.md, return its path.

    Phrase breaks occur on:
      - Silence gap >= 0.5 s between consecutive words
      - Speaker change
    """
    SILENCE_BREAK = 0.5

    words = transcript.get("words", [])
    phrases = []
    current: list[dict] = []

    for w in words:
        if w.get("type") not in ("word", "spacing"):
            continue
        if w.get("type") == "spacing":
            continue

        if not current:
            current.append(w)
            continue

        prev = current[-1]
        gap = w.get("start", 0) - prev.get("end", 0)
        speaker_change = w.get("speaker_id") != prev.get("speaker_id")

        if gap >= SILENCE_BREAK or speaker_change:
            phrases.append(current)
            current = [w]
        else:
            current.append(w)

    if current:
        phrases.append(current)

    lines = []
    for phrase in phrases:
        if not phrase:
            continue
        t_start = phrase[0].get("start", 0)
        t_end = phrase[-1].get("end", t_start)
        speaker = phrase[0].get("speaker_id", "S0")
        text = " ".join(w["text"] for w in phrase if w.get("text"))
        lines.append(f"[{t_start:7.2f} → {t_end:7.2f}] {speaker}: {text}")

    output = edit_dir / "takes_packed.md"
    output.write_text("\n".join(lines), encoding="utf-8")

    total_dur = phrases[-1][-1].get("end", 0) if phrases else 0
    print(f"  [pack] {len(phrases)} frases, {total_dur:.1f}s → {output.name}")
    return output
