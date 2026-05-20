# agent_service/func_agent

功能测试机器人统一业务域。`agent_service/func_agent` 对外提供稳定的调度入口，内部编排两条技术后端：

- AutoGLM（Python in-process）
- Midscene（Node subprocess, `--web-dispatch`）

## 目标

- 让 Web 后端只依赖一个业务域入口，而不是直接耦合具体技术实现
- 保持 `test_agent_backend=autoglm|midscene` 的运行选择能力
- 为后续新增执行技术路线预留统一扩展点

## 关键入口

- `agent_service/func_agent/orchestrator.py`：统一调度入口（executor 调用）
- `agent_service/func_agent/core.py`：统一 dispatch 模型
- `agent_service/func_agent/backends/autoglm/agent.py`：AutoGLM 执行核心
- `agent_service/func_agent/backends/midscene/runtime.py`：Midscene 运行时桥接
- `agent_service/func_agent/cli.py`：统一 CLI

## 入口约束

- 仓库内部执行入口仅允许 `agent_service/func_agent` 路径
- AutoGLM 入口：`agent_service.func_agent.backends.autoglm.agent`
- Midscene 入口：`agent_service.func_agent.backends.midscene.runtime`

新代码必须引用 `agent_service/func_agent` 路径。
