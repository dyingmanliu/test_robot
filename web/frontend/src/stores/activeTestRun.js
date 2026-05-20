/**
 * 测试执行工作台：支持多 run 并行轮询，focusedRun 驱动投屏/日志观看。
 */
import { defineStore } from "pinia";
import axios from "axios";
import client from "@/api/client";

const STORAGE_KEY = "tcm_active_run_id";
const STORAGE_RUNS_KEY = "tcm_active_run_ids";
const STORAGE_PROJECT_KEY = "tcm_active_run_project";

function isTransientPollError(e) {
  if (!axios.isAxiosError(e)) return false;
  if (!e.response) return true;
  const s = e.response.status;
  return s >= 500 || s === 408 || s === 429;
}

function isRunNotFoundError(e) {
  return axios.isAxiosError(e) && e.response?.status === 404;
}

/** 同平台下有效设备键（空表示走 .env 默认设备，多 run 共用视为冲突） */
export function deviceBindingKey(platform, deviceId) {
  const plat = String(platform || "android").toLowerCase() === "harmonyos" ? "harmonyos" : "android";
  const dev = String(deviceId || "").trim();
  return `${plat}::${dev || "__default__"}`;
}

export function isLiveRunStatus(status) {
  return status === "pending" || status === "running";
}

function isTerminalStatus(status) {
  return status === "success" || status === "failed" || status === "cancelled";
}

function runMatchesProject(run, projectId) {
  if (projectId == null || projectId === "") return true;
  const want = Number(projectId);
  if (!Number.isFinite(want)) return true;
  const pid = run?.project_id != null ? Number(run.project_id) : NaN;
  if (Number.isFinite(pid)) return pid === want;
  return true;
}

export const useActiveTestRunStore = defineStore("activeTestRun", {
  state: () => ({
    /** @type {Record<number, object>} */
    runsById: {},
    focusedRunId: null,
    projectId: null,
    polling: false,
    pollError: null,
    _pollGeneration: 0,
  }),

  getters: {
    /** 当前观看的 run（投屏、日志、停止按钮） */
    liveRun(state) {
      if (!state.focusedRunId) return null;
      return state.runsById[state.focusedRunId] ?? null;
    },

    runId(state) {
      return state.focusedRunId;
    },

    isActive(state) {
      return Object.values(state.runsById).some((r) => isLiveRunStatus(r.status));
    },

    activeRunCount(state) {
      return Object.values(state.runsById).filter((r) => isLiveRunStatus(r.status)).length;
    },

    executingRuns(state) {
      return Object.values(state.runsById)
        .filter((r) => isLiveRunStatus(r.status))
        .sort((a, b) => a.id - b.id);
    },

    /** 是否有其它进行中的 run 占用同一物理终端 */
    findLiveRunOnDevice: (state) => (platform, deviceId, excludeRunId = null) => {
      const key = deviceBindingKey(platform, deviceId);
      return (
        Object.values(state.runsById).find((r) => {
          if (!isLiveRunStatus(r.status)) return false;
          if (excludeRunId != null && r.id === excludeRunId) return false;
          return deviceBindingKey(r.device_platform, r.device_id) === key;
        }) ?? null
      );
    },

    belongsToProject: (state) => (projectId) => {
      if (projectId == null || projectId === "") return false;
      const want = Number(projectId);
      if (!Number.isFinite(want)) return false;
      const live = Object.values(state.runsById).filter((r) => isLiveRunStatus(r.status));
      if (live.some((r) => runMatchesProject(r, want))) return true;
      const pid =
        state.projectId != null
          ? Number(state.projectId)
          : Number(sessionStorage.getItem(STORAGE_PROJECT_KEY)) || NaN;
      return Number.isFinite(pid) && pid === want;
    },
  },

  actions: {
    _upsertRun(data) {
      if (!data?.id) return;
      this.runsById = { ...this.runsById, [data.id]: data };
      if (isLiveRunStatus(data.status) || isTerminalStatus(data.status)) {
        this._persist();
      }
    },

    _readStoredRunIds() {
      try {
        const raw = sessionStorage.getItem(STORAGE_RUNS_KEY);
        const arr = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(arr)) return [];
        return arr
          .map((id) => Number(id))
          .filter((id) => Number.isFinite(id) && id > 0);
      } catch {
        return [];
      }
    },

    _persist() {
      const liveIds = Object.values(this.runsById)
        .filter((r) => isLiveRunStatus(r.status))
        .map((r) => r.id);
      if (liveIds.length) {
        sessionStorage.setItem(STORAGE_RUNS_KEY, JSON.stringify(liveIds));
      } else {
        sessionStorage.removeItem(STORAGE_RUNS_KEY);
      }
      if (this.focusedRunId) {
        sessionStorage.setItem(STORAGE_KEY, String(this.focusedRunId));
      } else if (!liveIds.length) {
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

    focusRun(runId) {
      if (runId == null) {
        this.focusedRunId = null;
        sessionStorage.removeItem(STORAGE_KEY);
        return;
      }
      const id = Number(runId);
      if (!Number.isFinite(id) || id < 1) return;
      this.focusedRunId = id;
      this._persist();
    },

    removeRun(runId) {
      const id = Number(runId);
      if (!Number.isFinite(id)) return;
      const next = { ...this.runsById };
      delete next[id];
      this.runsById = next;
      if (this.focusedRunId === id) {
        const live = Object.values(next).find((r) => isLiveRunStatus(r.status));
        this.focusedRunId = live?.id ?? null;
        if (this.focusedRunId) this._persist();
        else sessionStorage.removeItem(STORAGE_KEY);
      }
      if (!Object.values(next).some((r) => isLiveRunStatus(r.status))) {
        this._stopPollingLoop();
      }
      this._persist();
    },

    async fetchRun(runId, { setFocus = false } = {}) {
      const { data } = await client.get(`/api/test-cases/runs/${runId}`);
      this._upsertRun(data);
      this._applyProjectFromRun(data);
      if (setFocus) this.focusRun(runId);
      return data;
    },

    setActiveProjectId(projectId) {
      if (projectId != null) {
        this.projectId = Number(projectId);
        sessionStorage.setItem(STORAGE_PROJECT_KEY, String(projectId));
      }
    },

    /** 发起执行（非阻塞）；返回 started run */
    async executeCase({ caseId, robotInstanceId, devicePlatform, deviceId, projectId }) {
      if (projectId != null) {
        this.setActiveProjectId(projectId);
      }
      this.pollError = null;
      const { data: started } = await client.post(`/api/test-cases/${caseId}/run`, {
        robot_instance_id: robotInstanceId,
        device_platform: devicePlatform,
        device_id: deviceId,
      });
      this._upsertRun(started);
      this.focusRun(started.id);
      this._persist();
      this._ensurePolling();
      return started;
    },

    /** 从机器人列表 active_run_id 发现并同步进行中的 run */
    async syncRunsFromRobots(robots, projectId = null) {
      if (projectId != null) {
        this.setActiveProjectId(projectId);
      }
      const fromRobots = [
        ...new Set(
          (Array.isArray(robots) ? robots : [])
            .map((r) => r.active_run_id)
            .filter((id) => id != null && Number(id) > 0),
        ),
      ];
      const existingLive = Object.values(this.runsById)
        .filter((r) => isLiveRunStatus(r.status) && runMatchesProject(r, projectId))
        .map((r) => r.id);
      const storedIds = this._readStoredRunIds();
      const ids = [...new Set([...fromRobots, ...existingLive, ...storedIds])];

      for (const id of ids) {
        try {
          const data = await this.fetchRun(id);
          if (projectId != null && data.project_id != null && !runMatchesProject(data, projectId)) {
            this.removeRun(id);
          }
        } catch (e) {
          if (isRunNotFoundError(e)) {
            this.removeRun(id);
          }
          // 瞬时网络错误等：保留 runsById 中已有记录，避免误删仍在执行的任务
        }
      }

      const focused = this.focusedRunId ? this.runsById[this.focusedRunId] : null;
      const focusedOk =
        focused &&
        isLiveRunStatus(focused.status) &&
        runMatchesProject(focused, projectId);
      if (!focusedOk) {
        const pick = Object.values(this.runsById).find(
          (r) => isLiveRunStatus(r.status) && runMatchesProject(r, projectId),
        );
        if (pick) this.focusRun(pick.id);
      }

      if (this.isActive) {
        this._ensurePolling();
      }
      this._persist();
      return this.executingRuns;
    },

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

      try {
        const data = await this.fetchRun(runId, { setFocus: true });
        this._persist();
        if (isTerminalStatus(data.status)) {
          return data;
        }
        this._ensurePolling();
        return data;
      } catch {
        this.removeRun(runId);
        return null;
      }
    },

    _ensurePolling() {
      if (this.polling) return;
      this.polling = true;
      this._pollLoop().catch((e) => {
        this.pollError = e.message || String(e);
        this.polling = false;
      });
    },

    async _pollLoop() {
      const gen = ++this._pollGeneration;
      const deadline = Date.now() + 2 * 60 * 60 * 1000;
      let transientStreak = 0;

      while (Date.now() < deadline) {
        if (gen !== this._pollGeneration) {
          return;
        }

        const liveIds = Object.values(this.runsById)
          .filter((r) => isLiveRunStatus(r.status))
          .map((r) => r.id);

        if (!liveIds.length) {
          this.polling = false;
          return;
        }

        let hadError = false;
        for (const id of liveIds) {
          try {
            const { data } = await client.get(`/api/test-cases/runs/${id}`);
            transientStreak = 0;
            this._upsertRun(data);
            if (isTerminalStatus(data.status)) {
              this._persist();
            }
          } catch (e) {
            hadError = true;
            if (isRunNotFoundError(e)) {
              this.removeRun(id);
              continue;
            }
            if (isTransientPollError(e)) {
              transientStreak += 1;
              if (transientStreak > 120) {
                this._stopPollingLoop();
                throw new Error(
                  "长时间无法连接后端（网络或服务异常）。若正在使用 uvicorn --reload，保存文件会重启进程并中断未完成的自动化任务；长时间跑测时请去掉 --reload。",
                );
              }
            } else {
              // 单个 run 拉取失败（如 403）不影响其它 run 继续轮询
              this.pollError =
                e.response?.data?.detail || e.message || String(e);
            }
          }
        }

        if (!hadError) {
          this.pollError = null;
        }

        await new Promise((r) => setTimeout(r, 1000));
      }

      this._stopPollingLoop();
      throw new Error("等待执行结果超时（超过 2 小时）");
    },

    async cancelCurrent() {
      const id = this.focusedRunId;
      if (!id) return;
      await this.cancelRunById(id);
    },

    async cancelRunById(runId) {
      const id = Number(runId);
      if (!Number.isFinite(id) || id < 1) return;
      await client.post(`/api/test-cases/runs/${id}/cancel`);
      try {
        const { data } = await client.get(`/api/test-cases/runs/${id}`);
        this._upsertRun(data);
        // 勿在此处 removeRun：与 _upsertRun 同 tick 会吞掉 watcher，CasesView 无法 absorb 到结果区
      } catch {
        this.removeRun(id);
      }
    },

    clear() {
      this._stopPollingLoop();
      this.runsById = {};
      this.focusedRunId = null;
      this.projectId = null;
      this.pollError = null;
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(STORAGE_RUNS_KEY);
      sessionStorage.removeItem(STORAGE_PROJECT_KEY);
    },
  },
});

export function getActiveRunProjectId() {
  return sessionStorage.getItem(STORAGE_PROJECT_KEY) || "";
}
