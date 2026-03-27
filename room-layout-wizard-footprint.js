/**
 * RW-1: axis-aligned room footprint inside room wizard (shared with tests).
 */
'use strict';

var ROOM_WIZARD_FOOTPRINT_MARGIN = 160;

/**
 * @param {object} room - room object with mutable size and polygon
 * @param {number} width
 * @param {number} height
 * @param {number} [margin]
 */
function applyAxisAlignedFootprint(room, width, height, margin) {
  const m = margin == null ? ROOM_WIZARD_FOOTPRINT_MARGIN : Number(margin);
  const W = Math.max(320, Number(width));
  const H = Math.max(320, Number(height));
  const inset = Math.max(32, Math.min(m, Math.floor(Math.min(W, H) / 4)));
  room.size = { width: W, height: H };
  room.polygon = [
    [inset, inset],
    [W - inset, inset],
    [W - inset, H - inset],
    [inset, H - inset]
  ];
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    applyAxisAlignedFootprint,
    ROOM_WIZARD_FOOTPRINT_MARGIN
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomLayoutWizardFootprint = {
    applyAxisAlignedFootprint,
    ROOM_WIZARD_FOOTPRINT_MARGIN
  };
}
