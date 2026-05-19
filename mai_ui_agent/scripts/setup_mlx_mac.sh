#!/usr/bin/env bash
# Mac Apple Silicon：安装 mlx-vlm 并下载 MAI-UI-2B MLX 权重
# 国内务必：export HF_ENDPOINT=https://hf-mirror.com
set -euo pipefail
cd "$(dirname "$0")/.."

# 优先使用 Homebrew Python 3.11+（系统自带的 3.9 只能装 mlx-vlm 0.1.x，且易下载失败）
PY="${MAI_UI_PYTHON:-}"
if [[ -z "${PY}" ]]; then
  for candidate in python3.13 python3.12 python3.11 python3.10; do
    if command -v "${candidate}" >/dev/null 2>&1 \
      && "${candidate}" -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="${candidate}"
      break
    fi
  done
fi
PY="${PY:-python3}"

ver="$("${PY}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! "${PY}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "错误：当前 ${PY} 为 Python ${ver}，mlx-vlm>=0.3 需要 Python >= 3.10。" >&2
  echo "请安装后重试，例如：brew install python@3.11" >&2
  echo "然后：rm -rf .venv && MAI_UI_PYTHON=python3.13 bash scripts/setup_mlx_mac.sh" >&2
  echo "（你已有 miniconda 时可直接: MAI_UI_PYTHON=python3.13 bash scripts/setup_mlx_mac.sh）" >&2
  exit 1
fi
echo "Using Python: ${PY} (${ver})"

if [[ -d .venv ]]; then
  venv_ver="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo 0)"
  if [[ "${venv_ver}" != "${ver}" ]]; then
    echo "检测到 .venv 为 Python ${venv_ver}，与 ${ver} 不一致，正在重建 .venv ..."
    rm -rf .venv
  fi
fi
if [[ ! -d .venv ]]; then
  "${PY}" -m venv .venv
fi
# 始终用项目 .venv，避免 conda base 把包装到 /opt/miniconda3
VENV_PY="$(pwd)/.venv/bin/python"
export VIRTUAL_ENV="$(pwd)/.venv"
export PATH="$(pwd)/.venv/bin:${PATH}"

# 国内默认走镜像（已设置 HF_ENDPOINT 时不覆盖）
if [[ -z "${HF_ENDPOINT:-}" ]]; then
  export HF_ENDPOINT="${MAI_UI_HF_ENDPOINT:-https://hf-mirror.com}"
  echo "HF_ENDPOINT=${HF_ENDPOINT} （海外用户可 export HF_ENDPOINT= 清空后重试）"
fi

"${VENV_PY}" -m pip install -U pip
"${VENV_PY}" -m pip install -e .
"${VENV_PY}" -m pip install -r requirements-mlx.txt

echo ""
echo "Downloading model weights (~4GB) ..."
"${VENV_PY}" scripts/download_model_hf.py

echo ""
echo "Done. Optional OpenAI-compatible server:"
echo "  pip install vllm-mlx"
echo "  bash scripts/serve_vllm_mlx.sh"
echo ""
echo "Or test with mlx-vlm CLI (no HTTP server):"
echo "  python -m mlx_vlm.generate --model models/MAI-UI-2B-bf16-v2 --image screen.png --prompt '描述界面' --max-tokens 256"
echo ""
echo "For mai_ui_agent grounding API, set in repo root .env:"
echo "  MAI_UI_BASE_URL=http://127.0.0.1:8100/v1   # after vllm-mlx serve"
echo "  MAI_UI_MODEL=$(pwd)/models/MAI-UI-2B-bf16-v2"
