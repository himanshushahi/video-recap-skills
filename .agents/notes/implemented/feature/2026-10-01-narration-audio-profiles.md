# Narration 音频 profile

## Problem

旧 narration 混音会把电影原声带进成片，旁白间隙恢复原声，短间隔也可能因频繁 duck/release 显得跳动。降低原声电平不能保证避开平台音频匹配；用户需要默认排除电影原声，同时能显式保留关键对白/动作声并降低切换频率。

## Decision

- `assemble.py` 与 `video-recap` 默认使用 `audio_profile=voiceover-only`：旁白正常放置，电影音轨不进入混音；可选 `BGM_PATH` 循环全片并在旁白下 duck，profile 至少用 3 秒 bridge；未配 BGM 的未覆盖区间为静音。
- `source-ducking` 是显式 narration profile：电影原声与配置的 BGM 在间隙各以 20% 播放，旁白下两者降至 5%，并各自至少用 3 秒 bridge。该 mix 保留原片声音，不承诺降低或消除版权 claim。
- `legacy-ducking` 保留旧的可配置原声 ducking 参数与自动化。
- Profile 通过 recap CLI、assembler CLI、run manifest、assembly manifest、timeline 与 assembly QC 传播；resume 检查将 profile 视为音频身份的一部分。严格采用 prepared bed 的路径要求调用者显式选择非默认 profile。
- BGM 必须由调用者配置；工具不核验是否免版权或授权范围。

## Alternatives considered

- **默认保留 20% 原声** — 最强理由：动作声和对白在间隙仍可听见。否：即使降音量也仍可能触发音频匹配，用户确认 voiceover-only 应作为默认。
- **只把原声音量设为零** — 最强理由：可复用现有混音图。否：完全不消费电影音轨比依赖增益或 fallback 更容易验证。
- **强制附加通用 BGM** — 最强理由：所有旁白间隙都有连续声音。否：仓库无适用于任意地区、平台和变现方式的已核验音乐；没有用户素材时保留静音。
- **删除旧混音** — 最强理由：减少选项与回归面。否：用户明确要求需要时保留现有 approach，因此以 `legacy-ducking` 保留。

## Consequences

- **收益**：默认混音不含电影原声；可选 BGM 填充空隙；source profile 对原声和 BGM 使用相同增益曲线与较长桥接；旧混音仍可显式选择。
- **代价**：voiceover-only 未配 BGM 时有静音区；source-ducking 仍可能被匹配或 claim；素材授权由调用者负责；profile 新字段改变 recap resume/audio manifest 身份。