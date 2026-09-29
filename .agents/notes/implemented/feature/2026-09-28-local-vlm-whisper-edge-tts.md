## Problem

`video-recap-skills` 目前只能走小米 MiMo 云端：ASR（`mimo-v2.5-asr`）、VLM（`mimo-v2.5`）、TTS（`mimo-v2.5-tts`）全部要求 `MIMO_API_KEY`，请求头只发 MiMo 私有的 `api-key`，payload 里硬编码 MiMo 私有的 `thinking: disabled`。用户想切换到本地/自带网关：VLM 走 OpenAI 兼容网关（`http://127.0.0.1:31415/v1`，`model: auto`），转写用本地 whisper large-turbo-v3（`C:\Users\himan\AppData\Local\Narrato\models\whisper\turbo`，已验证 faster-whisper 1.2.1 可直接加载），配音用 edge-tts（已安装 7.2.8，目标 Hindi 发音）。此外用户问 edge-tts 能否做转写——不能，edge-tts 是纯合成引擎。

## Decision

1. **VLM 兼容任意 OpenAI 兼容网关**：`MIMO_API_URL` / `MIMO_MODEL` 覆盖机制不变（零配置默认仍是 MiMo），传输层同时发送 `api-key` 和 `Authorization: Bearer`；`thinking: disabled` 只对 `*.xiaomimimo.com` 主机注入；`max_tokens` 与 `max_completion_tokens` 双向镜像。frame-VLM 主路径使用 `MIMO_VIDEO_API_URL` / `MIMO_VIDEO_API_KEY`，通用兼容网关须支持 chat-completions image input；`video-overview` 的 MiMo 专用 payload 在非 MiMo 端点跳过。ASR/TTS endpoint overrides 仍发送各自的 MiMo payload，不能假定通用 OpenAI 兼容服务直接支持。改动落在 4 份实际发请求的 `scripts/lib.py`（video-understanding、video-script、video-recap、video-voiceover；assemble/cut 两份无 API 调用）以及 `video-recap` 的 QC 请求 path（非 MiMo 端点剥离 `thinking`）。
2. **新增 `ASR_PROVIDER=auto|mimo-asr|whisper-local`**：`auto` 时 `WHISPER_MODEL_DIR` 存在即优先本地（local-first），否则回退 MiMo。新文件 `skills/video-understanding/scripts/whisper_local.py` 用 faster-whisper 整文件转录，输出同格式 `[{start, end, text}]`，证据状态为 `AVAILABLE_WHISPER_LOCAL`；ASR 缓存键记录实际解析的提供方与 `model.bin` 文件身份，模型替换或 auto 切换提供方后不复用旧转写；`WHISPER_MODEL_DIR` 默认指向 Narrato turbo 目录。`--asr-provider` 从 understanding 一直透传到 `recap.py`。
3. **新增 `edge-tts` TTS 引擎**：新文件 `skills/video-voiceover/scripts/providers/edge_tts.py`，只用 stdlib + `edge-tts` CLI 子进程 + ffmpeg 转 WAV，进入现有缓存/归一化链路。`TTS_PROVIDER` 新增 `edge-tts`；`auto` 时显式配置 `EDGE_TTS_VOICE` 即优先本地。`EDGE_TTS_VOICE` 默认 `hi-IN-SwaraNeural`。
4. **`doctor.py` 与文档**：doctor 按实际提供方上报（`whisper_local_asr` / `edge_tts` capability），检查 faster-whisper / edge-tts 依赖并拒绝未知 ASR provider；`config-playbook.md`、三个 `SKILL.md`、`data-schema.md`、`CHANGELOG.md`、`env-inventory-v1.json` 同步更新；密钥只走环境变量。配音技能的 dub ASR 读取 `MIMO_ASR_API_URL` / `MIMO_ASR_API_KEY`；英文 README 说明 Antigravity CLI（`agy`）和 OpenCode 通过 `.agents/skills` 发现技能及各 provider 的配置方法。

## Alternatives considered

- **edge-tts 做转写**：它最强的理由是“同一个免费本地依赖包办 ASR+TTS”。不用：edge-tts 协议只有合成端点，没有任何语音识别能力，转写必须由 whisper-local 承担。
- **把 6 份 `lib.py` 合并成共享包**：最强的理由是一处改动处处生效，避免本次复制 6 遍。但不用：`2026-06-14-self-contained-skills-dup` 已决定各 skill 自包含、禁止跨 skill import，合并属于架构翻转，应另开笔记，不能在本篇顺手做。
- **whisper 用 openai-whisper（PyTorch）而非 faster-whisper**：最强的理由是和 `model.bin` 的 transformers 伴生文件更“原生”。不用：本机已装 faster-whisper 1.2.1 且实测可直接加载该目录，CPU 上 `int8` 更快、内存更小；用户也明确选了 faster-whisper。
- **改默认 `MIMO_API_URL` 指向本地网关**：最强的理由是用户本机就是 local-first。不用：会破坏所有现有 MiMo 用户的零配置默认；local-first 只体现在 `auto` 解析顺序上，默认 URL 保持 MiMo。

## Consequences

- 收益：无 MiMo key 也能跑全流程（VLM 网关 + 本地 ASR + 免费 TTS）；传输层双认证头让现有 MiMo 用户无感；Hindi 配音开箱可用。实测：turbo 模型 CPU 8 秒加载、转写正常；edge-tts Hindi 在线合成正常；`doctor` 在用户配置下三项全绿（网关当时离线，VLM 未做 live 验证）。
- 代价：4 份 `lib.py` 同改同测（非 6 份：assemble/cut 无 API 调用）；新增两个可选重依赖（faster-whisper、edge-tts），缺件时报错明确而不静默回退；MiMo 私有的 `video_url` / `input_audio` payload 在通用网关上不可用，`analyze_video_overview` 在非 MiMo 端点下直接跳过并记日志（frame-VLM 主链不受影响）。
- 测试：新增 whisper-local、edge-tts、doctor、frame-VLM video-endpoint、dubbing ASR per-capability endpoint 和 ASR cache identity 回归测试。当前 understanding 组 189 passed、1 skipped、1 个 Windows/ffprobe 临时路径失败；ASR evidence/cache 31 passed；voiceover 138 passed；orchestrator doctor 68 passed。
