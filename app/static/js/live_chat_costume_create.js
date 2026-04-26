(function () {
  const root = document.querySelector(".costume-create-shell[data-session-id]");
  if (!root) return;

  const sessionId = Number(root.dataset.sessionId || 0);
  const form = document.getElementById("costumeCreateForm");
  const submitButton = document.getElementById("costumeCreateSubmitButton");
  const currentReference = document.getElementById("costumeCreateCurrentReference");
  const resultPanel = document.getElementById("costumeCreateResult");
  const resultActions = document.getElementById("costumeCreateResultActions");
  const costumeGrid = document.getElementById("costumeCreateGrid");

  function imageUrl(item) {
    return item?.asset?.media_url || "";
  }

  function renderImagePanel(container, item, emptyText, label) {
    if (!container) return;
    const mediaUrl = imageUrl(item);
    if (!mediaUrl) {
      container.innerHTML = `<div class="empty-panel">${emptyText}</div>`;
      return;
    }
    container.innerHTML = `
      <figure class="costume-create-image-card">
        <img src="${mediaUrl}" alt="${label}">
        <figcaption>${label}</figcaption>
      </figure>
    `;
  }

  function renderCostumeGrid(costumes) {
    if (!costumeGrid) return;
    if (!costumes.length) {
      costumeGrid.innerHTML = '<div class="empty-panel">衣装候補がありません。</div>';
      return;
    }
    costumeGrid.innerHTML = costumes.map((item) => {
      const mediaUrl = imageUrl(item);
      const label = item.image_type === "costume_initial" ? "初期衣装" : "衣装";
      return `
        <button class="live-chat-costume-card ${item.is_selected ? "selected" : ""}" type="button" data-costume-id="${item.id}">
          ${mediaUrl ? `<img src="${mediaUrl}" alt="${label}">` : "<span>No Image</span>"}
          <span class="live-chat-costume-card-label">${item.is_selected ? "選択中" : label}</span>
        </button>
      `;
    }).join("");
  }

  function setLoading(active) {
    if (!submitButton) return;
    submitButton.disabled = active;
    submitButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>生成中...'
      : "画像を生成";
  }

  async function loadContext() {
    const context = await LiveChatApi.loadContext(sessionId);
    const costumes = context.costumes || [];
    const selectedCostume = context.selected_costume || costumes.find((item) => item.is_selected) || costumes[0] || null;
    renderImagePanel(currentReference, selectedCostume, "現在の基準画像がありません。", "現在の基準画像");
    renderCostumeGrid(costumes);
    return context;
  }

  async function loadDefaultSettings() {
    try {
      const settings = await LiveChatApi.loadSettings();
      if (settings?.default_quality && form?.quality) {
        form.quality.value = settings.default_quality;
      }
    } catch (error) {
      // Defaults are enough if settings cannot be loaded.
    }
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const promptText = form.prompt_text.value.trim();
    if (!promptText) {
      NovelUI.toast("プロンプトを入力してください。", "warning");
      return;
    }
    setLoading(true);
    if (resultPanel) {
      resultPanel.innerHTML = '<div class="empty-panel"><span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>衣装画像を生成しています...</div>';
    }
    try {
      const result = await LiveChatApi.generateCostume(sessionId, {
        prompt_text: promptText,
        size: form.size.value,
        quality: form.quality.value,
      });
      renderImagePanel(resultPanel, result, "生成画像がありません。", "生成した衣装");
      if (resultActions) resultActions.hidden = false;
      form.prompt_text.value = "";
      await loadContext();
      NovelUI.toast("衣装を生成し、基準画像に設定しました。");
    } catch (error) {
      if (resultPanel) {
        resultPanel.innerHTML = '<div class="empty-panel">衣装生成に失敗しました。</div>';
      }
      NovelUI.toast(error.message || "衣装生成に失敗しました。", "danger");
    } finally {
      setLoading(false);
    }
  });

  costumeGrid?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-costume-id]");
    if (!button) return;
    try {
      await LiveChatApi.selectCostume(sessionId, button.dataset.costumeId);
      await loadContext();
      NovelUI.toast("衣装の基準画像を変更しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装の選択に失敗しました。", "danger");
    }
  });

  loadDefaultSettings().then(loadContext).catch((error) => {
    NovelUI.toast(error.message || "衣装生成画面の初期化に失敗しました。", "danger");
  });
})();
