"""Local Whisper ASR via faster-whisper (optional dependency).

Uses the local model directory from WHISPER_MODEL_DIR (a faster-whisper /
CTranslate2 converted Whisper directory, e.g. large-v3-turbo). The caller
transcribes resumable audio windows; returned model-native timestamps are
offset onto the source timeline instead of using MiMo's coarse window bounds.

Output matches the MiMo path: [{"start": s, "end": s, "text": str}].
"""

from pathlib import Path

from lib import CONFIG, log

SUPPORTED_ASR_PROVIDERS = ("auto", "mimo-asr", "whisper-local")

_MODEL = None


def whisper_model_available():
    """True when WHISPER_MODEL_DIR looks like a usable faster-whisper model dir."""
    model_dir = Path(str(CONFIG.get("whisper_model_dir") or "").strip()).expanduser()
    return bool(str(CONFIG.get("whisper_model_dir") or "").strip()) and (
        model_dir.is_dir() and (model_dir / "model.bin").exists()
    )


def resolve_asr_provider():
    """Pick mimo-asr or whisper-local. auto is local-first when configured."""
    want = str(CONFIG.get("asr_provider", "auto") or "auto").strip().lower()
    if want not in SUPPORTED_ASR_PROVIDERS:
        raise RuntimeError(
            "ASR_PROVIDER/--asr-provider 必须是 auto、mimo-asr 或 whisper-local"
        )
    if want == "whisper-local":
        if not whisper_model_available():
            raise RuntimeError(
                "ASR_PROVIDER=whisper-local 但 WHISPER_MODEL_DIR 不可用: "
                f"{CONFIG.get('whisper_model_dir')!r}（需要包含 model.bin 的 "
                "faster-whisper 模型目录）"
            )
        return "whisper-local"
    if want == "mimo-asr":
        return "mimo-asr"
    if whisper_model_available():
        return "whisper-local"
    return "mimo-asr"


def _load_model():
    """Load (once per process) the faster-whisper model from WHISPER_MODEL_DIR."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "本地 Whisper 需要 faster-whisper（pip install faster-whisper），"
            "或改用 ASR_PROVIDER=mimo-asr"
        ) from exc
    model_dir = str(Path(str(CONFIG["whisper_model_dir"])).expanduser())
    kwargs = {
        "device": (CONFIG.get("whisper_device") or "auto").strip() or "auto",
        "local_files_only": True,
    }
    compute_type = (CONFIG.get("whisper_compute_type") or "").strip()
    if compute_type:
        kwargs["compute_type"] = compute_type
    log(f"加载本地 Whisper 模型: {model_dir} ({kwargs['device']})")
    try:
        _MODEL = WhisperModel(model_dir, **kwargs)
    except Exception as exc:
        raise RuntimeError(f"本地 Whisper 模型加载失败 {model_dir}: {exc}") from exc
    return _MODEL


def transcribe_wav_local(wav_path, language=None):
    """Transcribe one wav file locally; return (segments, detected_language)."""
    model = _load_model()
    language = str(
        language if language is not None else CONFIG.get("whisper_language") or "auto"
    ).strip().lower()
    transcribe_kwargs = {
        "task": "transcribe",
        "vad_filter": bool(CONFIG.get("whisper_vad_filter", False)),
    }
    if language and language != "auto":
        transcribe_kwargs["language"] = language
    try:
        segments, info = model.transcribe(
            str(wav_path), **transcribe_kwargs
        )
        results = []
        for segment in segments:
            text = (segment.text or "").strip()
            if not text:
                continue
            results.append(
                {
                    "start": round(float(segment.start), 2),
                    "end": round(float(segment.end), 2),
                    "text": text,
                }
            )
        detected = getattr(info, "language", None) or language
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"本地 Whisper 转录失败: {exc}") from exc
    log(
        f"本地 Whisper 转录完成: {len(results)} 段"
        + (f"（检测语言: {detected}）" if detected else "")
    )
    return results, detected
