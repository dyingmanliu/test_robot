#!/usr/bin/env bash
# 启动 MAI-UI mlx_vlm Grounding HTTP 服务（默认 8101，模型常驻内存）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
cd "$ROOT"
export MAI_UI_BACKEND=mlx_vlm
if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env"; set +a; fi
if [[ -f "$ROOT/../.env" ]]; then set -a; source "$ROOT/../.env"; set +a; fi
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "未找到 $PY，请先运行: bash scripts/setup_mlx_mac.sh" >&2
  exit 1
fi
HOST="${MAI_UI_GROUNDING_HOST:-127.0.0.1}"
PORT="${MAI_UI_GROUNDING_PORT:-8101}"
HEALTH_URL="http://${HOST}:${PORT}/health"
if curl -sf --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
  echo "[mai_ui] Grounding 服务已在运行: http://${HOST}:${PORT}/ground"
  echo "[mai_ui] 若要重启: lsof -ti :${PORT} | xargs kill -9 后再执行本脚本"
  exit 0
fi
if lsof -ti ":${PORT}" >/dev/null 2>&1; then
  echo "[mai_ui] 端口 ${PORT} 已被占用，但 ${HEALTH_URL} 无响应。" >&2
  echo "请检查占用进程: lsof -i :${PORT}" >&2
  echo "或换端口: MAI_UI_GROUNDING_PORT=8102 bash scripts/serve_grounding_mlx.sh" >&2
  exit 1
fi
exec "$PY" -m mai_ui_tech.grounding_server "$@"
