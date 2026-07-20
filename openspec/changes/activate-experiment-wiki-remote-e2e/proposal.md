## Why

Phase 2 已完成 Wiki/Skill 候选生成和三案例科学验证，但系统刻意停在
`WITHHELD_PENDING_HUMAN_APPROVAL`：它没有正式 Wiki 发布类型、审批范围校验、
追加式权威存储或可直接进入 RAG 重建的发布文档。用户现已明确回复 `Yes`，要求
在 AutoDL 同步当前代码、正式写入实验 Wiki，并用一个 PINN 模型验证 Qwen RAG、
实验治理、执行、分析、决策、知识发布和重放的全链路完整性。

## What Changes

- 新增正式 `PublishedWikiEntry` 契约，要求有效科学候选、显式
  `KNOWLEDGE_PROMOTION` 人工批准、候选精确 scope 和显式发布时间。
- 新增物理隔离的追加式 Wiki 存储：一次发布同时生成权威 JSON、人类可读 Markdown、
  RAG `.index.json` 和哈希 manifest；目标版本不可覆盖，完全相同的重放可幂等验证。
- 新增 `pinn-strategy wiki publish`，所有路径、发布元数据、候选和批准均由操作者显式传入。
- 在全新 AutoDL 版本目录同步确定 Git 提交，复用隔离的 Qwen 与 PINN 环境，禁止持久凭据。
- 正式发布已验证的跨域 Wiki 候选，但不发布 Skill。
- 以独立 Poisson PINN 运行完成 Qwen 检索、审计、smoke/full、字段分析、决策、
  证据持久化、Wiki 索引重建、Qwen rerank 检索和零重启 replay。

## Capabilities

### New Capabilities

- `experiment-wiki-publication`: 定义 Wiki 人工批准、正式发布、追加式版本、原子持久化和 RAG 索引边界。
- `remote-pinn-rag-end-to-end`: 定义 AutoDL 上代码同步、环境隔离、真实 Qwen 推理、PINN 执行和证据回传门禁。

### Modified Capabilities

- None. 已完成的两个历史 changes 保持不可变；本 change 只增加显式发布路径和远端资格证据。

## Impact

- 目标仍为 `exp/hybrid-rag`；不创建 worktree，不修改非目标项目。
- 复用本地 `pinn_strategy_orchestrator`、远端 Qwen3 检索环境和远端
  Python 3.11.11/PyTorch 2.3.1 PINN 环境；首批不新增依赖。
- 远端使用全新版本化目录；若任何目标已存在，写入前创建 `_backup_2026-07-20` 备份。
- SSH 密码、主机、端口、私钥和直接连接字符串不得进入代码、OpenSpec、日志、Wiki、结果或提交。
- Wiki 发布不等于 Skill 发布。Skill 仍要求独立重放和单独人工批准。
- 失败运行、拒绝决策和冲突证据必须保留，不得为获得全链路 PASS 而删除或隐藏。
