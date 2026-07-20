## Context

现有 `KnowledgeGovernanceService` 能生成、替代和失效 Wiki 候选，但只有 Skill 具有
正式发布契约。RAG 只读取权威目录下的 `.index.json`，因此把候选 JSON 直接复制到
某个目录既不能证明人工批准，也不能成为可重建、可追溯的正式 Wiki。

## Goals

- 用不可变类型证明“谁批准了哪个候选”。
- 用追加式、原子、可验哈希的目录证明“正式发布了哪个版本”。
- 从同一发布对象派生 Markdown 和 RAG 文档，避免两套知识真相。
- 通过真实 Qwen embedding/reranker 和一个真实 PINN 运行证明跨层调用链。

## Non-Goals

- 不自动发布 Wiki 或 Skill。
- 不把 Qwen 生成文本当作科学决策依据。
- 不宣称一次远端 Poisson 运行证明所有 PINN 或所有 PDE 的科学有效性。
- 不实现网络 Wiki 服务、Web UI 或多用户权限系统。

## Decisions

### 1. 发布对象和发布元数据分离

`WikiPublicationSpec` 显式携带稳定 Wiki ID、发布时间、项目/PDE/框架检索元数据和
声明。`PublishedWikiEntry` 组合候选、批准和 spec，并在模型校验器中强制：候选仍是
有效候选、批准为 `KNOWLEDGE_PROMOTION/APPROVED`、scope 精确等于
`wiki:<candidate_id>`、发布时间不早于批准时间、新发布状态为 `VALID`。

### 2. 一个版本目录是一项原子事实

存储目标为 `<knowledge-root>/wiki/<wiki-id>/vNNNN/`。新发布先在同一根目录的 staging
目录生成 `publication.json`、`entry.md`、`entry.index.json` 和 `manifest.json`，逐个
计算 SHA-256 后以目录替换完成提交。既有目标只有在内容和 manifest 完全一致时允许
幂等重放；任何差异都报冲突，绝不覆盖。

### 3. RAG 文档是发布对象的派生视图

`.index.json` 的正文、验证状态、有效期、版本、来源行号和 claims 全部由正式发布对象
生成。索引删除或重建不会影响权威 Wiki 目录；Qdrant 仍是可丢弃派生状态。

### 4. CLI 不持有业务真相

`wiki publish` 只加载候选、批准和发布 spec，调用应用服务并返回稳定 JSON。CLI 不推断
时间、项目、PDE、批准 scope 或文件位置。

### 5. 远端全链路使用双环境

Qwen3-Embedding-8B 和 Qwen3-Reranker-4B 在已验证的隔离 GPU 环境运行；Poisson PINN
在 Python 3.11.11/PyTorch 2.3.1 环境运行。两者通过 JSON/文件契约交互，不互相导入。

## Failure Handling

- 发布审批不匹配：拒绝且不创建版本目录。
- staging 中断：保留隔离 partial，不形成正式版本。
- 目标版本冲突：拒绝覆盖。
- Qwen 或 PINN 失败：保留日志、状态和结果目录；不伪造 Wiki/RAG PASS。
- RAG 检索不到已发布条目或 provenance/revision 不匹配：全链路失败。
