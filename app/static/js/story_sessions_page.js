(() => {
  const projectId = Number(document.body.dataset.projectId || document.querySelector("[data-project-id]")?.dataset.projectId || 0);
  const grid = document.getElementById("sessionGrid");
  if (!projectId || !grid) return;

  function sessionThumbnail(session) {
    const mediaUrl = session.story?.opening_image_asset?.media_url || session.active_image?.media_url;
    if (mediaUrl) {
      return `<img class="story-session-card-thumbnail" src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(session.story?.title || session.title || "セッション")}">`;
    }
    return `
      <div class="story-session-card-thumbnail-placeholder">
        <i class="bi bi-image"></i>
        <span>サムネイルなし</span>
      </div>
    `;
  }

  async function loadSessions() {
    const sessions = await NovelUI.api(`/api/v1/projects/${projectId}/story-sessions`);
    if (!sessions.length) {
      grid.innerHTML = '<div class="empty-panel">まだセッションがありません。ストーリーから開始してください。</div>';
      return;
    }
    grid.innerHTML = sessions.map((session) => `
      <article class="project-card story-session-list-card entity-card-stable">
        <div class="story-session-list-main">
          <div class="story-session-card-thumb">${sessionThumbnail(session)}</div>
          <div class="story-session-list-copy">
            <div class="project-card-top">
              <span class="badge text-bg-light">${NovelUI.escape(session.status || "active")}</span>
              <span class="soft-code">${NovelUI.escape(session.player_name || "")}</span>
            </div>
            <h4>${NovelUI.escape(session.title || "セッション")}</h4>
            <p class="live-chat-session-excerpt">${NovelUI.escape(session.story?.title || "")}</p>
            <div class="small text-secondary">${NovelUI.escape(NovelUI.formatDateTime(session.updated_at))}</div>
          </div>
        </div>
        <a class="btn btn-sm btn-dark story-session-open-button" href="/projects/${projectId}/story-sessions/${session.id}">開く</a>
      </article>
    `).join("");
  }

  document.getElementById("sessionReloadButton")?.addEventListener("click", () => {
    loadSessions().catch((error) => NovelUI.toast(error.message || "セッションを読み込めませんでした。", "danger"));
  });
  loadSessions().catch((error) => NovelUI.toast(error.message || "セッションを読み込めませんでした。", "danger"));
})();
