import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "skills" / "video-voiceover" / "scripts"),
)

import providers.edge_tts as edge_tts
import voiceover
from lib import CONFIG, DEFAULT_EDGE_TTS_VOICE


def test_default_edge_voice_is_hindi_narration_voice():
    assert DEFAULT_EDGE_TTS_VOICE == "hi-IN-SwaraNeural"
    assert CONFIG["edge_tts_voice"] == "hi-IN-SwaraNeural"


def _fake_run_factory(monkeypatch, mp3_bytes=b"fake-mp3", wav_bytes=None):
    """Stub subprocess.run: edge-tts CLI writes an MP3, ffmpeg writes a WAV."""
    seen = []
    wav_payload = wav_bytes or (b"RIFF" + b"\x00" * 4 + b"WAVE" + b"x" * 64)

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        head = cmd[0]
        if "edge-tts" in str(head) or "edge_tts" in str(head):
            out = Path(cmd[cmd.index("--write-media") + 1])
            out.write_bytes(mp3_bytes)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if head == "ffmpeg":
            Path(cmd[-1]).write_bytes(wav_payload)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(edge_tts.subprocess, "run", fake_run)
    return seen


def test_edge_transport_writes_wav_with_voice_and_rate(monkeypatch, tmp_path):
    seen = _fake_run_factory(monkeypatch)
    monkeypatch.setitem(CONFIG, "tts_timeout", 12)

    output = tmp_path / "voice.wav"
    receipt = edge_tts.synthesize_edge_tts(
        "नमस्ते दुनिया", output, voice="hi-IN-SwaraNeural", rate="+5%", pitch="+0Hz"
    )

    cli = seen[0]
    assert "--voice" in cli and cli[cli.index("--voice") + 1] == "hi-IN-SwaraNeural"
    assert "--rate" in cli and cli[cli.index("--rate") + 1] == "+5%"
    assert seen[1][0] == "ffmpeg"
    assert output.read_bytes().startswith(b"RIFF")
    assert receipt == {"provider": "edge-tts", "voice": "hi-IN-SwaraNeural"}


def test_edge_transport_rejects_empty_text(monkeypatch, tmp_path):
    _fake_run_factory(monkeypatch)
    with pytest.raises(RuntimeError, match="为空"):
        edge_tts.synthesize_edge_tts("   ", tmp_path / "voice.wav")


def test_edge_transport_failure_leaves_no_output(monkeypatch, tmp_path):
    def boom(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="net down")

    monkeypatch.setattr(edge_tts.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="合成失败"):
        edge_tts.synthesize_edge_tts("hi", tmp_path / "voice.wav", voice="hi-IN-SwaraNeural")
    assert not (tmp_path / "voice.wav").exists()


def test_explicit_edge_provider_resolves_without_key(monkeypatch):
    monkeypatch.setitem(CONFIG, "tts_provider", "edge-tts")
    monkeypatch.setitem(CONFIG, "mimo_tts_api_key", "")
    monkeypatch.setitem(CONFIG, "fish_api_key", "")
    monkeypatch.setattr(edge_tts, "edge_tts_available", lambda: True)
    assert voiceover.resolve_tts_engine() == "edge-tts"


def test_auto_prefers_edge_when_voice_explicitly_set(monkeypatch):
    monkeypatch.setitem(CONFIG, "tts_provider", "auto")
    monkeypatch.setitem(CONFIG, "mimo_tts_api_key", "mimo-key")
    monkeypatch.setitem(CONFIG, "edge_tts_voice_source", "env")
    assert voiceover._configured_tts_engine_for_cache() == "edge-tts"

    monkeypatch.setitem(CONFIG, "edge_tts_voice_source", "default")
    assert voiceover._configured_tts_engine_for_cache() == "mimo-tts"


def test_explicit_edge_without_package_is_a_clear_error(monkeypatch):
    monkeypatch.setitem(CONFIG, "tts_provider", "edge-tts")
    monkeypatch.setattr(edge_tts, "edge_tts_available", lambda: False)
    with pytest.raises(RuntimeError, match="edge-tts"):
        voiceover.resolve_tts_engine()


def test_run_tts_engine_dispatches_to_edge(monkeypatch, tmp_path):
    output = tmp_path / "edge.wav"
    seen = []
    monkeypatch.setitem(CONFIG, "tts_retries", 1)

    def fake_synthesize(text, path, **kwargs):
        seen.append((text, kwargs))
        Path(path).write_bytes(b"wav")
        return {"provider": "edge-tts", "voice": "v"}

    monkeypatch.setattr(edge_tts, "synthesize_edge_tts", fake_synthesize)
    monkeypatch.setattr("voiceover.get_video_duration", lambda path: 1.0)

    receipt = voiceover._run_tts_engine("edge-tts", "नमस्ते", output, rate="+5%")

    assert output.read_bytes() == b"wav"
    assert receipt["provider"] == "edge-tts"
    assert seen[0][1]["rate"] == "+5%"


def test_edge_receipt_guards_cache_reuse(monkeypatch):
    monkeypatch.setitem(CONFIG, "edge_tts_voice", "hi-IN-SwaraNeural")
    good = {"provider_receipt": {"provider": "edge-tts", "voice": "hi-IN-SwaraNeural"}}
    stale = {"provider_receipt": {"provider": "edge-tts", "voice": "hi-IN-MadhurNeural"}}
    assert edge_tts.valid_cached_receipt(good, CONFIG) is True
    assert edge_tts.valid_cached_receipt(stale, CONFIG) is False


def test_voice_ref_rejected_for_edge(monkeypatch, tmp_path):
    monkeypatch.setitem(CONFIG, "tts_provider", "edge-tts")
    monkeypatch.setitem(CONFIG, "voice_ref", str(tmp_path / "ref.wav"))
    monkeypatch.setattr(edge_tts, "edge_tts_available", lambda: True)
    with pytest.raises(RuntimeError, match="edge-tts"):
        voiceover.synthesize_tts(
            [{"start": 0.0, "end": 2.0, "narration": "hi"}], tmp_path
        )
