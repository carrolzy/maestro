# ⚡ Maestro — 模型无关的 Agent 编排引擎

Maestro 是一个**Agent 编排产品**，任何 LLM 都可以接入 — Claude、Codex、Gemini、
DeepSeek，或任何支持 MCP 的客户端。它为每个接入的模型提供相同的可复用基础设施：
项目接入、记忆搜索、任务打包、工具执行，以及确定性的多步工作流编排。

从个人的 AI 效率系统起步，Maestro 已演进为完整的**本地 Agent OS** — 从命令行工具箱
到可视化控制台。不需要云服务，一切都在你的机器上运行。

> 🇺🇸 [English Documentation](README.md)

---

## 它做什么

| 能力 | 说明 |
|---|---|
| **项目接入** | 一条命令（或一个 Web 表单）注册任何项目。自动生成业务上下文、剧本和机器可读的商务名片。 |
| **记忆系统** | 分层记忆（项目卡片、案例、模式、规则），模型在工作前读取，工作后回写。 |
| **任务打包** | 从项目上下文 + 需求文本构建自包含的任务简报 — 可注入任何模型提示词。 |
| **MCP 工具层** | 10 个 MCP 工具，带有完整的 `inputSchema` / `outputSchema` 和一致性测试套件。任何 MCP 客户端都能获得可发现、已验证的契约。 |
| **Provider 适配器** | 同样的 10 个工具，以 OpenAI、DeepSeek、Anthropic、Gemini 原生 function-calling 格式暴露。纯翻译器，零业务逻辑。 |
| **工作流引擎** | 确定性 DAG 执行器 — 定义步骤和依赖关系，引擎自动并行执行，附带生命周期状态跟踪、验证门和重试机制。 |
| **可视化控制台** | 单页 Web UI — 浏览项目、调用工具、运行工作流、搜索记忆。全可点击，不需要记任何命令。 |

---

## 快速开始

### 前提条件

- **Python 3.10+**（代码使用了 `X | None` 语法）
- 一个终端

### 安装

```bash
git clone https://github.com/carrolzy/maestro.git
cd maestro
```

就这些。不需要 `pip install`，不需要 `npm install`。Maestro 是纯 Python 标准库 +
原生 HTML/CSS/JS。

### 接入第一个项目

**Web 控制台（推荐新手使用）：**

```bash
bin/dashboard.sh
# → 自动打开浏览器 http://localhost:8420
# → 点击「+ 新建」，填表单，点击「创建」
```

**交互式命令行：**

```bash
bin/onboard-project.sh
# → 回答三个问题（标识、描述、类型）
# → ✅ 所有检查通过
```

**脚本 / CI 模式：**

```bash
bin/onboard-project.sh \
  --project my-app \
  --summary "一个电商小程序" \
  --project-type uniapp-mini-program
```

### 构建任务包

```bash
bin/context-pack.sh --project my-app --requirement "增加购物车确认订单页面"
# 打印 package.md 到标准输出 — 注入到任何 LLM 的提示词中
```

### 运行工作流

```bash
# 通过控制台：工作流标签页 → 选择预设模板 → 点击运行
# 通过 API：
curl -X POST http://localhost:8420/api/workflows/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"my-app","steps":[
    {"id":"s1","tool":"search_memory","args":{"query":"购物车"}},
    {"id":"s2","tool":"validate_project","args":{"project":"my-app"}}
  ]}'
```

### 配合 Claude Code / Cursor 使用 (MCP)

在 MCP 客户端配置中添加：

```json
{
  "mcpServers": {
    "maestro": {
      "command": "python3",
      "args": ["tooling/ai_efficiency_mcp_server.py"],
      "env": {
        "PYTHONPATH": "<maestro目录>/tooling"
      }
    }
  }
}
```

### 配合 OpenAI / DeepSeek / Gemini 使用 (原生 API)

```bash
# 获取 provider 原生工具声明（复制到你的 API 调用中）
bin/provider-tools.sh --provider openai --list
bin/provider-tools.sh --provider gemini --list
bin/provider-tools.sh --provider anthropic --list
```

---

## 架构

Maestro 分五个阶段构建，每个阶段在前一阶段之上叠加，不破坏已有功能。

```
┌──────────────────────────────────────────────────┐
│  阶段 5 — 可视化控制台                             │
│  bin/dashboard.sh → api_server.py → dashboard.html │
├──────────────────────────────────────────────────┤
│  阶段 4 — 编排运行时                               │
│  workflow_engine.py (DAG + 并行 + 重试)            │
│  workflow_state.py (生命周期状态机)                 │
├──────────────────────────────────────────────────┤
│  阶段 3 — 可插拔业务接入                            │
│  playbook_schema.py • business_card.py            │
│  validate_project.py • onboard_project.py         │
├──────────────────────────────────────────────────┤
│  阶段 2 — 模型无关适配层                            │
│  adapters/ (OpenAI • DeepSeek • Anthropic • Gemini)│
│  tool_registry.py (规范工具注册表)                  │
├──────────────────────────────────────────────────┤
│  阶段 1 — MCP 工具层                               │
│  ai_efficiency_mcp_server.py (10 个工具, schema)   │
│  context_pack.py (原生 API 上下文注入)              │
├──────────────────────────────────────────────────┤
│  阶段 0 — 可复用资产库                              │
│  memory/ • projects/ • project-types/ • templates/│
│  skills/ • tooling/*.py                           │
└──────────────────────────────────────────────────┘
```

**设计原则：**
- **业务不进核心。** 只有通用引擎 + 每个项目自己的配置（`playbook.json`、`business-card.json`）。
- **先记忆，后工作。** 开始前读取先前的上下文；完成后回写。
- **先验证，后关闭。** 没有证据不关闭任务。
- **零运行时依赖。** 工具层只用 Python 标准库。控制台是原生 JS/CSS — 无构建步骤，无 npm。
- **模型无关。** 核心代码中没有 LLM 调用。每个表面（MCP、适配器、控制台 API）都通过相同的 `server.invoke()` 派发。

---

## 项目结构

```
maestro/
├── bin/                          # 一键启动脚本
│   ├── dashboard.sh              #   启动可视化控制台
│   ├── onboard-project.sh        #   交互式项目接入
│   ├── context-pack.sh           #   生成模型无关任务上下文
│   └── provider-tools.sh         #   Provider 原生工具声明
│
├── tooling/                      # 核心引擎（纯 Python，零依赖）
│   ├── ai_efficiency_mcp_server.py  # MCP JSON-RPC 服务器 (10 个工具)
│   ├── tool_registry.py          #   规范工具注册表（单一事实来源）
│   ├── adapters/                 #   各 provider 格式翻译器
│   │   ├── openai.py / anthropic.py / gemini.py / base.py
│   ├── workflow_engine.py        #   确定性 DAG 执行器
│   ├── workflow_state.py         #   生命周期状态机
│   ├── onboard_project.py        #   引导式项目接入 (CLI + API)
│   ├── validate_project.py       #   项目就绪校验器
│   ├── playbook_schema.py        #   playbook.json 模式 + 校验器
│   ├── business_card.py          #   business-card.json 模式 + 工具
│   ├── project_types.py          #   项目类型发现
│   ├── api_server.py             #   控制台 REST API (stdlib http.server)
│   ├── context_pack.py           #   模型无关上下文包生成器
│   ├── jsonschema_mini.py        #   零依赖 JSON Schema 校验器
│   ├── task_package_builder.py   #   从上下文构建任务包
│   ├── search_memory.py          #   搜索分层记忆
│   ├── register_project.py       #   注册新项目壳
│   ├── update_task_run_state.py  #   任务生命周期状态持久化
│   ├── writeback_and_sync_memory.py  # Obsidian 回写 + 记忆同步
│   ├── local_skills_doctor.py    #   技能安装诊断
│   ├── runtime_targets.py        #   Agent 运行时注册表
│   ├── ui/
│   │   └── dashboard.html        #   单页可视化控制台 (支持中英文切换)
│   └── tests/                    #   147 个测试 (unittest, 零依赖)
│
├── projects/                     # 各项目配置（业务数据 — 仅本地）
│   └── example-wxapp/            #   示例项目（演示用）
│       ├── business-context.md   #   人类可读的项目描述
│       ├── playbook.json         #   领域相关指导
│       └── ...
│
├── project-types/                # 可复用的项目类型模板
│   ├── uniapp-mini-program/      #   小程序 / uniapp
│   ├── admin-dashboard/          #   后台管理系统
│   ├── big-screen-dashboard/     #   大屏 / 可视化
│   ├── chrome-extension/         #   浏览器扩展
│   └── node-automation/          #   脚本 / 自动化
│
├── memory/                       # 分层持久化记忆
│   ├── patterns/                 #   可复用的解决方案模式
│   ├── rules/                    #   常驻规则
│   └── projects/                 #   每个项目的案例
│
├── templates/                    # 规范 Markdown 模板
├── skills/                       # Markdown 技能（按运行时安装）
├── docs/                         # 文档
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
│
├── README.md                     # 英文文档
└── README.zh-CN.md               # 你在这里
```

---

## 工具参考

10 个工具通过 MCP、Provider 适配器、控制台和 API 均可使用：

| 工具 | 说明 |
|---|---|
| `search_memory` | 搜索项目卡片、案例、模式、规则 |
| `build_task_package` | 从项目上下文 + 需求构建任务简报 |
| `register_project` | 从模板创建新项目壳 |
| `update_task_run_state` | 记录任务生命周期状态变更 |
| `writeback_and_sync_memory` | 将笔记写入知识库 + 同步到记忆 |
| `doctor_local_skills` | 诊断本地技能安装状态 |
| `validate_project` | 检查项目就绪状态（文件、剧本、名片、类型） |
| `list_project_types` | 列出可用项目类型模板及元数据 |
| `run_workflow` | 执行一个 DAG 工作流定义 |
| `get_workflow_status` | 按项目和 task_slug 查询工作流运行状态 |

---

## 工作流引擎

定义步骤和依赖 — 引擎处理剩下的：

```json
{
  "project": "my-app",
  "task_slug": "2026-06-04-cart-consistency",
  "steps": [
    { "id": "plan",    "tool": "build_task_package", "args": {...} },
    { "id": "impl-a",  "tool": "...", "args": {...}, "depends_on": ["plan"] },
    { "id": "impl-b",  "tool": "...", "args": {...}, "depends_on": ["plan"] },
    { "id": "verify",  "tool": "...", "args": {...}, "depends_on": ["impl-a", "impl-b"], "verify": {"condition": "no_error"} },
    { "id": "close",   "tool": "writeback_and_sync_memory", "args": {...}, "depends_on": ["verify"] }
  ]
}
```

- 没有相互依赖的步骤**并行执行**
- **`verify`** 验证门在失败时阻止后续步骤
- 任何步骤可配置 **`retry`**（`max_attempts`）
- 内置 **`fan_out`** 动词用于并行工具数组
- 完整生命周期状态机：`pending → in_progress → verifying → completed | failed → retry`

---

## 运行测试

```bash
PYTHONPATH=tooling python3.11 -m unittest discover -s tooling/tests -p 'test_*.py'
# 147 个测试通过
```

---

## 开发指南

- **分支模型：** `main` = 干净/可发布，`develop` = 工作中
- **提交风格：** Conventional Commits
- **防泄漏检查：** `bash bin/preflight-public.sh` — 阻止业务数据进入公开仓库
- **Python 版本：** 3.10+（PEP 604 `X | None` 语法）
- **依赖策略：** 工具层零运行时依赖。控制台是原生 HTML/CSS/JS。

---

## License

MIT — 详见 [LICENSE](LICENSE)。

---

🤖 使用 [Claude Code](https://claude.com/claude-code) 构建
