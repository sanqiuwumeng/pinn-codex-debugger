## Why

`build-rag-multi-agent-dl-strategy-system` 已完成 65/65 项工程 MVP 验收，证明了通用 PINN 契约、三级架构、LangGraph 门禁、确定性指标与量纲审计、可恢复运行、知识治理以及一次受控 full run。当前成果仍缺少面向操作者的稳定入口、真正可复用的本地/远端执行后端、正式 Qwen3 检索提供者以及跨种子、跨 PDE 的科学资格验证，因此还不能作为长期运行的产品交付。

本 change 将 MVP 产品化，但不改变已经确认的物理原则：用户提供的 PDE/BC/IC/几何/参数是物理模型权威；参考场是独立证据；单位门禁检查模型内一致性和转换链，而不是强制 SI；指标必须由案例契约确认；通用核心不得含传热语义。

## What Changes

- 建立可审计 Git 发布基线，区分应进入版本库的源代码/报告/小型 manifest 与只保存在 artifact store 的模型、数组、日志、数据库和派生工作区。
- 将验证脚本中的本地进程能力提升为生产 `LocalProcessRunnerBackend`，并新增使用系统 OpenSSH 的 `AutoDLSSHRunnerBackend`；两者共享 manifest-first、幂等、对账、取消、日志和产物回收契约。
- 在隔离模型进程中实现 `Qwen3EmbeddingProvider` 与 `Qwen3RerankerProvider`，固定已验收的不可变模型 revisions，并通过显式传输契约与编排层通信。
- 为 Qdrant 派生索引增加版本标识、构建后切换、重建和回滚语义；冲突证据在 rerank 后仍必须进入确定性冲突门禁。
- 新增 `pinn-strategy` 操作者 CLI，覆盖 `audit`、`plan`、`smoke`、`full`、`status`、`replay` 和 RAG 索引操作；所有命令同时支持人类可读和 JSON 输出。
- 完成至少三个种子的现有传热案例复核，以及经典黏性 Burgers PINN 的多 seed 全流程案例，证明系统结论不是由单个 seed、单一传热模型或稳态线性 PDE 支撑；二维 Poisson 保留为非传热接口与语义隔离回归案例。
- 只有重复、有效且来源完整的模式才能生成 Wiki/Skill 候选；发布仍需显式人工批准。

## Capabilities

### New Capabilities

- `release-baseline-governance`: 定义源代码、证据、派生数据和凭据的版本控制边界，以及可恢复发布基线门禁。
- `production-execution-backends`: 定义本地和 AutoDL SSH 执行后端的 staging、launch、reconcile、cancel、collect 与幂等语义。
- `qwen3-retrieval-runtime`: 定义隔离 Qwen3 embedding/reranker 提供者、模型版本固定、候选池政策和 Qdrant 索引版本治理。
- `operator-cli`: 定义稳定 CLI 命令、显式输入、结构化输出、退出码和审批语义。
- `cross-domain-scientific-qualification`: 定义多 seed 传热复核、非传热真实案例和知识晋级所需证据。

### Modified Capabilities

- None. Phase 1 change 保持已完成状态；Phase 2 通过新的实现和适配器扩展，不篡改历史验收记录。

## Impact

- 目标仍仅为 `exp/hybrid-rag` 工作树；不创建新 worktree，不修改其他分支工作树。
- 复用 `pinn_strategy_orchestrator` 作为编排层环境，训练继续使用案例锁定环境；首批实现不新增 Python 包。
- Qwen3 模型运行时继续与编排层和训练环境物理隔离，固定已验收 revisions，不在仓库中保存模型权重。
- AutoDL 凭据只从操作者运行时注入；仓库、manifest、checkpoint、日志和 Wiki 中不得出现密码、私钥或可直接使用的连接字符串。
- 现有未提交成果在基线整理前不得被覆盖、删除或静默排除；修改现有文件前必须创建日期备份。
- standing full-run authorization 允许后续受控执行，但不取消物理、指标、完整性、幂等、产物、回滚和知识晋级门禁。
