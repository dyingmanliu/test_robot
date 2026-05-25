"""agent_service Web 服务配置。"""

import os

SERVICE_HOST = os.getenv("AGENT_SERVICE_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("AGENT_SERVICE_PORT", "8100"))

# 任务记录 TTL（秒），超过此时间的任务记录将被清理
TASK_TTL_SECONDS = 3600

# 清理任务执行间隔（秒）
CLEANUP_INTERVAL_SECONDS = 300

# 最大并发长任务数
MAX_CONCURRENT_TASKS = 10
