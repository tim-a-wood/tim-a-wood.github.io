'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Validation ? root.RoomEditor.Validation : {};

function validateLayout(data) {
        const report = {
          run_at: new Date().toISOString(),
          level_1: { passed: true, checks: [] },
          level_2: { passed: true, checks: [] },
          summary: { errors: 0, warnings: 0 }
        };

        function fail(level, id, roomId, msg) {
          report[`level_${level}`].passed = false;
          report[`level_${level}`].checks.push({ id, room: roomId, severity: 'error', message: msg });
          report.summary.errors += 1;
        }

        function warn(level, id, roomId, msg) {
          report[`level_${level}`].checks.push({ id, room: roomId, severity: 'warning', message: msg });
          report.summary.warnings += 1;
        }

        const rooms = (data && data.rooms) || [];
        const roomIds = new Set(rooms.map((r) => r && r.id).filter(Boolean));

        const seenIds = {};
        rooms.forEach((r) => {
          const rid = r && r.id;
          if (rid == null || rid === '') return;
          if (seenIds[rid]) fail(1, 'L1-001', rid, `Duplicate room ID: ${rid}`);
          seenIds[rid] = true;
        });

        rooms.forEach((room) => {
          const rid = room && room.id != null ? room.id : '?';

          if (!room.polygon || room.polygon.length < 3) {
            fail(1, 'L1-002', rid, `Room ${rid} has fewer than 3 vertices (has ${(room.polygon || []).length})`);
          }

          (room.doors || []).forEach((door) => {
            if (door.targetRoom && !roomIds.has(door.targetRoom)) {
              fail(1, 'L1-003', rid, `Door ${door.id} targets non-existent room: ${door.targetRoom}`);
            }
          });

          (room.edgeLinks || []).forEach((link) => {
            const polyLen = (room.polygon || []).length;
            const targetRoom = rooms.find((r) => r.id === link.targetRoomId);
            const ei = Number(link.edgeIndex);
            if (Number.isInteger(ei) && ei >= polyLen) {
              fail(1, 'L1-004', rid, `Edge link in ${rid} references edge index ${link.edgeIndex} but room only has ${polyLen} edges`);
            }
            if (targetRoom) {
              const targetPolyLen = (targetRoom.polygon || []).length;
              const tei = Number(link.targetEdgeIndex);
              if (Number.isInteger(tei) && tei >= targetPolyLen) {
                fail(1, 'L1-004', rid, `Edge link in ${rid} targets edge index ${link.targetEdgeIndex} in ${link.targetRoomId} which only has ${targetPolyLen} edges`);
              }
            } else if (link.targetRoomId) {
              fail(1, 'L1-003', rid, `Edge link in ${rid} targets non-existent room: ${link.targetRoomId}`);
            }
          });

          const elementIds = new Set();
          [room.platforms, room.doors, room.keys, room.abilities, room.movingPlatforms].forEach((list) => {
            (list || []).forEach((el) => {
              if (!el || el.id == null) return;
              if (elementIds.has(el.id)) fail(1, 'L1-005', rid, `Duplicate element ID ${el.id} in room ${rid}`);
              elementIds.add(el.id);
            });
          });
        });

        const hasPlayerStart = rooms.some((r) => {
          const p = r.playerStart;
          return p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y));
        });
        if (!hasPlayerStart) fail(1, 'L1-006', null, 'No player start position defined in any room');

        function platformSpanX(p) {
          const w = (p.len || 1) * RoomEditor.Constants.TILE;
          return { left: p.x, right: p.x + w };
        }

        function horizontalGapBetweenPlatforms(a, b) {
          const A = platformSpanX(a);
          const B = platformSpanX(b);
          return Math.max(0, Math.max(B.left - A.right, A.left - B.right));
        }

        rooms.forEach((room) => {
          const rid = room && room.id != null ? room.id : '?';
          const platforms = room.platforms || [];
          if (platforms.length < 2) return;

          const pairCap = RoomEditor.Constants.VALIDATION_L2.maxHorizontalSeparationForPairPx;
          const vMax = RoomEditor.Constants.VALIDATION_L2.maxVerticalStepPx;
          const hMax = RoomEditor.Constants.VALIDATION_L2.maxHorizontalGapPx;
          const interactD = RoomEditor.Constants.VALIDATION_L2.interactMaxDistPx;

          for (let ai = 0; ai < platforms.length; ai += 1) {
            const a = platforms[ai];
            let best = null;
            let bestY = Infinity;
            for (let bi = 0; bi < platforms.length; bi += 1) {
              if (bi === ai) continue;
              const b = platforms[bi];
              if (b.y <= a.y) continue;
              const gx = horizontalGapBetweenPlatforms(a, b);
              if (gx > pairCap) continue;
              if (b.y < bestY) {
                bestY = b.y;
                best = b;
              }
            }
            if (!best) continue;
            const verticalDelta = best.y - a.y;
            const hGap = horizontalGapBetweenPlatforms(a, best);
            if (verticalDelta > vMax) {
              warn(
                2,
                'L2-001',
                rid,
                `Platforms ${a.id} and ${best.id} in ${rid}: vertical step ${Math.round(verticalDelta)}px exceeds ${vMax}px (nearest related platform below)`
              );
            }
            if (hGap > hMax) {
              warn(
                2,
                'L2-002',
                rid,
                `Platforms ${a.id} and ${best.id} in ${rid}: horizontal gap ${Math.round(hGap)}px exceeds ${hMax}px (nearest related platform below)`
              );
            }
          }

          const allInteractable = [
            ...(room.doors || []),
            ...(room.keys || []),
            ...(room.abilities || [])
          ];
          allInteractable.forEach((item) => {
            if (item.x == null || item.y == null) return;
            const nearPlatform = platforms.some((p) => {
              const pRight = p.x + (p.len || 1) * RoomEditor.Constants.TILE;
              const dx = Math.max(0, Math.max(p.x - item.x, item.x - pRight));
              const dy = Math.abs(item.y - p.y);
              return Math.sqrt(dx * dx + dy * dy) <= interactD;
            });
            if (!nearPlatform) {
              warn(2, 'L2-003', rid, `Element ${item.id} in ${rid} is more than ${interactD}px from any platform`);
            }
          });
        });

        report.level_1.passed = report.level_1.checks.filter((c) => c.severity === 'error').length === 0;
        report.level_2.passed = report.level_2.checks.filter((c) => c.severity === 'error').length === 0;

        return report;
      }

function renderValidationResults(report) {
        const container = document.getElementById('validationResults');
        const badge = document.getElementById('validationSummaryBadge');
        if (!container) return;

        const allChecks = [...report.level_1.checks, ...report.level_2.checks];

        if (badge) {
          if (report.summary.errors > 0) {
            badge.textContent = `${report.summary.errors} error${report.summary.errors > 1 ? 's' : ''}`;
            badge.className = 'validation-summary-badge fail';
          } else if (report.summary.warnings > 0) {
            badge.textContent = `${report.summary.warnings} warning${report.summary.warnings > 1 ? 's' : ''}`;
            badge.className = 'validation-summary-badge warn';
          } else {
            badge.textContent = 'All checks passed';
            badge.className = 'validation-summary-badge pass';
          }
        }

        if (allChecks.length === 0) {
          container.innerHTML = '<div class="validation-pass-row">✓ All structural and traversal checks passed</div>';
          return;
        }

        container.innerHTML = allChecks
          .map((check) => {
            const sev = check.severity === 'error' ? 'error' : 'warning';
            const roomAttr = check.room != null && check.room !== '' ? ` data-room="${RoomEditor.Ui.escapeHtml(String(check.room))}"` : '';
            return `
    <div class="validation-result-item ${sev}"${roomAttr}>
      <div class="validation-result-icon"></div>
      <div class="validation-result-body">
        <div class="validation-result-id">${RoomEditor.Ui.escapeHtml(String(check.id))}</div>
        <div class="validation-result-msg">${RoomEditor.Ui.escapeHtml(String(check.message))}</div>
        ${check.room ? `<div class="validation-result-room">Room: ${RoomEditor.Ui.escapeHtml(String(check.room))}</div>` : ''}
      </div>
    </div>`;
          })
          .join('');

        container.querySelectorAll('.validation-result-item[data-room]').forEach((el) => {
          const roomId = el.getAttribute('data-room');
          if (!roomId) return;
          el.addEventListener('click', () => {
            const roomSelect = document.getElementById('roomSelect');
            if (!roomSelect) return;
            const opt = Array.from(roomSelect.options).find((o) => o.value === roomId);
            if (!opt) return;
            roomSelect.value = roomId;
            roomSelect.dispatchEvent(new Event('change'));
          });
        });
      }

  Module.validateLayout = validateLayout;
  Module.renderValidationResults = renderValidationResults;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Validation = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
