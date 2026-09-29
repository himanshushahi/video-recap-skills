# Agent Note: 将英文 README 设为仓库默认入口

## Problem

仓库同时有中文 `README.md` 与英文 `README.en.md`。GitHub 对仓库根目录优先展示 `README.md`，所以默认访问者仍首先看到中文；英文文件顶部还把读者指回中文 README，且 README 测试将两种语言都视为必须存在。

## Decision

根目录的唯一 README 是英语 `README.md`，其内容来自原 `README.en.md`。中文 `README.md` 与冗余 `README.en.md` 文件已删除；README masthead 不再显示语言切换链接，也不保留两份文档同步时间注释。README 合同测试验证英语定位和安装/宿主指引，并断言 `README.en.md` 不存在。

## Alternatives considered

- **保留中文为 `README.md`，只在顶部突出英文链接。** 最强理由：不会删除中文读者的入口，也不改变已有路径。否：GitHub 默认展示仍是中文，用户明确希望默认入口为英语。
- **将中文改名为 `README.zh.md`，同时将英文升为 `README.md`。** 最强理由：保留中文内容供需要的人访问。否：用户明确要求移除中文 README，且维护两个长文版本会继续产生同步成本。
- **只把中文 README 内容覆盖为英文，继续保留 `README.en.md` 副本。** 最强理由：外部或旧链接仍可访问英文路径。否：会有两个英文副本，之后容易漂移；仓库内链接与测试应改为单一 canonical 路径。

## Consequences

- 收益：GitHub 根页面默认展示英语；README 只有一个维护来源；主入口与英语用户实际受众一致。
- 代价：中文 README 内容及 `README.en.md` 旧路径消失，旧外部链接可能失效；中文内容若后续需要，应以独立翻译策略另行添加，而不是保留双重默认入口。

## Verification

- `pytest tests/orchestrator/test_plugin_manifest.py -q`: 5 passed.
- Search found no live documentation/source references to `README.en.md`; remaining mentions are historical decision notes and the regression assertion that the old file is absent.
