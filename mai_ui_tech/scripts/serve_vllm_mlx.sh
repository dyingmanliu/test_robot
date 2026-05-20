#!/usr/bin/env bash
# Apple Silicon：用 vllm-mlx 启动 MAI-UI-2B MLX 权重（OpenAI 兼容，端口 8100）
# 需: pip install vllm-mlx  且已下载 mlx-community/MAI-UI-2B-bf16-v2
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_LOCAL="${SCRIPT_DIR}/../models/MAI-UI-2B-bf16-v2"
if [[ -d "${DEFAULT_LOCAL}" ]]; then
  MODEL="${MAI_UI_MLX_MODEL:-${DEFAULT_LOCAL}}"
else
  MODEL="${MAI_UI_MLX_MODEL:-mlx-community/MAI-UI-2B-bf16-v2}"
fi
PORT="${MAI_UI_SERVE_PORT:-8100}"
HOST="${MAI_UI_SERVE_HOST:-127.0.0.1}"
SERVED_NAME="${MAI_UI_SERVED_MODEL_NAME:-MAI-UI-2B}"

ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY="python3"
fi

if [[ -d "${DEFAULT_LOCAL}" ]] && [[ ! -f "${DEFAULT_LOCAL}/model.safetensors" ]]; then
  echo "错误: 模型目录不完整，缺少 model.safetensors: ${DEFAULT_LOCAL}" >&2
  echo "请先: bash scripts/setup_mlx_mac.sh 或 python scripts/download_model_hf.py" >&2
  exit 1
fi

if command -v lsof >/dev/null 2>&1 && lsof -ti ":${PORT}" >/dev/null 2>&1; then
  echo "警告: 端口 ${PORT} 已被占用。若 --check 返回 502，请先结束旧进程：" >&2
  echo "  lsof -ti :${PORT} | xargs kill -9" >&2
  echo "" >&2
fi

if ! "${PY}" -c "import vllm_mlx" 2>/dev/null; then
  echo "未安装 vllm-mlx，正在安装..." >&2
  "${PY}" -m pip install vllm-mlx
fi

echo "Starting vllm-mlx on http://${HOST}:${PORT}/v1"
echo "（本窗口请保持运行；首次加载约 4GB 模型需 1–3 分钟，看到 Uvicorn running 后再另开终端 --check）"
echo "  model=${MODEL}"
echo "  served-model-name=${SERVED_NAME}"
exec "${PY}" -m vllm_mlx.cli serve "${MODEL}" \
  --mllm \
  --host "${HOST}" \
  --port "${PORT}" \
  --served-model-name "${SERVED_NAME}" \
  --trust-remote-code
