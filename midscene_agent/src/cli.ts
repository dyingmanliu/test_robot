#!/usr/bin/env node
/**
 * CLI — HarmonyOS APP 自然语言自动化（Midscene.js）
 *
 * Usage:
 *   cd midscene_agent && npm install
 *   npm run task -- "打开设置并进入关于本机"
 *   npm run task -- --steps "打开设置" "向下滑动一屏"
 */

import { parseArgs } from 'node:util';

import './config.js';
import { HarmonyTestAgent } from './agent.js';
import { checkHdcVersion, listHdcTargets } from './hdc.js';

async function main(): Promise<number> {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      device: { type: 'string', short: 'd' },
      steps: { type: 'boolean', short: 's', default: false },
      'check-hdc': { type: 'boolean', default: false },
    },
  });

  if (values['check-hdc']) {
    const ver = await checkHdcVersion(process.env.HDC_HOME);
    console.log('HDC version:', ver);
    const targets = await listHdcTargets(process.env.HDC_HOME);
    console.log('Targets:', targets.length ? targets.map((t) => t.deviceId).join(', ') : '(none)');
    return targets.length ? 0 : 1;
  }

  const agent = new HarmonyTestAgent({
    deviceId: values.device ?? process.env.HDC_DEVICE_ID,
    hdcHome: process.env.HDC_HOME,
  });

  let task = positionals.join(' ').trim();
  if (!task) {
    task = await readStdinTask();
  }
  if (!task && !values.steps) {
    console.error('用法: npm run task -- "自然语言任务"');
    console.error('  或多步: npm run task -- --steps "步骤1" "步骤2"');
    return 1;
  }

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
    if (phase === 'start') console.log(`\n[步骤 ${step}] ${t}`);
    if (phase === 'error') console.error(`[步骤 ${step} 失败] ${error}`);
  };

  let outcome;
  if (values.steps) {
    const steps = positionals.map((s) => s.trim()).filter(Boolean);
    outcome = await agent.runSteps(steps, { onStep });
  } else {
    outcome = await agent.run(task, { onStep });
  }

  console.log('\n--- 最终结果 ---\n', outcome.message);
  if (outcome.reportFile) {
    console.log('报告文件:', outcome.reportFile);
  }
  return outcome.ok ? 0 : 1;
}

async function readStdinTask(): Promise<string> {
  if (process.stdin.isTTY) {
    return '';
  }
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString('utf8').trim();
}

main().then((code) => process.exit(code));
