#!/usr/bin/env bash
# 从任意目录调用 mai_ui_agent CLI（自动使用 mai_ui_agent/.venv）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  echo "未找到 ${ROOT}/.venv，请先: cd ${ROOT} && bash scripts/setup_mlx_mac.sh" >&2
  exit 1
fi
cd "${ROOT}"
exec "${PY}" -m mai_ui_agent.cli "$@"
