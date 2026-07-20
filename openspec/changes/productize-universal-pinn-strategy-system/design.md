# RFC: 通用 PINN 策略系统 Phase 2 产品化

- **Status:** Approved for implementation
- **Date:** 2026-07-16
- **OpenSpec change:** `productize-universal-pinn-strategy-system`
- **Target:** `exp/hybrid-rag`
- **Environment:** existing `pinn_strategy_orchestrator`; case-locked training environments remain separate

## Context

Phase 1 已经证明核心判断链可以正确运行：实验前审计、用户指标契约、误差位置分析、单变量策略、smoke/full 门禁、持久化、幂等重放和结果回滚均有测试与一次全量案例证据。产品化缺口集中在四个边界：未冻结的 Git 基线、验证脚本而非生产后端、协议存在但 Qwen3 提供者缺失、以及仅一个真实传热 full case。

Phase 2 不重新设计通用核心，而是把已验证接口变成稳定操作面，并用跨域证据证实隔离边界。

## Goals / Non-Goals

**Goals:**

- 建立小而可恢复、可复核的版本控制基线。
- 提供本地 Windows 与 AutoDL SSH 两个生产执行后端。
- 接入正式 Qwen3 embedding/reranking 提供者，保持模型进程隔离。
- 提供适合人类和自动化使用的稳定 CLI。
- 用多 seed 和非传热真实案例完成科学资格验证。

**Non-Goals:**

- 不在本 change 中构建 Web UI、SaaS 多租户平台或通用深度学习自动调参平台。
- 不把用户凭据、模型权重、训练数据库或大数组提交到 Git。
- 不取消案例级指标确认，不把 `max_abs -> RMSE` 或 K 单位强制推广到所有 PDE。
- 不自动发布 Wiki、Skill 或模型。
- 不为旧接口编写双轨兼容层；切换必须通过一次明确、测试覆盖的接口迁移完成。

## Product Boundary

```text
Operator / CI
    |
    v
pinn-strategy CLI
    |
    v
LangGraph application service
    |-------------------------|
    v                         v
Assurance services       Retrieval gateway
    |                         |
    v                         v
Execution service        Isolated Qwen3 model process
    |                         |
    +--> Local backend        +--> versioned Qdrant index
    +--> AutoDL SSH backend
```

CLI 只负责解析输入、调用应用服务并呈现结果；它不得复制图转换或指标判定。Runner 不负责策略选择。Qwen3 进程不读取工作流数据库。Qdrant 仍是可重建派生索引。

## Decision 1: Freeze a selective Git baseline before feature edits

基线只提交实现源代码、测试、OpenSpec、报告、小型 JSON/CSV manifest 和 checksum 清单。模型权重、NumPy 数组、SQLite 运行库、完整日志、临时工作区、环境安装日志和可重建索引留在 artifact store，并由 manifest 引用。

基线过程 SHALL 先生成分类清单和 SHA-256 证据，再更新 ignore 规则，运行全部门禁，最后创建单一基线 commit；是否打 tag 由同一发布门禁决定。不得使用清理命令删除本地证据。

## Decision 2: Replace the launch-only backend with a lifecycle backend

生产接口使用显式、版本化对象：

```text
ExecutionBackend
  prepare(ExecutionRequest) -> PreparedRun
  launch(PreparedRun) -> BackendRunRef
  reconcile(BackendRunRef) -> BackendRunStatus
  cancel(BackendRunRef, CancellationApproval) -> BackendRunStatus
  collect(BackendRunRef, ArtifactCollectionSpec) -> ArtifactCollectionReport
```

`ManifestFirstRunner` 仍拥有幂等预留和审批校验，但不猜测进程状态。任何 launch 超时都进入 `LAUNCH_UNKNOWN`，必须先 `reconcile`，不得盲目重试。

### Local backend

- 使用显式 `cwd`、参数数组、环境白名单和绝对输出路径启动进程。
- 在 launch 前持久化 source/environment/command manifests。
- 状态由 PID、进程创建时间、status 文件、exit code、日志游标和必需产物共同判定，避免 PID 重用误判。
- 取消使用进程树边界并记录审批与终止结果。

### AutoDL SSH backend

- 使用 Windows 系统 `ssh.exe`/`scp.exe` 和已批准密钥；不引入 Python SSH 包。
- `prepare` 创建远端 run 目录、备份可能被覆盖的路径、上传内容寻址 staging 包并校验 SHA-256。
- `launch` 使用远端耐久 launcher 写入 PID、status、stdout、stderr 和 heartbeat；断开 SSH 不终止任务。
- `reconcile` 合并远端进程、PID 创建时间、status、heartbeat、日志和产物信息。
- `collect` 先生成远端 manifest，再传输归档并在本地逐文件校验；部分传输保留为非权威证据。
- 持久记录只能包含连接 profile ID、主机指纹和密钥指纹，不得包含凭据或直接连接字符串。

## Decision 3: Use an isolated retrieval-model gateway

编排进程只依赖协议和客户端：

```text
EmbeddingRequest -> EmbeddingResponse
RerankRequest -> RerankResponse
ModelHealthRequest -> ModelHealthResponse
```

传输层是显式注入的 `ModelTransport`，首批实现支持隔离 subprocess JSONL；远端模型执行通过同一请求/响应契约封装，不允许 provider 读取全局 SSH 配置或环境单例。

固定模型：

- `Qwen/Qwen3-Embedding-8B` revision `1d8ad4ca9b3dd8059ad90a75d4983776a23d44af`；
- `Qwen/Qwen3-Reranker-4B` revision `22e683669bc0f0bd69640a1354a6d0aebcfeede5`。

每个响应必须返回模型 ID、revision、运行环境摘要、输入摘要、维度或分数数量和请求 ID。模型按需顺序加载并释放，避免把两套大模型常驻为编排层隐式资源。

候选池政策保持已验收结果：普通单证据查询至少 6 个 rerank 候选；冲突或 all-evidence 查询至少 10 个。Reranker 只排序，不能删除 provenance 或冲突语义。

## Decision 4: Version the derived vector index

集合身份由 embedding revision、chunk schema version、metadata schema version 和 source manifest hash 共同决定。重建流程先构建新集合、执行计数/维度/provenance/查询 canary，再原子更新小型 active-index record。失败时旧集合保持可用，不原地删除事实或当前索引。

## Decision 5: Keep the CLI thin and deterministic

首批命令：

```text
pinn-strategy audit  --case <path>
pinn-strategy plan   --case <path>
pinn-strategy smoke  --workflow <id>
pinn-strategy full   --workflow <id>
pinn-strategy status --workflow <id>
pinn-strategy replay --workflow <id>
pinn-strategy rag rebuild --source <path>
pinn-strategy rag query --case <path> --query <text>
```

所有路径解析为绝对路径并写入请求契约；不能依赖当前工作目录。默认输出简洁文本，`--json` 输出版本化对象。退出码区分成功、需要用户确认、门禁拒绝、运行失败和内部错误。`full` 只能消费持久化 approval；standing authorization 可以由已有 approval record 满足，但 CLI 不自行生成批准。

## Decision 6: Use three active peer scientific validation cases and defer NS full qualification

用户在 2026-07-20 决定暂不继续顶盖驱动方腔 NS full qualification。当前发布资格验证由 Poisson、Burgers 和二维传热三个平级案例组成；此前将 Burgers 称为主要非传热科学门禁、将 Poisson 称为轻量回归证据的表述仍被取代。系统必须按案例矩阵报告证据覆盖，不能根据实施顺序、非线性程度或计算成本给案例分级。

三个当前案例覆盖互补而平级的验证维度：Poisson 覆盖稳态线性椭圆算子，Burgers 覆盖非线性时变高梯度解，二维传热覆盖真实物理量、量纲校对和复杂热边界。每个案例都拥有自己的 `PhysicalModelAuthority`、`UnitSystemContract`、`ReferenceEvidence`、用户确认指标契约和多 seed 证据；一个案例的单位、ROI 或 guardrail 不得隐式进入另一个案例。

Burgers 保持 `u_t + u*u_x - (0.01/pi)*u_xx = 0`、独立收敛参考和用户确认的 `relative_l2 -> max_abs` 指标。Poisson 必须从已有 worker/provider 基础补齐同等级的受治理多 seed 科学验证，而不再只作为语义隔离回归。

已实现的顶盖驱动方腔参考、worker 和 NS domain provider 保留为非活动原型。它们不得被默认导入通用核心，也不得计入当前发布完成度；未来恢复时必须重新取得架构确认，并独立完成指标确认、多 seed、局部误差、replay 和 provenance 全套门禁。

## Decision 7: Make the four operational layers one explicit closed loop

```text
MCP quick diagnosis
  -> manifest-driven Project Adapter
  -> LangGraph/CLI audit, approval and execution
  -> deterministic Post-run Evaluator
  -> immutable evidence candidate
```

项目适配器只扫描显式 project root 和 include paths，计算 source snapshot，并从已声明的物理、单位、指标、实验和运行信息生成 `OperatorCase`。缺失或歧义字段成为结构化 unresolved records；适配器不得从变量名、目录名或单一案例模板静默推断 PDE、单位换算、参考真值或指标优先级。

MCP 快速诊断通过独立 stdio 子进程和只读工具注解调用现有 `pinn-hybrid-rag`。它返回初步检查与来源锚点，但不拥有治理契约、审批状态或执行副作用。

运行后评估从显式字段 artifact contract 加载 baseline、candidate 和 reference，先执行对齐和 `max_abs` 位置分析，再按用户确认的 `MetricContract` 做确定性比较。报告与决策作为不可覆盖 JSON artifact 固化；只有验证通过且满足重复证据要求的结果才能成为 Wiki/Skill 候选，仍不得自动发布。

## Failure and Recovery Semantics

- 已持久化 manifest 但 launch 不确定：进入 reconcile，不重复 launch。
- 远端断线：保留 `RUNNING_UNKNOWN`，从 status/heartbeat/进程/产物对账。
- 模型服务失败：检索响应标为模型 provider 不可用；确定性检索仍可返回证据，但系统不得声称完成了 Qwen3 门禁。
- 索引构建失败：active index 不变，新集合标记失败并保留诊断。
- 结果缺失或坐标不对齐：`RESULT_INVALID`，不得生成有效 Wiki/Skill 候选。
- CLI 中断：工作流状态留在持久化层，重启后由 `status`/`replay` 恢复。

## Security and Data Safety

- 任何已有文件修改前创建 `original_filename_backup_2026-07-16` 形式备份。
- 日志和错误对象在落盘前执行 credential redaction。
- 命令使用参数数组和受控模板，不拼接用户文本为 shell 代码。
- 远端路径必须位于显式 run root；取消和回收不能越过该根目录。
- 不执行自动删除；索引切换和 artifact 回收保留旧证据。

## Release Gates

1. Git 基线分类、备份、完整回归和 SHA-256 manifest 通过。
2. 本地 backend 的 launch/reconcile/cancel/collect 与失败注入通过。
3. AutoDL backend 的只读 preflight、耐久 launch、断线对账和传输校验通过。
4. Qwen3 provider 在固定 revisions 下重现质量门禁，索引 rebuild/switch/rollback 通过。
5. CLI 的文本/JSON/退出码/无隐式 cwd/审批门禁通过。
6. Poisson、Burgers 和二维传热完成各自受治理的多 seed 科学验证，按平级案例矩阵报告且结论不越界；NS full qualification 明确为延期项。
7. MCP 诊断、项目适配、编排执行、运行后评估和不可覆盖证据固化的端到端契约测试通过。
8. 编排、MCP、OpenSpec、架构隔离和 credential scan 全部通过。

## Open Questions

- Phase 2 完成后是否增加 Web UI；这不阻断当前 CLI 产品化。
- 何时恢复顶盖驱动方腔 full qualification，以及届时是否增加 Taylor-Green vortex；两者均不阻断当前三个平级案例的发布资格验证。
- 是否将 artifact store 从文件系统升级为对象存储；当前仍保持显式接口，不在本 change 引入新服务。
