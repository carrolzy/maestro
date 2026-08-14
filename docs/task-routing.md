# Maestro 自适应任务路由

Maestro 在执行其他生命周期流程前，先根据“工程量 + 风险”选择最低安全治理等级。目标是让局部、低风险的小改动快速完成，同时让公共边界、交易、安全和外部副作用保持强拦截。

## 等级与流程

| 等级 | 典型任务 | 必需流程 | 默认跳过 |
|---|---|---|---|
| L0 快速通道 | 单页文案、局部样式、局部资源替换、机制明确的隔离修复 | 只读预检、当前分支修改、针对性验证 | 分支、任务包、Change Spec、Spec Gate、写回 |
| L1 标准通道 | 范围明确但超过快速通道，或项目尚未配置完整路由 | 必要上下文、分支、实现、验证、文档影响检查 | 任务包、Change Spec、Spec Gate、写回 |
| L2 治理通道 | 登录、交易、共享状态、公共组件、请求/接口、构建或依赖配置 | 分支、任务包、记忆、Change Spec、审批、Spec Gate、完整验证、文档影响检查、写回 | 无 |
| L3 严格治理 | 权限、隐私、生产操作、破坏性数据操作、部署或远程推送 | L2 全流程，并在高风险副作用前额外人工确认 | 无 |

等级表示最低治理下限。用户可以要求更高等级，但不能绕过项目风险下限或硬安全边界。

## 风险否决与快速通道条件

风险信号对工程量拥有否决权。任务即使只改一行，只要涉及鉴权、交易、共享状态、公共请求、全局配置、依赖、安全、生产或外部写操作，就不能因为“改动小”自动进入 L0。

自动 L0 必须同时满足：

- 项目已配置 `routing`；
- 候选文件为 1～2 个，并命中项目或项目类型的 `fast_path_signals`；
- 没有不确定项、外部操作和硬风险；
- 候选文件没有与用户未提交修改重叠；
- 不涉及 Maestro 识别出的全局或公共文件。

置信度不是装饰字段：`confidence != high` 时不得自动进入快速通道。

## 调用 `route_task`

在修改前做低成本只读预检，然后通过 MCP 调用：

```json
{
  "project": "example-wxapp",
  "requirement": "调整商品详情页标题间距",
  "repo_root": "/path/to/example-wxapp",
  "candidate_files": ["pages2/goods-detail/index.vue"],
  "observed_signals": ["local_scoped_style"],
  "uncertainties": [],
  "requested_actions": []
}
```

返回值包括：

- `tier`、`confidence`；
- `risk_hits`、`hard_vetoes` 和 `reasons`；
- `required_steps`、`skipped_steps`；
- `requires_user_confirmation` 与重新路由触发条件。

路由日志写入 `runtime/routing-decisions.jsonl`，只记录等级、风险标签、耗时和升级状态，不保存 Prompt、代码或候选文件内容。日志写入失败只产生警告，不改变路由结果。

## 项目配置

策略按以下顺序合并，后续层只能提高最低等级：

1. 全局策略：`base/task-routing-policy.json`；
2. 项目类型：`project-types/<type>/routing.json`；
3. 项目配置：`projects/<project>/playbook.json` 的 `routing`；
4. 运行时事实：Git 重叠修改、候选范围、不确定项和请求的外部操作。

项目 `routing` 示例：

```json
{
  "routing": {
    "fast_path_signals": ["local_scoped_style", "local_copy_change"],
    "risk_rules": [
      {
        "signals": ["payment"],
        "min_tier": "L2",
        "reason": "交易链路需要完整验证",
        "hard_veto_l0": true
      }
    ],
    "risky_paths": [
      {
        "patterns": ["store/**"],
        "min_tier": "L2",
        "reason": "共享状态影响多个页面"
      }
    ]
  }
}
```

未配置项目默认至少为 L1，避免陌生项目被误判为快速任务。

## 分支与项目规则

- L0 默认在当前分支完成；用户明确要求创建分支，或结果为 L1/L2/L3 时，进入项目自己的分支工作流。
- 只读 Git 状态和差异检查可在分支名确认前执行；会改变仓库或远程状态的命令必须遵守项目规则。
- 目标文件存在重叠未提交修改时暂停。无关的用户修改保持原样，不得自行 stash、commit、reset，也不得混入本次提交。
- 项目 `AGENTS.md` 中技术评审、分支、字体等高优先级规则先执行。

## 重新路由：只升不降

实现中出现以下任一情况，必须携带当前 `current_tier` 再次调用 `route_task`：

- 候选文件或模块范围扩大；
- 发现公共组件、共享状态或全局配置边界；
- 接口契约或业务规则发生变化；
- 验证失败且原因尚不明确。

策略执行“只升不降”：重新路由结果不能低于 `current_tier`。若新结果升到 L2/L3，应先补齐相应治理步骤，再继续编辑业务代码。

## 关闭与文档影响

调用 `update_task_run_state` 写入 `closed` 时，必须提供：

```json
{
  "governance_tier": "L1",
  "documentation_impact": {
    "status": "updated",
    "files": ["README.zh-CN.md", "docs/task-routing.md"],
    "reason": "记录用户可见的任务路由和关闭门禁。"
  }
}
```

若无需更新文档，使用 `"status": "not_needed"` 并给出非空 `reason`。L0 可以跳过文档，但同样必须明确说明“不需要”的原因；L1～L3 应优先更新 README 或使用文档。缺少等级或文档影响时，关闭操作会失败。

## 故障排查

- 意外进入 L1：检查项目是否存在有效 `playbook.json` 与 `routing`，以及信号是否属于 `fast_path_signals`。
- 意外进入 L2/L3：查看 `risk_hits`、`hard_vetoes` 和命中的 `risky_paths`，不要手工删除真实风险信号。
- 无法进入 L0：检查候选文件数量、Git 重叠修改、全局/公共文件和不确定项。
- 日志警告：检查 `runtime/` 写权限；路由结论仍然有效。
