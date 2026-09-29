# Agent Note: 多语言解说与 CapCut 交接边界

## Problem

recap 与 script 技能原先把中文写作描述为唯一输出，review rubric 与 ASR 清洗也含中文专用指令；自动 brief 把中文字符预算展示为通用预算；英文字幕按字符硬切会切断单词，烧录字幕还会把所有 em dash 替换为中文逗号。用户希望自然语言指定 English/Hindi 电影解说和 CapCut 交付。recap 原先没有逐次选择 Edge TTS 音色的参数。已有草稿导出器实际按 JianYing/剪映协议模板输出，未验证所有国际版 CapCut，不能承诺通用原生工程兼容。

## Decision

1. recap/script 服从用户明确指定的旁白语言；未指定时按请求主要语言，无法判断时询问。旁白烧录字幕与 SRT/ASS 跟随旁白语言，原声台词字幕保留源语言，除非用户要求翻译。dub 仍明确标注为独立的英译中 MiMo voice-clone 功能。
2. recap 新增逐次 `--edge-tts-voice`：显式传入时选择 `edge-tts`，传到 voiceover 和续跑命令并覆盖本次 TTS voice/cache setting。配置表列出 Hindi / English 示例 voice。TTS 保留稿件语言，不负责翻译。
3. review rubric 与 ASR 清洗提示不再要求中文；ASR cleanup 保留每段源语言和文字系统。brief 的 speech budget 被标为近似内部节奏单位，不是跨语言字数/词数限制；创作规范要求按目标语言自然口播时长估算。
4. 英文长字幕优先按空格边界拆分，只有超长无空格片段才硬切；em dash 重复时压成一个 em dash，不替换为中文标点。交付指导要求检查 Hindi/其他文字系统的字体覆盖。
5. README 中提供 Hindi、English recap + CapCut MP4/SRT 请求示例。保证可移植交付为渲染 MP4 与字幕文件；`--export-jianying` 导出的是 JianYing/剪映协议格式，不保证所有国际版 CapCut 版本可原生打开，需目标应用实测。

## Alternatives considered

- **只改 README，依赖模型忽略 skill 中的中文约束。** 最强理由是改动小、模型通常理解用户语言。否：技能明文要求中文，review 与 ASR cleanup 同样产生指令冲突。
- **把 `--export-jianying` 改名为 `--export-capcut` 并承诺兼容。** 最强理由是用户想要直接打开的可编辑 CapCut 工程。否：实现基于剪映 JSON 协议模板，没有对各地区/版本的 CapCut 做应用级验证；改参数名不能证明格式兼容。
- **按目标语言自动推断并锁定唯一 Edge TTS voice。** 最强理由是单句 prompt 即开箱合成。否：语言可能有地区、口音、性别和用户偏好差异；保留默认并提供逐次 voice 参数，Agent 可根据请求选择，用户也可明确指定。
- **把简体中文字符速率直接套给 English/Hindi。** 最强理由是当前 brief 已有一个可计算的预算。否：中文字符数、拉丁词数、天城文口播时长不可互换；预算现在明确为估算提示，写稿以目标语言自然口播时长与实际 TTS 时长为准。

## Consequences

- 收益：自然语言指定 English/Hindi 时，不再被技能提示拉回中文；TTS voice 可逐次匹配目标语言；英文字幕不再因固定硬切而常见地截断单词；字幕标点保留语言语义；CapCut 交付边界准确。
- 代价：Devanagari 等字体依赖本机已安装并可被 ffmpeg/libass 找到的字体，需检查成片；原生 CapCut 项目兼容性仍需用户目标版本 smoke test，跨版本交接以 MP4 + SRT/ASS 为准；中文 demo 本身仍是中文案例。

## Verification

- `tests/script`: 117 passed。
- `tests/voiceover`: 138 passed。
- `tests/orchestrator/test_audio_routing.py tests/orchestrator/test_plugin_manifest.py`: 32 passed（27 routing + 5 README contract checks）。
- Pylance changed-file diagnostics: no errors.
- Pylance runtime snippet: English subtitle chunks stay within configured width, preserve all non-space text and do not end a cue with `wit`; repeated em dash normalizes to one dash.
- Assembly pytest collection is blocked in this environment because pytest has already imported the external PyPA `packaging` package before the skill-local `packaging.py`; assembly behavior was checked with the runtime snippet but the full assemble regression file could not be run here.
