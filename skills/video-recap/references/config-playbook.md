# Config playbook (override-only)

The bundle runs **zero-config** with sensible defaults. To change behavior, set the
environment variables below (or pass the noted CLI flags) — they **override** the defaults.
Nothing here is required; this is documentation only. The only config file any tool reads is an
optional `recap_project.json` passed with `--project` (see `resource-library.md`): it resolves to the same
variables below, and a variable you set that disagrees with the project stops the run. The bundle ships no
root `CLAUDE.md` (so it never collides with your project/global instructions).
Defaults below are bundle-level defaults unless a note scopes them to a specific stage.

| Concern | Env var / flag | Default | Notes |
|---|---|---|---|
| MiMo API key | `MIMO_API_KEY` | — | **required for the default pipeline**; one key drives ASR + VLM + default MiMo TTS. `tp-*` Token-Plan keys auto-route to the cluster base URL; `sk-*` keys support pay-as-you-go without a subscription. Any OpenAI-compatible gateway key works once `MIMO_API_URL` points at it |
| API endpoint override | `MIMO_API_URL` (+ `MIMO_VIDEO_API_URL` / `MIMO_ASR_API_URL` / `MIMO_TTS_API_URL`, and matching `MIMO_VIDEO_API_KEY` / `MIMO_ASR_API_KEY` / `MIMO_TTS_API_KEY`) | MiMo defaults | `MIMO_API_URL` and frame-VLM `MIMO_VIDEO_API_URL` accept OpenAI-compatible chat-completions endpoints (the VLM endpoint must support image inputs); ASR/TTS overrides use provider-specific payloads and need a proxy that translates them. Both `api-key` and `Authorization: Bearer` headers are sent; the MiMo-only `thinking` field is only injected for `*.xiaomimimo.com` hosts |
| Token-Plan cluster | `MIMO_TOKEN_PLAN_CLUSTER` | `cn` | `cn` / `sgp` / `ams` (only for `tp-*` keys) |
| VLM / chat model | `MIMO_MODEL` | `mimo-v2.5` | frame VLM + reviewer + consolidate; any gateway model id (e.g. `auto`) |
| ASR provider | `ASR_PROVIDER` / `--asr-provider {auto,mimo-asr,whisper-local}` | `auto` | `auto` prefers local Whisper when `WHISPER_MODEL_DIR` exists, else MiMo |
| ASR audio track | `ASR_AUDIO_STREAM_INDEX` / `--asr-audio-stream-index` | auto | global FFmpeg stream index; a unique original/default track is auto-selected, otherwise inspect with `--list-audio-tracks` and choose explicitly |
| ASR language | `ASR_LANGUAGE` / `--asr-language` | `auto` | pin a language such as `hi` or `en`; precedence is unified setting, fixed provider-specific setting, recognized track tag, then provider auto-detection |
| Local Whisper model | `WHISPER_MODEL_DIR` | `<Narrato>/models/whisper/turbo` | faster-whisper/CTranslate2 model dir (must contain `model.bin`); needs `pip install faster-whisper` |
| Local Whisper runtime | `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` / `WHISPER_LANGUAGE` / `WHISPER_VAD_FILTER` | `auto` / faster-whisper default / `auto` / off | device `auto`/`cpu`/`cuda`; language `auto` = detect per ASR window when no higher-priority language is resolved; VAD filter is opt-in |
| ASR model | `MIMO_ASR_MODEL` | `mimo-v2.5-asr` | speech-to-text |
| MiMo ASR language | `MIMO_ASR_LANGUAGE` | `auto` | Provider-specific fixed language; used when `ASR_LANGUAGE=auto`, before track-language metadata |
| ASR window | `ASR_SEGMENT_SECONDS` | `15` | smaller → finer dialogue timestamps (stays under MiMo's 10MB base64 cap) |
| TTS provider | `TTS_PROVIDER` / `--tts-provider {auto,mimo-tts,fish-audio,edge-tts,index-tts}` | `auto` | `auto` prefers edge-tts when `EDGE_TTS_VOICE` is explicitly set, then configured MiMo, then Fish Audio, and never picks index-tts; explicit selection is recommended for repeatable runs |
| Edge TTS voice | `EDGE_TTS_VOICE` / `--edge-tts-voice` | `hi-IN-SwaraNeural` | no API key; needs `pip install edge-tts` + ffmpeg; per-run option overrides the environment/default voice and selects edge-tts; examples: `hi-IN-SwaraNeural` (Hindi), `en-US-AriaNeural` (English), `zh-CN-YunyangNeural` (Chinese). edge-tts is online synthesis-only and cannot transcribe |
| MiMo TTS model | `MIMO_TTS_MODEL` | `mimo-v2.5-tts` | MiMo provider only |
| MiMo voice | `MIMO_TTS_VOICE` / `--mimo-tts-voice` | `冰糖` | |
| Cloned narration voice | `VOICE_REF` / `--voice-ref` | off | MiMo full/cut only; lazily normalize once, then use `mimo-v2.5-tts-voiceclone`; mutually exclusive with `--mimo-tts-voice`; requires authorization and sends the reference to MiMo |
| Fish Audio key | `FISH_API_KEY` | — | required when Fish Audio is selected; never written to artifacts or cache metadata |
| Fish Audio model | `FISH_TTS_MODEL` | `s2.1-pro-free` | free model under Fair Use, no SLA; check Fish Audio's current policy |
| Fish Audio voice | `FISH_TTS_REFERENCE_ID` | `5653cea4ac83480aaf2bf45406556185`（娱乐扒妹） | optional override for the built-in narration voice; part of the per-segment cache settings |
| Fish Audio endpoint | `FISH_TTS_API_URL` | `https://api.fish.audio/v1/tts` | returns WAV directly to the existing voiceover pipeline |
| Self-hosted TTS | `INDEX_TTS_ENDPOINT` / `INDEX_TTS_VOICE` | — | explicit `--tts-provider index-tts` only; the endpoint is never written to disk, and segment `emotion`/style is rejected |
| TTS transport | `TTS_TIMEOUT` / `TTS_WORKERS` / `TTS_RETRIES` | `300` / `4` / `3` | request timeout, parallel segments, and per-segment retries for all providers |
| Advisory MiMo QC | `MIMO_QC` / `--mimo-qc {off,pre-assemble,post-render,both}` | `off` | optional subjective review at the selected stage(s), one request per stage. Always fail-open: results only point the agent/user to `mimo_qc.json`, never block or auto-repair |
| MiMo QC refresh/model | `MIMO_QC_REFRESH` / `--mimo-qc-refresh`; `MIMO_QC_MODEL` | cache on / VLM fallback | the reuse check compares evidence file sizes/mtimes, model and prompt, never absolute paths. Post-render temporarily samples at most 6 JPEGs (≤768px); base64 is never persisted. The standalone adapter requires explicit `mimo_qc.py --live` for network access |
| Narration block coverage | `NARRATION_COVERAGE_TARGET` / `NARRATION_BLOCK_SECONDS` | `0.7` / `9.0` | current block-recap density controls |
| Narration speed | `NARRATION_SPEED` | `1.15` | global atempo on the voiceover; set `1.0` for long-form/documentary |
| Narration authored start | `NARRATION_DELAY_SECONDS` | `0` | the renderer uses the Agent-authored `start` exactly. Set a non-zero value only for legacy drafts; hidden delay can move a validated sentence-boundary entry back into source speech |
| Source sentence boundary detector | `SOURCE_BOUNDARY_NOISE_THRESHOLD` / `SOURCE_BOUNDARY_MIN_PAUSE` / `SOURCE_BOUNDARY_MAX_ALIGNMENT_ERROR` | `-18dB` / `0.12` / `2.1` | aligns ASR terminal punctuation to short acoustic pauses and writes `speech_boundary_anchors.json`; unsafe narration entries and cut in/out points are blocked. There is no intentional-interrupt override |
| Cut sentence snapping | `SNAP_CLIP_LINE_END` / `CLIP_START_SNAP_MAX_PREPEND` / `CLIP_START_SNAP_MAX_TRIM` / `CLIP_SNAP_MAX_EXTEND` | on / `1.8` / `0.35` / `2.0` | scene-cut cleanup runs first; reliable sentence/quiet snapping runs last. An ASR-owned edge still inside speech produces `unsafe_clip_sentence_boundary` instead of a half sentence |
| Mask source subs | `MASK_SOURCE_SUBTITLES` / `SOURCE_SUBTITLE_MASK_POLICY` / `SOURCE_SUBTITLE_MASK_RATIO` | off / `off` / `0.14` | masking requires an explicit policy (`opt_in`, `safe`, or `forced`) and burned recap subtitles. Passing measured `--subtitle-y-top/--subtitle-y-bot` opts in automatically. With `--no-burn-subtitles`, the MP4 stays unmasked |
| Measured subtitle band | `SUBTITLE_Y_TOP` / `SUBTITLE_Y_BOT`; `--subtitle-y-top/--subtitle-y-bot` | off | half-open `[top, bot)` ffmpeg auto-rotated display-frame pixel coordinates; square-pixel video and bottom ASS alignment (1/2/3) only; use `tools/measure_subtitle.py` to generate source-identified previews and suggestions |
| Subtitle mask look | `SUBTITLE_MASK_OPACITY` / `SOURCE_SUBTITLE_MASK_TIMING` / `SUBTITLE_MASK_PADDING` | `0.6` / `narration` / `4` | generic ratio masks stay translucent by default; an explicitly measured `--subtitle-y-top/--subtitle-y-bot` band defaults to opaque so source glyphs cannot show through. Set `SUBTITLE_MASK_OPACITY` to override; timing `all` restores full-time masking |
| Narration audio profile | `--audio-profile` | `voiceover-only` | default excludes movie audio; an optional `BGM_PATH` fills narration gaps and ducks under voiceover with at least a 3-second bridge. `source-ducking` opts into movie audio and BGM at 20% in gaps / 5% under narration with at least a 3-second bridge. `legacy-ducking` restores the previous configurable source mix |
| Legacy original ducking | `IDLE_ORIG_VOLUME` / `SPEECH_DUCKING_VOLUME` | `1.0` / `0.2` | used by `legacy-ducking`: original audio returns to `IDLE` in gaps and ducks to `SPEECH` under narration. `DUCKING_ORIG_VOLUME` (`0.3`) is only the fallback when beats carry no placement info |
| Foreign source audio | `FOREIGN_SOURCE_AUDIO` | off | set when the original audio is in a language the narration is **not** (e.g. a Japanese drama recapped in Chinese). It adjusts the legacy under-narration levels to reduce foreign speech bleeding under narration; the `source-ducking` profile uses its fixed 5% under-voiceover level. Pairs with bring-your-own `user_subtitles.*` for the foreign dialogue |
| Duck fade | `DUCK_FADE_SECONDS` | `0.3` | attack ramp target. Sentence-safe source restore is shortened to fit wholly inside the measured acoustic pause (`pause_start`→anchor), so it never reveals the previous source sentence tail |
| Duck bridge | `DUCK_BRIDGE_SECONDS` | `1.5` | legacy/source gap threshold; `source-ducking` uses at least 3 seconds to avoid rapid source-audio level changes |
| Background music | `BGM_PATH` / `BGM_VOLUME` / `BGM_DUCKING_VOLUME` | off / `0.18` / `0.10` | optional looped music bed mixed as its own track; in `voiceover-only`, it fills gaps and ducks under narration. The caller must verify that the supplied file is licensed for the intended use |
| Final loudness | `FINAL_LOUDNORM` / `TARGET_LUFS` | `true` / `-14` | end-of-pipeline normalize |
| Output compression | `OUTPUT_CRF` / `OUTPUT_PRESET` / `OUTPUT_MAX_HEIGHT` | `18` / `veryfast` / `0` | x264 re-encode controls, applied whenever the final mux re-encodes (burning subtitles / masking / scaling / `FORCE_VIDEO_REENCODE`). Higher `OUTPUT_CRF` = smaller file/lower quality (18≈visually lossless, 23–26 much smaller); `slow`/`slower` preset shrinks more at the same CRF; `OUTPUT_MAX_HEIGHT>0` downscales the final height (keeps aspect, even width), e.g. `720` to halve 1080p pixels. Subtitles/mask render at native res then downscale, so they stay crisp |
| Style | `--style` | `纪录片` | freeform verbatim guidance passed into the agent brief. The agent synthesizes voice/pacing from this exact text plus evidence; it is not a fixed option list, preset, switch, or finite style taxonomy |
| Edit mode | `EDIT_MODE` / `--edit-mode` | `full` | `full`, `cut`, or `dub`; multi-source input supports `cut` only |
| Cut target | `TARGET_DURATION` / `--target-duration` | — | e.g. `10m` (cut mode) |
| Scene threshold | `--scene-threshold` | `0.1` | scene-cut sensitivity |
| Shot-change-aware cut | `SCENE_CUT_SNAP` / `SCENE_CUT_SNAP_MARGIN` / `SCENE_CUT_DETECT_THRESHOLD` | on / `0.5` / `0.4` | cut mode: nudge each clip boundary off the original footage's hard cuts so the edit point doesn't flash a sliver of the adjacent shot (闪烁). source_start moves forward onto / source_end back onto any shot-change within the margin; boundaries already on a cut, or that would shrink a clip below ~0.5s, are left as-is. Set `SCENE_CUT_SNAP=0` to disable |
| VLM workers | `VLM_WORKERS` | `8` | lower to 1 if a proxy/WAF rate-limits |
| Subtitle size | `SUBTITLE_FONT_SIZE` / `SUBTITLE_MARGIN_V` | `42` / `48` | look & placement |
| Subtitle font | `SUBTITLE_FONT_NAME` / `SUBTITLE_FONT_FILE` | `Arial` / — | with a font file, burned ASS subtitles load fonts from its directory (`fontsdir`) and on-screen text overlays use it (`fontfile`); `SUBTITLE_FONT_NAME` must be that file's family name. A bound `subtitle_style` template sets both |
| 整理 / index | `--no-consolidate` / `--consolidate-asr` | on | build the understanding index (and optionally clean ASR); use `--no-consolidate` to skip |
| Advisory / strict narration review | `REVIEW_NARRATION` / `--review-narration` / `--no-review-narration`; strict: `REQUIRE_NARRATION_REVIEW` / `--require-narration-review` | advisory on, strict off | runs the narration review stage after validation and before TTS. Default advisory mode is fail-open; strict mode blocks TTS on review failure, parse error, or error-severity findings. In cut mode the reviewer uses `clip_plan_validated.json` to remap VLM/ASR grounding onto the output timeline |
| 剪映 export (optional) | `--export-jianying` / `EXPORT_JIANYING` | off | after rendering, also write a 剪映/JianYing draft from `timeline.json`. Decoupled — the core render never needs it |
| 剪映 draft dir | `JIANYING_DRAFT_DIR` | work_dir | parent folder for the exported draft (point it at 剪映's drafts root to open in-app) |
| 剪映 bundle media | `JIANYING_BUNDLE_MEDIA` / `--jianying-no-bundle-media` | **on** | copies video/audio/photo into `Resources/local/*`, uses draft-placeholder paths, and writes the type-0 material index in `draft_meta_info.json`. This makes a cloned/moved draft self-contained and is required on sandboxed macOS. Use `--jianying-no-bundle-media` only if 剪映 can reach the original paths |
| Source video | `--source-video` | — | original video (cut mode) so `timeline.json` / 剪映 export reference the real source clips instead of the concatenated `edited_source.mp4`; direct `video-assemble` runs intentionally ignore ambient `SOURCE_VIDEO` unless `--source-video` is passed |

`video-assemble` always writes `timeline.json` — a backend-neutral multi-track model
(video / original-audio / narration / BGM / subtitle, with ducking automation). The
canonical renderer is ffmpeg; the 剪映 exporter is an optional consumer of the same file. Subtitle text in `timeline.json` is display-ready and follows the same terminal-punctuation policy as SRT/ASS.

See each stage skill's SKILL.md for the full per-stage option list.
