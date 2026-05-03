(() => {
  const page = document.querySelector("[data-project-id][data-story-id]");
  const projectId = Number(page?.dataset.projectId || 0);
  let storyId = page?.dataset.storyId ? Number(page.dataset.storyId) : null;
  let currentStory = null;

  const form = document.getElementById("storyEditForm");
  const draftButton = document.getElementById("storyDraftButton");
  const openingImageButton = document.getElementById("storyOpeningImageButton");
  const openingImageUploadInput = document.getElementById("storyOpeningImageUploadInput");
  const openingImagePreview = document.getElementById("storyOpeningImagePreview");
  const markdownInput = document.getElementById("storyMarkdownInput");
  const markdownPreview = document.getElementById("storyMarkdownPreview");
  const characterSelect = document.getElementById("storyCharacterSelect");
  const outfitInput = document.getElementById("storyOutfitInput");
  const outfitPicker = document.getElementById("storyOutfitPicker");
  const outfitPickerController = window.OutfitPicker.create({
    characterSelect,
    input: outfitInput,
    picker: outfitPicker,
  });

  function readMaxTurns() {
    const value = Number(document.getElementById("storyMaxTurnsInput").value || 10);
    return Math.max(5, Math.min(20, Number.isFinite(value) ? Math.round(value) : 10));
  }

  async function loadCharacters() {
    const characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    const rows = Array.isArray(characters) ? characters : [];
    characterSelect.innerHTML = rows.map((character) => `<option value="${character.id}">${NovelUI.escape(character.name)}</option>`).join("");
  }

  async function loadOutfits(selectedOutfitId = "") {
    return outfitPickerController.load(selectedOutfitId);
  }

  function readPayload() {
    return {
      title: document.getElementById("storyTitleInput").value.trim(),
      description: document.getElementById("storyDescriptionInput").value.trim(),
      status: document.getElementById("storyStatusSelect").value,
      character_id: Number(characterSelect.value),
      default_outfit_id: outfitInput.value ? Number(outfitInput.value) : null,
      story_mode: document.getElementById("storyModeSelect").value || "free_chat",
      max_turns: readMaxTurns(),
      config_markdown: markdownInput.value,
    };
  }

  function renderMarkdownPreview() {
    markdownPreview.innerHTML = window.MarkdownEditor.markdownToHtml(markdownInput.value);
  }

  function extractMarkdownTitle(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const titleLine = lines.find((line) => line.trim().startsWith("# "));
    return titleLine ? titleLine.trim().replace(/^#\s+/, "").trim() : "";
  }

  function renderOpeningImage(asset) {
    if (!openingImagePreview) return;
    const mediaUrl = asset?.media_url;
    openingImagePreview.innerHTML = mediaUrl
      ? `
        <figure class="costume-create-image-card">
          <img src="${NovelUI.escape(mediaUrl)}" alt="オープニング画像">
          <figcaption>オープニング画像 / 1536x1024</figcaption>
        </figure>
      `
      : '<div class="empty-panel mb-0">オープニング画像はまだありません。</div>';
  }

  function fillForm(story) {
    currentStory = story;
    document.getElementById("storyTitleInput").value = story.title || "";
    document.getElementById("storyDescriptionInput").value = story.description || "";
    document.getElementById("storyStatusSelect").value = story.status || "draft";
    characterSelect.value = story.character_id || "";
    outfitInput.value = story.default_outfit_id || "";
    const modeSelect = document.getElementById("storyModeSelect");
    const mode = story.story_mode || "free_chat";
    if ([...modeSelect.options].some((option) => option.value === mode)) {
      modeSelect.value = mode;
    } else {
      modeSelect.value = "free_chat";
    }
    const maxTurns = story.config_json?.max_turns || story.initial_state_json?.goal_state?.max_turns || 10;
    document.getElementById("storyMaxTurnsInput").value = Math.max(5, Math.min(20, Number(maxTurns) || 10));
    markdownInput.value = story.config_markdown || "";
    renderMarkdownPreview();
    renderOpeningImage(story.opening_image_asset);
  }

  async function loadStory() {
    if (!storyId) return;
    const story = await NovelUI.api(`/api/v1/stories/${storyId}`);
    fillForm(story);
    await loadOutfits(story.default_outfit_id || "");
  }

  async function saveStory() {
    const payload = readPayload();
    if (!payload.title || !payload.character_id) {
      NovelUI.toast("タイトルとメインキャラクターを入力してください。", "warning");
      return null;
    }
    const saved = storyId
      ? await NovelUI.api(`/api/v1/stories/${storyId}`, { method: "PATCH", body: payload })
      : await NovelUI.api(`/api/v1/projects/${projectId}/stories`, { method: "POST", body: payload });
    storyId = saved.id;
    fillForm(saved);
    NovelUI.toast("ストーリーを保存しました。");
    if (!window.location.pathname.endsWith(`/stories/${storyId}/edit`)) {
      history.replaceState(null, "", `/projects/${projectId}/stories/${storyId}/edit`);
    }
    return saved;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await saveStory();
  });

  draftButton.addEventListener("click", async () => {
    const title = document.getElementById("storyTitleInput").value.trim();
    const characterId = Number(document.getElementById("storyCharacterSelect").value);
    draftButton.disabled = true;
    draftButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>作成中...';
    try {
      const draft = await NovelUI.api(`/api/v1/projects/${projectId}/stories/draft-markdown`, {
        method: "POST",
        body: {
          title,
          character_id: characterId,
          story_mode: document.getElementById("storyModeSelect").value || "dungeon_trpg",
          max_turns: readMaxTurns(),
        },
      });
      markdownInput.value = draft.config_markdown || "";
      const generatedTitle = extractMarkdownTitle(markdownInput.value);
      if (generatedTitle) {
        document.getElementById("storyTitleInput").value = generatedTitle;
      }
      renderMarkdownPreview();
      if (draft.story_mode) {
        document.getElementById("storyModeSelect").value = draft.story_mode;
      }
      if (draft.max_turns) {
        document.getElementById("storyMaxTurnsInput").value = draft.max_turns;
      }
      NovelUI.toast("Markdown設定を自動作成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "Markdown設定の自動作成に失敗しました。", "danger");
    } finally {
      draftButton.disabled = false;
      draftButton.innerHTML = "Markdown自動作成";
    }
  });

  markdownInput.addEventListener("input", renderMarkdownPreview);

  openingImageButton.addEventListener("click", async () => {
    openingImageButton.disabled = true;
    openingImageButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>生成中...';
    try {
      const saved = await saveStory();
      if (!saved) return;
      openingImagePreview.innerHTML = '<div class="empty-panel mb-0"><span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>オープニング画像を生成しています...</div>';
      const result = await NovelUI.api(`/api/v1/stories/${storyId}/opening-image`, {
        method: "POST",
        body: {},
      });
      if (result.story) {
        fillForm(result.story);
      } else {
        renderOpeningImage(result.asset);
      }
      NovelUI.toast("オープニング画像を生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "オープニング画像の生成に失敗しました。", "danger");
    } finally {
      openingImageButton.disabled = false;
      openingImageButton.innerHTML = "オープニング画像を作成";
    }
  });

  openingImageUploadInput.addEventListener("change", async () => {
    const file = openingImageUploadInput.files?.[0];
    if (!file) return;
    try {
      if (!storyId) {
        const saved = await saveStory();
        if (!saved) return;
      }
      const body = new FormData();
      body.append("file", file);
      openingImagePreview.innerHTML = '<div class="empty-panel mb-0"><span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>オープニング画像をアップロードしています...</div>';
      const response = await fetch(`/api/v1/stories/${storyId}/opening-image/upload`, {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      const result = payload?.data || payload;
      if (!response.ok) {
        throw new Error(result?.message || payload?.message || `HTTP ${response.status}`);
      }
      if (result.story) {
        fillForm(result.story);
      } else {
        renderOpeningImage(result.asset);
      }
      NovelUI.toast("オープニング画像をアップロードしました。");
    } catch (error) {
      NovelUI.toast(error.message || "オープニング画像のアップロードに失敗しました。", "danger");
    } finally {
      openingImageUploadInput.value = "";
    }
  });

  renderOpeningImage(null);
  Promise.all([loadCharacters()])
    .then(() => storyId ? loadStory() : loadOutfits(""))
    .catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
})();
