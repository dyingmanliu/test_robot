# midscene_agent

基于字节跳动 **[Midscene.js](https://midscenejs.com/)**（`@midscene/harmony`）的 **HarmonyOS 6.x / HarmonyOS NEXT** APP 自动化测试子项目，与仓库根目录 `autoglm_phone_agent`（Android + AutoGLM-Phone）并列。

## 能力

- 通过 **HDC** 连接鸿蒙真机或模拟器
- 使用视觉大模型进行 **自然语言驱动** 的 UI 操作（`aiAct`）、查询（`aiQuery`）、断言（`aiAssert`）
- 生成可回放的 **HTML 测试报告**

## 前置条件

- **Node.js** ≥ 18
- **HDC**：随 [DevEco Studio](https://developer.huawei.com/consumer/en/deveco-studio/) 或 HarmonyOS 命令行工具安装
- 设备已开启开发者模式与 USB 调试：`hdc list targets` 能看到设备 ID
- 配置 Midscene 模型 API（见 [Model strategy](https://midscenejs.com/model-strategy)）

## 环境变量

复制 [`midscene_agent/.env.example`](./.env.example) 或在**仓库根目录** [`.env`](../.env.example) 中增加：

```bash
MIDSCENE_MODEL_BASE_URL=...
MIDSCENE_MODEL_API_KEY=...
MIDSCENE_MODEL_NAME=...
MIDSCENE_MODEL_FAMILY=...
# HDC_DEVICE_ID=          # 可选
# HDC_HOME=               # 可选
```

## 安装与运行

```bash
cd midscene_agent
npm install

# 检查 HDC
npm run task -- --check-hdc

# 单条自然语言任务
npm run task -- "打开设置并进入关于本机"

# 多步顺序执行
npm run task -- --steps "打开设置" "向下滑动一屏"

# 官方风格 Demo（设置应用）
npm run demo

# 零代码 Playground
npm run playground
```

## 在代码中引用

```typescript
import { HarmonyTestAgent } from './src/index.js';

const agent = new HarmonyTestAgent({ deviceId: 'YOUR_DEVICE_ID' });
const outcome = await agent.run('在浏览器中搜索 Headphones');
console.log(outcome.ok, outcome.message, outcome.reportFile);
```

## 目录说明

| 路径 | 说明 |
|------|------|
| `src/agent.ts` | `HarmonyTestAgent` 封装 |
| `src/cli.ts` | 命令行入口 |
| `src/hdc.ts` | HDC 检测与设备解析 |
| `scripts/demo-settings.ts` | 设置应用示例 |

## 相关文档

- [HarmonyOS Getting Started](https://midscenejs.com/harmony-getting-started)
- [HarmonyOS API Reference](https://midscenejs.com/harmony-api-reference)
- [官方 JS Demo](https://github.com/web-infra-dev/midscene-example/tree/main/harmony/javascript-sdk-demo)
