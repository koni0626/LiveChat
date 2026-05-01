(() => {
  const page = document.querySelector(".live-chat-room-page");
  const projectId = Number(page?.dataset.projectId || document.body.dataset.projectId || 0);
  const manageMode = page?.dataset.manageMode === "true";
  const roomGrid = document.getElementById("liveChatRoomGrid");
  if (!page || !projectId || !roomGrid) return;

  let rooms = [];

  async function loadRooms() {
    const data = await NovelUI.api(`/api/v1/projects/${projectId}/chat/available-rooms`);
    const loadedRooms = Array.isArray(data) ? data : [];
    rooms = manageMode ? loadedRooms : loadedRooms.filter((room) => (room.status || "draft") === "published");
    renderRooms();
  }

  async function loadMySessions(roomId) {
    return NovelUI.api(`/api/v1/chat/rooms/${roomId}/my-sessions`);
  }

  function renderRooms() {
    if (!rooms.length) {
      roomGrid.innerHTML = `<div class="empty-panel">${manageMode ? "まだルームがありません。新規追加から作成してください。" : "まだライブチャットは公開されていません。"}</div>`;
      return;
    }
    roomGrid.innerHTML = rooms.map((room) => {
      const characterName = room.character?.name || "キャラクター未設定";
      const characterThumb = room.character?.thumbnail_asset?.media_url || room.character?.base_asset?.media_url || "";
      const status = room.status || "draft";
      return `
        <article class="project-card live-chat-room-card entity-card-stable" data-room-id="${room.id}">
          <div class="project-card-top">
            <span class="badge text-bg-light">${manageMode ? NovelUI.escape(NovelUI.statusLabel(status)) : "ライブチャット"}</span>
            <span class="soft-code">${manageMode ? `${room.my_session_count || 0} sessions` : `履歴 ${room.my_session_count || 0}件`}</span>
          </div>
          <div class="live-chat-room-card-main">
            <div class="live-chat-room-character-thumb">
              ${characterThumb
                ? `<img src="${NovelUI.escape(characterThumb)}" alt="${NovelUI.escape(characterName)}">`
                : `<span>${NovelUI.escape((characterName || "?").slice(0, 1))}</span>`}
            </div>
            <div class="live-chat-room-card-copy">
              <h4>${NovelUI.escape(room.title || "ライブチャット")}</h4>
              <p class="live-chat-session-excerpt">${NovelUI.escape(NovelUI.truncateText(room.description || room.conversation_objective))}</p>
              <div class="small text-secondary">話す相手: ${NovelUI.escape(characterName)}</div>
            </div>
          </div>
          ${manageMode ? renderManageActions(room) : renderStartForm(room)}
          <div class="live-chat-room-session-list entity-history-list mt-3" id="roomSessions-${room.id}"></div>
        </article>
      `;
    }).join("");
  }

  function renderManageActions(room) {
    return `
      <div class="live-chat-room-actions">
        <a class="btn btn-sm btn-outline-dark" href="/projects/${projectId}/live-chat/rooms/${room.id}/edit">編集</a>
        <button class="btn btn-sm btn-outline-dark" type="button" data-load-room-sessions="${room.id}">チャット履歴</button>
        <button class="btn btn-sm btn-outline-danger" type="button" data-delete-room="${room.id}">削除</button>
      </div>
    `;
  }

  function renderStartForm(room) {
    return `
      <div class="live-chat-room-actions">
        <button class="btn btn-sm btn-outline-dark" type="button" data-load-room-sessions="${room.id}">過去のチャット</button>
      </div>
      <div class="live-chat-room-start">
        <button class="btn btn-dark" type="button" data-start-room="${room.id}">新しくチャット</button>
      </div>
    `;
  }

  async function startRoom(roomId, button = null) {
    const originalLabel = button?.textContent || "";
    if (button) {
      button.disabled = true;
      button.textContent = "準備中...";
    }
    const isMobileViewport = window.matchMedia("(max-width: 767.98px)").matches;
    const initialImageSize = isMobileViewport ? "1024x1536" : "1536x1024";
    try {
      const created = await NovelUI.api(`/api/v1/chat/rooms/${roomId}/sessions`, {
        method: "POST",
        body: {
          size: initialImageSize,
        },
      });
      if (created.image_generation_error) {
        NovelUI.toast(`会話は作成しましたが、初期画像生成に失敗しました: ${created.image_generation_error}`, "warning");
      } else {
        NovelUI.toast("会話セッションを開始し、初期画像を生成しました。");
      }
      window.location.href = `/projects/${projectId}/live-chat/${created.session.id}`;
    } catch (error) {
      if (button) {
        button.disabled = false;
        button.textContent = originalLabel;
      }
      throw error;
    }
  }

  async function renderRoomSessions(roomId, button = null) {
    const container = document.getElementById(`roomSessions-${roomId}`);
    if (!container) return;
    await NovelUI.toggleLazyList({
      container,
      button: button || document.querySelector(`[data-load-room-sessions="${roomId}"]`),
      openLabel: "履歴を閉じる",
      closedLabel: manageMode ? "チャット履歴" : "過去のチャット",
      loadingHtml: '<div class="empty-panel">履歴を読み込み中...</div>',
      emptyHtml: '<div class="empty-panel">このルームの自分の会話はまだありません。</div>',
      load: () => loadMySessions(roomId),
      render: (sessions) => NovelUI.renderHistoryRows(sessions, {
        href: (item) => `/projects/${projectId}/live-chat/${item.id}`,
        title: (item) => item.title || "会話セッション",
        meta: (item) => `${item.player_name || "player"} / ${item.message_count || 0} messages`,
      }),
    });
  }

  async function deleteRoom(roomId) {
    if (!window.confirm("このルームを削除しますか？既存の会話セッションは削除されません。")) return;
    await NovelUI.api(`/api/v1/chat/rooms/${roomId}`, { method: "DELETE" });
    NovelUI.toast("ルームを削除しました。");
    await loadRooms();
  }

  document.getElementById("liveChatReloadButton")?.addEventListener("click", () => {
    loadRooms().catch((error) => NovelUI.toast(error.message || "再読み込みに失敗しました。", "danger"));
  });

  roomGrid.addEventListener("click", (event) => {
    const startButton = event.target.closest("[data-start-room]");
    if (startButton) {
      startRoom(Number(startButton.dataset.startRoom), startButton).catch((error) => NovelUI.toast(error.message || "会話開始に失敗しました。", "danger"));
      return;
    }
    const sessionsButton = event.target.closest("[data-load-room-sessions]");
    if (sessionsButton) {
      renderRoomSessions(Number(sessionsButton.dataset.loadRoomSessions), sessionsButton).catch((error) => NovelUI.toast(error.message || "セッション一覧の取得に失敗しました。", "danger"));
      return;
    }
    const deleteButton = event.target.closest("[data-delete-room]");
    if (deleteButton) {
      deleteRoom(Number(deleteButton.dataset.deleteRoom)).catch((error) => NovelUI.toast(error.message || "ルーム削除に失敗しました。", "danger"));
    }
  });

  loadRooms().catch((error) => {
    NovelUI.toast(error.message || "ライブチャットルームの読み込みに失敗しました。", "danger");
  });
})();
