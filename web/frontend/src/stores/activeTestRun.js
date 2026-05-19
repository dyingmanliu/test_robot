/**
 * 跨页面保持测试执行会话：离开用例页后仍轮询，返回时恢复实时进度。
 */
import { defineStore } from "pinia";
import axios from "axios";
import client from "@/api/client";

const STORAGE_KEY = "tcm_active_run_id";
const STORAGE_PROJECT_KEY = "tcm_active_run_project";

function isTransientPollError(e) {
  if (!axios.isAxiosError(e)) return false;
  if (!e.response) return true;
  const s = e.response.status;
  return s >= 500 || s === 408 || s === 429;
}

function isTerminalStatus(status) {
  return status === "success" || status === "failed" || status === "cancelled";
}

export const useActiveTestRunStore = defineStore("activeTestRun", {
  state: () => ({
    runId: null,
    projectId: null,
    liveRun: null,
    polling: false,
    pollError: null,
    _pollGeneration: 0,
  }),

  getters: {
    isActive(state) {
      const st = state.liveRun?.status;
      return st === "pending" || st === "running";
    },
    /** 执行是否属于指定项目空间（projectId 未知时返回 false） */
    belongsToProject: (state) => (projectId) => {
      if (projectId == null || projectId === "") return false;
      const want = Number(projectId);
      if (!Number.isFinite(want)) return false;
      const pid =
        state.liveRun?.project_id != null
          ? Number(state.liveRun.project_id)
          : state.projectId != null
            ? Number(state.projectId)
            : NaN;
      return Number.isFinite(pid) && pid === want;
    },
  },

  actions: {
    _persist() {
      if (this.runId) {
        sessionStorage.setItem(STORAGE_KEY, String(this.runId));
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    },

    _stopPollingLoop() {
      this._pollGeneration += 1;
      this.polling = false;
    },

    _applyProjectFromRun(data) {
      const pid = data?.project_id;
      if (pid != null && pid !== "") {
        this.projectId = Number(pid);
        sessionStorage.setItem(STORAGE_PROJECT_KEY, String(pid));
      }
    },

    async fetchRun(runId) {
      const { data } = await client.get(`/api/test-cases/runs/${runId}`);
      this.runId = runId;
      this.liveRun = data;
      this._applyProjectFromRun(data);
      return data;
    },

    setActiveProjectId(projectId) {
      if (projectId != null) {
        this.projectId = Number(projectId);
        sessionStorage.setItem(STORAGE_PROJECT_KEY, String(projectId));
      }
    },

    async executeCase({ caseId, robotInstanceId, devicePlatform, deviceId, projectId }) {
      if (projectId != null) {
        this.setActiveProjectId(projectId);
      }
      this.pollError = null;
      this._stopPollingLoop();
      this.polling = true;
      try {
        const { data: started } = await client.post(`/api/test-cases/${caseId}/run`, {
          robot_instance_id: robotInstanceId,
          device_platform: devicePlatform,
          device_id: deviceId,
        });
        this.runId = started.id;
        this.liveRun = { ...started };
        this._applyProjectFromRun(started);
        this._persist();
        return await this._pollUntilDone();
      } catch (e) {
        const msg = e.response?.data?.detail || String(e.message || e);
        this.pollError = typeof msg === "string" ? msg : String(msg);
        throw e;
      } finally {
        this.polling = false;
      }
    },

    /** 进入用例页时恢复：读 sessionStorage / 可选 runId，若仍在执行则继续轮询 */
    async resumeIfNeeded(preferredRunId = null) {
      const raw =
        preferredRunId != null
          ? String(preferredRunId)
          : sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const runId = Number(raw);
      if (!Number.isFinite(runId) || runId < 1) {
        this.clear();
        return null;
      }

      if (this.polling && this.runId === runId) {
        try {
          return await this.fetchRun(runId);
        } catch {
          return this.liveRun;
        }
      }

      this.pollError = null;
      try {
        const data = await this.fetchRun(runId);
        this._persist();
        if (isTerminalStatus(data.status)) {
          this._stopPollingLoop();
          return data;
        }
        this.polling = true;
        this._pollUntilDone().catch((e) => {
          this.pollError = e.message || String(e);
        });
        return data;
      } catch {
        this.clear();
        return null;
      }
    },

    async _pollUntilDone() {
      const gen = ++this._pollGeneration;
      const runId = this.runId;
      if (!runId) return this.liveRun;

      const deadline = Date.now() + 2 * 60 * 60 * 1000;
      let transientStreak = 0;

      while (Date.now() < deadline) {
        if (gen !== this._pollGeneration) {
          return this.liveRun;
        }
        try {
          const { data } = await client.get(`/api/test-cases/runs/${runId}`);
          transientStreak = 0;
          this.liveRun = data;
          if (isTerminalStatus(data.status)) {
            this._stopPollingLoop();
            this._persist();
            return data;
          }
        } catch (e) {
          if (isTransientPollError(e)) {
            transientStreak += 1;
            if (transientStreak > 120) {
              this._stopPollingLoop();
              throw new Error(
                "长时间无法连接后端（网络或服务异常）。若正在使用 uvicorn --reload，保存文件会重启进程并中断未完成的自动化任务；长时间跑测时请去掉 --reload。",
              );
            }
          } else {
            this._stopPollingLoop();
            throw e;
          }
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
      this._stopPollingLoop();
      throw new Error("等待执行结果超时（超过 2 小时）");
    },

    async cancelCurrent() {
      const id = this.runId;
      if (!id) return;
      await client.post(`/api/test-cases/runs/${id}/cancel`);
    },

    clear() {
      this._stopPollingLoop();
      this.runId = null;
      this.projectId = null;
      this.liveRun = null;
      this.pollError = null;
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_PROJECT_KEY);
    },
  },
});

export function getActiveRunProjectId() {
  return sessionStorage.getItem(STORAGE_PROJECT_KEY) || "";
}
