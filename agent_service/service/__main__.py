"""python -m agent_service.service  →  启动 agent_service Web 服务。"""

import uvicorn

from agent_service.service.config import SERVICE_HOST, SERVICE_PORT

if __name__ == "__main__":
    uvicorn.run(
        "agent_service.service.app:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        log_config=None,
        access_log=False,
    )
