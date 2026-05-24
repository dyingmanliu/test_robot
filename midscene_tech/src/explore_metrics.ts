/** 功能遍历 Phase 0：耗时与 LLM/返回 次数观测 */

import type { ExploreMachineEvent, TraverseMode } from './explore_types.js';

export interface ExploreMetricsPayload {
  kind: 'explore_metrics';
  traverse_mode: TraverseMode;
  screens_visited: number;
  llm_query: number;
  llm_act: number;
  llm_total: number;
  back_count: number;
  tap_count: number;
  screen_record_ms_avg: number;
  elapsed_ms: number;
  queue_pending?: number;
}

export class ExploreMetrics {
  llm_query = 0;
  llm_act = 0;
  back_count = 0;
  tap_count = 0;
  private screen_ms_total = 0;
  private screen_ms_count = 0;
  private screen_t0: number | undefined;
  private readonly started = Date.now();

  onLlm(op: 'aiQuery' | 'aiAct'): void {
    if (op === 'aiQuery') this.llm_query += 1;
    else this.llm_act += 1;
  }

  onBack(): void {
    this.back_count += 1;
  }

  onTap(): void {
    this.tap_count += 1;
  }

  beginScreen(): void {
    this.screen_t0 = Date.now();
  }

  endScreen(): void {
    if (this.screen_t0 == null) return;
    this.screen_ms_total += Date.now() - this.screen_t0;
    this.screen_ms_count += 1;
    this.screen_t0 = undefined;
  }

  snapshot(
    traverse_mode: TraverseMode,
    screens_visited: number,
    queue_pending?: number,
  ): ExploreMetricsPayload {
    const avg =
      this.screen_ms_count > 0
        ? Math.round(this.screen_ms_total / this.screen_ms_count)
        : 0;
    return {
      kind: 'explore_metrics',
      traverse_mode,
      screens_visited,
      llm_query: this.llm_query,
      llm_act: this.llm_act,
      llm_total: this.llm_query + this.llm_act,
      back_count: this.back_count,
      tap_count: this.tap_count,
      screen_record_ms_avg: avg,
      elapsed_ms: Date.now() - this.started,
      queue_pending,
    };
  }

  asEvent(
    traverse_mode: TraverseMode,
    screens_visited: number,
    queue_pending?: number,
  ): ExploreMachineEvent {
    return this.snapshot(traverse_mode, screens_visited, queue_pending);
  }
}
