(function () {
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

  function activeProjectId() {
    try {
      return (new URL(window.location.href)).searchParams.get('project') || '';
    } catch (_) {
      return '';
    }
  }

  function projectUrl(projectId) {
    const url = new URL('./index.html', window.location.href);
    if (projectId) url.searchParams.set('project', projectId);
    return url.toString();
  }

  function attachProjectCard(card) {
    const href = card.getAttribute('data-project-url');
    card.addEventListener('click', (event) => {
      if (event.target.closest('button')) return;
      if (href) window.location.href = href;
    });
    card.querySelector('[data-action="load"]')?.addEventListener('click', (event) => {
      event.stopPropagation();
      if (href) window.location.href = href;
    });
  }

  function renderFallback(projects, errorMessage) {
    const root = document.getElementById('project-list');
    if (!root || root.children.length > 0) return;

    if (errorMessage) {
      root.innerHTML = `
        <div class="project-card project-card--load-error">
          <strong>Projects unavailable</strong>
          <div class="small-note project-card__error-detail">${escapeHtml(errorMessage)}</div>
        </div>
      `;
      return;
    }

    const currentId = activeProjectId();
    const cards = [...projects]
      .sort((a, b) => (a.archived_at ? 1 : 0) - (b.archived_at ? 1 : 0))
      .map((project) => {
        const archivedLine = project.archived_at
          ? '<div class="small-note">Archived project. Still openable from this fallback list.</div>'
          : '';
        return `
          <div class="project-card ${currentId === project.project_id ? 'active' : ''}" data-project-url="${escapeHtml(projectUrl(project.project_id))}">
            <strong>${escapeHtml(project.project_name || project.project_id)}</strong>
            <small>${escapeHtml(project.current_stage || 'Sprite Creation')}</small>
            ${archivedLine}
            <div class="small-note">Last modified ${escapeHtml(formatDate(project.updated_at))}</div>
            <div class="project-actions">
              <button class="secondary" data-action="load">Load Project</button>
            </div>
          </div>
        `;
      });

    root.innerHTML = cards.length ? cards.join('') : '<div class="empty">No projects yet.</div>';
    Array.from(root.querySelectorAll('.project-card[data-project-url]')).forEach(attachProjectCard);
  }

  async function runFallback() {
    const root = document.getElementById('project-list');
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
