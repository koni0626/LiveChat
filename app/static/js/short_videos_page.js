document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-short-video-page]");
  if (!root) return;
  if (!window.NovelUI) return;
  const NovelUI = window.NovelUI;
  const projectId = Number(root.dataset.projectId || 0);
  const createForm = document.getElementById("shortVideoCreateForm");
  const videoList = document.getElementById("shortVideoList");
  const editorPanel = document.getElementById("shortVideoEditorPanel");
  const editorTitle = document.getElementById("shortVideoEditorTitle");
  const exportButton = document.getElementById("shortVideoExportButton");
  const bgmSelect = document.getElementById("shortVideoBgmSelect");
  const bgmVolumeSelect = document.getElementById("shortVideoBgmVolumeSelect");
  const bgmUploadInput = document.getElementById("shortVideoBgmUploadInput");
  const sceneThumbs = document.getElementById("shortVideoSceneThumbs");
  const preview = document.getElementById("shortVideoPreview");
  const characterPicker = document.getElementById("shortVideoCharacterPicker");
  const scenePrompt = document.getElementById("shortVideoScenePrompt");
  const headline = document.getElementById("shortVideoHeadline");
  const revisionNote = document.getElementById("shortVideoRevisionNote");
  const historyGrid = document.getElementById("shortVideoHistory");
  const statusBox = document.getElementById("shortVideoStatus");
  const saveButton = document.getElementById("shortVideoSaveScene");
  const generateButton = document.getElementById("shortVideoGenerateScene");
  const addButton = document.getElementById("shortVideoAddScene");
  const copyButton = document.getElementById("shortVideoCopyScene");
  const deleteButton = document.getElementById("shortVideoDeleteScene");
  const escape = NovelUI.escape;

  let videos = [];
  let characters = [];
  let bgmAssets = [];
  let activeVideo = null;
  let activeSceneIndex = 0;
  let draggingSceneIndex = null;
  let suppressSceneClick = false;

  function scenes() {
    return activeVideo?.chapters?.[0]?.scene_json || [];
  }

  function chapter() {
    return activeVideo?.chapters?.[0] || null;
  }

  function activeScene() {
    return scenes()[activeSceneIndex] || null;
  }

  function imageUrl(scene) {
    return scene?.still_asset?.media_url || scene?.background_asset?.media_url || "";
  }

  function selectedCharacterIds() {
    return Array.from(characterPicker.querySelectorAll("input[type='checkbox']:checked"))
      .map((input) => Number(input.value))
      .filter(Boolean);
  }

  function setStatus(message, type = "") {
    if (!statusBox) return;
    statusBox.classList.toggle("text-danger", type === "danger");
    statusBox.classList.toggle("text-success", type === "success");
    statusBox.textContent = message || "";
  }

  function bgmStorageKey() {
    return `shortVideoBgm:${projectId}`;
  }

  function selectedBgmQuery() {
    const bgmAssetId = Number(bgmSelect?.value || 0);
    if (!bgmAssetId) return "";
    const params = new URLSearchParams({
      bgm_asset_id: String(bgmAssetId),
      bgm_volume: String(bgmVolumeSelect?.value || "0.45"),
    });
    return `?${params.toString()}`;
  }

  function persistBgmSettings() {
    if (!bgmSelect || !bgmVolumeSelect) return;
    window.localStorage?.setItem?.(bgmStorageKey(), JSON.stringify({
      bgm_asset_id: bgmSelect.value || "",
      bgm_volume: bgmVolumeSelect.value || "0.45",
    }));
  }

  function restoreBgmSettings() {
    const raw = window.localStorage?.getItem?.(bgmStorageKey());
    if (!raw) return;
    try {
      const settings = JSON.parse(raw);
      if (bgmSelect && [...bgmSelect.options].some((option) => option.value === String(settings.bgm_asset_id || ""))) {
        bgmSelect.value = String(settings.bgm_asset_id || "");
      }
      if (bgmVolumeSelect && [...bgmVolumeSelect.options].some((option) => option.value === String(settings.bgm_volume || ""))) {
        bgmVolumeSelect.value = String(settings.bgm_volume || "0.45");
      }
    } catch (_error) {
      window.localStorage?.removeItem?.(bgmStorageKey());
    }
  }

  function updateExportHref() {
    if (!exportButton || !activeVideo) return;
    exportButton.href = `/api/v1/cinema-novels/${activeVideo.id}/comic-short-video${selectedBgmQuery()}`;
  }

  function bgmLabel(asset) {
    return String(asset?.display_name || asset?.metadata?.original_file_name || asset?.file_name || "BGM").trim();
  }

  function renderBgmOptions() {
    if (!bgmSelect) return;
    const current = bgmSelect.value;
    bgmSelect.innerHTML = [
      `<option value="">BGMなし</option>`,
      ...bgmAssets.map((asset) => `<option value="${escape(asset.id)}">${escape(bgmLabel(asset))}</option>`),
    ].join("");
    if ([...bgmSelect.options].some((option) => option.value === current)) {
      bgmSelect.value = current;
    }
    restoreBgmSettings();
    updateExportHref();
  }

  async function uploadBgmAsset(file) {
    if (!file || !bgmUploadInput) return;
    const label = bgmUploadInput.closest("label");
    const labelSpan = label?.querySelector("span");
    const originalHtml = labelSpan?.innerHTML;
    if (labelSpan) labelSpan.innerHTML = `<span class="spinner-border spinner-border-sm"></span> アップロード中`;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`/api/v1/projects/${projectId}/cinema-novels/bgm`, {
        method: "POST",
        credentials: "same-origin",
        body: formData,
      });
      const payload = await response.json().catch(() => ({}));
      const data = payload?.data || payload;
      if (!response.ok) throw new Error(data?.message || payload?.message || `HTTP ${response.status}`);
      bgmAssets = await NovelUI.api(`/api/v1/projects/${projectId}/cinema-novels/bgm`);
      renderBgmOptions();
      if (bgmSelect) bgmSelect.value = String(data.id);
      persistBgmSettings();
      updateExportHref();
      setStatus("BGMをアップロードしました。", "success");
    } finally {
      bgmUploadInput.value = "";
      if (labelSpan) labelSpan.innerHTML = originalHtml || `<i class="bi bi-music-note-beamed"></i> BGMをアップロード`;
    }
  }

  function renderList() {
    if (!videoList) return;
    videoList.innerHTML = videos.length ? videos.map((video) => `
      <button class="short-video-list-item ${activeVideo?.id === video.id ? "is-active" : ""}" type="button" data-short-video-id="${video.id}">
        <strong>${escape(video.title || "ショート動画")}</strong>
        <span>${(video.chapters?.[0]?.scene_json || []).length} scenes / ${NovelUI.statusLabel(video.status)}</span>
      </button>
    `).join("") : `<div class="cinema-comic-editor-empty">まだショート動画がありません。</div>`;
  }

  function renderCharacters(scene) {
    const selected = new Set((scene?.character_ids || []).map(Number));
    characterPicker.innerHTML = characters.length ? characters.map((character) => `
      <label class="short-video-character-chip ${selected.has(Number(character.id)) ? "is-selected" : ""}">
        <input type="checkbox" value="${character.id}" ${selected.has(Number(character.id)) ? "checked" : ""}>
        <span>${escape(character.name || character.nickname || "Character")}</span>
      </label>
    `).join("") : `<div class="cinema-comic-editor-empty">参照できるキャラクターがありません。</div>`;
  }

  function renderEditor() {
    renderList();
    if (!activeVideo) {
      editorPanel.hidden = true;
      return;
    }
    editorPanel.hidden = false;
    const list = scenes();
    activeSceneIndex = Math.max(0, Math.min(activeSceneIndex, Math.max(0, list.length - 1)));
    const scene = activeScene();
    editorTitle.textContent = `ショート動画編集: ${activeVideo.title || ""}`;
    updateExportHref();
    sceneThumbs.innerHTML = list.map((item, index) => {
      const url = imageUrl(item);
      return `
        <button class="cinema-comic-editor-thumb ${index === activeSceneIndex ? "is-active" : ""}" type="button" draggable="true" data-scene-index="${index}" title="ドラッグで順番を入れ替え">
          ${url ? `<img src="${escape(url)}" alt="">` : `<span class="cinema-comic-editor-noimage">No image</span>`}
          <strong>${index + 1}</strong>
          <small>${escape(item.caption || item.image_prompt || "").slice(0, 44)}</small>
        </button>
      `;
    }).join("");
    const url = imageUrl(scene);
    preview.innerHTML = url
      ? `<img src="${escape(url)}" alt=""><p>${escape(scene?.caption || "")}</p>`
      : `<div class="cinema-comic-editor-empty">このシーンにはまだ画像がありません。</div>`;
    renderCharacters(scene);
    scenePrompt.value = scene?.image_prompt || scene?.visual_focus || "";
    headline.value = scene?.caption || scene?.text || "";
    revisionNote.value = "";
    const history = Array.isArray(scene?.still_asset_history) ? scene.still_asset_history : [];
    historyGrid.innerHTML = history.length ? history.map((asset, index) => `
      <button class="cinema-comic-editor-history-item" type="button" data-history-asset-id="${asset.id}">
        <img src="${escape(asset.media_url || "")}" alt="">
        <span>履歴 ${index + 1}</span>
      </button>
    `).join("") : `<div class="cinema-comic-editor-history-empty">画像を再生成すると前の画像がここに残ります。</div>`;
  }

  async function loadAll() {
    const [videoPayload, characterPayload] = await Promise.all([
      NovelUI.api(`/api/v1/projects/${projectId}/short-videos`),
      NovelUI.api(`/api/v1/projects/${projectId}/characters`),
    ]);
    videos = Array.isArray(videoPayload) ? videoPayload : [];
    characters = Array.isArray(characterPayload) ? characterPayload : [];
    if (bgmSelect) {
      bgmAssets = await NovelUI.api(`/api/v1/projects/${projectId}/cinema-novels/bgm`);
      renderBgmOptions();
    }
    if (!activeVideo && videos.length) activeVideo = videos[0];
    if (activeVideo) {
      activeVideo = videos.find((item) => Number(item.id) === Number(activeVideo.id)) || activeVideo;
    }
    renderEditor();
  }

  async function refreshActive() {
    if (!activeVideo) return;
    activeVideo = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}`);
    const index = videos.findIndex((item) => Number(item.id) === Number(activeVideo.id));
    if (index >= 0) videos[index] = activeVideo;
    else videos.unshift(activeVideo);
    renderEditor();
  }

  async function createVideo(event) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(createForm).entries());
    const created = await NovelUI.api(`/api/v1/projects/${projectId}/short-videos`, {
      method: "POST",
      body,
    });
    activeVideo = created;
    activeSceneIndex = 0;
    createForm.reset();
    await loadAll();
    setStatus("ショート動画を作成しました。", "success");
  }

  async function saveScene({ silent = false } = {}) {
    const item = activeScene();
    const currentChapter = chapter();
    if (!activeVideo || !item || !currentChapter) return null;
    if (!silent) setStatus("保存中...");
    const result = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}/comic-scenes`, {
      method: "PUT",
      body: {
        chapter_id: currentChapter.id,
        scene_index: activeSceneIndex,
        caption: headline.value,
        image_prompt: scenePrompt.value,
        visual_focus: scenePrompt.value,
        character_ids: selectedCharacterIds(),
      },
    });
    activeVideo = result.novel || activeVideo;
    renderEditor();
    if (!silent) setStatus("保存しました。", "success");
    return result;
  }

  async function generateScene() {
    generateButton.disabled = true;
    saveButton.disabled = true;
    const original = generateButton.innerHTML;
    generateButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 生成中`;
    setStatus("画像を生成しています...");
    try {
      const scenePromptValue = scenePrompt.value;
      const headlineValue = headline.value;
      const revisionValue = revisionNote.value.trim();
      const characterIds = selectedCharacterIds();
      await saveScene({ silent: true });
      const imagePrompt = [scenePromptValue, revisionValue ? `Revision note: ${revisionValue}` : ""].filter(Boolean).join("\n");
      const result = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}/comic-scenes/regenerate`, {
        method: "POST",
        body: {
          chapter_id: chapter().id,
          scene_index: activeSceneIndex,
          caption: headlineValue,
          image_prompt: imagePrompt,
          visual_focus: scenePromptValue,
          character_ids: characterIds,
          revision_prompt: revisionValue,
          use_current_image: false,
        },
      });
      activeVideo = result.novel || activeVideo;
      renderEditor();
      const failed = (result.failed_assets || []).length;
      setStatus(failed ? "画像生成に失敗したシーンがあります。" : "画像を生成しました。", failed ? "danger" : "success");
      await loadAll();
    } finally {
      generateButton.disabled = false;
      saveButton.disabled = false;
      generateButton.innerHTML = original;
    }
  }

  async function mutateScene(operation) {
    if (!activeVideo || !chapter()) return;
    if (operation === "delete" && !window.confirm("このシーンを削除しますか？")) return;
    await saveScene({ silent: true }).catch(() => {});
    const result = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}/comic-scenes/mutate`, {
      method: "POST",
      body: {
        chapter_id: chapter().id,
        scene_index: activeSceneIndex,
        operation,
        caption: headline.value || "新しいシーン",
        image_prompt: scenePrompt.value,
        character_ids: selectedCharacterIds(),
      },
    });
    activeVideo = result.novel || activeVideo;
    activeSceneIndex = Number(result.scene_index || 0);
    renderEditor();
    setStatus("シーン構成を更新しました。", "success");
    await loadAll();
  }

  async function reorderScene(fromIndex, toIndex) {
    if (!activeVideo || !chapter()) return;
    if (fromIndex === toIndex) return;
    const previousActiveId = activeScene()?.id || "";
    await saveScene({ silent: true }).catch(() => {});
    const result = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}/comic-scenes/mutate`, {
      method: "POST",
      body: {
        chapter_id: chapter().id,
        scene_index: activeSceneIndex,
        operation: "reorder",
        from_scene_index: fromIndex,
        to_scene_index: toIndex,
      },
    });
    activeVideo = result.novel || activeVideo;
    const nextScenes = scenes();
    const activeById = nextScenes.findIndex((item) => item?.id && item.id === previousActiveId);
    activeSceneIndex = activeById >= 0 ? activeById : Number(result.scene_index || 0);
    renderEditor();
    setStatus("シーンの順番を入れ替えました。", "success");
    await loadAll();
  }

  async function selectHistory(assetId) {
    if (!activeVideo || !chapter() || !assetId) return;
    const result = await NovelUI.api(`/api/v1/cinema-novels/${activeVideo.id}/comic-scenes`, {
      method: "PUT",
      body: {
        chapter_id: chapter().id,
        scene_index: activeSceneIndex,
        selected_asset_id: Number(assetId),
      },
    });
    activeVideo = result.novel || activeVideo;
    renderEditor();
    setStatus("履歴画像を反映しました。", "success");
  }

  createForm?.addEventListener("submit", (event) => createVideo(event).catch((error) => NovelUI.toast(error.message || "作成に失敗しました。", "danger")));
  videoList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-short-video-id]");
    if (!button) return;
    activeVideo = videos.find((item) => Number(item.id) === Number(button.dataset.shortVideoId)) || null;
    activeSceneIndex = 0;
    renderEditor();
  });
  sceneThumbs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-scene-index]");
    if (!button) return;
    if (suppressSceneClick) {
      suppressSceneClick = false;
      return;
    }
    activeSceneIndex = Number(button.dataset.sceneIndex || 0);
    renderEditor();
  });
  sceneThumbs?.addEventListener("dragstart", (event) => {
    const button = event.target.closest("[data-scene-index]");
    if (!button) return;
    draggingSceneIndex = Number(button.dataset.sceneIndex || 0);
    suppressSceneClick = true;
    button.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(draggingSceneIndex));
  });
  sceneThumbs?.addEventListener("dragover", (event) => {
    const button = event.target.closest("[data-scene-index]");
    if (!button || draggingSceneIndex === null) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    sceneThumbs.querySelectorAll(".is-drop-target").forEach((item) => item.classList.remove("is-drop-target"));
    button.classList.add("is-drop-target");
  });
  sceneThumbs?.addEventListener("dragleave", (event) => {
    const button = event.target.closest("[data-scene-index]");
    if (button && !button.contains(event.relatedTarget)) button.classList.remove("is-drop-target");
  });
  sceneThumbs?.addEventListener("drop", (event) => {
    const button = event.target.closest("[data-scene-index]");
    if (!button || draggingSceneIndex === null) return;
    event.preventDefault();
    const fromIndex = draggingSceneIndex;
    const toIndex = Number(button.dataset.sceneIndex || 0);
    draggingSceneIndex = null;
    sceneThumbs.querySelectorAll(".is-dragging, .is-drop-target").forEach((item) => item.classList.remove("is-dragging", "is-drop-target"));
    reorderScene(fromIndex, toIndex).catch((error) => NovelUI.toast(error.message || "並び替えに失敗しました。", "danger"));
  });
  sceneThumbs?.addEventListener("dragend", () => {
    draggingSceneIndex = null;
    sceneThumbs.querySelectorAll(".is-dragging, .is-drop-target").forEach((item) => item.classList.remove("is-dragging", "is-drop-target"));
    window.setTimeout(() => {
      suppressSceneClick = false;
    }, 0);
  });
  characterPicker?.addEventListener("change", () => {
    characterPicker.querySelectorAll(".short-video-character-chip").forEach((label) => {
      label.classList.toggle("is-selected", Boolean(label.querySelector("input")?.checked));
    });
  });
  saveButton?.addEventListener("click", () => saveScene().catch((error) => NovelUI.toast(error.message || "保存に失敗しました。", "danger")));
  generateButton?.addEventListener("click", () => generateScene().catch((error) => {
    setStatus(error.message || "画像生成に失敗しました。", "danger");
    NovelUI.toast(error.message || "画像生成に失敗しました。", "danger");
  }));
  addButton?.addEventListener("click", () => mutateScene("add_after").catch((error) => NovelUI.toast(error.message || "追加に失敗しました。", "danger")));
  copyButton?.addEventListener("click", () => mutateScene("copy_after").catch((error) => NovelUI.toast(error.message || "コピーに失敗しました。", "danger")));
  deleteButton?.addEventListener("click", () => mutateScene("delete").catch((error) => NovelUI.toast(error.message || "削除に失敗しました。", "danger")));
  bgmSelect?.addEventListener("change", () => {
    persistBgmSettings();
    updateExportHref();
  });
  bgmVolumeSelect?.addEventListener("change", () => {
    persistBgmSettings();
    updateExportHref();
  });
  bgmUploadInput?.addEventListener("change", () => {
    uploadBgmAsset(bgmUploadInput.files?.[0]).catch((error) => NovelUI.toast(error.message || "BGMアップロードに失敗しました。", "danger"));
  });
  historyGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-history-asset-id]");
    if (button) selectHistory(button.dataset.historyAssetId).catch((error) => NovelUI.toast(error.message || "履歴画像の反映に失敗しました。", "danger"));
  });

  loadAll().catch((error) => NovelUI.toast(error.message || "ショート動画の読み込みに失敗しました。", "danger"));
});
