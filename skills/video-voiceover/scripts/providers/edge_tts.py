"""Microsoft Edge TTS transport (free, online, no API key) for video-voiceover.

Runs the installed `edge-tts` package via its console script (or
`python -m edge_tts` as fallback) into a temporary MP3, then converts to WAV
with ffmpeg so the existing voiceover pipeline (per-segment cache, RMS
normalization, assembly) sees the same WAV contract as the other providers.

Only stdlib + the `edge-tts` / `ffmpeg` binaries are used here; voiceover.py
only selects the engine.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lib import CONFIG, log

DEFAULT_EDGE_TTS_VOICE = "hi-IN-SwaraNeural"


def edge_tts_available():
    """True when the `edge-tts` package or console script can be invoked."""
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return shutil.which("edge-tts") is not None


def _edge_tts_command():
    if shutil.which("edge-tts"):
        return ["edge-tts"]
    return [sys.executable, "-m", "edge_tts"]


def _convert_to_wav(mp3_path, wav_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(mp3_path),
        "-ac", "1",
        "-ar", "24000",
        "-acodec", "pcm_s16le",
        str(wav_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError as exc:
        raise RuntimeError("edge-tts 转码需要 ffmpeg（未在 PATH 上找到）") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("edge-tts 转码超时（ffmpeg 120s 未完成）") from exc
    if result.returncode != 0 or not Path(wav_path).is_file():
        detail = (result.stderr or "")[-300:]
        raise RuntimeError(f"edge-tts 转码失败: {detail}")


def synthesize_edge_tts(text, output_path, *, voice=None, rate="+0%", pitch="+0Hz",
                        timeout=None):
    """Synthesize one narration block and atomically write a WAV file.

    Returns a provider receipt dict for the per-segment TTS cache.
    """
    text = (text or "").strip()
    if not text:
        raise RuntimeError("edge-tts 合成文本为空，已跳过")
    resolved_voice = (voice or CONFIG.get("edge_tts_voice") or DEFAULT_EDGE_TTS_VOICE).strip()
    if not resolved_voice:
        raise RuntimeError("请设置 EDGE_TTS_VOICE（如 hi-IN-SwaraNeural）用于 edge-tts 配音")
    if timeout is None:
        timeout = CONFIG["tts_timeout"]

    output = Path(output_path)
    with tempfile.TemporaryDirectory(prefix="video-recap-edge-tts-") as temp_dir:
        text_file = Path(temp_dir) / "text.txt"
        mp3_file = Path(temp_dir) / "out.mp3"
        text_file.write_text(text, encoding="utf-8")
        cmd = [
            *_edge_tts_command(),
            "--voice", resolved_voice,
            "--rate", rate,
            "--pitch", pitch,
            "--file", str(text_file),
            "--write-media", str(mp3_file),
        ]
        log(f"edge-tts 合成 ({resolved_voice}, {rate}/{pitch}): {text[:30]}…")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "缺少 edge-tts（pip install edge-tts），或改用 TTS_PROVIDER=mimo-tts"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"edge-tts 合成超时（{timeout}s）") from exc
        if result.returncode != 0 or not mp3_file.is_file() or mp3_file.stat().st_size == 0:
            detail = ((result.stderr or result.stdout) or "")[-300:]
            raise RuntimeError(f"edge-tts 合成失败: {detail or '无输出'}")
        _convert_to_wav(mp3_file, output)

    if output.stat().st_size <= 44:
        output.unlink(missing_ok=True)
        raise RuntimeError("edge-tts 输出音频为空")
    return {"provider": "edge-tts", "voice": resolved_voice}


def valid_cached_receipt(cache_data, config):
    """A cached edge-tts segment must carry the receipt for the current voice."""
    receipt = cache_data.get("provider_receipt")
    return isinstance(receipt, dict) and receipt == {
        "provider": "edge-tts",
        "voice": config["edge_tts_voice"],
    }


def cache_settings(config):
    """Non-secret settings that decide reuse."""
    return {"edge_tts_voice": config["edge_tts_voice"]}
