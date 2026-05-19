#!/usr/bin/env node
/**
 * CLI — HarmonyOS APP 自然语言自动化（Midscene.js）
 *
 * Usage:
 *   cd midscene_agent && npm install
 *   npm run task -- "打开设置并进入关于本机"
 *   npm run explore -- --name 设置
 *
 * Web 后端下发（stdin 为 JSON，见 web_dispatch.ts）：
 *   printf '%s' '{"version":1,"agent_task":"..."}' | npm run task -- --web-dispatch
 */
import { parseArgs } from 'node:util';

import './config.js';
import { MidsceneTestAgent } from './agent.js';
import { applyAgentBackendModelEnv } from './config.js';
import { runAppFeatureExplore } from './explore.js';
import { checkHdcVersion, listHdcTargets } from './hdc.js';
import { parseAgentBackend, parseDevicePlatform } from './platform.js';
import { parseWebDispatchJson, type WebTestDispatch } from './web_dispatch.js';

async function readStdinAll(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString('utf8').trim();
}

async function main(): Promise<number> {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      device: { type: 'string', short: 'd' },
      steps: { type: 'boolean', short: 's', default: false },
      explore: { type: 'boolean', default: false },
      name: { type: 'string', short: 'n', description: 'APP 显示名称（报告用）' },
      'app-id': { type: 'string', description: 'APP ID（bundleName，bm dump -a）' },
      'max-screens': { type: 'string' },
      'max-depth': { type: 'string' },
      'check-hdc': { type: 'boolean', default: false },
      'machine-out': { type: 'boolean', default: false },
      'web-dispatch': { type: 'boolean', default: false },
    },
  });

  if (values['check-hdc']) {
    const ver = await checkHdcVersion(process.env.HDC_HOME);
    console.log('HDC version:', ver);
    const targets = await listHdcTargets(process.env.HDC_HOME);
    console.log(
      'Targets:',
      targets.length ? targets.map((t) => t.deviceId).join(', ') : '(none)',
    );
    return targets.length ? 0 : 1;
  }

  const webDispatch = Boolean(values['web-dispatch']);
  const machineOut = Boolean(values['machine-out']) || webDispatch;
  const cliExplore = Boolean(values.explore);

  if (webDispatch && (values.steps || cliExplore)) {
    console.error('错误: --web-dispatch 不能与 --steps / --explore 同时使用');
    return 1;
  }

  let task = '';
  let webPayload: WebTestDispatch | null = null;
  let webYamlMode = false;
  let webExploreMode = false;

  if (webDispatch) {
    const raw = await readStdinAll();
    try {
      webPayload = parseWebDispatchJson(raw);
    } catch (e) {
      console.error(e instanceof Error ? e.message : String(e));
      return 1;
    }
    webYamlMode = webPayload.execution_mode === 'yaml';
    webExploreMode = webPayload.execution_mode === 'explore';
    task = webYamlMode
      ? (webPayload.yaml_script ?? '')
      : (webPayload.agent_task ?? '');
  } else if (cliExplore) {
    webExploreMode = true;
  } else {
    task = positionals.join(' ').trim();
    if (!task) {
      task = await readStdinTask();
    }
  }

  if (!webExploreMode && !task && !values.steps) {
    console.error('用法: npm run task -- "自然语言任务"');
    console.error('  或多步: npm run task -- --steps "步骤1" "步骤2"');
    console.error(
      '  功能遍历: npm run explore -- --bundle com.example.app --name 应用名',
    );
    console.error(
      '  Web explore: printf \'%s\' \'{"version":1,"execution_mode":"explore","app_name":"设置"}\' | npm run task -- --web-dispatch',
    );
    return 1;
  }

  const devicePlatform = parseDevicePlatform(
    webPayload?.device_platform ?? process.env.MIDSCENE_DEVICE_PLATFORM,
  );
  const agentBackend = parseAgentBackend(
    webPayload?.agent_backend ?? process.env.MIDSCENE_AGENT_BACKEND,
  );
  applyAgentBackendModelEnv(agentBackend);

  if (webDispatch && webPayload && machineOut) {
    process.stdout.write(
      `${JSON.stringify({
        kind: 'meta',
        source: 'web',
        version: webPayload.version,
        execution_mode: webPayload.execution_mode ?? 'natural',
        agent_backend: agentBackend,
        device_platform: devicePlatform,
        run_id: webPayload.run_id,
        case_id: webPayload.case_id,
        robot_instance_id: webPayload.robot_instance_id,
        app_name: webPayload.app_name,
      })}\n`,
    );
  }

  const resolvedDeviceId =
    values.device ??
    (webPayload?.device_id?.trim() ||
      (devicePlatform === 'android'
        ? process.env.ADB_DEVICE_ID
        : process.env.HDC_DEVICE_ID));
  const hdcHome = process.env.HDC_HOME;

  if (devicePlatform === 'harmonyos' || webExploreMode || cliExplore) {
    try {
      await checkHdcVersion(hdcHome);
    } catch (e) {
      console.warn(String(e instanceof Error ? e.message : e));
    }
  }

  const onStep = ({
    step,
    phase,
    task: t,
    error,
  }: {
    step: number;
    phase: string;
    task: string;
    error?: string;
  }) => {
    if (machineOut) {
      process.stdout.write(
        `${JSON.stringify({ kind: 'step', step, phase, task: t, error })}\n`,
      );
      return;
    }
    if (phase === 'start') console.log(`\n[步骤 ${step}] ${t}`);
    if (phase === 'error') console.error(`[步骤 ${step} 失败] ${error}`);
  };

  if (webExploreMode || cliExplore) {
    const bundleId = (webPayload?.bundle_id ?? values['app-id'] ?? '').trim();
    const appName = (webPayload?.app_name ?? values.name ?? bundleId).trim();
    if (!bundleId) {
      console.error('explore 模式需要 --app-id 或 bundle_id（hdc shell bm dump -a）');
      return 1;
    }
    const maxScreens = webPayload?.max_screens ?? numOpt(values['max-screens'], 30);
    const maxDepth = webPayload?.max_depth ?? numOpt(values['max-depth'], 4);

    const exploreOutcome = await runAppFeatureExplore({
      appName: appName || bundleId,
      bundleId,
      maxScreens,
      maxDepth,
      deviceId: resolvedDeviceId,
      hdcHome,
      machineOut,
      onEvent: (ev) => {
        if (machineOut) {
          process.stdout.write(`${JSON.stringify(ev)}\n`);
        } else if (ev.kind === 'explore_page') {
          console.log(
            `[页面 depth=${ev.depth}] ${ev.screen_title} (${ev.path.join(' > ') || '根'})`,
          );
        } else if (ev.kind === 'explore_feature') {
          console.log(`  + ${ev.feature.path.join(' > ')}`);
        } else if (ev.kind === 'step' && ev.phase === 'start') {
          console.log(`  … ${ev.task}`);
        }
      },
    });

    if (machineOut) {
      process.stdout.write(
        `${JSON.stringify({
          kind: 'done',
          ok: exploreOutcome.ok,
          message: exploreOutcome.message,
          reportFile: exploreOutcome.reportFile,
          feature_count: exploreOutcome.tree.features.length,
          tree: exploreOutcome.tree,
        })}\n`,
      );
    } else {
      console.log('\n--- 探索结果 ---\n', exploreOutcome.message);
      console.log(`功能项: ${exploreOutcome.tree.features.length}`);
      if (exploreOutcome.reportFile) console.log('报告:', exploreOutcome.reportFile);
    }
    return exploreOutcome.ok ? 0 : 1;
  }

  const agent = new MidsceneTestAgent({
    devicePlatform,
    agentBackend,
    deviceId: resolvedDeviceId,
    hdcHome,
  });

  const webSteps =
    webPayload?.agent_steps?.length ? webPayload.agent_steps : undefined;

  let outcome;
  if (values.steps) {
    const steps = positionals.map((s) => s.trim()).filter(Boolean);
    outcome = await agent.runSteps(steps, { onStep });
  } else if (webSteps?.length) {
    outcome = await agent.runSteps(webSteps, { onStep });
  } else if (webYamlMode) {
    outcome = await agent.runYamlScript(task, { onStep });
  } else {
    outcome = await agent.run(task, { onStep });
  }

  if (machineOut) {
    process.stdout.write(
      `${JSON.stringify({
        kind: 'done',
        ok: outcome.ok,
        message: outcome.message,
        reportFile: outcome.reportFile,
      })}\n`,
    );
  } else {
    console.log('\n--- 最终结果 ---\n', outcome.message);
    if (outcome.reportFile) console.log('报告文件:', outcome.reportFile);
  }
  return outcome.ok ? 0 : 1;
}

function numOpt(v: string | undefined, fallback: number): number {
  if (v === undefined || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

async function readStdinTask(): Promise<string> {
  if (process.stdin.isTTY) {
    return '';
  }
  return readStdinAll();
}

function emitMachineDone(ok: boolean, message: string, reportFile?: string): void {
  process.stdout.write(
    `${JSON.stringify({
      kind: 'done',
      ok,
      message,
      reportFile: reportFile ?? undefined,
    })}\n`,
  );
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(msg);
    const webDispatch = process.argv.includes('--web-dispatch');
    const machineOut =
      process.argv.includes('--machine-out') || webDispatch;
    if (machineOut) {
      emitMachineDone(false, msg);
    }
    process.exit(1);
  });
