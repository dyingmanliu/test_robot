# mai_ui_tech

基于阿里 **[MAI-UI-2B](https://huggingface.co/Tongyi-MAI/MAI-UI-2B)** 的本地 **GUI Grounding** 子项目：输入 APP 截图 + 自然语言描述，输出 UI 元素坐标。与 `autoglm_phone_tech`、`midscene_tech` 并列，**不修改**其他子项目代码。

## 硬件与模型选型（MacBook Air M5 · 16GB）

| 模型 | 是否推荐 | 说明 |
|------|----------|------|
| **MAI-UI-2B** | ✅ 推荐 | MLX bf16 约 4GB 权重，推理峰值约 5–6GB 内存，16GB 统一内存可稳定运行 |
| MAI-UI-8B | ❌ 不推荐 | 16GB 机器易 OOM 或严重换页，仅适合 32GB+ 或独立 GPU 服务器 |

本仓库默认配置为 **2B**；推理实现通过 **OpenAI 兼容 HTTP API** 调用本地服务，与官方 `MAIGroundingAgent` 协议一致。

## 能力说明

- **支持**：给定描述定位单个控件（如「登录按钮」「搜索框」），坐标尺度 0–999，并转换为像素 / 0–1000。
- **不支持**：一次性列出截图中全部 UI 元素（官方说明需 OmniParser 等二阶段方案）。

## 目录结构

```
mai_ui_tech/
├── README.md
├── requirements.txt
├── .env.example
├── mai_ui_tech/
│   ├── config.py
│   ├── grounding.py      # MaiUiGroundingAgent
│   ├── cli.py
│   └── health.py
└── scripts/
    ├── pull_ollama_model.sh
    └── serve_vllm_mlx.sh
```

## 部署方式（Mac Apple Silicon）

### 方式 A：Ollama（简单，需能访问 registry.ollama.ai）

1. 安装 [Ollama](https://ollama.com/)（≥ 0.12.7）。
2. 拉取 2B 模型：

```bash
bash scripts/pull_ollama_model.sh
# 或: ollama pull maternion/mai-ui:2b
```

3. 确保 Ollama 在运行（菜单栏或 `ollama serve`），默认 API：`http://127.0.0.1:11434/v1`。

#### Ollama 拉取失败：`lookup registry.ollama.ai: i/o timeout`

说明本机 **无法解析或连接 Ollama 官方仓库**（常见于国内网络、公司防火墙、未配置代理），与项目脚本无关。

可尝试：

1. **换网络 / 代理**（系统 VPN 或终端代理）后重试：
   ```bash
   export HTTPS_PROXY=http://127.0.0.1:7890   # 按你的代理端口修改
   ollama pull maternion/mai-ui:2b
   ```
2. **检查 DNS**：`ping registry.ollama.ai` 或 `nslookup registry.ollama.ai` 是否超时。
3. **改用方式 B（推荐国内 Mac）**：不依赖 Ollama，用 Hugging Face MLX 权重 + `vllm-mlx`（见下）。

### 方式 B：vllm-mlx + MLX 权重（Apple Silicon 原生，国内更易成功）

适合希望使用 [mlx-community/MAI-UI-2B-bf16-v2](https://huggingface.co/mlx-community/MAI-UI-2B-bf16-v2) 的场景；**无法拉 Ollama 时优先用此方式**。

**环境要求：Python ≥ 3.10（推荐 3.11）**。macOS 自带 `python3` 多为 **3.9**，会导致只装上 `mlx-vlm 0.1.x` 且 Hugging Face 下载失败。

```bash
cd mai_ui_tech
rm -rf .venv   # 若之前用 3.9 建过 venv，必须先删

# 任选其一（Python >= 3.10 即可；你本机 miniconda 的 python3.13 可用）
MAI_UI_PYTHON=python3.13 bash scripts/setup_mlx_mac.sh
# 或: brew install python@3.11 && MAI_UI_PYTHON=python3.11 bash scripts/setup_mlx_mac.sh

source .venv/bin/activate   # 务必用项目 .venv，不要只用 conda base
pip install vllm-mlx
bash scripts/serve_grounding_mlx.sh   # 推荐：Grounding HTTP 服务 http://127.0.0.1:8101
# 可选：bash scripts/serve_vllm_mlx.sh   # OpenAI 兼容 :8100（当前 chat/completions 易 500，勿用于识图）
```

脚本会自动设置 `HF_ENDPOINT=https://hf-mirror.com`（国内）。海外用户可先 `export HF_ENDPOINT=` 再运行。

**识图 / Grounding** 请用 `serve_grounding_mlx.sh`（`mlx_vlm` 直连本地权重）。CLI 与 Web 默认识图后端为 `mlx_vlm`（检测到 `models/MAI-UI-2B-bf16-v2/` 时自动启用）。

#### Metal 崩溃 / Web 502（`GPU Address Fault`）

长截图 prefill 过大时，Mac 16GB 可能触发 Metal 进程 **abort**，Web 显示 `Grounding 服务 HTTP 502`。处理：

1. 在 `.env` 设置 `MAI_UI_MAX_IMAGE_LONG_EDGE=1280`（仍失败可改为 `960`）。
2. `MAI_UI_MAX_TOKENS=512`（Grounding 输出很短，不必 2048）。
3. 关闭其它占内存应用，**重启** `bash scripts/serve_grounding_mlx.sh`。

#### Hugging Face 下载失败

若出现 `FileMetadataError` / `LocalEntryNotFoundError` / `does not seem to be on huggingface.co`：

1. 确认 **Python ≥ 3.10** 且已 `rm -rf .venv` 后重建。
2. 用项目 venv 显式指定镜像（`endpoint` 会传给 huggingface_hub）：
   ```bash
   source .venv/bin/activate
   python scripts/download_model_hf.py --endpoint https://hf-mirror.com
   ```
3. 镜像仍失败时，开 VPN 走官方：
   ```bash
   python scripts/download_model_hf.py --endpoint https://huggingface.co
   ```
4. 仍失败：浏览器打开 [hf-mirror 模型页](https://hf-mirror.com/mlx-community/MAI-UI-2B-bf16-v2) 下载到 `mai_ui_tech/models/MAI-UI-2B-bf16-v2/`，在 `.env` 设 `MAI_UI_MODEL` 为该目录绝对路径。
5. 终端代理：`export HTTPS_PROXY=http://127.0.0.1:7890`（端口按本机修改）。

#### `python3.11: command not found`

不必装 Homebrew Python，你已有 **miniconda `python3.13`** 即可：

```bash
MAI_UI_PYTHON=python3.13 bash scripts/setup_mlx_mac.sh
```

**`--check` 返回 HTTP 502**：8100 上有进程但推理未就绪。常见原因：

1. **未成功启动 vllm-mlx**（例如旧脚本 `--localhost` 报错后立即退出，端口被其它程序占用）。
2. **模型仍在加载**，需等终端出现 `Uvicorn running` 再测。
3. **旧进程僵死**：`lsof -ti :8100 | xargs kill -9` 后重新 `bash scripts/serve_vllm_mlx.sh`。

正确顺序：**终端 A** 启动服务并等待就绪 → **终端 B** `python -m mai_ui_tech.cli --check`。

服务默认 `http://127.0.0.1:8100/v1`，请在 `.env` 中改为：

```env
MAI_UI_BASE_URL=http://127.0.0.1:8100/v1
MAI_UI_MODEL=mlx-community/MAI-UI-2B-bf16-v2
```

> **注意**：勿与 Web 后端 Uvicorn（8000）端口混淆；MAI-UI 推理单独占 **8100** 或 **11434**。

### 方式 C：Linux + NVIDIA + vLLM

若在 Linux GPU 服务器部署官方权重，见 [MAI-UI README](https://github.com/Tongyi-MAI/MAI-UI)（`vllm==0.11.0`）。Mac 上一般不装 CUDA 版 vLLM。

## 安装与配置

```bash
cd mai_ui_tech
source .venv/bin/activate
pip install -e .    # 注册 mai_ui_tech 包（仅需一次）
```

在**仓库根目录**时不要 `source .venv`（根目录没有该 venv），请用：

```bash
# 方式 1：进入子项目
cd mai_ui_tech && source .venv/bin/activate
python -m mai_ui_tech.cli --check

# 方式 2：任意目录
bash mai_ui_tech/scripts/run_cli.sh --check
```

环境变量（可复制 [`.env.example`](./.env.example) 到仓库根目录 `.env`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `MAI_UI_BASE_URL` | `http://127.0.0.1:11434/v1` | OpenAI 兼容地址 |
| `MAI_UI_API_KEY` | `ollama` | Ollama 可任意非空 |
| `MAI_UI_MODEL` | `maternion/mai-ui:2b` | 与推理端 `served-model-name` 一致 |

## 使用

### 检查推理服务

```bash
python -m mai_ui_tech.cli --check
```

### 单张截图 Grounding

```bash
python -m mai_ui_tech.cli \
  --image /path/to/screenshot.png \
  --query "登录按钮"

# 批量
python -m mai_ui_tech.cli -i screen.png \
  --queries "搜索框" "购物车" --json
```

### Python API

```python
from mai_ui_tech import MaiUiGroundingAgent, load_config

agent = MaiUiGroundingAgent(load_config())
result = agent.ground("设置图标", "screen.png")
print(result.coordinate_px, result.ok)
```

## Web 平台集成

登录后顶部菜单 **「MAI-UI 识图」**（`/mai-ui`）可：

- 查看本地推理服务状态（`GET /api/mai-ui/status`）
- 上传截图自动识别当前页全部菜单（顶栏/底栏/侧栏等，`POST /api/mai-ui/detect-menus`，表格展示）
- （可选）按描述单点 Grounding（`POST /api/mai-ui/ground`）

后端封装见 `web/backend/app/services/mai_ui_service.py`。

1. **终端 A**（`mai_ui_tech` 目录）：`bash scripts/serve_grounding_mlx.sh`，等待出现 `Grounding 服务: http://127.0.0.1:8101`。
2. 仓库根 `.env` 建议：

```env
MAI_UI_BACKEND=mlx_vlm
MAI_UI_GROUNDING_URL=http://127.0.0.1:8101
```

Web 后端为 Python 3.9 时会通过 HTTP 调用上述服务；勿依赖 vllm-mlx 的 `/v1/chat/completions`（当前对 MAI-UI 多模态请求常返回 500）。

## 参考

- [Tongyi-MAI/MAI-UI](https://github.com/Tongyi-MAI/MAI-UI)
- [MAI-UI-2B on Hugging Face](https://huggingface.co/Tongyi-MAI/MAI-UI-2B)
- [mlx-community/MAI-UI-2B-bf16-v2](https://huggingface.co/mlx-community/MAI-UI-2B-bf16-v2)
