(() => {
  const root = document.querySelector("[data-character-line-rooms]");
  if (!root) return;

  const projectId = Number(root.dataset.characterLineRooms || 0);
  const grid = document.getElementById("lineRoomGrid");
  const form = document.getElementById("lineRoomCreateForm");
  const titleInput = document.getElementById("lineRoomTitleInput");
  const checks = document.getElementById("lineRoomCharacterChecks");
  const createButton = document.getElementById("lineRoomCreateButton");
  const selectAllButton = document.getElementById("lineRoomSelectAllButton");
  const clearButton = document.getElementById("lineRoomClearButton");
  const escapeText = (value) => NovelUI.escape(value ?? "");

  let characters = [];

  function characterAvatar(character, className = "line-avatar") {
    const url = character?.thumbnail_asset?.media_url;
    const name = character?.name || "?";
    if (url) return `<img class="${className}" src="${escapeText(url)}" alt="${escapeText(name)}">`;
    return `<div class="${className}">${escapeText(name.slice(0, 1) || "?")}</div>`;
  }

  function renderChecks() {
    if (!characters.length) {
      checks.innerHTML = '<div class="empty-panel mb-0">キャラクターがまだいません。</div>';
      return;
    }
    checks.innerHTML = characters.map((character) => `
      <label class="line-character-check">
        <input type="checkbox" value="${character.id}">
        ${characterAvatar(character, "line-avatar line-avatar-small")}
        <span>${escapeText(character.name || "Character")}</span>
      </label>
    `).join("");
  }

  function renderRooms(rooms) {
    if (!rooms.length) {
      grid.innerHTML = '<div class="empty-panel mb-0">まだルームがありません。</div>';
      return;
    }
    grid.innerHTML = rooms.map((room) => {
      const latest = room.latest_message?.body || room.last_theme || "まだ会話はありません。";
      const badge = room.is_default ? '<span class="line-room-badge">全員</span>' : "";
      return `
        <a class="line-room-card" href="/projects/${projectId}/line/rooms/${room.id}">
          <div class="line-room-card-main">
            <div class="line-room-icon"><i class="bi bi-chat-left-heart"></i></div>
            <div>
              <div class="line-room-title">${escapeText(room.title || "LINE")}${badge}</div>
              <div class="line-room-preview">${escapeText(latest)}</div>
            </div>
          </div>
          <div class="line-room-count"><i class="bi bi-people"></i>${Number(room.participant_count || 0)}</div>
        </a>
      `;
    }).join("");
  }

  function selectedParticipantIds() {
    return [...checks.querySelectorAll("input[type='checkbox']:checked")].map((input) => Number(input.value));
  }

  async function load() {
    try {
      const [loadedCharacters, rooms] = await Promise.all([
        NovelUI.api(`/api/v1/projects/${projectId}/characters`),
        NovelUI.api(`/api/v1/projects/${projectId}/line/rooms`),
      ]);
      characters = Array.isArray(loadedCharacters) ? loadedCharacters : [];
      renderChecks();
      renderRooms(Array.isArray(rooms) ? rooms : []);
    } catch (error) {
      NovelUI.toast(error.message || "LINEルームの読み込みに失敗しました。", "danger");
    }
  }

  selectAllButton?.addEventListener("click", () => {
    checks.querySelectorAll("input[type='checkbox']").forEach((input) => { input.checked = true; });
  });

  clearButton?.addEventListener("click", () => {
    checks.querySelectorAll("input[type='checkbox']").forEach((input) => { input.checked = false; });
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    createButton.disabled = true;
    try {
      const room = await NovelUI.api(`/api/v1/projects/${projectId}/line/rooms`, {
        method: "POST",
        body: {
          title: titleInput.value.trim(),
          participant_ids: selectedParticipantIds(),
        },
      });
      location.href = `/projects/${projectId}/line/rooms/${room.id}`;
    } catch (error) {
      NovelUI.toast(error.message || "ルーム作成に失敗しました。", "danger");
    } finally {
      createButton.disabled = false;
    }
  });

  load();
})();
