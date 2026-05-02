(function () {
  const shell = document.querySelector(".cinema-list-shell");
  if (!shell) return;
  const projectId = Number(shell.dataset.projectId);
  const list = document.getElementById("cinemaNovelList");
  const empty = document.getElementById("cinemaNovelEmpty");
  const importButton = document.getElementById("cinemaImportAkaganeButton");
  const outlineForm = document.getElementById("cinemaProductionOutlineForm");
  const mainCharacterSelect = document.getElementById("cinemaMainCharacterSelect");
  const outlineResult = document.getElementById("cinemaProductionResult");
  const suggestPremiseButton = document.getElementById("cinemaSuggestPremiseButton");
  const chapterPanel = document.getElementById("cinemaChapterProductionPanel");
  const chapterPanelTitle = document.getElementById("cinemaChapterProductionTitle");
  const chapterSelect = document.getElementById("cinemaProductionChapterSelect");
  const chapterMeta = document.getElementById("cinemaChapterProductionMeta");
  const chapterDraftTextarea = document.getElementById("cinemaChapterDraftTextarea");
  const imagePlanTextarea = document.getElementById("cinemaImagePlanTextarea");
  const generatedImageGrid = document.getElementById("cinemaGeneratedImageGrid");
  const createChaptersButton = document.getElementById("cinemaCreateChaptersButton");
  const generateChapterDraftButton = document.getElementById("cinemaGenerateChapterDraftButton");
  const applyChapterDraftButton = document.getElementById("cinemaApplyChapterDraftButton");
  const generateImagePlanButton = document.getElementById("cinemaGenerateImagePlanButton");
  const generateChapterImagesButton = document.getElementById("cinemaGenerateChapterImagesButton");
  const overwriteImagesCheck = document.getElementById("cinemaOverwriteImagesCheck");
  const closeChapterProductionButton = document.getElementById("cinemaChapterProductionClose");
  let activeNovel = null;
  let latestProductionOutline = null;
  let latestProductionInput = null;
  let productionCharacters = [];

  function escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[ch]));
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(cleanErrorMessage(payload?.data?.message || "request failed"));
    return payload.data;
  }

  function cleanErrorMessage(message) {
    const text = String(message || "").trim();
    const lowered = text.toLowerCase();
    if (lowered.includes("<!doctype html") || lowered.includes("<html") || lowered.includes("bad gateway") || lowered.includes("(502)")) {
      return "画像生成APIが一時的に失敗しました (502 Bad Gateway)。本文は反映済みです。少し待ってから画像生成だけ再実行してください。";
    }
    if (lowered.includes("timed out") || lowered.includes("timeout")) {
      return "生成がタイムアウトしました。少し待ってから再実行してください。";
    }
    return text.length > 500 ? `${text.slice(0, 500)}...` : text;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function formatElapsed(startedAt) {
    const start = startedAt ? new Date(startedAt).getTime() : Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - start) / 1000));
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  function selectedMainCharacter() {
    const characterId = Number(mainCharacterSelect?.value || 0);
    return productionCharacters.find((character) => Number(character.id) === characterId) || null;
  }

  function productionFormBody() {
    const body = Object.fromEntries(new FormData(outlineForm).entries());
    const character = selectedMainCharacter();
    body.main_character = character?.name || "";
    if (character?.nickname) body.main_character_nickname = character.nickname;
    return body;
  }

  function setMainCharacterByName(name) {
    if (!mainCharacterSelect || !name) return;
    const normalized = String(name).trim().toLowerCase();
    const character = productionCharacters.find((item) => {
      return [item.name, item.nickname]
        .filter(Boolean)
        .some((value) => String(value).trim().toLowerCase() === normalized);
    });
    if (character) mainCharacterSelect.value = String(character.id);
  }

  async function loadProductionCharacters() {
    if (!mainCharacterSelect) return;
    productionCharacters = await api(`/api/v1/projects/${projectId}/characters`);
    mainCharacterSelect.innerHTML = '<option value="">主役はAIが選定</option>' + (productionCharacters || []).map((character) => {
      const label = [character.name || `#${character.id}`, character.nickname ? `(${character.nickname})` : ""].filter(Boolean).join(" ");
      return `<option value="${escape(character.id)}">${escape(label)}</option>`;
    }).join("");
  }

  async function waitProductionOutlineJob(job) {
    let current = job;
    while (current?.status === "queued" || current?.status === "running") {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `
          <div class="cinema-production-result-meta">
            生成中です。画面は閉じずに待ってください / status: ${escape(current.status)} / elapsed: ${escape(formatElapsed(current.started_at || current.created_at))}
          </div>
          <pre>gpt-5.5で制作設計を作っています。長い場合は10分以上かかることがあります。</pre>
        `;
      }
      await sleep(5000);
      current = await api(`/api/v1/projects/${projectId}/cinema-novels/production-outline-jobs/${current.id}`);
    }
    if (current?.status === "failed") {
      throw new Error(current.error || "生成に失敗しました。");
    }
    return current?.result || {};
  }

  function premiseText(premise) {
    return [
      `タイトル: ${premise.title || ""}`,
      `主役: ${premise.main_character || ""}`,
      `ジャンル: ${premise.genre || ""}`,
      `章数: ${premise.chapter_count || ""}`,
      `テーマ: ${premise.theme || ""}`,
      "",
      premise.concept_note || "",
      premise.protagonist_reason ? `\n主人公選定理由: ${premise.protagonist_reason}` : "",
    ].join("\n").trim();
  }

  async function saveProductionOutline(input, outline, premise) {
    return api(`/api/v1/projects/${projectId}/cinema-novels/production-outline/save`, {
      method: "POST",
      body: JSON.stringify({
        title: input?.title || premise?.title || "無題のノベル作品",
        subtitle: "ノベル制作設計",
        description: input?.theme || premise?.theme || "",
        source_input: { ...(input || {}), premise: premise || {} },
        outline_markdown: outline?.outline_markdown || "",
        model: outline?.model,
        chapter_target_chars: outline?.chapter_target_chars,
        usage: outline?.usage,
        status: "draft",
      }),
    });
  }

  function renderAutoBuildResult({ premise, outline, titleImage }) {
    if (!outlineResult) return;
    const titleImageUrl = titleImage?.asset?.media_url || "";
    outlineResult.hidden = false;
    outlineResult.innerHTML = `
      <div class="cinema-production-result-meta">
        企画、章立て、章データ、タイトル画像を作成しました。ここからは下の章制作で1章ずつ本文と画像を作れます。
      </div>
      ${titleImageUrl ? `
        <figure class="cinema-title-image-preview">
          <img src="${escape(titleImageUrl)}" alt="">
          <figcaption>タイトル画像</figcaption>
        </figure>
      ` : ""}
      <div class="cinema-production-textarea-grid">
        <label>
          <span>企画の内容</span>
          <textarea class="form-control" readonly rows="12">${escape(premiseText(premise))}</textarea>
        </label>
        <label>
          <span>章立て</span>
          <textarea class="form-control" readonly rows="12">${escape(outline?.outline_markdown || "")}</textarea>
        </label>
      </div>
    `;
  }

  function renderNovel(novel) {
    const href = `/projects/${projectId}/cinema-novels/${novel.id}`;
    const progressCopy = novel.progress ? "続きあり" : "未読";
    const posterUrl = novel.poster_asset?.media_url || novel.cover_asset?.media_url || "";
    return `
      <article class="cinema-novel-card">
        <a class="cinema-novel-card-link" href="${href}">
          <div class="cinema-novel-poster">
            ${posterUrl
              ? `<img class="${novel.poster_asset?.asset_type === "cinema_novel_title_image" ? "cinema-novel-title-poster" : ""}" src="${posterUrl}" alt="">`
              : `<div class="cinema-novel-poster-empty"><i class="bi bi-film"></i></div>`}
          </div>
          <div class="cinema-novel-card-body">
            <div class="cinema-novel-status">${progressCopy} / ${novel.chapter_count || 0}章</div>
            <h3>${escape(novel.title)}</h3>
            <p>${escape(novel.subtitle || novel.description || "ノベル作品")}</p>
          </div>
        </a>
        <div class="cinema-novel-card-actions">
          <button class="btn btn-sm btn-outline-dark" type="button" data-production-novel-id="${novel.id}">
            <i class="bi bi-tools"></i>
            制作
          </button>
        </div>
      </article>
    `;
  }

  async function loadNovels() {
    const novels = await api(`/api/v1/projects/${projectId}/cinema-novels`);
    list.innerHTML = novels.map(renderNovel).join("");
    empty.hidden = novels.length > 0;
  }

  function activeChapter() {
    const chapterId = Number(chapterSelect?.value || 0);
    return (activeNovel?.chapters || []).find((chapter) => chapter.id === chapterId) || null;
  }

  function chapterImages(chapter) {
    if (!chapter) return [];
    const images = [];
    const seenUrls = new Set();
    const addImage = (label, url) => {
      if (!url || seenUrls.has(url)) return;
      seenUrls.add(url);
      images.push({ label, url });
    };
    (chapter.generated_assets || []).forEach((asset, index) => {
      addImage(asset.label || `image ${index + 1}`, asset.media_url);
    });
    (chapter.scene_json || []).forEach((scene, index) => {
      addImage(`scene ${index + 1}`, scene?.still_asset?.media_url);
    });
    (chapter.scene_json || []).forEach((scene, index) => {
      const legacyAssets = scene?.generated_assets || scene?.assets || [];
      if (Array.isArray(legacyAssets)) {
        legacyAssets.forEach((asset, assetIndex) => addImage(`scene ${index + 1}-${assetIndex + 1}`, asset?.media_url));
      }
    });
    return images;
  }

  function renderGeneratedImages(chapter) {
    if (!generatedImageGrid) return;
    const images = chapterImages(chapter);
    if (!images.length) {
      generatedImageGrid.innerHTML = `<div class="cinema-generated-image-empty">生成済み画像はまだありません。</div>`;
      return;
    }
    generatedImageGrid.innerHTML = images.map((image) => `
      <figure class="cinema-generated-image-card">
        <a href="${escape(image.url)}" target="_blank" rel="noopener">
          <img src="${escape(image.url)}" alt="${escape(image.label)}">
        </a>
        <figcaption>${escape(image.label)}</figcaption>
      </figure>
    `).join("");
  }

  function renderChapterProduction(novel) {
    activeNovel = novel;
    if (!chapterPanel || !chapterSelect) return;
    chapterPanel.hidden = false;
    chapterPanelTitle.textContent = `${novel.title} / 章制作`;
    chapterSelect.innerHTML = (novel.chapters || []).map((chapter) => `
      <option value="${chapter.id}">${String(chapter.chapter_no).padStart(2, "0")} ${escape(chapter.title)}</option>
    `).join("");
    const firstChapter = (novel.chapters || [])[0];
    if (firstChapter) {
      chapterSelect.value = String(firstChapter.id);
      chapterDraftTextarea.value = firstChapter.body_markdown || "";
      if (imagePlanTextarea) imagePlanTextarea.value = "";
      renderGeneratedImages(firstChapter);
      chapterMeta.textContent = `現在本文: ${(firstChapter.body_markdown || "").length}文字 / ${(firstChapter.scene_json || []).length}シーン`;
      if (createChaptersButton) createChaptersButton.hidden = true;
      generateChapterDraftButton.disabled = false;
      generateImagePlanButton.disabled = false;
      generateChapterImagesButton.disabled = false;
    }
    if (!firstChapter) {
      chapterDraftTextarea.value = "";
      if (imagePlanTextarea) imagePlanTextarea.value = "";
      renderGeneratedImages(null);
      chapterMeta.textContent = "この作品にはまだ章がありません。企画を自動提案し直してください。";
      if (createChaptersButton) createChaptersButton.hidden = false;
      generateChapterDraftButton.disabled = true;
      generateImagePlanButton.disabled = true;
      generateChapterImagesButton.disabled = true;
    }
    applyChapterDraftButton.disabled = true;
    chapterPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function openChapterProduction(novelId) {
    const novel = await api(`/api/v1/cinema-novels/${novelId}`);
    renderChapterProduction(novel);
  }

  function syncSelectedChapter() {
    const chapter = activeChapter();
    if (!chapter) return;
    chapterDraftTextarea.value = chapter.body_markdown || "";
    if (imagePlanTextarea) imagePlanTextarea.value = "";
    renderGeneratedImages(chapter);
    chapterMeta.textContent = `現在本文: ${(chapter.body_markdown || "").length}文字 / ${(chapter.scene_json || []).length}シーン`;
    applyChapterDraftButton.disabled = true;
  }

  async function generateChapterDraft() {
    const chapter = activeChapter();
    if (!activeNovel || !chapter) return;
    generateChapterDraftButton.disabled = true;
    generateImagePlanButton.disabled = true;
    generateChapterImagesButton.disabled = true;
    applyChapterDraftButton.disabled = true;
    generateChapterDraftButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 本文生成中`;
    try {
      const result = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}/deepen`, {
        method: "POST",
        body: JSON.stringify({ apply: true }),
      });
      chapterDraftTextarea.value = result.chapter_markdown || "";
      if (result.chapter) {
        const index = activeNovel.chapters.findIndex((item) => item.id === result.chapter.id);
        if (index >= 0) activeNovel.chapters[index] = result.chapter;
      }
      chapterMeta.textContent = `本文を反映しました。画像案を作成中... / draft: ${chapterDraftTextarea.value.length}文字`;
      const plan = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}/image-plan`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (imagePlanTextarea) imagePlanTextarea.value = [
        "# 劇中スチル案",
        ...(plan.still_prompts || []).map((item) => `## scene ${item.scene_index + 1}\n${item.prompt}`),
      ].join("\n");
      chapterMeta.textContent = "画像を生成して紐づけ中...";
      const imageResult = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}/images`, {
        method: "POST",
        body: JSON.stringify({ still_count: 20, generate_cover: false, overwrite: Boolean(overwriteImagesCheck?.checked), parallel: true }),
      });
      const updated = imageResult.chapter;
      const updatedIndex = activeNovel.chapters.findIndex((item) => item.id === updated.id);
      if (updatedIndex >= 0) activeNovel.chapters[updatedIndex] = updated;
      renderGeneratedImages(updated);
      const assetCount = (imageResult.assets || []).length;
      const failedCount = (imageResult.failed_assets || []).length;
      const referenceCount = (imageResult.reference_asset_ids || []).length;
      const options = imageResult.image_options || {};
      chapterMeta.textContent = `自動生成完了: 本文反映済み / 画像 ${assetCount}枚 / 失敗 ${failedCount}枚 / 参照画像 ${referenceCount}枚 / ${options.provider || ""} ${options.model || ""} ${options.size || ""}`;
      applyChapterDraftButton.disabled = true;
    } catch (error) {
      chapterMeta.innerHTML = `<span class="text-danger">${escape(cleanErrorMessage(error.message))}</span>`;
    } finally {
      generateChapterDraftButton.disabled = false;
      generateImagePlanButton.disabled = false;
      generateChapterImagesButton.disabled = false;
      generateChapterDraftButton.innerHTML = `<i class="bi bi-pencil-square"></i> 本文と画像を自動生成`;
    }
  }

  async function applyChapterDraft() {
    const chapter = activeChapter();
    if (!activeNovel || !chapter || !chapterDraftTextarea.value.trim()) return;
    applyChapterDraftButton.disabled = true;
    applyChapterDraftButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 反映中`;
    try {
      const updated = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}`, {
        method: "PUT",
        body: JSON.stringify({ body_markdown: chapterDraftTextarea.value }),
      });
      const index = activeNovel.chapters.findIndex((item) => item.id === updated.id);
      if (index >= 0) activeNovel.chapters[index] = updated;
      chapterMeta.textContent = `反映済み: ${(updated.body_markdown || "").length}文字 / ${(updated.scene_json || []).length}シーン`;
    } catch (error) {
      chapterMeta.innerHTML = `<span class="text-danger">${escape(cleanErrorMessage(error.message))}</span>`;
    } finally {
      applyChapterDraftButton.disabled = false;
      applyChapterDraftButton.innerHTML = `<i class="bi bi-check2-circle"></i> 章へ反映`;
    }
  }

  async function generateImagePlan() {
    const chapter = activeChapter();
    if (!activeNovel || !chapter) return;
    generateImagePlanButton.disabled = true;
    generateImagePlanButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 作成中`;
    try {
      const result = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}/image-plan`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (imagePlanTextarea) imagePlanTextarea.value = [
        "# 劇中スチル案",
        ...(result.still_prompts || []).map((item) => `## scene ${item.scene_index + 1}\n${item.prompt}`),
      ].join("\n");
      chapterMeta.textContent = "画像案を作成しました。章本文ドラフトは変更していません。";
    } catch (error) {
      chapterMeta.innerHTML = `<span class="text-danger">${escape(cleanErrorMessage(error.message))}</span>`;
    } finally {
      generateImagePlanButton.disabled = false;
      generateImagePlanButton.innerHTML = `<i class="bi bi-images"></i> 画像案`;
    }
  }

  async function generateChapterImages() {
    const chapter = activeChapter();
    if (!activeNovel || !chapter) return;
    generateChapterImagesButton.disabled = true;
    generateChapterImagesButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 生成中`;
    try {
      const result = await api(`/api/v1/cinema-novels/${activeNovel.id}/chapters/${chapter.id}/images`, {
        method: "POST",
        body: JSON.stringify({ still_count: 20, generate_cover: false, overwrite: Boolean(overwriteImagesCheck?.checked), parallel: true }),
      });
      const updated = result.chapter;
      const index = activeNovel.chapters.findIndex((item) => item.id === updated.id);
      if (index >= 0) activeNovel.chapters[index] = updated;
      renderGeneratedImages(updated);
      const assetCount = (result.assets || []).length;
      const failedCount = (result.failed_assets || []).length;
      const referenceCount = (result.reference_asset_ids || []).length;
      const options = result.image_options || {};
      chapterMeta.textContent = `画像生成済み: ${assetCount}枚 / 失敗: ${failedCount}枚 / 参照画像: ${referenceCount}枚 / ${options.provider || ""} ${options.model || ""} ${options.size || ""}`;
      if (imagePlanTextarea) imagePlanTextarea.value = [
        "# 生成済み画像",
        ...(updated.scene_json || [])
          .filter((scene) => scene.still_asset?.media_url)
          .map((scene, sceneIndex) => `scene ${sceneIndex + 1}: ${scene.still_asset.media_url}`),
      ].join("\n");
    } catch (error) {
      chapterMeta.innerHTML = `<span class="text-danger">${escape(error.message)}</span>`;
    } finally {
      generateChapterImagesButton.disabled = false;
      generateChapterImagesButton.innerHTML = `<i class="bi bi-card-image"></i> 画像を生成して紐づけ`;
    }
  }

  async function importAkagane() {
    if (!importButton) return;
    importButton.disabled = true;
    importButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 取り込み中`;
    try {
      await api(`/api/v1/projects/${projectId}/cinema-novels/import-markdown-folder`, {
        method: "POST",
        body: JSON.stringify({
          title: "赤金の観測者",
          subtitle: "ノベル作品",
          description: "ノア指数事件をもとにした、事前生成済み映画ノベル。",
          status: "published",
          source_path: "docs/book/赤金の観測者",
        }),
      });
      await loadNovels();
    } finally {
      importButton.disabled = false;
      importButton.innerHTML = `<i class="bi bi-folder-plus"></i> 赤金の観測者を取り込む`;
    }
  }

  async function suggestProductionPremise() {
    if (!outlineForm || !suggestPremiseButton) return;
    const currentBody = productionFormBody();
    suggestPremiseButton.disabled = true;
    suggestPremiseButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 自動生成中`;
    if (outlineResult) {
      outlineResult.hidden = false;
      outlineResult.innerHTML = `<div class="cinema-production-result-meta">1/5 DBキャラクターと世界観から企画案を作っています。</div>`;
    }
    try {
      const premise = await api(`/api/v1/projects/${projectId}/cinema-novels/production-premise`, {
        method: "POST",
        body: JSON.stringify({ current_input: currentBody }),
      });
      for (const [name, value] of Object.entries({
        title: premise.title,
        genre: premise.genre,
        chapter_count: premise.chapter_count,
        theme: premise.theme,
      })) {
        const field = outlineForm.querySelector(`[name="${name}"]`);
        if (field && value !== undefined && value !== null) field.value = value;
      }
      setMainCharacterByName(premise.main_character);
      const outlineInput = productionFormBody();
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="cinema-production-result-meta">2/5 企画を元に章立てを生成しています。</div>`;
      }
      const outlineJob = await api(`/api/v1/projects/${projectId}/cinema-novels/production-outline-jobs`, {
        method: "POST",
        body: JSON.stringify(outlineInput),
      });
      const outline = await waitProductionOutlineJob(outlineJob);
      latestProductionOutline = outline;
      latestProductionInput = outlineInput;
      if (outlineResult) {
        outlineResult.innerHTML = `<div class="cinema-production-result-meta">3/5 作品を保存して章データを作成しています。</div>`;
      }
      const saved = await saveProductionOutline(outlineInput, outline, premise);
      const chaptersPromise = api(`/api/v1/cinema-novels/${saved.id}/chapters/from-production-outline`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (outlineResult) {
        outlineResult.innerHTML = `<div class="cinema-production-result-meta">4/5 タイトル画像を生成しています。ロゴ入りのオープニング画像を作っています。</div>`;
      }
      const titleImagePromise = api(`/api/v1/cinema-novels/${saved.id}/title-image`, {
        method: "POST",
        body: JSON.stringify({ premise: premiseText(premise) }),
      });
      const [, titleImage] = await Promise.all([chaptersPromise, titleImagePromise]);
      if (outlineResult) {
        outlineResult.innerHTML = `<div class="cinema-production-result-meta">5/5 画面へ反映しています。</div>`;
      }
      await loadNovels();
      await openChapterProduction(saved.id);
      renderAutoBuildResult({ premise, outline, titleImage });
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(error.message)}</div>`;
      }
    } finally {
      suggestPremiseButton.disabled = false;
      suggestPremiseButton.innerHTML = `<i class="bi bi-stars"></i> 企画を自動提案`;
    }
  }

  importButton?.addEventListener("click", importAkagane);
  suggestPremiseButton?.addEventListener("click", suggestProductionPremise);
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-production-novel-id]");
    if (!button) return;
    event.preventDefault();
    openChapterProduction(Number(button.dataset.productionNovelId)).catch((error) => {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(error.message)}</div>`;
      }
    });
  });
  chapterSelect?.addEventListener("change", syncSelectedChapter);
  generateChapterDraftButton?.addEventListener("click", generateChapterDraft);
  applyChapterDraftButton?.addEventListener("click", applyChapterDraft);
  generateImagePlanButton?.addEventListener("click", generateImagePlan);
  generateChapterImagesButton?.addEventListener("click", generateChapterImages);
  closeChapterProductionButton?.addEventListener("click", () => {
    if (chapterPanel) chapterPanel.hidden = true;
  });
  outlineForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    suggestProductionPremise();
  });
  Promise.all([loadProductionCharacters(), loadNovels()]).catch((error) => {
    list.innerHTML = `<div class="alert alert-danger">${escape(error.message)}</div>`;
  });
})();
