(() => {
  const page = document.querySelector("[data-character-list-page]");
  if (!page) return;

  const projectId = Number(page.dataset.projectId);
  const canManageProject = page.dataset.canManageProject === "true";
  const form = document.getElementById("characterSearchForm");
  const grid = document.getElementById("characterGrid");
  if (!projectId || !form || !grid) return;

  function escapeText(value) {
    return NovelUI.escape(value || "");
  }

  function renderThumbnail(character) {
    const url = character.bromide_asset?.media_url || character.thumbnail_asset?.media_url || character.base_asset?.media_url;
    if (!url) {
      return `
        <div class="character-card-bromide character-card-placeholder">
          <i class="bi bi-person-bounding-box"></i>
          <span>No image</span>
        </div>
      `;
    }
    return `<img class="character-card-bromide" src="${escapeText(url)}" alt="${escapeText(character.name)}">`;
  }

  function renderCharacter(character) {
    const nickname = character.nickname ? `<span class="character-role-badge">${escapeText(character.nickname)}</span>` : "";
    const intro = character.introduction_text || character.character_summary || character.personality || "自己紹介文はまだ生成されていません。";
    const action = canManageProject
      ? `<div class="character-card-actions">
          <a class="btn btn-sm btn-outline-light character-edit-button" href="/projects/${projectId}/characters/${character.id}/edit">Edit</a>
          <button class="btn btn-sm btn-outline-danger character-delete-button" type="button" data-character-id="${character.id}">Delete</button>
        </div>`
      : "";
    const cardClass = "project-card character-list-card is-clickable";
    const clickableAttrs = `tabindex="0" role="button" aria-label="${escapeText(character.name)} home"`;

    return `
      <article class="${cardClass}" data-character-id="${character.id}" ${clickableAttrs}>
        <div class="character-card-copy">
          <div class="character-card-kicker">${nickname || "<span>PROFILE</span>"}</div>
          <h4>${escapeText(character.name)}</h4>
          <p class="character-card-introduction">${escapeText(intro)}</p>
          ${action}
        </div>
        <div class="character-card-media">
          ${renderThumbnail(character)}
        </div>
      </article>
    `;
  }

  function renderEmpty() {
    grid.innerHTML = `
      <div class="empty-panel span-12">
        <div class="empty-panel-icon"><i class="bi bi-people"></i></div>
        <div>
          <h3>キャラクターはまだ登録されていません</h3>
          <p>まずはワールドで会話するキャラクターを追加してください。</p>
        </div>
      </div>
    `;
  }

  async function loadCharacters() {
    const params = new URLSearchParams(new FormData(form));
    const query = params.get("search") ? `?${params.toString()}` : "";
    const characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters${query}`);
    if (!characters.length) {
      renderEmpty();
      return;
    }
    grid.innerHTML = characters.map(renderCharacter).join("");
  }

  async function deleteCharacter(characterId) {
    if (!canManageProject) return;
    if (!confirm("このキャラクターを削除しますか？削除後は一覧に表示されません。")) return;
    await NovelUI.api(`/api/v1/characters/${characterId}`, { method: "DELETE" });
    NovelUI.toast("キャラクターを削除しました。");
    await loadCharacters();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadCharacters().catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
  });

  grid.addEventListener("click", (event) => {
    const deleteButton = event.target.closest(".character-delete-button");
    if (deleteButton) {
      event.stopPropagation();
      deleteCharacter(Number(deleteButton.dataset.characterId)).catch((error) => {
        NovelUI.toast(error.message || "キャラクターの削除に失敗しました。", "danger");
      });
      return;
    }

    if (event.target.closest(".character-edit-button")) return;

    const card = event.target.closest("[data-character-id]");
    if (card) location.href = `/projects/${projectId}/characters/${card.dataset.characterId}/home`;
  });

  grid.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const card = event.target.closest("[data-character-id]");
    if (!card) return;
    event.preventDefault();
    location.href = `/projects/${projectId}/characters/${card.dataset.characterId}/home`;
  });

  loadCharacters().catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
})();
