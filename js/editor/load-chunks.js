'use strict';
(function () {
  const chunks = globalThis.__RoomEditorChunks || [];
  const src = "'use strict';\n" + chunks.join("\n");
  const run = new Function(src);
  run();
  globalThis.__RoomEditorChunks.length = 0;
})();
