/** 单步 aiAct / aiQuery 超时（与 MidsceneTestAgent 共用） */

export function stepTimeoutMs(): number {
  const raw = process.env.MIDSCENE_STEP_TIMEOUT_SEC?.trim();
  if (!raw) return 0;
  const sec = Number(raw);
  return Number.isFinite(sec) && sec > 0 ? sec * 1000 : 0;
}

/** 功能遍历默认单步超时（秒），未配置 MIDSCENE_STEP_TIMEOUT_SEC 时生效 */
export function exploreStepTimeoutMs(): number {
  const env = stepTimeoutMs();
  if (env > 0) return env;
  const raw = process.env.MIDSCENE_EXPLORE_STEP_TIMEOUT_SEC?.trim();
  if (raw) {
    const sec = Number(raw);
    if (Number.isFinite(sec) && sec > 0) return sec * 1000;
  }
  return 120_000;
}

export async function withStepTimeout<T>(
  promise: Promise<T>,
  label: string,
  timeoutMs?: number,
): Promise<T> {
  const ms = timeoutMs ?? exploreStepTimeoutMs();
  if (!ms) return promise;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`${label} 超时（${ms / 1000}s）`)),
      ms,
    );
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}
