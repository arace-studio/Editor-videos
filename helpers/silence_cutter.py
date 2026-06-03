"""Build an EDL (Edit Decision List) removing silences and repetitions."""

import json
from pathlib import Path


def _find_repetitions(phrases: list[dict], similarity_threshold: float = 0.7) -> set[int]:
    """
    Return indices of phrases that are repetitions of a nearby previous phrase.
    Uses word-overlap (Jaccard) within a 5-phrase lookahead window.
    """
    def jaccard(a: list[str], b: list[str]) -> float:
        sa, sb = set(a), set(b)
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union else 0.0

    repeated = set()
    for i in range(1, len(phrases)):
        words_i = [w.lower() for w in phrases[i]["words"] if len(w) > 2]
        if len(words_i) < 3:
            continue
        for j in range(max(0, i - 5), i):
            if j in repeated:
                continue
            words_j = [w.lower() for w in phrases[j]["words"] if len(w) > 2]
            if len(words_j) < 3:
                continue
            if jaccard(words_i, words_j) >= similarity_threshold:
                repeated.add(i)
                break
    return repeated


def _words_to_phrases(words: list[dict], silence_threshold: float) -> list[dict]:
    """Group word entries into phrase dicts with start/end/words fields."""
    SPACING_TYPES = {"spacing", "audio_event"}
    phrases = []
    current_words = []
    current_text = []

    for w in words:
        if w.get("type") in SPACING_TYPES:
            continue
        if w.get("type") != "word":
            continue

        if not current_words:
            current_words.append(w)
            current_text.append(w.get("text", ""))
            continue

        gap = w.get("start", 0) - current_words[-1].get("end", 0)
        speaker_change = w.get("speaker_id") != current_words[-1].get("speaker_id")

        if gap >= silence_threshold or speaker_change:
            phrases.append({
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "words": current_text[:],
                "gap_before": current_words[0]["start"] - (phrases[-1]["end"] if phrases else 0),
            })
            current_words = [w]
            current_text = [w.get("text", "")]
        else:
            current_words.append(w)
            current_text.append(w.get("text", ""))

    if current_words:
        phrases.append({
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"],
            "words": current_text[:],
            "gap_before": current_words[0]["start"] - (phrases[-1]["end"] if phrases else 0),
        })

    return phrases


def build_edl(
    transcript: dict,
    edit_dir: Path,
    silence_threshold: float = 0.4,
    cut_padding: float = 0.05,
) -> Path:
    """
    Analyse transcript and write edit/edl.json.

    silence_threshold: gaps >= this (seconds) are cut
    cut_padding: seconds kept before/after each cut boundary (avoids pops)
    """
    words = transcript.get("words", [])
    if not words:
        raise ValueError("Transcript vazio — sem palavras encontradas")

    # Group into phrases (break on silence >= 0.5s for phrase detection)
    phrases = _words_to_phrases(words, silence_threshold=0.5)
    repeated_indices = _find_repetitions(phrases)

    # Build kept segments by scanning word-level gaps
    segments = []
    seg_start = None
    seg_end = None

    def flush(start, end):
        if start is None or end is None:
            return
        s = max(0.0, start - cut_padding)
        e = end + cut_padding
        if segments and s <= segments[-1]["end"] + 0.01:
            segments[-1]["end"] = e
        else:
            segments.append({"start": round(s, 4), "end": round(e, 4)})

    prev_end = 0.0
    prev_phrase_idx = -1

    for i, phrase in enumerate(phrases):
        if i in repeated_indices:
            flush(seg_start, seg_end)
            seg_start = seg_end = None
            prev_phrase_idx = i
            continue

        gap = phrase["start"] - prev_end

        if gap >= silence_threshold:
            flush(seg_start, seg_end)
            seg_start = phrase["start"]
        elif seg_start is None:
            seg_start = phrase["start"]

        seg_end = phrase["end"]
        prev_end = phrase["end"]
        prev_phrase_idx = i

    flush(seg_start, seg_end)

    total_original = words[-1].get("end", 0) if words else 0
    total_kept = sum(s["end"] - s["start"] for s in segments)
    removed_count = len(repeated_indices)

    edl = {
        "segments": segments,
        "stats": {
            "original_duration": round(total_original, 2),
            "edited_duration": round(total_kept, 2),
            "silences_removed": round(total_original - total_kept - sum(
                p["end"] - p["start"] for i, p in enumerate(phrases) if i in repeated_indices
            ), 2),
            "repetitions_removed": removed_count,
            "silence_threshold": silence_threshold,
            "cut_padding": cut_padding,
        },
    }

    edl_path = edit_dir / "edl.json"
    edl_path.write_text(json.dumps(edl, indent=2))

    stats = edl["stats"]
    print(
        f"  [silence_cutter] {len(segments)} segmentos | "
        f"{stats['original_duration']:.1f}s → {stats['edited_duration']:.1f}s | "
        f"{removed_count} repetições removidas"
    )
    return edl_path
