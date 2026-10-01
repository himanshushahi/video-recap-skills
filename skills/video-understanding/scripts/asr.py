import base64
import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

from lib import CONFIG
from lib import log, run_cmd, get_video_duration, mimo_asr_api_call
from audio_tracks import audio_stream_map_args, language_for_audio_track, select_audio_stream
from whisper_local import resolve_asr_provider, transcribe_wav_local
from detect import _audio_meta_path, _write_audio_meta
from asr_timing_evidence import (
    EVIDENCE_FILENAME,
    load_glossary_names,
    write_asr_timing_evidence,
)

# ── Step 3: ASR 转录（MiMo mimo-v2.5-asr，云端 API）────────────────────────

_ASR_AUDIO_MIME = "audio/wav"


class ASRProviderError(RuntimeError):
    """Provider/API response failed, so an empty transcript is not cacheable success."""


def _load_name_glossary(work_dir):
    """从 background_research.json 收集已知人名（characters 键 + character_details 键及别名）。

    返回去重后、长度 >=2 的人名列表（按长度降序，长名优先匹配）。文件缺失或无名字时返回 []。
    """
    return load_glossary_names(work_dir)


def _correct_text_with_glossary(text, names):
    """用人名表修正 ASR 同音字错误（如 叶青眉 → 叶轻眉）。

    对每个已知人名，扫描文本中所有等长窗口；若某窗口与人名恰好相差一个字符（仅一处不同），
    则替换为该人名。严格约束为「恰好一字之差」，避免过度纠正（叶轻风 与 叶轻眉 也是一字之差，
    但这正是限制为单字替换的边界——只有当窗口本身不是任何已知人名时才会被改写）。
    """
    if not text or not names:
        return text
    name_set = set(names)
    for name in names:
        n = len(name)
        if n < 2 or len(text) < n:
            continue
        i = 0
        while i <= len(text) - n:
            window = text[i:i + n]
            # Only rewrite a one-char-off window when it is NOT itself a known name —
            # otherwise a distinct real name one char away (叶轻风 vs 叶轻眉) would be corrupted.
            if window != name and window not in name_set and _one_char_diff(window, name):
                text = text[:i] + name + text[i + n:]
                i += n
            else:
                i += 1
    return text


def _one_char_diff(a, b):
    """两个等长字符串是否恰好相差一个字符（仅一处不同）。"""
    if len(a) != len(b):
        return False
    diff = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            diff += 1
            if diff > 1:
                return False
    return diff == 1


def _apply_glossary_corrections(segments, work_dir):
    """对已转录的 segments 就地应用人名表修正；无人名表时为 no-op。"""
    names = _load_name_glossary(work_dir)
    if not names:
        return segments
    for seg in segments:
        original = seg["text"]
        corrected = _correct_text_with_glossary(original, names)
        if corrected != original:
            seg["text"] = corrected
    return segments



def transcribe_audio(video_path, work_dir, *, resume=True, cache_payload=None):
    """提取音频并转录：whisper-local（本地 faster-whisper）或 MiMo ASR 分段转录。"""
    work_dir = Path(work_dir)
    asr_file = work_dir / "asr_result.json"
    (work_dir / EVIDENCE_FILENAME).unlink(missing_ok=True)

    provider = resolve_asr_provider()
    if provider == "mimo-asr" and not CONFIG["mimo_asr_api_key"]:
        key_name = CONFIG["mimo_asr_env_var"]
        log(f"ASR 跳过：未设置 {key_name}，且未配置本地 Whisper（WHISPER_MODEL_DIR）。"
            f"如不需要对白可加 --skip-asr")
        asr_file.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
        write_asr_timing_evidence(
            work_dir, video_path, "UNAVAILABLE_NO_KEY", final_segments=[]
        )
        return []
    log(f"ASR 提供方: {provider}")

    audio_stream = select_audio_stream(video_path)
    asr_language = _resolve_asr_language(audio_stream, provider)
    if asr_language != "auto":
        log(f"ASR 语言: {asr_language}（由配置或音轨元数据固定）")

    # 提取音频
    audio_wav = work_dir / "audio.wav"
    audio_meta = _audio_meta_path(work_dir)
    audio_wav.unlink(missing_ok=True)
    audio_meta.unlink(missing_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(video_path),
           *audio_stream_map_args(audio_stream), "-vn",
           "-ar", "16000", "-ac", "1", str(audio_wav)]
    try:
        result = run_cmd(cmd)
    except Exception as exc:
        audio_wav.unlink(missing_ok=True)
        audio_meta.unlink(missing_ok=True)
        asr_file.unlink(missing_ok=True)
        write_asr_timing_evidence(
            work_dir, video_path, "FAILED_AUDIO_EXTRACTION", audio_stream=audio_stream,
            asr_language=asr_language,
        )
        raise RuntimeError("音频提取失败: ffmpeg 无法完成") from exc
    if result.returncode != 0:
        audio_wav.unlink(missing_ok=True)
        audio_meta.unlink(missing_ok=True)
        asr_file.unlink(missing_ok=True)
        write_asr_timing_evidence(
            work_dir, video_path, "FAILED_AUDIO_EXTRACTION", audio_stream=audio_stream,
            asr_language=asr_language,
        )
        raise RuntimeError(f"音频提取失败: {result.stderr}")
    _write_audio_meta(work_dir, video_path, audio_stream)

    # 获取音频时长；ffprobe 失败时不伪造时长（否则会向 asr_result.json 写入虚构时间戳），
    # 而是记录 UNAVAILABLE_NO_DURATION 证据并跳过转录
    try:
        duration = get_video_duration(audio_wav)
    except RuntimeError as exc:
        log(f"ASR 警告: 无法获取音频时长，跳过 ASR 转录: {exc}")
        asr_file.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
        write_asr_timing_evidence(
            work_dir,
            video_path,
            "UNAVAILABLE_NO_DURATION",
            final_segments=[],
            audio_path=audio_wav,
            audio_stream=audio_stream,
            asr_language=asr_language,
        )
        return []

    segments_dir = work_dir / "audio_segments"
    segments_dir.mkdir(exist_ok=True)
    segment_length = int(CONFIG["asr_segment_seconds"])
    if cache_payload is None:
        from understanding_cache import _asr_cache_payload

        cache_payload = _asr_cache_payload(video_path)
    partial_path = work_dir / "asr_result.partial.json"
    partial_key = hashlib.sha256(
        json.dumps(cache_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    partial_windows = _load_partial_windows(partial_path, partial_key, resume)
    language_decisions = []
    try:
        asr_result = _segment_and_transcribe(
            audio_wav,
            segments_dir,
            duration,
            segment_length,
            provider=provider,
            language=asr_language,
            partial_path=partial_path,
            partial_key=partial_key,
            partial_windows=partial_windows,
            language_decisions=language_decisions,
        )
    except ASRProviderError:
        asr_file.unlink(missing_ok=True)
        write_asr_timing_evidence(
            work_dir, video_path, "FAILED_PROVIDER", audio_path=audio_wav,
            audio_stream=audio_stream, asr_language=asr_language,
        )
        raise

    # 用 background_research.json 的人名表修正 ASR 同音字错误（如 叶青眉 → 叶轻眉）；无人名表时为 no-op
    observed_result = [dict(segment) for segment in asr_result]
    _apply_glossary_corrections(asr_result, work_dir)

    # 保存
    _write_json_atomic(asr_file, asr_result)
    if any(s["text"] for s in asr_result):
        status = "AVAILABLE_WHISPER_LOCAL" if provider == "whisper-local" else "AVAILABLE_COARSE"
    else:
        status = "EMPTY_UNKNOWN"
    write_asr_timing_evidence(
        work_dir,
        video_path,
        status,
        observed_segments=observed_result,
        final_segments=asr_result,
        audio_path=audio_wav,
        audio_stream=audio_stream,
        asr_language=asr_language,
        language_decisions=language_decisions,
    )
    partial_path.unlink(missing_ok=True)

    total_text = " ".join(s["text"] for s in asr_result if s["text"])
    empty = sum(1 for s in asr_result if not s["text"])
    suffix = f"（{empty} 段无文本：原因未知，不代表已证实静音）" if empty else ""
    log(f"ASR 转录完成: {len(asr_result)} 段, 共 {len(total_text)} 字{suffix}")
    return asr_result


def _resolve_asr_language(audio_stream, provider):
    configured = str(CONFIG.get("asr_language", "auto") or "auto").strip().lower()
    if configured != "auto":
        return configured
    provider_setting = (
        CONFIG.get("mimo_asr_language") if provider == "mimo-asr"
        else CONFIG.get("whisper_language")
    )
    provider_setting = str(provider_setting or "auto").strip().lower()
    if provider_setting != "auto":
        return provider_setting
    return language_for_audio_track(audio_stream)


def _load_partial_windows(path, expected_key, resume):
    path = Path(path)
    if not resume:
        path.unlink(missing_ok=True)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("cache_key") != expected_key
        or not isinstance(payload.get("windows"), dict)
    ):
        log("忽略 ASR partial cache（来源或设置已变化）")
        return {}
    return payload["windows"]


def _write_partial_windows(path, cache_key, windows):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {"schema_version": 1, "cache_key": cache_key, "windows": windows},
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _write_json_atomic(path, payload):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _strip_reasoning_residue(text):
    """Remove MiMo reasoning-model <think>…</think> leakage from ASR content.

    Thinking-disable is not applied to -asr models (lib._prepare_api_payload), so the reasoning
    model can leak a <think> block — full, truncated/unclosed, or a leading orphan/residual tag
    (a bare "think>" prefix) — into the transcript. The dubbing implementation carries its own
    copy of this policy; keep behavior aligned through tests.
    """
    text = re.sub(r"(?is)<think\b.*?</think\s*>", "", text)  # full <think>…</think> block
    text = re.sub(r"(?is)<think\b.*\Z", "", text)            # unclosed/truncated <think tail
    return re.sub(r"(?i)^\s*<?/?think\s*>\s*", "", text)     # leading orphan/residual think tag


def _run_asr(wav_path, language=None):
    """用 MiMo ASR (mimo-v2.5-asr) 转录单个 wav 文件，返回纯文本。

    音频以 base64 data-URI 放进 OpenAI 风格的 chat/completions 消息里，转写文本回到
    choices[0].message.content。API/响应结构失败会抛错，避免把瞬时失败缓存成空转写；
    只有无音频、超体积等确定不可发送的片段返回空串。
    """
    try:
        raw = Path(wav_path).read_bytes()
    except OSError as e:
        log(f"ASR 警告: 无法读取音频 {wav_path}: {e}")
        return ""
    if not raw:
        return ""

    b64 = base64.b64encode(raw).decode("ascii")
    max_b64_bytes = int(float(CONFIG["mimo_asr_base64_max_mb"]) * 1024 * 1024)
    if len(b64) > max_b64_bytes:
        log(f"ASR 警告: 分片 base64 体积 {len(b64) / 1024 / 1024:.1f}MB 超过 MiMo 上限 "
            f"{CONFIG['mimo_asr_base64_max_mb']}MB，跳过该段；可调小 ASR_SEGMENT_SECONDS")
        return ""

    payload = {
        "model": CONFIG["mimo_asr_model"],
        "messages": [{
            "role": "user",
            "content": [{
                "type": "input_audio",
                "input_audio": {"data": f"data:{_ASR_AUDIO_MIME};base64,{b64}"},
            }],
        }],
        "asr_options": {"language": language or CONFIG["mimo_asr_language"]},
    }
    try:
        resp = mimo_asr_api_call(payload)
    except Exception as e:
        raise ASRProviderError(f"MiMo ASR 调用失败: {e}") from e
    try:
        return _strip_reasoning_residue(str(resp["choices"][0]["message"]["content"] or "")).strip()
    except (KeyError, IndexError, TypeError):
        raise ASRProviderError(
            f"MiMo ASR 返回结构异常: {json.dumps(resp, ensure_ascii=False)[:200]}"
        )


def _segment_and_transcribe(
    audio_wav,
    segments_dir,
    total_duration,
    segment_length=None,
    *,
    provider="mimo-asr",
    language="auto",
    partial_path=None,
    partial_key=None,
    partial_windows=None,
    language_decisions=None,
):
    """分段转录长音频"""
    if segment_length is None:
        segment_length = int(CONFIG["asr_segment_seconds"])
    # 长视频 ASR 是顺序调用；可选节流让调用间隔开，降低踩到集群限流的频率（默认 0=不节流）
    try:
        throttle = max(0.0, float(os.environ.get("ASR_THROTTLE_SECONDS", "0") or 0))
    except ValueError:
        throttle = 0.0
    results = []
    partial_windows = partial_windows if partial_windows is not None else {}
    language_decisions = language_decisions if language_decisions is not None else []

    duration_seconds = max(1, math.ceil(float(total_duration)))
    for window_index, start in enumerate(range(0, duration_seconds, segment_length)):
        if throttle and window_index:
            time.sleep(throttle)
        end = min(start + segment_length, total_duration)
        cached = partial_windows.get(str(window_index))
        if (
            isinstance(cached, dict)
            and cached.get("start") == round(start, 2)
            and cached.get("end") == round(end, 2)
            and isinstance(cached.get("segments"), list)
            and any(str(item.get("text") or "") for item in cached["segments"] if isinstance(item, dict))
        ):
            results.extend(cached["segments"])
            language_decisions.append({
                "index": window_index, "start": round(start, 2), "end": round(end, 2),
                "language": cached.get("language") or language,
            })
            log(f"  段 {window_index+1}: 复用 partial cache")
            continue
        seg_wav = segments_dir / f"seg_{window_index:03d}.wav"

        cmd = ["ffmpeg", "-y", "-i", str(audio_wav),
               "-ss", str(start), "-to", str(end),
               "-ar", "16000", "-ac", "1", str(seg_wav)]
        cut = run_cmd(cmd)
        if cut.returncode != 0:
            # 切分失败时不要对磁盘上的陈旧/残缺音频转录，否则会得到错位文本
            log(f"  段 {window_index+1}: 切分失败，跳过转录 ({cut.stderr.strip()[:200]})")
            text = ""
            detected_language = language
            window_segments = [{
                "start": round(start, 2),
                "end": round(end, 2),
                "text": "",
            }]
        else:
            detected_language = language
            if provider == "whisper-local":
                try:
                    if language == "auto":
                        local_segments, detected_language = transcribe_wav_local(seg_wav)
                    else:
                        local_segments, detected_language = transcribe_wav_local(
                            seg_wav, language=language
                        )
                except RuntimeError as exc:
                    raise ASRProviderError(str(exc)) from exc
                window_segments = [
                    {
                        "start": round(start + float(item["start"]), 2),
                        "end": round(min(end, start + float(item["end"])), 2),
                        "text": str(item["text"] or "").strip(),
                    }
                    for item in local_segments
                    if str(item.get("text") or "").strip()
                ]
                text = " ".join(item["text"] for item in window_segments)
            else:
                if language == "auto":
                    text = _run_asr(seg_wav)
                else:
                    text = _run_asr(seg_wav, language=language)
                window_segments = [{
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": text,
                }]

        results.extend(window_segments)
        language_decisions.append({
            "index": window_index, "start": round(start, 2), "end": round(end, 2),
            "language": detected_language or language,
        })
        if text.strip() and partial_path is not None and partial_key:
            partial_windows[str(window_index)] = {
                "start": round(start, 2),
                "end": round(end, 2),
                "language": detected_language or language,
                "segments": window_segments,
            }
            _write_partial_windows(partial_path, partial_key, partial_windows)
        log(f"  段 {window_index+1}: {start:.0f}s-{end:.0f}s => {len(text)} 字")

    return results
