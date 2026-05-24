/**
 * 轻量单测（Node built-in test runner）
 * 运行：npx tsx --test src/explore_common.test.ts
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  longestCommonPrefix,
  shouldEnqueueTap,
  frontierPriority,
} from './explore_common.js';

describe('longestCommonPrefix', () => {
  it('returns shared prefix length', () => {
    assert.equal(longestCommonPrefix(['首页', '设置'], ['首页', '我的']), 1);
    assert.equal(longestCommonPrefix([], ['a']), 0);
    assert.equal(longestCommonPrefix(['a', 'b'], ['a', 'b']), 2);
  });
});

describe('shouldEnqueueTap hybrid', () => {
  it('prefers tabs at depth 0', () => {
    assert.equal(
      shouldEnqueueTap('hybrid', 0, { name: '首页', region: 'bottom_tab' }, 1),
      true,
    );
    assert.equal(
      shouldEnqueueTap('hybrid', 0, { name: '搜索', region: 'button' }, 1),
      false,
    );
  });

  it('allows buttons after bfs layer', () => {
    assert.equal(
      shouldEnqueueTap('hybrid', 1, { name: '设置', region: 'button' }, 1),
      true,
    );
  });
});

describe('frontierPriority', () => {
  it('orders shallower depth first', () => {
    const shallow = frontierPriority(1, { name: 'A', region: 'button' });
    const deep = frontierPriority(3, { name: 'B', region: 'bottom_tab' });
    assert.ok(shallow < deep);
  });
});
