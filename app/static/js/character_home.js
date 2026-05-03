(function () {
  const root = document.querySelector("[data-character-home]");
  if (!root) return;

  const projectId = Number(root.dataset.projectId);
  const characterId = Number(root.dataset.characterId);
  const nameEl = document.getElementById("characterHomeName");
  const introEl = document.getElementById("characterHomeIntro");
  const portraitEl = document.getElementById("characterHomePortrait");
  const previewEl = document.getElementById("characterHomePreview");
  const editorEl = document.getElementById("characterHomeEditor");
  const textarea = document.getElementById("characterHomeMarkdown");
  const toggleButton = document.getElementById("characterHomeEditToggle");
  const saveButton = document.getElementById("characterHomeSaveButton");
  const imageInput = document.getElementById("characterHomeImageInput");

  function defaultMarkdown(character) {
    const lines = [`# ${character.name || "Character"}`];
    if (character.introduction_text) lines.push("", character.introduction_text);
    if (character.character_summary) lines.push("", "## プロフィール", character.character_summary);
    return lines.join("\n");
  }

  function renderCharacter(character) {
    const image = character.bromide_asset?.media_url || character.thumbnail_asset?.media_url || character.base_asset?.media_url;
    nameEl.textContent = character.name || "Character";
    introEl.textContent = character.introduction_text || character.character_summary || "";
    portraitEl.innerHTML = image
      ? `<img src="${NovelUI.escape(image)}" alt="${NovelUI.escape(character.name || "character")}">`
      : '<div class="character-home-portrait-empty"><i class="bi bi-person-bounding-box"></i></div>';
    const markdown = character.home_markdown || defaultMarkdown(character);
    if (textarea) textarea.value = markdown;
    previewEl.innerHTML = MarkdownEditor.markdownToHtml(markdown);
  }

  async function loadCharacter() {
    renderCharacter(await NovelUI.api(`/api/v1/characters/${characterId}`));
  }

  async function saveHome() {
    saveButton.disabled = true;
    try {
      const updated = await NovelUI.api(`/api/v1/characters/${characterId}`, {
        method: "PATCH",
        body: { home_markdown: textarea.value },
      });
      renderCharacter(updated);
      NovelUI.toast("キャラクターホームを保存しました。");
    } catch (error) {
      NovelUI.toast(error.message || "保存に失敗しました。", "danger");
    } finally {
      saveButton.disabled = false;
    }
  }

  async function uploadHomeImage(file) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("画像ファイルを選択してください。", "warning");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    body.append("project_id", String(projectId));
    body.append("asset_type", "character_home_image");
    const response = await fetch("/api/v1/assets/upload", { method: "POST", body, credentials: "same-origin" });
    const payload = await response.json().catch(() => ({}));
    const asset = payload?.data;
    if (!response.ok || !asset?.media_url) {
      throw new Error(payload?.data?.message || payload?.message || `HTTP ${response.status}`);
    }
    insertImageMarkdown(asset);
    NovelUI.toast("画像を本文に追加しました。");
  }

  function insertImageMarkdown(asset) {
    const insert = `\n\n![${asset.file_name || "image"}](${asset.media_url})\n`;
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    textarea.value = `${textarea.value.slice(0, start)}${insert}${textarea.value.slice(end)}`;
    previewEl.innerHTML = MarkdownEditor.markdownToHtml(textarea.value);
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = start + insert.length;
  }

  toggleButton?.addEventListener("click", () => {
    editorEl?.classList.toggle("is-hidden");
  });
  textarea?.addEventListener("input", () => {
    previewEl.innerHTML = MarkdownEditor.markdownToHtml(textarea.value);
  });
  saveButton?.addEventListener("click", saveHome);
  imageInput?.addEventListener("change", async () => {
    try {
      await uploadHomeImage(imageInput.files?.[0]);
    } catch (error) {
      NovelUI.toast(error.message || "画像アップロードに失敗しました。", "danger");
    } finally {
      imageInput.value = "";
    }
  });

  loadCharacter().catch((error) => NovelUI.toast(error.message || "キャラクターの読み込みに失敗しました。", "danger"));
})();
