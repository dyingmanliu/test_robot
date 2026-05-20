#!/usr/bin/env bash
# 在 Mac 上拉取 MAI-UI-2B（Ollama 社区镜像），需已安装 Ollama >= 0.12.7
set -euo pipefail
echo "Pulling maternion/mai-ui:2b ..."
ollama pull maternion/mai-ui:2b
echo "Done. Serve with: ollama serve  (default http://127.0.0.1:11434/v1)"
