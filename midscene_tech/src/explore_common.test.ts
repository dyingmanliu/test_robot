/**
 * 轻量单测（Node built-in test runner）
 * 运行：npx tsx --test src/explore_common.test.ts
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  longestCommonPrefix,
  SEARCH_FEATURE_LABEL,
  canonicalizeSearchNavItem,
  isSearchItem,
  normalizeNavItems,
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

describe('isSearchItem', () => {
  it('detects search_bar region', () => {
    assert.equal(
      isSearchItem({ name: '搜索框', region: 'search_bar' }),
      true,
    );
  });
});

describe('normalizeNavItems keeps search bar', () => {
  it('retains search_bar in feature list', () => {
    const items = normalizeNavItems([
      { name: '搜索框', region: 'search_bar', clickable: true },
      { name: '首页', region: 'bottom_tab', clickable: true },
    ]);
    assert.equal(items.length, 2);
    assert.ok(items.some((i) => i.region === 'search_bar'));
  });

  it('canonicalizes placeholder text to 搜索框', () => {
    const item = canonicalizeSearchNavItem({
      name: '爆矿247人下井仅记录124人 | 矿难',
      region: 'search_bar',
      clickable: true,
    });
    assert.equal(item.name, SEARCH_FEATURE_LABEL);
    assert.equal(item.region, 'search_bar');
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

  it('does not enqueue search bar', () => {
    assert.equal(
      shouldEnqueueTap('hybrid', 0, { name: '搜索框', region: 'search_bar' }, 1),
      false,
    );
  });
});

describe('shouldEnqueueTap bfs', () => {
  it('enqueues all clickable non-search items regardless of depth', () => {
    assert.equal(
      shouldEnqueueTap('bfs', 0, { name: '首页', region: 'bottom_tab' }, 1),
      true,
    );
    assert.equal(
      shouldEnqueueTap('bfs', 0, { name: '更多', region: 'button' }, 1),
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
