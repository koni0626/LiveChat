(function () {
  const shell = document.querySelector(".cinema-reader-shell");
  if (!shell) return;
  const novelId = Number(shell.dataset.novelId);
  const state = { novel: null, chapterIndex: 0, sceneIndex: 0 };

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
  };

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
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

  function sceneImageUrl(scene) {
    return scene?.still_asset?.media_url || scene?.background_asset?.media_url || "";
  }

  function currentImageUrl(chapter) {
    const scenes = chapter?.scene_json || [];
    const currentUrl = sceneImageUrl(scenes[state.sceneIndex]);
    if (currentUrl) return currentUrl;
    for (let chapterIndex = state.chapterIndex; chapterIndex >= 0; chapterIndex -= 1) {
      const chapterScenes = chapters()[chapterIndex]?.scene_json || [];
      const startIndex = chapterIndex === state.chapterIndex ? state.sceneIndex - 1 : chapterScenes.length - 1;
      for (let sceneIndex = startIndex; sceneIndex >= 0; sceneIndex -= 1) {
        const url = sceneImageUrl(chapterScenes[sceneIndex]);
        if (url) return url;
      }
    }
    return state.novel?.poster_asset?.media_url || state.novel?.cover_asset?.media_url || "";
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
    els.stillWrap.innerHTML = `<img src="${url}" alt="">`;
  }

  function renderChapterList() {
    els.chapterList.innerHTML = chapters().map((chapter, index) => `
      <button class="cinema-reader-chapter-button${index === state.chapterIndex ? " active" : ""}" type="button" data-chapter-index="${index}">
        <span>${String(chapter.chapter_no).padStart(2, "0")}</span>
        ${escape(chapter.title)}
      </button>
    `).join("");
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
