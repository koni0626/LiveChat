(() => {
  const root = document.querySelector("[data-stamp-page]");
  if (!root) return;

  const projectId = Number(root.dataset.projectId || 0);
  const canManageProject = root.dataset.canManageProject === "true";
  const form = document.getElementById("stampGenerateForm");
  const characterSelect = document.getElementById("stampCharacterSelect");
  const filterCharacterSelect = document.getElementById("stampFilterCharacterSelect");
  const grid = document.getElementById("stampGrid");
  const countLabel = document.getElementById("stampCountLabel");
  const reloadButton = document.getElementById("stampReloadButton");
  const generateButton = document.getElementById("stampGenerateButton");
  const characterHint = document.getElementById("stampCharacterHint");
  let characters = [];
  let stamps = [];

  function characterLabel(character) {
    return character?.nickname && character.nickname !== character.name
      ? `${character.name} / ${character.nickname}`
      : character?.name || "Character";
  }

  function selectedCharacter() {
    const id = Number(characterSelect.value || 0);
    return characters.find((character) => Number(character.id) === id);
  }

  function renderCharacterOptions() {
    const options = characters.map((character) => `
      <option value="${character.id}" ${character.base_asset_id ? "" : "disabled"}>
        ${NovelUI.escape(characterLabel(character))}${character.base_asset_id ? "" : "（ベース画像なし）"}
      </option>
    `).join("");
    characterSelect.innerHTML = options || '<option value="">キャラクターがありません</option>';
    filterCharacterSelect.innerHTML = `<option value="">すべて</option>${characters.map((character) => `
      <option value="${character.id}">${NovelUI.escape(character.name || "Character")}</option>
    `).join("")}`;
    updateCharacterHint();
  }

  function updateCharacterHint() {
    const character = selectedCharacter();
    if (!character) {
      characterHint.textContent = "";
      return;
    }
    characterHint.textContent = character.base_asset_id
      ? `${character.name} のベース画像を参照して生成します。`
      : `${character.name} はベース画像がないため生成できません。`;
  }

  async function loadCharacters() {
    characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    renderCharacterOptions();
  }

  async function loadStamps() {
    const params = new URLSearchParams();
    if (filterCharacterSelect.value) params.set("character_id", filterCharacterSelect.value);
    const query = params.toString();
    stamps = await NovelUI.api(`/api/v1/projects/${projectId}/stamps${query ? `?${query}` : ""}`);
    renderStamps();
  }

  function renderStamps() {
    countLabel.textContent = `${stamps.length}件`;
    if (!stamps.length) {
      grid.innerHTML = '<div class="empty-panel">まだスタンプがありません。</div>';
      return;
    }
    grid.innerHTML = stamps.map((stamp) => `
      <article class="stamp-card">
        <button class="stamp-preview" type="button" data-preview-id="${stamp.asset_id}" aria-label="${NovelUI.escape(stamp.text || "スタンプ")}">
          <img src="${NovelUI.escape(stamp.media_url || "")}" alt="${NovelUI.escape(stamp.text || stamp.file_name || "stamp")}">
        </button>
        <div class="stamp-card-body">
          <strong>${NovelUI.escape(stamp.text || "スタンプ")}</strong>
          <span>${NovelUI.escape(stamp.character_name || "")}</span>
        </div>
        <div class="stamp-card-actions">
          <a class="btn btn-sm btn-outline-dark" href="${NovelUI.escape(stamp.media_url || "#")}" target="_blank" rel="noopener">
            <i class="bi bi-box-arrow-up-right"></i>
          </a>
          ${canManageProject ? `
            <button class="btn btn-sm btn-outline-danger" type="button" data-delete-id="${stamp.asset_id}">
              <i class="bi bi-trash"></i>
            </button>
          ` : ""}
        </div>
      </article>
    `).join("");
  }

  function openPreview(stamp) {
    if (!stamp?.media_url) return;
    let overlay = document.querySelector(".stamp-lightbox");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "stamp-lightbox";
      overlay.innerHTML = `
        <button class="stamp-lightbox-close" type="button" aria-label="閉じる"><i class="bi bi-x-lg"></i></button>
        <img alt="">
      `;
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay || event.target.closest(".stamp-lightbox-close")) {
          overlay.classList.remove("is-open");
        }
      });
      document.body.appendChild(overlay);
    }
    const image = overlay.querySelector("img");
    image.src = stamp.media_url;
    image.alt = stamp.text || "stamp";
    overlay.classList.add("is-open");
  }

  async function generateStamp(event) {
    event.preventDefault();
    const character = selectedCharacter();
    if (!character?.base_asset_id) {
      NovelUI.toast("ベース画像があるキャラクターを選んでください。", "warning");
      return;
    }
    const body = Object.fromEntries(new FormData(form).entries());
    generateButton.disabled = true;
    generateButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>生成中</span>';
    try {
      const stamp = await NovelUI.api(`/api/v1/projects/${projectId}/stamps/generate`, {
        method: "POST",
        body,
      });
      NovelUI.toast("スタンプを生成しました。");
      form.reset();
      characterSelect.value = String(character.id);
      document.getElementById("stampQualitySelect").value = "medium";
      document.getElementById("stampSizeSelect").value = "1024x1024";
      updateCharacterHint();
      stamps = [stamp, ...stamps];
      renderStamps();
    } catch (error) {
      NovelUI.toast(error.message || "スタンプ生成に失敗しました。", "danger");
    } finally {
      generateButton.disabled = false;
      generateButton.innerHTML = '<i class="bi bi-stars"></i><span>生成</span>';
    }
  }

  async function deleteStamp(assetId) {
    if (!window.confirm("このスタンプを削除しますか？")) return;
    await NovelUI.api(`/api/v1/projects/${projectId}/stamps/${assetId}`, { method: "DELETE" });
    stamps = stamps.filter((stamp) => Number(stamp.asset_id) !== Number(assetId));
    renderStamps();
    NovelUI.toast("スタンプを削除しました。");
  }

  characterSelect.addEventListener("change", updateCharacterHint);
  filterCharacterSelect.addEventListener("change", () => {
    loadStamps().catch((error) => NovelUI.toast(error.message || "スタンプを読み込めませんでした。", "danger"));
  });
  reloadButton.addEventListener("click", () => {
    loadStamps().catch((error) => NovelUI.toast(error.message || "スタンプを読み込めませんでした。", "danger"));
  });
  form.addEventListener("submit", generateStamp);
  grid.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-preview-id]");
    if (preview) {
      const stamp = stamps.find((item) => Number(item.asset_id) === Number(preview.dataset.previewId));
      openPreview(stamp);
      return;
    }
    const deleteButton = event.target.closest("[data-delete-id]");
    if (deleteButton) {
      deleteStamp(deleteButton.dataset.deleteId).catch((error) => NovelUI.toast(error.message || "削除に失敗しました。", "danger"));
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.querySelector(".stamp-lightbox")?.classList.remove("is-open");
  });

  Promise.all([loadCharacters(), loadStamps()]).catch((error) => {
    NovelUI.toast(error.message || "スタンプ画面の読み込みに失敗しました。", "danger");
  });
})();
