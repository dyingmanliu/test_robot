# midscene_tech（runtime backend）

基于字节跳动 **[Midscene.js](https://midscenejs.com/)** 的 **Android**（`@midscene/android` + ADB）与 **鸿蒙 HarmonyOS 6.x / NEXT**（`@midscene/harmony` + HDC）APP 自动化子项目。当前作为 [`agent_service/func_agent`](../agent_service/func_agent/README.md) 业务域下的 Midscene 运行时后端使用。

## 能力

- **Android**：`adb` 连接真机/模拟器，`aiAct` / `aiQuery` / `aiAssert`、YAML `runYaml`
- **鸿蒙**：`hdc` 连接设备，同上 Midscene 能力
- 生成可回放的 **HTML 测试报告**
- Web 后端通过 `--web-dispatch` 子进程模式执行（见 `src/web_dispatch.ts`）

## 与 Web 平台的关系（通过 agent_service/func_agent 调度）

| Web 实例配置 | 是否走本子项目 |
|-------------|----------------|
| `midscene` + `android` | 是（`@midscene/android`） |
| `midscene` + `harmonyos` | 是（`@midscene/harmony`） |
| `autoglm` + `harmonyos` | 否（走 `autoglm_phone_tech` + HDC，见 Open-AutoGLM） |
| `autoglm` + `android` | 否（走 `autoglm_phone_tech` + ADB） |

完整矩阵见仓库根目录 [README.md](../README.md) 与 [ARCHITECTURE.md](../ARCHITECTURE.md)。

Web 用例页可在执行前指定 **`device_platform`** 与 **`device_id`**（多机时选择具体 ADB serial / HDC target）；`agent_service.func_agent.backends.midscene.runtime` 会调用本子项目 `--web-dispatch`，协议见 `src/web_dispatch.ts`。

## 前置条件

- **Node.js** ≥ 18
- **Android**：ADB、`adb devices` 可见设备；可选 `ADB_DEVICE_ID`
- **鸿蒙**：HDC（[DevEco Studio](https://developer.huawei.com/consumer/en/deveco-studio/) toolchains）、`hdc list targets` 可见设备
- **模型**：`MIDSCENE_MODEL_*` 或 DashScope 千问等（见 [Model strategy](https://midscenejs.com/model-strategy)）

## 环境变量

复制 [`midscene_tech/.env.example`](./.env.example) 或在**仓库根目录** [`.env`](../.env.example) 中配置：

```bash
# 视觉模型（必填）
MIDSCENE_MODEL_BASE_URL=...
MIDSCENE_MODEL_API_KEY=...
MIDSCENE_MODEL_NAME=...
MIDSCENE_MODEL_FAMILY=...

# CLI 默认平台（Web 执行时由下发 JSON 覆盖）
# MIDSCENE_DEVICE_PLATFORM=harmonyos   # android | harmonyos
# MIDSCENE_AGENT_BACKEND=midscene      # autoglm | midscene

# Android
# ADB_DEVICE_ID=

# 鸿蒙
# HDC_DEVICE_ID=
# HDC_HOME=/path/to/toolchains
```

## 安装与运行

```bash
cd midscene_tech
npm install

# 鸿蒙：检查 HDC
npm run task -- --check-hdc

# 鸿蒙自然语言（默认平台）
npm run task -- "打开设置并进入关于本机"

# Android 自然语言
MIDSCENE_DEVICE_PLATFORM=android npm run task -- "打开设置"

# 多步
npm run task -- --steps "打开设置" "向下滑动一屏"

# APP 功能清单遍历（输出 JSONL，含 explore_feature / explore_metrics / done.tree）
npm run explore -- --app-id com.huawei.hmos.settings --name 设置

# Web 下发时可传 traverse_mode、max_screens、max_depth、bfs_max_depth、fair_share_per_root
# 环境变量 EXPLORE_TRAVERSE_MODE=hybrid|bfs|dfs

# 鸿蒙 Demo
npm run demo

# Playground（鸿蒙）
npm run playground
```

Android Playground：`npx --yes @midscene/android-playground`

## 在代码中引用

```typescript
import { MidsceneTestAgent } from './src/index.js';

// 鸿蒙
const harmony = new MidsceneTestAgent({ devicePlatform: 'harmonyos' });
await harmony.run('打开设置');

// Android
const android = new MidsceneTestAgent({ devicePlatform: 'android' });
await android.run('打开浏览器并搜索 Headphones');
```

`HarmonyTestAgent` 为 `MidsceneTestAgent` 的兼容别名。

## 目录说明

| 路径 | 说明 |
|------|------|
| `src/agent.ts` | `MidsceneTestAgent` 跨平台封装 |
| `src/device_runtime.ts` | Android / 鸿蒙 Device+Agent 创建 |
| `src/platform.ts` | `DevicePlatform`、`AgentBackend` 解析 |
| `src/cli.ts` | CLI；`--web-dispatch` 供 Web 后端 |
| `src/explore.ts` | APP 功能菜单遍历入口（默认 **hybrid**；可选 bfs/dfs） |
| `src/explore_traverse.ts` | frontier 队列与混合/广度主循环 |
| `src/explore_snapshot.ts` | 合并界面快照 `aiQuery`、点击后稳定等待 |
| `src/explore_nav.ts` | 路径 LCA 回退与重放 |
| `src/explore_metrics.ts` | 遍历观测（LLM/返回/耗时） |
| `src/explore_fair_share.ts` | 按一级 Tab 公平分配 `max_screens` |
| `src/web_dispatch.ts` | Web 下发 JSON 协议 |
| `src/yaml_runner.ts` | YAML 脚本执行 |
| `src/hdc.ts` | HDC 工具链 |
| `scripts/demo-settings.ts` | 鸿蒙设置应用示例 |

## 相关文档

- [Android Getting Started](https://midscenejs.com/android-getting-started)
- [HarmonyOS Getting Started](https://midscenejs.com/harmony-getting-started)
- [Model configuration](https://midscenejs.com/model-config)
- [Android JS Demo](https://github.com/web-infra-dev/midscene-example/tree/main/android/javascript-sdk-demo)
- [Harmony JS Demo](https://github.com/web-infra-dev/midscene-example/tree/main/harmony/javascript-sdk-demo)
