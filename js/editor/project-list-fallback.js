(function () {
  const LOCAL_PREFIX = 'ashen-hollow-room-layout-v1:local:';

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (match) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[match]));
  }

  function formatDate(value) {
    if (!value) return 'Unknown';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString([], {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  }

  function currentProjectId() {
    try {
      return (new URL(window.location.href)).searchParams.get('project_id') || '';
    } catch (_) {
      return '';
    }
  }

  function currentLocalSlot() {
    try {
      return (new URL(window.location.href)).searchParams.get('local_slot') || '';
    } catch (_) {
      return '';
    }
  }

  function roomUrl(projectId, localSlot) {
    const url = new URL('./room-layout-editor.html', window.location.href);
    if (projectId) url.searchParams.set('project_id', projectId);
    if (!projectId && localSlot) url.searchParams.set('local_slot', localSlot);
    return url.toString();
  }

  function spriteUrl(projectId) {
    const url = new URL('./tools/2d-sprite-and-animation/index.html', window.location.href);
    if (projectId) url.searchParams.set('project', projectId);
    return url.toString();
  }

  function listLocalSlots() {
    const slots = [];
    try {
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith(LOCAL_PREFIX)) {
          slots.push(key.slice(LOCAL_PREFIX.length));
        }
      }
    } catch (_) {}
    return slots.sort((a, b) => a.localeCompare(b));
  }

  function wireCards(root) {
    Array.from(root.querySelectorAll('.project-card[data-room-url]')).forEach((card) => {
      const roomHref = card.getAttribute('data-room-url');
      const spriteHref = card.getAttribute('data-sprite-url');
      card.addEventListener('click', (event) => {
        if (event.target.closest('button')) return;
        if (roomHref) window.location.href = roomHref;
      });
      card.querySelector('[data-action="open-room"]')?.addEventListener('click', (event) => {
        event.stopPropagation();
        if (roomHref) window.location.href = roomHref;
      });
      card.querySelector('[data-action="open-sprite"]')?.addEventListener('click', (event) => {
        event.stopPropagation();
        if (spriteHref) window.location.href = spriteHref;
      });
    });
  }

  function renderFallback(projects, errorMessage) {
    const root = document.getElementById('room-project-list');
    if (!root || root.children.length > 0) return;

    const activeProjectId = currentProjectId();
    const activeLocalSlot = currentLocalSlot();
    const cards = [];

    cards.push(`
      <div class="project-card ${!activeProjectId && !activeLocalSlot ? 'active' : ''}" data-room-url="${escapeHtml(roomUrl('', ''))}">
        <strong>Local Layout</strong>
        <small>Default scratch</small>
        <div class="small-note">Fallback list renderer active. Your browser save still opens here.</div>
        <div class="project-actions">
          <button class="secondary" data-action="open-room">Open</button>
        </div>
      </div>
    `);

    listLocalSlots().forEach((slot) => {
      cards.push(`
        <div class="project-card ${!activeProjectId && activeLocalSlot === slot ? 'active' : ''}" data-room-url="${escapeHtml(roomUrl('', slot))}">
          <strong>Local · ${escapeHtml(slot)}</strong>
          <small>Browser sandbox</small>
          <div class="small-note">Recovered from local browser storage.</div>
          <div class="project-actions">
            <button class="secondary" data-action="open-room">Open</button>
          </div>
        </div>
      `);
    });

    if (errorMessage) {
      cards.push(`
        <div class="project-card project-card--load-error">
          <strong>Workbench projects unavailable</strong>
          <div class="small-note project-card__error-detail">${escapeHtml(errorMessage)}</div>
          <div class="small-note">This fallback renderer could not reach <code>/api/projects</code>.</div>
        </div>
      `);
    } else {
      [...projects]
        .sort((a, b) => (a.archived_at ? 1 : 0) - (b.archived_at ? 1 : 0))
        .forEach((project) => {
          const archivedLine = project.archived_at
            ? '<div class="small-note">Archived project. Still openable from this fallback list.</div>'
            : '';
          cards.push(`
            <div class="project-card ${activeProjectId === project.project_id ? 'active' : ''}" data-room-url="${escapeHtml(roomUrl(project.project_id, ''))}" data-sprite-url="${escapeHtml(spriteUrl(project.project_id))}">
              <strong>${escapeHtml(project.project_name || project.project_id)}</strong>
              <small>${escapeHtml(project.current_stage || 'Sprite Creation')} · Last modified ${escapeHtml(formatDate(project.updated_at))}</small>
              ${archivedLine}
              <div class="project-actions">
                <button class="secondary" data-action="open-room">Load Room</button>
                <button class="secondary" data-action="open-sprite">Sprite Creation</button>
              </div>
            </div>
          `);
        });
    }

    root.innerHTML = cards.join('');
    wireCards(root);
  }

  async function runFallback() {
    const root = document.getElementById('room-project-list');
    if (!root || root.children.length > 0) return;
    try {
      const response = await fetch('/api/projects?include_archived=1', { cache: 'no-store' });
      if (!response.ok) throw new Error(`Project load failed (${response.status})`);
      const payload = await response.json();
      renderFallback(Array.isArray(payload.projects) ? payload.projects : [], '');
    } catch (error) {
      renderFallback([], error && error.message ? error.message : 'offline or blocked');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.setTimeout(runFallback, 1200), { once: true });
  } else {
    window.setTimeout(runFallback, 1200);
  }
})();
