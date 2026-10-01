"""Discover and select a source audio stream for understanding-stage ASR."""

import json
from lib import CONFIG, run_cmd


class AudioTrackSelectionError(RuntimeError):
    """Raised when a source audio stream cannot be selected safely."""


_ISO_639_2_TO_1 = {
    "ara": "ar", "ben": "bn", "chi": "zh", "deu": "de", "dut": "nl",
    "eng": "en", "fas": "fa", "fre": "fr", "fra": "fr", "ger": "de",
    "hin": "hi", "ita": "it", "jpn": "ja", "kor": "ko", "mar": "mr",
    "por": "pt", "rus": "ru", "spa": "es", "tam": "ta", "tel": "te",
    "urd": "ur", "zho": "zh",
}


def probe_audio_streams(video_path):
    """Return audio streams with stable global indexes and useful container metadata."""
    command = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries",
        "stream=index,codec_name,channels,channel_layout:stream_tags=language,title:stream_disposition=default,original,commentary,descriptive",
        "-of", "json", str(video_path),
    ]
    result = run_cmd(command)
    if result.returncode != 0:
        raise AudioTrackSelectionError(
            f"ffprobe could not inspect audio tracks: {result.stderr.strip()[-500:]}"
        )
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError) as exc:
        raise AudioTrackSelectionError("ffprobe returned invalid audio stream JSON") from exc

    streams = []
    for stream in payload.get("streams", []):
        index = stream.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            continue
        tags = stream.get("tags") or {}
        disposition = stream.get("disposition") or {}
        streams.append({
            "index": index,
            "language": tags.get("language"),
            "title": tags.get("title"),
            "codec": stream.get("codec_name"),
            "channels": stream.get("channels"),
            "channel_layout": stream.get("channel_layout"),
            "default": bool(disposition.get("default", 0)),
            "original": bool(disposition.get("original", 0)),
            "commentary": bool(disposition.get("commentary", 0)),
            "descriptive": bool(disposition.get("descriptive", 0)),
        })
    return streams


def select_audio_stream(video_path, requested_index=None):
    """Select by explicit global index, unique original/default disposition, or sole track."""
    streams = probe_audio_streams(video_path)
    if not streams:
        raise AudioTrackSelectionError(f"No audio tracks found in {video_path}")

    if requested_index is None:
        requested_index = CONFIG.get("asr_audio_stream_index")
    if requested_index is not None:
        selected = next((stream for stream in streams if stream["index"] == requested_index), None)
        if selected is None:
            raise AudioTrackSelectionError(
                f"Audio stream index {requested_index} is not available. Tracks:\n"
                f"{json.dumps(streams, ensure_ascii=False, indent=2)}"
            )
        return selected

    if len(streams) == 1:
        return streams[0]
    for disposition in ("original", "default"):
        marked = [stream for stream in streams if stream[disposition]]
        if len(marked) == 1:
            return marked[0]
    raise AudioTrackSelectionError(
        "Multiple audio tracks found; select one with --asr-audio-stream-index. "
        "Track inventory:\n"
        f"{json.dumps(streams, ensure_ascii=False, indent=2)}"
    )


def language_for_audio_track(track, requested_language=None):
    """Resolve a pinned language from explicit configuration or recognized track tags."""
    requested = str(
        requested_language if requested_language is not None else CONFIG.get("asr_language", "auto")
    ).strip().lower()
    if requested and requested != "auto":
        return requested

    tag = str(track.get("language") or "").strip().lower().replace("_", "-")
    if not tag:
        return "auto"
    primary = tag.split("-", 1)[0]
    if len(primary) == 2 and primary.isalpha():
        return primary
    return _ISO_639_2_TO_1.get(primary, "auto")


def audio_stream_map_args(track):
    """Return FFmpeg arguments mapping the selected global stream index."""
    return ["-map", f"0:{track['index']}"]