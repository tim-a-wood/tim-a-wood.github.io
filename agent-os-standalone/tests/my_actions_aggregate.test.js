/**
 * Pure helpers mirrored from `os-dashboard.html` My Actions block.
 * Keep FNV / id rules in sync when changing the dashboard aggregate.
 */

'use strict';

const assert = require('assert');
const test = require('node:test');

function maHash32(s) {
  var str = String(s || '');
  var h = 2166136261 >>> 0;
  for (var i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function maNormTitle(t) {
  return String(t || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function maFounderId(agent, fd) {
  var explicit = fd && fd.my_actions_id != null ? String(fd.my_actions_id).trim() : '';
  if (explicit) return agent + ':founder:' + explicit;
  var t = (fd.title || '') + '\0' + (fd.source || '') + '\0' + (fd.note || '');
  return agent + ':founder:' + maHash32(t).toString(16);
}

function itemVisibleInOsProductContext(agent, item, ctx) {
  if (ctx === 'all') return true;
  if (!item || typeof item !== 'object') return true;
  var raw = item.os_contexts != null ? item.os_contexts : item.os_context;
  if (raw == null) return true;
  var arr = Array.isArray(raw) ? raw : [raw];
  var cleaned = arr.map(function(x) { return String(x).trim(); }).filter(Boolean);
  if (cleaned.length === 0) return true;
  return cleaned.indexOf(ctx) !== -1;
}

function aggregateMyActionsFromCaches(avStatusFiles, avCache, ctx) {
  var blocking = [];
  var decision = [];
  var review = [];
  var seenFounder = Object.create(null);

  avStatusFiles.forEach(function(entry) {
    var data = avCache[entry.file];
    if (!data || typeof data !== 'object') return;
    var agent = entry.agent;

    if (Array.isArray(data.founder_decisions)) {
      data.founder_decisions.forEach(function(fd) {
        if (!fd || typeof fd !== 'object') return;
        if (!itemVisibleInOsProductContext(agent, fd, ctx)) return;
        var title = fd.title != null ? String(fd.title).trim() : '';
        if (!title) return;
        var isBlock = fd.blocking === true;
        var dedupe = (isBlock ? 'b' : 'd') + ':' + maNormTitle(title);
        if (seenFounder[dedupe]) return;
        seenFounder[dedupe] = true;
        var id = maFounderId(agent, fd);
        var item = { id: id, type: isBlock ? 'blocking' : 'decision', agent: agent, title: title };
        if (isBlock) blocking.push(item);
        else decision.push(item);
      });
    }

    if (Array.isArray(data.priorities)) {
      data.priorities.forEach(function(p) {
        if (!p || typeof p !== 'object') return;
        if ((p.status || '') !== 'needs-review') return;
        if (!itemVisibleInOsProductContext(agent, p, ctx)) return;
        var title = p.title != null ? String(p.title).trim() : '';
        if (!title) return;
        review.push({
          id: agent + ':priority:' + String(p.id),
          type: 'review',
          agent: agent,
          title: title,
        });
      });
    }
  });

  return { blocking: blocking, decision: decision, review: review };
}

test('maHash32 is deterministic', function() {
  assert.strictEqual(maHash32('hello'), maHash32('hello'));
  assert.notStrictEqual(maHash32('hello'), maHash32('hallo'));
});

test('maFounderId prefers my_actions_id', function() {
  assert.strictEqual(
    maFounderId('engineering', { my_actions_id: 'copilot-bar', title: 'x' }),
    'engineering:founder:copilot-bar'
  );
});

test('aggregate respects blocking flag and needs-review', function() {
  var files = [{ file: 'a.json', agent: 'orchestrator' }];
  var cache = {
    'a.json': {
      founder_decisions: [
        { title: 'Block me', blocking: true, source: 'qa' },
        { title: 'Decide me', blocking: false },
      ],
      priorities: [
        { id: 9, title: 'Review me', status: 'needs-review', risk: 'high' },
        { id: 10, title: 'Skip me', status: 'in-progress' },
      ],
    },
  };
  var agg = aggregateMyActionsFromCaches(files, cache, 'all');
  assert.strictEqual(agg.blocking.length, 1);
  assert.strictEqual(agg.decision.length, 1);
  assert.strictEqual(agg.review.length, 1);
  assert.strictEqual(agg.review[0].id, 'orchestrator:priority:9');
});

test('aggregate dedupes same normalized founder title', function() {
  var files = [
    { file: 'x.json', agent: 'strategy' },
    { file: 'y.json', agent: 'orchestrator' },
  ];
  var cache = {
    'x.json': {
      founder_decisions: [{ title: 'Same   Title', source: 'a' }],
    },
    'y.json': {
      founder_decisions: [{ title: 'same title', source: 'b' }],
    },
  };
  var agg = aggregateMyActionsFromCaches(files, cache, 'all');
  assert.strictEqual(agg.decision.length, 1);
});

test('aggregate filters review rows by os_contexts', function() {
  var files = [{ file: 'e.json', agent: 'engineering' }];
  var cache = {
    'e.json': {
      priorities: [
        { id: 1, title: 'Sprite only', status: 'needs-review', os_contexts: ['sprite'] },
        { id: 2, title: 'Business only', status: 'needs-review', os_contexts: ['business'] },
      ],
    },
  };
  var sprite = aggregateMyActionsFromCaches(files, cache, 'sprite');
  assert.strictEqual(sprite.review.length, 1);
  assert.strictEqual(sprite.review[0].title, 'Sprite only');
});
