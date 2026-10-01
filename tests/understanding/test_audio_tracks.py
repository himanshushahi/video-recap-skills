import json
import shutil
import sys
from pathlib import Path
import subprocess
from subprocess import CompletedProcess

import pytest


SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "video-understanding"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))

import audio_tracks  # noqa: E402


def _probe(monkeypatch, streams):
    payload = json.dumps({"streams": streams})
    monkeypatch.setattr(
        audio_tracks,
        "run_cmd",
        lambda command: CompletedProcess(command, 0, stdout=payload, stderr=""),
    )


def test_probe_audio_streams_preserves_global_index_and_track_metadata(monkeypatch):
    _probe(monkeypatch, [{
        "index": 2,
        "codec_name": "aac",
        "channels": 2,
        "channel_layout": "stereo",
        "tags": {"language": "hin", "title": "Original"},
        "disposition": {"default": 1, "original": 1},
    }])

    tracks = audio_tracks.probe_audio_streams("movie.mkv")

    assert tracks == [{
        "index": 2,
        "language": "hin",
        "title": "Original",
        "codec": "aac",
        "channels": 2,
        "channel_layout": "stereo",
        "default": True,
        "original": True,
        "commentary": False,
        "descriptive": False,
    }]


@pytest.mark.parametrize(
    ("streams", "selected"),
    [
        ([{"index": 1, "tags": {}, "disposition": {}}], 1),
        ([
            {"index": 1, "tags": {}, "disposition": {"default": 1}},
            {"index": 2, "tags": {}, "disposition": {}},
        ], 1),
        ([
            {"index": 1, "tags": {}, "disposition": {"default": 1}},
            {"index": 2, "tags": {}, "disposition": {"original": 1}},
        ], 2),
    ],
)
def test_select_audio_stream_uses_sole_or_unique_marked_track(monkeypatch, streams, selected):
    _probe(monkeypatch, streams)

    assert audio_tracks.select_audio_stream("movie.mkv")["index"] == selected


def test_select_audio_stream_requires_explicit_choice_when_ambiguous(monkeypatch):
    _probe(monkeypatch, [
        {"index": 1, "tags": {"language": "eng"}, "disposition": {}},
        {"index": 2, "tags": {"language": "hin"}, "disposition": {}},
    ])

    with pytest.raises(audio_tracks.AudioTrackSelectionError, match="Track inventory"):
        audio_tracks.select_audio_stream("movie.mkv")


def test_explicit_track_and_metadata_language_resolution(monkeypatch):
    _probe(monkeypatch, [
        {"index": 1, "tags": {"language": "eng"}, "disposition": {}},
        {"index": 2, "tags": {"language": "hin"}, "disposition": {}},
    ])
    track = audio_tracks.select_audio_stream("movie.mkv", requested_index=2)

    assert audio_tracks.audio_stream_map_args(track) == ["-map", "0:2"]
    assert audio_tracks.language_for_audio_track(track) == "hi"
    assert audio_tracks.language_for_audio_track(track, "en") == "en"


def test_explicit_unknown_index_is_rejected(monkeypatch):
    _probe(monkeypatch, [{"index": 1, "tags": {}, "disposition": {}}])

    with pytest.raises(audio_tracks.AudioTrackSelectionError, match="index 7"):
        audio_tracks.select_audio_stream("movie.mkv", requested_index=7)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="requires local media tools")
def test_real_ffprobe_selects_original_language_track(tmp_path):
    video = tmp_path / "two-audio-tracks.mkv"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=660:duration=1",
            "-map", "0:a", "-map", "1:a", "-c:a", "pcm_s16le",
            "-metadata:s:a:0", "language=eng",
            "-metadata:s:a:1", "language=hin",
            "-disposition:a:0", "default",
            "-disposition:a:1", "original",
            str(video),
        ],
        check=True,
        capture_output=True,
    )

    tracks = audio_tracks.probe_audio_streams(video)

    assert len(tracks) == 2
    assert audio_tracks.select_audio_stream(video)["index"] == tracks[1]["index"]
    assert audio_tracks.language_for_audio_track(tracks[1]) == "hi"