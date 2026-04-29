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
  const uploadForm = document.getElementById("costumeUploadForm");
  const uploadInput = document.getElementById("costumeUploadInput");
  const uploadDrop = document.getElementById("costumeUploadDrop");
  const uploadPreview = document.getElementById("costumeUploadPreview");
  const uploadPreviewImage = document.getElementById("costumeUploadPreviewImage");
  const uploadPreviewName = document.getElementById("costumeUploadPreviewName");
  const uploadSubmitButton = document.getElementById("costumeUploadSubmitButton");
  let selectedUploadFile = null;

  function imageUrl(item) {
    return item?.asset?.media_url || "";
  }

  function renderImagePanel(container, item, emptyText, label) {
    if (!container) return;
    const mediaUrl = imageUrl(item);
    if (!mediaUrl) {
      container.innerHTML = `<div class="empty-panel">${NovelUI.escape(emptyText)}</div>`;
      return;
    }
    container.innerHTML = `
      <figure class="costume-create-image-card" data-result-costume-id="${NovelUI.escape(item.id || "")}">
        <img src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(label)}">
        <figcaption>${NovelUI.escape(label)}</figcaption>
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
      const deleteButton = item.image_type === "costume_reference" && !item.is_shared
        ? `<button class="live-chat-costume-delete" type="button" data-delete-costume-id="${NovelUI.escape(item.id)}" aria-label="衣装を削除" title="衣装を削除">削除</button>`
        : "";
      return `
        <div class="live-chat-costume-card ${item.is_selected ? "selected" : ""}">
          <button class="live-chat-costume-select" type="button" data-costume-id="${NovelUI.escape(item.id)}">
            ${mediaUrl ? `<img src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(label)}">` : "<span>No Image</span>"}
            <span class="live-chat-costume-card-label">${item.is_selected ? "選択中" : NovelUI.escape(label)}</span>
          </button>
          ${deleteButton}
        </div>
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

  function setUploadLoading(active) {
    if (!uploadSubmitButton) return;
    uploadSubmitButton.disabled = active;
    uploadSubmitButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>登録中...'
      : "衣装として登録";
  }

  function setUploadFile(file) {
    selectedUploadFile = file || null;
    if (!selectedUploadFile) {
      uploadPreview?.classList.add("is-hidden");
      uploadPreviewImage?.removeAttribute("src");
      if (uploadPreviewName) uploadPreviewName.textContent = "";
      return;
    }
    if (uploadPreviewImage) {
      uploadPreviewImage.src = URL.createObjectURL(selectedUploadFile);
    }
    if (uploadPreviewName) {
      uploadPreviewName.textContent = selectedUploadFile.name;
    }
    uploadPreview?.classList.remove("is-hidden");
  }

  async function loadContext() {
    const context = await StoryCostumeApi.loadContext(sessionId);
    const costumes = context.costumes || [];
    const selectedCostume = context.selected_costume || costumes.find((item) => item.is_selected) || costumes[0] || null;
    renderImagePanel(currentReference, selectedCostume, "現在の基準画像がありません。", "現在の基準画像");
    renderCostumeGrid(costumes);
    return context;
  }

  async function loadDefaultSettings() {
    try {
      const settings = await StoryCostumeApi.loadSettings();
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
      const result = await StoryCostumeApi.generateCostume(sessionId, {
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

  uploadInput?.addEventListener("change", () => {
    setUploadFile(uploadInput.files?.[0] || null);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    uploadDrop?.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadDrop.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    uploadDrop?.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadDrop.classList.remove("is-dragover");
    });
  });

  uploadDrop?.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0] || null;
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("画像ファイルを選択してください。", "warning");
      return;
    }
    if (uploadInput) {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      uploadInput.files = transfer.files;
    }
    setUploadFile(file);
  });

  uploadForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = selectedUploadFile || uploadInput?.files?.[0];
    if (!file) {
      NovelUI.toast("衣装画像を選択してください。", "warning");
      return;
    }
    setUploadLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("prompt_text", "衣装ルームでアップロードした衣装画像");
      const result = await StoryCostumeApi.uploadCostume(sessionId, formData);
      renderImagePanel(resultPanel, result, "アップロード画像がありません。", "登録した衣装");
      if (resultActions) resultActions.hidden = false;
      uploadForm.reset();
      setUploadFile(null);
      await loadContext();
      NovelUI.toast("アップロード画像を衣装として登録しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装画像のアップロードに失敗しました。", "danger");
    } finally {
      setUploadLoading(false);
    }
  });

  costumeGrid?.addEventListener("click", async (event) => {
    if (event.target.closest("[data-delete-costume-id]")) return;
    const button = event.target.closest("[data-costume-id]");
    if (!button) return;
    try {
      await StoryCostumeApi.selectCostume(sessionId, button.dataset.costumeId);
      await loadContext();
      NovelUI.toast("衣装の基準画像を変更しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装の選択に失敗しました。", "danger");
    }
  });

  costumeGrid?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-delete-costume-id]");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm("この衣装を削除しますか？")) return;
    button.disabled = true;
    try {
      const deletedId = Number(button.dataset.deleteCostumeId || 0);
      await StoryCostumeApi.deleteCostume(sessionId, deletedId);
      if (resultPanel?.querySelector(`[data-result-costume-id="${deletedId}"]`)) {
        resultPanel.innerHTML = '<div class="empty-panel">削除済みの衣装です。</div>';
        if (resultActions) resultActions.hidden = true;
      }
      await loadContext();
      NovelUI.toast("衣装を削除しました。");
    } catch (error) {
      button.disabled = false;
      NovelUI.toast(error.message || "衣装の削除に失敗しました。", "danger");
    }
  });

  loadDefaultSettings().then(loadContext).catch((error) => {
    NovelUI.toast(error.message || "衣装生成画面の初期化に失敗しました。", "danger");
  });
})();
