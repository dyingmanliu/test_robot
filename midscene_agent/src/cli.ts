#!/usr/bin/env node
/**
 * CLI — HarmonyOS APP 自然语言自动化（Midscene.js）
 *
 * Usage:
 *   cd midscene_agent && npm install
 *   npm run task -- "打开设置并进入关于本机"
 *   npm run task -- --steps "打开设置" "向下滑动一屏"
 *
 * Web 后端下发（stdin 为 JSON，见 web_dispatch.ts）：
 *   printf '%s' '{"version":1,"agent_task":"..."}' | npm run task -- --web-dispatch
 */
import { parseArgs } from 'node:util';

import './config.js';
import { HarmonyTestAgent } from './agent.js';
import { checkHdcVersion, listHdcTargets } from './hdc.js';
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
      'check-hdc': { type: 'boolean', default: false },
      /** 供 Web 后端子进程解析：stdout 每行一条 JSON，含 kind: step | done */
      'machine-out': { type: 'boolean', default: false },
      /** stdin 读入 WebTestDispatch JSON，执行 agent_task；stdout 固定为 machine 协议（含 meta） */
      'web-dispatch': { type: 'boolean', default: false },
    },
  });

  if (values['check-hdc']) {
    const ver = await checkHdcVersion(process.env.HDC_HOME);
    console.log('HDC version:', ver);
    const targets = await listHdcTargets(process.env.HDC_HOME);
    console.log('Targets:', targets.length ? targets.map((t) => t.deviceId).join(', ') : '(none)');
    return targets.length ? 0 : 1;
  }

  const webDispatch = Boolean(values['web-dispatch']);
  const machineOut = Boolean(values['machine-out']) || webDispatch;

  if (webDispatch && values.steps) {
    console.error('错误: --web-dispatch 不能与 --steps 同时使用');
    return 1;
  }

  let task = '';
  let webPayload: WebTestDispatch | null = null;
  let webYamlMode = false;

  if (webDispatch) {
    const raw = await readStdinAll();
    try {
      webPayload = parseWebDispatchJson(raw);
    } catch (e) {
      console.error(e instanceof Error ? e.message : String(e));
      return 1;
    }
    webYamlMode = webPayload.execution_mode === 'yaml';
    task = webYamlMode
      ? (webPayload.yaml_script ?? '')
      : (webPayload.agent_task ?? '');
  } else {
    task = positionals.join(' ').trim();
    if (!task) {
      task = await readStdinTask();
    }
  }

  if (!task && !values.steps) {
    console.error('用法: npm run task -- "自然语言任务"');
    console.error('  或多步: npm run task -- --steps "步骤1" "步骤2"');
    console.error(
      '  Web 自然语言: printf \'%s\' \'{"version":1,"execution_mode":"natural","agent_task":"..."}\' | npm run task -- --web-dispatch',
    );
    console.error(
      '  Web YAML: printf \'%s\' \'{"version":1,"execution_mode":"yaml","yaml_script":"tasks:\\n  - ..."}\' | npm run task -- --web-dispatch',
    );
    return 1;
  }

  if (webDispatch && webPayload && machineOut) {
    process.stdout.write(
      `${JSON.stringify({
        kind: 'meta',
        source: 'web',
        version: webPayload.version,
        execution_mode: webPayload.execution_mode ?? 'natural',
        run_id: webPayload.run_id,
        case_id: webPayload.case_id,
        robot_instance_id: webPayload.robot_instance_id,
      })}\n`,
    );
  }

  const agent = new HarmonyTestAgent({
    deviceId: values.device ?? process.env.HDC_DEVICE_ID,
    hdcHome: process.env.HDC_HOME,
  });

  try {
    await checkHdcVersion(process.env.HDC_HOME);
  } catch (e) {
    console.warn(String(e instanceof Error ? e.message : e));
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
      const line = JSON.stringify({
        kind: 'step',
        step,
        phase,
        task: t,
        error,
      });
      process.stdout.write(`${line}\n`);
      return;
    }
    if (phase === 'start') console.log(`\n[步骤 ${step}] ${t}`);
    if (phase === 'error') console.error(`[步骤 ${step} 失败] ${error}`);
  };

  let outcome;
  if (values.steps) {
    const steps = positionals.map((s) => s.trim()).filter(Boolean);
    outcome = await agent.runSteps(steps, { onStep });
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
    if (outcome.reportFile) {
      console.log('报告文件:', outcome.reportFile);
    }
  }
  return outcome.ok ? 0 : 1;
}

async function readStdinTask(): Promise<string> {
  if (process.stdin.isTTY) {
    return '';
  }
  return readStdinAll();
}

main().then((code) => process.exit(code));
