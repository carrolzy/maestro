---
name: task-routing
description: Use when a coding, debugging, refactoring, styling, documentation, configuration, deployment, or repository task for a registered project is about to begin and its Maestro L0-L3 governance level has not yet been selected, especially when small work may avoid full lifecycle overhead or safety signals may require escalation.
---

# Task Routing

## Overview

在其他 Maestro 生命周期 Skill 之前选择最低安全治理等级。工程量决定流程成本，风险信号拥有否决权；路由只能维持或提高等级。

Skill 只负责编排。等级判断、策略合并和日志写入由 MCP `route_task` / `tooling/task_router.py` 负责。

## 必需输入

- `project`、`requirement`、业务仓库 `repo_root`
- 只读预检得到的 `candidate_files`、`observed_signals`、`uncertainties`、`requested_actions`
- 重新路由时传入 `current_tier`

## 执行流程

1. 从用户 Prompt 提炼真实目标与明确非目标，不把“尽快”“简单改一下”当作低风险证据。
2. 只读预检：检查 Git 状态，定位 1～2 个候选文件，识别公共文件、共享状态、请求/接口、交易、安全、配置、依赖和外部操作；不要先改代码。
3. 调用一次 `route_task`。不得手工覆盖硬风险、删除不确定项或伪造高置信度。
4. 用一行说明 `等级 + 核心理由`，然后按返回的 `required_steps` / `skipped_steps` 执行：
   - L0：直接修改并做针对性验证；不创建分支、任务包、Change Spec 或写回。
   - L1：读取必要上下文，创建分支，实现并验证；不强制任务包和 Change Spec。
   - L2：执行分支、任务包、Change Spec、明确审批、Spec Gate、完整验证、文档影响检查和写回。
   - L3：执行 L2 全流程，并在生产、安全、权限、数据破坏或外部副作用前获得额外人工确认。
5. 实现中若文件/模块扩张、进入公共边界、业务规则或接口变化、验证原因不明地失败，立即使用 `current_tier` 重新调用 `route_task`。结果不得低于当前等级。

## 安全拦截

- `confidence != high`、存在 `hard_vetoes`、关键 `uncertainties` 或目标文件重叠改动时，不得自动进入 L0。
- 目标文件有未提交重叠修改时暂停；不得自行 stash、commit、reset 或覆盖。
- 用户可要求更高等级。用户要求降低等级时，项目风险下限和硬安全边界仍然有效。
- 项目 `AGENTS.md` 中更高优先级的评审文档、分支、字体或业务规则先执行；路由只调整不冲突的 Maestro 流程成本。

## 输出约定

L0 只报告一行等级说明和最终验证结果。L1～L3 报告等级、风险命中、需要确认的事项和下一治理步骤；不要展开完整 Prompt 或代码到路由日志。

## 后端

- MCP：`route_task`
- 策略：`base/task-routing-policy.json`
- 实现：`tooling/task_router.py`
- 配置：`project-types/<type>/routing.json`、`projects/<project>/playbook.json`
