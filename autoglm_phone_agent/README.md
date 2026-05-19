# autoglm_phone_agent

基于智谱 **AutoGLM-Phone** 的移动端 UI 自动化 Python 包，设备层设计参考 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) 的 `device_factory`（`adb` / `hdc`）。

## 支持的平台

| 平台 | 连接工具 | 实现模块 | 文本输入 |
|------|----------|----------|----------|
| Android | ADB | `device/adb_bridge.py` | ADB Keyboard（需设备安装） |
| 鸿蒙 HarmonyOS | HDC | `device/hdc_bridge.py` | 原生 `uitest uiInput text`（无需 ADB Keyboard） |

## 目录结构

```
autoglm_phone_agent/
├── agent.py                 # PhoneTestAgent 观察→推理→执行循环
├── actions/handler.py       # 解析 do()/finish() 并调用设备层
├── config/
│   ├── apps.py              # Android 应用包名
│   ├── apps_harmonyos.py    # 鸿蒙 bundle / ability（摘自 Open-AutoGLM）
│   └── prompts_zh.py
├── device/
│   ├── platform.py          # DevicePlatform 枚举
│   ├── device_factory.py    # create_device() 工厂
│   ├── adb_bridge.py
│   ├── hdc_bridge.py
│   ├── adb_resolve.py
│   └── hdc_resolve.py
└── model/client.py          # OpenAI 兼容 API 客户端
```

## 环境变量

与仓库根目录 `.env` 共用（见 [`.env.example`](../.env.example)）：

| 变量 | 用途 |
|------|------|
| `BIGMODEL_API_KEY` / `ZHIPU_API_KEY` | 智谱 API（必填） |
| `OPENAI_BASE_URL` | 默认智谱 Paas |
| `PHONE_AGENT_MODEL` | 如 `autoglm-phone` |
| `PHONE_AGENT_MAX_STEPS` | 单任务最大步数 |
| `ADB_DEVICE_ID` | Android 多设备 serial |
| `HDC_DEVICE_ID` / `HDC_HOME` | 鸿蒙设备 / hdc 路径 |
| `PHONE_AGENT_DEVICE_TYPE` | CLI 默认：`adb` 或 `hdc` |

## CLI 使用

仓库根目录 [`main.py`](../main.py)：

```bash
pip install -r requirements.txt

# Android（默认）
python main.py "打开美团搜索附近的火锅店"
python main.py --device-type adb --device-id emulator-5554 "任务"

# 鸿蒙
python main.py --device-type hdc "打开设置并进入关于本机"
hdc list targets   # 执行前确认设备在线
```

## 在代码中使用

```python
from autoglm_phone_agent import PhoneTestAgent, AgentConfig
from autoglm_phone_agent.model.client import ModelConfig

model = ModelConfig(api_key="...", base_url="https://open.bigmodel.cn/api/paas/v4")
cfg = AgentConfig(device_platform="harmonyos", device_id="YOUR_HDC_TARGET")
agent = PhoneTestAgent(model_config=model, agent_config=cfg)
result = agent.run("在设置中打开 WLAN")
print(result.ok, result.message)
```

## 与 Web 平台的关系

Web 后端 `executor.run_phone_agent_task()` 在机器人实例为 **`test_agent_backend=autoglm`** 时调用本包（**Android 与鸿蒙均同进程**），根据 `device_platform` 选择 ADB 或 HDC。Midscene 引擎走 `midscene_agent` 子项目，见 [执行矩阵](../README.md#1c-执行引擎--设备平台web-机器人实例)。

## 参考

- [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) — 上游 Phone Agent 与 HDC 实现参考
- [ARCHITECTURE.md](../ARCHITECTURE.md) — 全仓架构与执行链路
