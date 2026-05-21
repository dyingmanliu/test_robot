# 项目功能点分析 — 设计说明

**状态**：已对齐（讨论确认）  
**日期**：2026-05-21

## 1. 目标

在项目空间内提供 **功能点分析**：上传/安装 App 或选择已安装 App，由 **测试分析类数字机器人实例** 在真机上做界面深度遍历，产出 **功能菜单树**；支持编辑、确认、**多版本持久化**，并在后续页面中 **查看历史** 与导出。

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 机器人 | **仅** `catalog_robot_id=test_analysis`（选项 B）；用户不选功能执行实例 |
| 平台 | **双平台**：Android（ADB）+ 鸿蒙（HDC） |
| 遍历引擎 | 对内固定 **Midscene explore**（`MIDSCENE_*`）；与 `CASE_GEN_*` 用例生成分离 |
| 用例执行 | 分析实例 **仍禁止** `test_runs` 用例执行（`robot_run_guard` 不变） |
| 功能树版本 | **多版保留**，按时间排序；不覆盖历史确认版 |
| 确认后下游 | 第一期：**持久化 + 列表/详情查看 + 导出**；生成用例/任务下发为后续 |

## 3. 架构

### 3.1 能力分层

```
用户 → 测试分析机器人实例
         ├─ 用例自动生成（现有）analysis_agent + CASE_GEN_*
         └─ 功能点分析（新增）feature_analysis_service → Midscene explore 子进程
```

- 新任务域：**不**使用 `executor` / `test_runs`。
- 与 `app_explore_runs`（顶栏「功能清单探索」）分离；项目内走新表。

### 3.2 实例互斥

同一 `robot_instance_id`（test_analysis）同时仅允许一种占用：

- `analysis_generation_lock`（用例生成），或
- `project_feature_analysis_runs` 状态 `pending` / `running`

### 3.3 实例配置

- 使用已有字段：`device_platform`（默认平台）、本次 `device_id`。
- 功能点分析内部强制 `test_agent_backend=midscene`（可在服务层写死，不要求用户理解执行引擎）。

## 4. 数据模型

### 4.1 `project_feature_analysis_runs`

| 字段 | 说明 |
|------|------|
| id | PK |
| project_id | FK projects |
| owner_id | FK users |
| robot_instance_id | 须 test_analysis |
| device_platform | android \| harmonyos |
| device_id | 可选，ADB serial / HDC target |
| app_source | uploaded \| installed |
| app_artifact_id | 可选 FK project_app_artifacts |
| bundle_id | package / bundleName |
| app_display_name | 展示名 |
| status | pending \| running \| success \| failed \| cancelled |
| feature_json | 原始树 JSON（遍历结果） |
| step_log | 行级 JSON 事件（同 explore） |
| excel_path | 可选草稿导出 |
| output_message, error_trace | |
| started_at, finished_at, created_at | |

### 4.2 `project_feature_trees`

| 字段 | 说明 |
|------|------|
| id | PK |
| project_id | FK |
| run_id | FK project_feature_analysis_runs |
| owner_id | 确认人 |
| tree_json | **用户确认版**树 |
| version_label | 可选，如 v1、v2 或自动序号 |
| confirmed_at | |
| created_at | |

同一 `project_id` 可有多条 `project_feature_trees`（多版）。

## 5. API（草案）

前缀：`/api/projects/{project_id}/feature-analysis`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/runs` | 分析任务列表（分页可选） |
| POST | `/runs` | 创建并异步执行分析 |
| GET | `/runs/{run_id}` | 任务详情 + 实时状态 |
| POST | `/runs/{run_id}/cancel` | 取消 |
| GET | `/runs/{run_id}/download` | 导出 Excel（草稿） |
| POST | `/artifacts` | 上传安装包（复用或代理 project_app_artifacts） |
| POST | `/artifacts/{id}/install` | 装到指定 device_platform + device_id |
| GET | `/installed-apps` | 按 platform 列已安装包 |
| GET | `/trees` | 已确认功能树列表（多版） |
| GET | `/trees/{tree_id}` | 树详情（查看） |
| PUT | `/trees/{tree_id}` | 更新确认版（可选：再编辑） |
| POST | `/runs/{run_id}/confirm` | 提交编辑后树 → 写入 project_feature_trees |

权限：与项目空间读/写一致（`project_scope_query` / owner）。

## 6. 前端页面

| 路由 | 说明 |
|------|------|
| `/projects/:projectId/feature-analysis` | 主流程：选分析实例、设备、App、分析、编辑确认 |
| `/projects/:projectId/feature-analysis/history` | 分析记录 + 已确认树列表 |
| `/projects/:projectId/feature-trees/:treeId` | 树详情（查看/导出；可选再编辑） |

**项目空间卡片**（`ProjectsView`）：

- 按钮「功能点分析」→ 主流程页
- 文案/链接：「功能树记录」→ history；展示 `已确认 N 版`

**顶栏「功能清单探索」**：保留为运维/全局探索，与项目内能力区分；项目按钮不再复用 `AppExploreView`。

## 7. 实现分期

### P0 — 鸿蒙优先

- 表 + API + 专用前端页（分析 + 确认 + 持久化）
- 复用 `explore.ts`（鸿蒙路径）
- HDC：安装包、已安装列表、遍历
- 历史列表 + 树详情查看
- 分析实例 guard + 与用例生成互斥

### P1 — Android

- `explore.ts` 抽象 `device_platform`（`device_runtime` 或等价）
- ADB：install、list packages、Android DFS
- 前端平台切换与安装包类型（apk/aab）

### P2 — 下游

- 从确认树批量生成用例草稿（CASE_GEN）
- 对接功能测试任务下发用例集

## 8. 代码落点（规划）

| 层 | 路径 |
|----|------|
| Agent/编排 | `agent_service/feature_analysis/` 或 `web/backend/app/services/feature_analysis_service.py` |
| 路由 | `web/backend/app/routers/project_feature_analysis.py` |
| 模型 | `web/backend/app/models.py` + `database.ensure_schema()` |
| 遍历 | `midscene_tech/src/explore.ts`（P1 双平台） |
| 前端 | `ProjectFeatureAnalysisView.vue`、`ProjectFeatureAnalysisHistoryView.vue`、`ProjectFeatureTreeDetailView.vue` |
| 文档 | `ARCHITECTURE.md`、`README.md` 增补一节 |

## 9. 非目标（本期）

- 不要求 AutoGLM 做 DFS 遍历
- 不改为测试执行实例驱动项目内功能点分析
- 不自动覆盖旧版确认树
