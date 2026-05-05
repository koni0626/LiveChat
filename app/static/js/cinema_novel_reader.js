(function () {
  const shell = document.querySelector(".cinema-reader-shell");
  if (!shell) return;
  const novelId = Number(shell.dataset.novelId);
  const currentUserId = Number(shell.dataset.currentUserId || 0);
  const state = { novel: null, chapterIndex: 0, sceneIndex: 0, isEditingImage: false, isUploadingImage: false, isDeletingImage: false };

  const els = {
    title: document.getElementById("cinemaReaderTitle"),
    description: document.getElementById("cinemaReaderDescription"),
    speaker: document.getElementById("cinemaReaderSpeaker"),
    text: document.getElementById("cinemaReaderText"),
    position: document.getElementById("cinemaReaderPosition"),
    progressBar: document.getElementById("cinemaReaderProgressBar"),
    chapterSelect: document.getElementById("cinemaReaderChapterSelect"),
    chapterList: document.getElementById("cinemaReaderChapterList"),
    next: document.getElementById("cinemaReaderNextButton"),
    prev: document.getElementById("cinemaReaderPrevButton"),
    inlinePrev: document.getElementById("cinemaReaderInlinePrevButton"),
    bookmark: document.getElementById("cinemaReaderBookmarkButton"),
    continueButton: document.getElementById("cinemaReaderContinueButton"),
    stillWrap: document.getElementById("cinemaReaderStillWrap"),
    imageTools: document.getElementById("cinemaReaderImageTools"),
    imageEditButton: document.getElementById("cinemaReaderImageEditButton"),
    imageDeleteButton: document.getElementById("cinemaReaderImageDeleteButton"),
    imageEditModal: document.getElementById("cinemaReaderImageEditModal"),
    imageEditForm: document.getElementById("cinemaReaderImageEditForm"),
    imageEditPrompt: document.getElementById("cinemaReaderImageEditPrompt"),
    imageEditSubmit: document.getElementById("cinemaReaderImageEditSubmit"),
    imageUploadDrop: document.getElementById("cinemaReaderImageUploadDrop"),
    imageUploadInput: document.getElementById("cinemaReaderImageUploadInput"),
    imageUploadLabel: document.getElementById("cinemaReaderImageUploadLabel"),
  };

  if (els.imageEditModal && els.imageEditModal.parentElement !== document.body) {
    document.body.appendChild(els.imageEditModal);
  }

  const imageEditModal = els.imageEditModal && window.bootstrap?.Modal
    ? new window.bootstrap.Modal(els.imageEditModal)
    : null;

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    if (options.body && !isFormData && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.data?.message || "request failed");
    return payload.data;
  }

  function escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[ch]));
  }

  function chapters() {
    return state.novel?.chapters || [];
  }

  function currentChapter() {
    return chapters()[state.chapterIndex] || null;
  }

  function currentScenes() {
    return currentChapter()?.scene_json || [];
  }

  function currentScene() {
    return currentScenes()[state.sceneIndex] || null;
  }

  function totalScenesBeforeChapter(index) {
    return chapters().slice(0, index).reduce((sum, chapter) => sum + (chapter.scene_json || []).length, 0);
  }

  function totalSceneCount() {
    return chapters().reduce((sum, chapter) => sum + (chapter.scene_json || []).length, 0);
  }

  function sceneImageAsset(scene) {
    return scene?.still_asset || scene?.background_asset || null;
  }

  function currentSceneImageAsset() {
    return sceneImageAsset(currentScene());
  }

  function currentImageAsset(chapter) {
    const scenes = chapter?.scene_json || [];
    const currentAsset = sceneImageAsset(scenes[state.sceneIndex]);
    if (currentAsset?.media_url) return currentAsset;
    for (let chapterIndex = state.chapterIndex; chapterIndex >= 0; chapterIndex -= 1) {
      const chapterScenes = chapters()[chapterIndex]?.scene_json || [];
      const startIndex = chapterIndex === state.chapterIndex ? state.sceneIndex - 1 : chapterScenes.length - 1;
      for (let sceneIndex = startIndex; sceneIndex >= 0; sceneIndex -= 1) {
        const asset = sceneImageAsset(chapterScenes[sceneIndex]);
        if (asset?.media_url) return asset;
      }
    }
    return state.novel?.poster_asset || state.novel?.cover_asset || null;
  }

  function currentImageUrl(chapter) {
    return currentImageAsset(chapter)?.media_url || "";
  }

  function canEditImage(chapter) {
    return Boolean(
      currentUserId
      && state.novel?.created_by_user_id
      && Number(state.novel.created_by_user_id) === currentUserId
      && currentImageAsset(chapter)?.id
    );
  }

  function canUploadImage() {
    return Boolean(currentUserId && state.novel?.created_by_user_id && Number(state.novel.created_by_user_id) === currentUserId && currentChapter() && currentScene());
  }

  function canDeleteImage(chapter) {
    const displayed = currentImageAsset(chapter);
    const sceneAsset = currentSceneImageAsset();
    return Boolean(canUploadImage() && displayed?.id && sceneAsset?.id && Number(displayed.id) === Number(sceneAsset.id));
  }

  function renderStill(chapter) {
    const url = currentImageUrl(chapter);
    if (!url) {
      els.stillWrap.innerHTML = `
        <div class="cinema-reader-placeholder">
          <i class="bi bi-film"></i>
          <span>Prebuilt Novel</span>
        </div>
      `;
      return;
    }
    els.stillWrap.innerHTML = `<img src="${escape(url)}" alt="">`;
  }

  function renderChapterList() {
    els.chapterList.innerHTML = chapters().map((chapter, index) => `
      <button class="cinema-reader-chapter-button${index === state.chapterIndex ? " active" : ""}" type="button" data-chapter-index="${index}">
        <span>${String(chapter.chapter_no).padStart(2, "0")}</span>
        ${escape(chapter.title)}
      </button>
    `).join("");
  }

  function renderImageTools(chapter) {
    if (!els.imageTools) return;
    const hasEditPermission = canUploadImage();
    els.imageTools.hidden = !hasEditPermission;
    if (els.imageEditButton) {
      els.imageEditButton.disabled = state.isEditingImage || state.isUploadingImage || !hasEditPermission;
    }
    if (els.imageDeleteButton) {
      els.imageDeleteButton.disabled = state.isEditingImage || state.isUploadingImage || state.isDeletingImage || !canDeleteImage(chapter);
    }
  }

  function render() {
    const novel = state.novel;
    const chapter = currentChapter();
    const scene = currentScene();
    if (!novel || !chapter || !scene) return;
    els.title.textContent = novel.title;
    els.description.textContent = novel.subtitle || novel.description || "";
    const speaker = String(scene.speaker || "").trim();
    els.speaker.textContent = speaker;
    els.speaker.hidden = !speaker;
    els.text.textContent = scene.text || "";
    els.chapterSelect.value = String(chapter.id);
    const currentNo = totalScenesBeforeChapter(state.chapterIndex) + state.sceneIndex + 1;
    const totalNo = Math.max(1, totalSceneCount());
    els.position.textContent = `${chapter.chapter_no}. ${chapter.title} / ${state.sceneIndex + 1} scene`;
    els.progressBar.style.width = `${Math.min(100, Math.round((currentNo / totalNo) * 100))}%`;
    const isAtStart = state.chapterIndex === 0 && state.sceneIndex === 0;
    els.prev.disabled = isAtStart;
    if (els.inlinePrev) els.inlinePrev.disabled = isAtStart;
    els.next.textContent = currentNo >= totalNo ? "End" : "Next";
    renderStill(chapter);
    renderImageTools(chapter);
    renderChapterList();
    saveProgress(false).catch(() => {});
  }

  function goNext() {
    const scenes = currentScenes();
    if (state.sceneIndex < scenes.length - 1) {
      state.sceneIndex += 1;
    } else if (state.chapterIndex < chapters().length - 1) {
      state.chapterIndex += 1;
      state.sceneIndex = 0;
    }
    render();
  }

  function goPrev() {
    if (state.sceneIndex > 0) {
      state.sceneIndex -= 1;
    } else if (state.chapterIndex > 0) {
      state.chapterIndex -= 1;
      state.sceneIndex = Math.max(0, currentScenes().length - 1);
    }
    render();
  }

  async function saveProgress(showFeedback = true) {
    const chapter = currentChapter();
    if (!chapter) return;
    await api(`/api/v1/cinema-novels/${novelId}/progress`, {
      method: "PUT",
      body: JSON.stringify({
        chapter_id: chapter.id,
        scene_index: state.sceneIndex,
        page_index: 0,
      }),
    });
    if (showFeedback) {
      els.bookmark.innerHTML = `<i class="bi bi-bookmark-check-fill"></i> 保存済み`;
      window.setTimeout(() => {
        els.bookmark.innerHTML = `<i class="bi bi-bookmark-check"></i> 栞`;
      }, 1200);
    }
  }

  function applyProgress(progress) {
    if (!progress) return;
    const index = chapters().findIndex((chapter) => chapter.id === progress.chapter_id);
    if (index >= 0) {
      state.chapterIndex = index;
      state.sceneIndex = Math.max(0, Math.min(progress.scene_index || 0, (chapters()[index].scene_json || []).length - 1));
    }
  }

  function restorePosition(chapterId, sceneIndex) {
    const index = chapters().findIndex((chapter) => chapter.id === chapterId);
    if (index < 0) return;
    state.chapterIndex = index;
    state.sceneIndex = Math.max(0, Math.min(sceneIndex, (chapters()[index].scene_json || []).length - 1));
  }

  async function submitImageEdit(event) {
    event.preventDefault();
    const prompt = String(els.imageEditPrompt?.value || "").trim();
    const chapter = currentChapter();
    const asset = currentImageAsset(chapter);
    if (!prompt || !chapter || !asset?.id || state.isEditingImage) return;
    const previousChapterId = chapter.id;
    const previousSceneIndex = state.sceneIndex;
    state.isEditingImage = true;
    renderImageTools(chapter);
    els.imageEditSubmit.disabled = true;
    els.imageEditSubmit.querySelector(".spinner-border")?.removeAttribute("hidden");
    try {
      const result = await api(`/api/v1/cinema-novels/${novelId}/image-edit`, {
        method: "POST",
        body: JSON.stringify({
          prompt,
          chapter_id: chapter.id,
          scene_index: state.sceneIndex,
          source_asset_id: asset.id,
        }),
      });
      state.novel = result.novel;
      restorePosition(previousChapterId, previousSceneIndex);
      imageEditModal?.hide();
      els.imageEditPrompt.value = "";
      render();
    } catch (error) {
      window.alert(error.message || "画像の変更に失敗しました");
    } finally {
      state.isEditingImage = false;
      els.imageEditSubmit.disabled = false;
      els.imageEditSubmit.querySelector(".spinner-border")?.setAttribute("hidden", "");
      renderImageTools(currentChapter());
    }
  }

  async function uploadSceneImage(file) {
    if (!file || state.isUploadingImage) return;
    if (!String(file.type || "").startsWith("image/")) {
      window.NovelUI?.toast?.("画像ファイルを選択してください。", "danger");
      return;
    }
    const chapter = currentChapter();
    if (!chapter || !currentScene()) return;
    const previousChapterId = chapter.id;
    const previousSceneIndex = state.sceneIndex;
    const body = new FormData();
    body.append("file", file);
    body.append("chapter_id", String(chapter.id));
    body.append("scene_index", String(state.sceneIndex));
    state.isUploadingImage = true;
    renderImageTools(chapter);
    els.imageUploadDrop?.classList.remove("is-dragover");
    if (els.imageUploadLabel) els.imageUploadLabel.textContent = "アップロード中...";
    try {
      const result = await api(`/api/v1/cinema-novels/${novelId}/image-upload`, {
        method: "POST",
        body,
      });
      state.novel = result.novel;
      restorePosition(previousChapterId, previousSceneIndex);
      imageEditModal?.hide();
      if (els.imageUploadInput) els.imageUploadInput.value = "";
      window.NovelUI?.toast?.("画像を差し替えました。");
      render();
    } catch (error) {
      window.NovelUI?.toast?.(error.message || "画像のアップロードに失敗しました。", "danger");
    } finally {
      state.isUploadingImage = false;
      if (els.imageUploadLabel) els.imageUploadLabel.textContent = "画像を選択、またはドラッグ&ドロップ";
      renderImageTools(currentChapter());
    }
  }

  async function deleteSceneImage() {
    const chapter = currentChapter();
    const asset = currentSceneImageAsset();
    if (!chapter || !asset?.id || !canDeleteImage(chapter) || state.isDeletingImage) return;
    if (!window.confirm("このシーンに紐づく画像を削除しますか？")) return;
    const previousChapterId = chapter.id;
    const previousSceneIndex = state.sceneIndex;
    state.isDeletingImage = true;
    renderImageTools(chapter);
    try {
      const result = await api(`/api/v1/cinema-novels/${novelId}/image`, {
        method: "DELETE",
        body: JSON.stringify({
          chapter_id: chapter.id,
          scene_index: state.sceneIndex,
          asset_id: asset.id,
        }),
      });
      state.novel = result.novel;
      restorePosition(previousChapterId, previousSceneIndex);
      window.NovelUI?.toast?.("シーン画像を削除しました。");
      render();
    } catch (error) {
      window.NovelUI?.toast?.(error.message || "シーン画像の削除に失敗しました。", "danger");
    } finally {
      state.isDeletingImage = false;
      renderImageTools(currentChapter());
    }
  }

  async function load() {
    state.novel = await api(`/api/v1/cinema-novels/${novelId}`);
    els.chapterSelect.innerHTML = chapters().map((chapter) => `
      <option value="${chapter.id}">${String(chapter.chapter_no).padStart(2, "0")} ${escape(chapter.title)}</option>
    `).join("");
    applyProgress(state.novel.progress);
    render();
  }

  els.next.addEventListener("click", goNext);
  els.prev.addEventListener("click", goPrev);
  els.inlinePrev?.addEventListener("click", goPrev);
  els.bookmark.addEventListener("click", () => saveProgress(true).catch(console.error));
  els.continueButton.addEventListener("click", () => {
    applyProgress(state.novel?.progress);
    render();
  });
  els.imageEditButton?.addEventListener("click", () => {
    els.imageEditPrompt.value = "";
    imageEditModal?.show();
    window.setTimeout(() => els.imageEditPrompt?.focus(), 160);
  });
  els.imageDeleteButton?.addEventListener("click", () => {
    deleteSceneImage().catch(console.error);
  });
  els.imageEditForm?.addEventListener("submit", submitImageEdit);
  els.imageUploadInput?.addEventListener("change", () => {
    uploadSceneImage(els.imageUploadInput.files?.[0]).catch(console.error);
  });
  if (els.imageUploadDrop) {
    ["dragenter", "dragover"].forEach((eventName) => {
      els.imageUploadDrop.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        els.imageUploadDrop.classList.add("is-dragover");
      });
    });
    ["dragleave", "dragend"].forEach((eventName) => {
      els.imageUploadDrop.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!els.imageUploadDrop.contains(event.relatedTarget)) els.imageUploadDrop.classList.remove("is-dragover");
      });
    });
    els.imageUploadDrop.addEventListener("drop", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const [file] = event.dataTransfer?.files || [];
      uploadSceneImage(file).catch(console.error);
    });
  }
  els.chapterSelect.addEventListener("change", () => {
    const index = chapters().findIndex((chapter) => String(chapter.id) === els.chapterSelect.value);
    if (index >= 0) {
      state.chapterIndex = index;
      state.sceneIndex = 0;
      render();
    }
  });
  els.chapterList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-chapter-index]");
    if (!button) return;
    state.chapterIndex = Number(button.dataset.chapterIndex || 0);
    state.sceneIndex = 0;
    render();
  });
  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, textarea, select, button") || document.body.classList.contains("modal-open")) return;
    if (event.key === "ArrowRight" || event.key === " ") {
      event.preventDefault();
      goNext();
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      goPrev();
    }
  });

  load().catch((error) => {
    els.text.textContent = error.message;
  });
})();
