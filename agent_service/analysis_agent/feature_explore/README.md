# feature_explore — 功能点 / 功能菜单树遍历

测试分析机器人在真机上采集 App 功能结构，产出 GIIC 对齐的 `feature_json`（含 `function_tree` / `function_tree_by_path`）。

## 调用链

```
ProjectFeatureAnalysisView
  → POST /api/projects/{id}/feature-analysis/runs
  → feature_analysis_bridge.execute_feature_analysis_run
  → FeatureExploreAgent.run(ExploreDispatch)
  → midscene_tech CLI --web-dispatch（execution_mode=explore）
  → runAppFeatureExplore（explore.ts）
```

## ExploreDispatch 字段

| 字段 | 默认 | 说明 |
|------|------|------|
| `traverse_mode` | `hybrid` | `hybrid` \| `bfs` \| `dfs` |
| `max_screens` | 1000 | 最多记录不同界面数 |
| `max_depth` | 5 | 导航路径最大深度 |
| `bfs_max_depth` | 1 | **仅 hybrid**：前几层路径仅 Tab/主导航入队；bfs 模式忽略此参数 |
| `fair_share_per_root` | 0 | `0` 关；`-1` 自动；`>0` 每级 Tab 分支固定屏数上限 |

环境变量 `EXPLORE_TRAVERSE_MODE` 可在未传 `traverse_mode` 时作为全局默认。

## 事件流（JSONL）

与 `midscene_tech` 一致，Web 层追加写入 `project_feature_analysis_runs.step_log`：

- `explore_page` — 进入界面
- `explore_feature` — 发现/访问功能项（增量更新 `feature_json`）
- `explore_queue` — frontier 待探索数量
- `explore_metrics` — 观测汇总
- `step` — 单步 aiAct 描述
- `done` — 结束（含完整 `tree`）

## 确认保存

由 Web API `POST …/runs/{id}/confirm` 完成，不在本包内写 `project_feature_trees`。任务状态为 `success`、`cancelled` 或 `failed` 且含功能点即可确认。

详见根目录 [`ARCHITECTURE.md`](../../../ARCHITECTURE.md) §4.6。
