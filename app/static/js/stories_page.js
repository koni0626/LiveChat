(() => {
  const projectId = Number(document.body.dataset.projectId || document.querySelector("[data-project-id]")?.dataset.projectId || 0);
  const grid = document.getElementById("storyGrid");
  if (!projectId || !grid) return;

  function storyModeLabel(value) {
    const labels = {
      free_chat: "自由会話",
      dungeon_trpg: "ダンジョン探索",
      romance_adventure: "恋愛アドベンチャー",
      romantic_comedy: "ラブコメ",
      comedy_adventure: "コメディ冒険",
      daily_comedy: "日常ドタバタ",
      school_mystery: "学園ミステリー",
      horror_trpg: "怪異・ホラー",
      escape_game: "脱出ゲーム",
      isekai_adventure: "異世界冒険",
      buddy_mission: "バディ任務",
      mystery_trpg: "ミステリー攻略",
      event_trpg: "イベント重視",
    };
    return labels[value] || value || "自由会話";
  }

  function renderStoryThumbnail(story) {
    const mediaUrl = story.opening_image_asset?.media_url;
    if (mediaUrl) {
      return `<img class="story-card-thumbnail" src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(story.title || "ストーリー")}">`;
    }
    return `
      <div class="story-card-thumbnail-placeholder">
        <i class="bi bi-image"></i>
        <span>サムネイル未設定</span>
      </div>
    `;
  }

  async function loadStories() {
    const stories = await NovelUI.api(`/api/v1/projects/${projectId}/stories`);
    if (!stories.length) {
      grid.innerHTML = '<div class="empty-panel">まだストーリーがありません。</div>';
      return;
    }
    grid.innerHTML = stories.map((story) => `
      <article class="project-card story-card entity-card-stable">
        ${renderStoryThumbnail(story)}
        <div class="project-card-top">
          <span class="badge text-bg-light">${NovelUI.escape(NovelUI.statusLabel(story.status))}</span>
          <span class="soft-code">履歴 ${story.my_session_count || 0}件</span>
        </div>
        <h4>${NovelUI.escape(story.title || "ストーリー")}</h4>
        <div class="soft-code mb-2">${NovelUI.escape(storyModeLabel(story.story_mode))}</div>
        ${story.description ? `<p class="live-chat-session-excerpt">${NovelUI.escape(NovelUI.truncateText(story.description, 90))}</p>` : ""}
        <div class="small text-secondary">相手: ${NovelUI.escape(story.character?.name || "未設定")}</div>
        <div class="d-flex gap-2 flex-wrap mt-3">
          <a class="btn btn-sm btn-outline-dark" href="/projects/${projectId}/stories/${story.id}/edit">編集</a>
          ${story.status === "published" ? renderStartForm(story) : ""}
          <button class="btn btn-sm btn-outline-dark" type="button" data-load-story-sessions="${story.id}">セッション履歴</button>
        </div>
        <div class="live-chat-room-session-list entity-history-list mt-3" id="storySessions-${story.id}"></div>
      </article>
    `).join("");
  }

  function renderStartForm(story) {
    return `
      <button class="btn btn-sm btn-dark" type="button" data-start-story="${story.id}">開始</button>
    `;
  }

  async function loadStorySessions(storyId) {
    return NovelUI.api(`/api/v1/stories/${storyId}/sessions`);
  }

  async function renderStorySessions(storyId, button = null) {
    const container = document.getElementById(`storySessions-${storyId}`);
    if (!container) return;
    await NovelUI.toggleLazyList({
      container,
      button,
      openLabel: "履歴を閉じる",
      closedLabel: "セッション履歴",
      loadingHtml: '<div class="empty-panel">セッション履歴を読み込み中...</div>',
      emptyHtml: '<div class="empty-panel">このストーリーのセッション履歴はまだありません。</div>',
      load: () => loadStorySessions(storyId),
      render: (sessions) => NovelUI.renderHistoryRows(sessions, {
        href: (item) => `/projects/${projectId}/story-sessions/${item.id}`,
        title: (item) => item.title || "セッション",
        meta: (item) => `${item.player_name || "player"} / ${NovelUI.formatDateTime(item.updated_at)}`,
      }),
    });
  }

  document.addEventListener("click", async (event) => {
    const reload = event.target.closest("#storyReloadButton");
    if (reload) {
      await loadStories();
      return;
    }
    const sessionsButton = event.target.closest("[data-load-story-sessions]");
    if (sessionsButton) {
      renderStorySessions(Number(sessionsButton.dataset.loadStorySessions), sessionsButton).catch((error) => {
        NovelUI.toast(error.message || "セッション履歴の取得に失敗しました。", "danger");
      });
      return;
    }
    const start = event.target.closest("[data-start-story]");
    if (!start) return;
    const storyId = Number(start.dataset.startStory);
    const originalLabel = start.textContent;
    start.disabled = true;
    start.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>準備中...';
    try {
      const created = await NovelUI.api(`/api/v1/stories/${storyId}/sessions`, {
        method: "POST",
        body: { generate_initial_image: true },
      });
      if (created.image_generation_error) {
        NovelUI.toast(`セッションは開始しましたが、初期画像生成に失敗しました: ${created.image_generation_error}`, "warning");
      } else {
        NovelUI.toast("セッションを開始し、初期画像を生成しました。");
      }
      window.location.href = `/projects/${projectId}/story-sessions/${created.id}`;
    } catch (error) {
      start.disabled = false;
      start.textContent = originalLabel;
      NovelUI.toast(error.message || "セッション開始に失敗しました。", "danger");
    }
  });

  loadStories().catch((error) => NovelUI.toast(error.message || "ストーリーを読み込めませんでした。", "danger"));
})();
