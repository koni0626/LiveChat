(function () {
  const shell = document.querySelector(".cinema-list-shell");
  if (!shell) return;
  const projectId = Number(shell.dataset.projectId);
  const canManageProject = shell.dataset.canManageProject === "true";
  const list = document.getElementById("cinemaNovelList");
  const empty = document.getElementById("cinemaNovelEmpty");
  const importButton = document.getElementById("cinemaImportAkaganeButton");
  const outlineForm = document.getElementById("cinemaProductionOutlineForm");
  const mainCharacterSelect = document.getElementById("cinemaMainCharacterSelect");
  const outlineResult = document.getElementById("cinemaProductionResult");
  const suggestPremiseButton = document.getElementById("cinemaSuggestPremiseButton");
  const createShortComicButton = document.getElementById("cinemaCreateShortComicButton");
  const comicLayoutSelect = document.querySelector('[name="comic_layout"]');
  const targetPanelInput = document.querySelector('[name="target_panel_count"]');
  const useSourceNovelCheck = document.getElementById("cinemaUseSourceNovelCheck");
  const sourceNovelSelect = document.getElementById("cinemaSourceNovelSelect");
  const sourceNovelFields = Array.from(document.querySelectorAll("[data-production-source-novel]"));
  const productionModeHelp = document.getElementById("cinemaProductionModeHelp");
  const productionModeButtons = Array.from(document.querySelectorAll("[data-production-mode]"));
  const productionModeFields = Array.from(document.querySelectorAll("[data-production-field]"));
  const bgmSelect = document.getElementById("cinemaBgmSelect");
  const bgmVolumeSelect = document.getElementById("cinemaBgmVolumeSelect");
  const bgmUploadInput = document.getElementById("cinemaBgmUploadInput");
  const suggestPremiseButtonDefaultHtml = suggestPremiseButton?.innerHTML || '<i class="bi bi-stars"></i> ノベルゲームを生成';
  const createShortComicButtonDefaultHtml = createShortComicButton?.innerHTML || '<i class="bi bi-badge-cc"></i> ショート漫画を生成';
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
  const reviewPanel = document.getElementById("cinemaReviewPanel");
  const reviewTitle = document.getElementById("cinemaReviewTitle");
  const reviewCharacterSelect = document.getElementById("cinemaReviewCharacterSelect");
  const createReviewButton = document.getElementById("cinemaCreateReviewButton");
  const reviewCloseButton = document.getElementById("cinemaReviewCloseButton");
  const reviewResult = document.getElementById("cinemaReviewResult");
  const novelStatusSelect = document.getElementById("cinemaNovelStatusSelect");
  const novelMobileVisibleCheck = document.getElementById("cinemaNovelMobileVisibleCheck");
  const novelStatusSaveButton = document.getElementById("cinemaNovelStatusSaveButton");
  const comicEditorPanel = document.getElementById("cinemaComicEditorPanel");
  const comicEditorTitle = document.getElementById("cinemaComicEditorTitle");
  const comicEditorCloseButton = document.getElementById("cinemaComicEditorClose");
  const comicEditorThumbs = document.getElementById("cinemaComicEditorThumbs");
  const comicEditorPreview = document.getElementById("cinemaComicEditorPreview");
  const comicEditorCaption = document.getElementById("cinemaComicEditorCaption");
  const comicEditorImagePrompt = document.getElementById("cinemaComicEditorImagePrompt");
  const comicEditorEditPrompt = document.getElementById("cinemaComicEditorEditPrompt");
  const comicEditorHistory = document.getElementById("cinemaComicEditorHistory");
  const comicEditorAddAfterButton = document.getElementById("cinemaComicEditorAddAfter");
  const comicEditorCopyAfterButton = document.getElementById("cinemaComicEditorCopyAfter");
  const comicEditorDeleteSceneButton = document.getElementById("cinemaComicEditorDeleteScene");
  const comicEditorSaveTextButton = document.getElementById("cinemaComicEditorSaveText");
  const comicEditorRegenerateButton = document.getElementById("cinemaComicEditorRegenerate");
  const comicEditorStatus = document.getElementById("cinemaComicEditorStatus");
  let activeNovel = null;
  let activeReviewNovel = null;
  let activeComicNovel = null;
  let activeComicChapter = null;
  let activeComicSceneIndex = 0;
  let latestProductionOutline = null;
  let latestProductionInput = null;
  let productionCharacters = [];
  let bgmAssets = [];
  let cinemaNovels = [];
  let productionMode = "novel";

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
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
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
    const formData = new FormData(outlineForm);
    const body = Object.fromEntries(formData.entries());
    body.reference_sources = formData.getAll("reference_sources");
    const character = selectedMainCharacter();
    body.main_character = character?.name || "";
    if (character?.nickname) body.main_character_nickname = character.nickname;
    body.mobile_visible = Boolean(outlineForm.querySelector('[name="mobile_visible"]')?.checked);
    return body;
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

  function statusLabel(status) {
    return status === "published" ? "公開" : "非公開";
  }

  function statusClass(status) {
    return status === "published" ? "is-published" : "is-draft";
  }

  function isShortComicNovel(novel) {
    return novel?.mode === "short_comic_video";
  }

  function isComicPageNovel(novel) {
    const production = novel?.production_json || {};
    return novel?.mode === "short_comic_video" && production?.comic_layout === "page";
  }

  function syncSourceNovelControls() {
    const visible = productionMode === "comic";
    const checked = Boolean(useSourceNovelCheck?.checked);
    sourceNovelFields.forEach((field) => {
      field.hidden = !visible;
      field.querySelectorAll?.("input, select, textarea, button").forEach((control) => {
        if (control === sourceNovelSelect) {
          control.disabled = !visible || !checked;
        } else {
          control.disabled = !visible;
        }
      });
    });
    if (sourceNovelSelect) sourceNovelSelect.disabled = !visible || !checked;
  }

  function renderSourceNovelOptions() {
    if (!sourceNovelSelect) return;
    const current = sourceNovelSelect.value;
    const sourceNovels = (cinemaNovels || []).filter((novel) => !isShortComicNovel(novel));
    sourceNovelSelect.innerHTML = [
      '<option value="">小説を選択してください</option>',
      ...sourceNovels.map((novel) => {
        const chapterText = novel.chapter_count ? ` / ${novel.chapter_count}章` : "";
        const statusText = novel.status === "published" ? "公開" : "非公開";
        return `<option value="${escape(novel.id)}">${escape(novel.title || `#${novel.id}`)}${escape(chapterText)} (${escape(statusText)})</option>`;
      }),
    ].join("");
    if (sourceNovels.some((novel) => String(novel.id) === String(current))) {
      sourceNovelSelect.value = current;
    }
    syncSourceNovelControls();
  }

  function setProductionMode(mode) {
    productionMode = ["novel", "comic", "both"].includes(mode) ? mode : "novel";
    productionModeButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.productionMode === productionMode);
    });
    productionModeFields.forEach((field) => {
      const visible = productionMode === "both"
        ? ["novel", "comic"].includes(field.dataset.productionField)
        : field.dataset.productionField === productionMode;
      field.hidden = !visible;
      if ("disabled" in field) field.disabled = !visible;
      field.querySelectorAll?.("input, select, textarea, button").forEach((control) => {
        control.disabled = !visible;
      });
    });
    if (suggestPremiseButton) {
      suggestPremiseButton.hidden = productionMode !== "novel";
      suggestPremiseButton.disabled = productionMode !== "novel";
      suggestPremiseButton.innerHTML = suggestPremiseButtonDefaultHtml;
    }
    if (createShortComicButton) {
      createShortComicButton.hidden = productionMode === "novel";
      createShortComicButton.disabled = productionMode === "novel";
      createShortComicButton.innerHTML = productionMode === "both"
        ? '<i class="bi bi-layers"></i> ノベルとショート漫画を生成'
        : createShortComicButtonDefaultHtml;
    }
    if (productionModeHelp) {
      productionModeHelp.textContent = productionMode === "both"
        ? "まずノベルゲームを作成し、その本文を元にショート漫画または漫画ページを作成します。"
        : productionMode === "comic"
          ? "ショート漫画または漫画ページを作成します。作成後に漫画動画やEPUBとして出力できます。"
          : "ノベルゲームを作成します。作成後にPPT化や動画化ができます。";
    }
    syncSourceNovelControls();
  }

  function syncComicLayoutDefaults() {
    if (!comicLayoutSelect || !targetPanelInput) return;
    if (comicLayoutSelect.value === "page" && Number(targetPanelInput.value || 0) > 12) {
      targetPanelInput.value = "4";
    } else if (comicLayoutSelect.value !== "page" && !targetPanelInput.value) {
      targetPanelInput.value = "20";
    }
  }

  function mobileVisibleLabel(visible) {
    return visible ? "スマホ表示" : "PCのみ";
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
    if (reviewCharacterSelect) {
      reviewCharacterSelect.innerHTML = '<option value="">レビューするキャラクターを選択</option>' + (productionCharacters || []).map((character) => {
        const label = [character.name || `#${character.id}`, character.nickname ? `(${character.nickname})` : ""].filter(Boolean).join(" ");
        return `<option value="${escape(character.id)}">${escape(label)}</option>`;
      }).join("");
    }
  }

  function renderBgmOptions() {
    if (!bgmSelect) return;
    const current = bgmSelect.value;
    const bgmLabel = (asset) => {
      return String(asset?.display_name || asset?.metadata?.original_file_name || asset?.file_name || "BGM").trim();
    };
    bgmSelect.innerHTML = [
      `<option value="">BGMなし</option>`,
      ...bgmAssets.map((asset) => `<option value="${asset.id}">${escape(bgmLabel(asset))}</option>`),
    ].join("");
    if ([...bgmSelect.options].some((option) => option.value === current)) {
      bgmSelect.value = current;
    }
  }

  async function loadBgmAssets() {
    if (!bgmSelect) return;
    bgmAssets = await api(`/api/v1/projects/${projectId}/cinema-novels/bgm`);
    renderBgmOptions();
  }

  async function uploadBgmAsset(file) {
    if (!file || !bgmUploadInput) return;
    const label = bgmUploadInput.closest("label");
    const labelSpan = label?.querySelector("span");
    const originalHtml = labelSpan?.innerHTML;
    if (labelSpan) {
      labelSpan.innerHTML = `<span class="spinner-border spinner-border-sm"></span> アップロード中`;
    }
    try {
      const formData = new FormData();
      formData.append("file", file);
      const asset = await api(`/api/v1/projects/${projectId}/cinema-novels/bgm`, {
        method: "POST",
        body: formData,
      });
      await loadBgmAssets();
      if (bgmSelect) bgmSelect.value = String(asset.id);
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(cleanErrorMessage(error.message))}</div>`;
      }
    } finally {
      bgmUploadInput.value = "";
      if (labelSpan) {
        labelSpan.innerHTML = originalHtml || `<i class="bi bi-music-note-beamed"></i> BGMをアップロード`;
      }
    }
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

  async function waitShortComicJob(job) {
    let current = job;
    while (current?.status === "queued" || current?.status === "running") {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `
          <div class="cinema-production-result-meta">
            ショート漫画を生成中です / status: ${escape(current.status)} / elapsed: ${escape(formatElapsed(current.started_at || current.created_at))}
          </div>
          <pre>台本、文字入りコマ画像、DB保存をまとめて進めています。画像生成があるため少し時間がかかります。</pre>
        `;
      }
      await sleep(5000);
      current = await api(`/api/v1/projects/${projectId}/cinema-novels/short-comic-jobs/${current.id}`);
    }
    if (current?.status === "failed") {
      throw new Error(current.error || "ショート漫画生成に失敗しました。");
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
        status: input?.status || "draft",
        mobile_visible: Boolean(input?.mobile_visible),
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
    const posterAsset = novel.poster_asset?.media_url ? novel.poster_asset : novel.cover_asset;
    const posterUrl = posterAsset?.media_url || "";
    const posterClasses = [
      posterAsset?.asset_type === "cinema_novel_title_image" ? "cinema-novel-title-poster" : "",
      Number(posterAsset?.height || 0) > Number(posterAsset?.width || 0) ? "cinema-novel-poster-portrait" : "",
    ].filter(Boolean).join(" ");
    const reviews = Array.isArray(novel.reviews) ? novel.reviews : [];
    const shortComic = isShortComicNovel(novel);
    const comicPage = isComicPageNovel(novel);
    const progressText = shortComic ? (comicPage ? "漫画ページ用" : "漫画動画用") : `${progressCopy} / ${novel.chapter_count || 0}章`;
    const workTypeBadge = `<span class="cinema-novel-status-badge ${shortComic ? "is-mobile-visible" : "is-draft"}">${comicPage ? "漫画ページ" : shortComic ? "ショート漫画" : "ノベルゲーム"}</span>`;
    const statusBadge = `<span class="cinema-novel-status-badge ${statusClass(novel.status)}">${statusLabel(novel.status)}</span>`;
    const mobileBadge = canManageProject ? `<span class="cinema-novel-status-badge ${novel.mobile_visible ? "is-mobile-visible" : "is-mobile-hidden"}">${mobileVisibleLabel(novel.mobile_visible)}</span>` : "";
    const reviewersHtml = reviews.length ? `
      <div class="cinema-reviewers" title="レビュー済み">
        ${reviews.slice(0, 8).map((review) => {
          const character = review.character || {};
          const imageUrl = character.thumbnail_asset?.media_url || "";
          return imageUrl
            ? `<img src="${escape(imageUrl)}" alt="${escape(character.name || "")}" title="${escape(character.name || "")}">`
            : `<span title="${escape(character.name || "")}">${escape(String(character.name || "?").slice(0, 1))}</span>`;
        }).join("")}
      </div>
    ` : "";
    const actionsHtml = shortComic ? `
          <button class="btn btn-sm btn-outline-dark" type="button" data-comic-editor-novel-id="${novel.id}">
            <i class="bi bi-easel"></i>
            編集
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-comic-video-novel-id="${novel.id}">
            <i class="bi bi-badge-cc"></i>
            漫画動画
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-epub-novel-id="${novel.id}">
            <i class="bi bi-book"></i>
            EPUB
          </button>
    ` : `
          <button class="btn btn-sm btn-outline-dark" type="button" data-production-novel-id="${novel.id}">
            <i class="bi bi-tools"></i>
            制作
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-export-novel-id="${novel.id}">
            <i class="bi bi-file-earmark-ppt"></i>
            PPT
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-video-novel-id="${novel.id}">
            <i class="bi bi-file-earmark-play"></i>
            動画
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-epub-novel-id="${novel.id}">
            <i class="bi bi-book"></i>
            EPUB
          </button>
          <button class="btn btn-sm btn-outline-dark" type="button" data-vertical-epub-novel-id="${novel.id}">
            <i class="bi bi-layout-text-window-reverse"></i>
            縦書きEPUB
          </button>
    `;
    const publicationButton = `
          <button class="btn btn-sm btn-outline-dark" type="button" data-toggle-status-novel-id="${novel.id}" data-next-status="${novel.status === "published" ? "draft" : "published"}">
            <i class="bi ${novel.status === "published" ? "bi-eye-slash" : "bi-eye"}"></i>
            ${novel.status === "published" ? "非公開にする" : "公開にする"}
          </button>
    `;
    return `
      <article class="cinema-novel-card" data-novel-id="${novel.id}" data-novel-mode="${escape(novel.mode || "")}">
        <a class="cinema-novel-card-link" href="${href}">
          <div class="cinema-novel-poster">
            ${posterUrl
              ? `<img class="${posterClasses}" src="${posterUrl}" alt="">`
              : `<div class="cinema-novel-poster-empty"><i class="bi bi-film"></i></div>`}
          </div>
          <div class="cinema-novel-card-body">
            <div class="cinema-novel-status">${workTypeBadge}${statusBadge}${mobileBadge}<span>${progressText}</span></div>
            <h3>${escape(novel.title)}</h3>
            <p>${escape(novel.subtitle || novel.description || "ノベル作品")}</p>
          </div>
        </a>
        ${canManageProject ? `<div class="cinema-novel-card-actions">${actionsHtml}${publicationButton}</div>` : ""}
      </article>
    `;
  }

  async function loadNovels() {
    const novels = await api(`/api/v1/projects/${projectId}/cinema-novels`);
    cinemaNovels = Array.isArray(novels) ? novels : [];
    window.__cinemaNovels = novels;
    renderSourceNovelOptions();
    list.innerHTML = novels.map(renderNovel).join("");
    decorateReviewControls(novels);
    empty.hidden = novels.length > 0;
  }

  function decorateReviewControls(novels) {
    if (!canManageProject) return;
    const novelById = new Map((novels || []).map((novel) => [Number(novel.id), novel]));
    list.querySelectorAll(".cinema-novel-card").forEach((card) => {
      const productionButton = card.querySelector("[data-production-novel-id]");
      const novelId = Number(card.dataset.novelId || productionButton?.dataset.productionNovelId || 0);
      const novel = novelById.get(novelId);
      if (!novel) return;
      const body = card.querySelector(".cinema-novel-card-body");
      const actions = card.querySelector(".cinema-novel-card-actions");
      const reviews = Array.isArray(novel.reviews) ? novel.reviews : [];
      if (body && reviews.length) {
        const reviewers = document.createElement("div");
        reviewers.className = "cinema-reviewers";
        reviewers.title = "レビュー済み";
        reviewers.innerHTML = reviews.slice(0, 8).map((review) => {
          const character = review.character || {};
          const imageUrl = character.thumbnail_asset?.media_url || "";
          return imageUrl
            ? `<img src="${escape(imageUrl)}" alt="${escape(character.name || "")}" title="${escape(character.name || "")}">`
            : `<span title="${escape(character.name || "")}">${escape(String(character.name || "?").slice(0, 1))}</span>`;
        }).join("");
        body.appendChild(reviewers);
      }
      if (actions) {
        if (!isShortComicNovel(novel) && productionButton) {
          const reviewButton = document.createElement("button");
          reviewButton.className = "btn btn-sm btn-outline-dark";
          reviewButton.type = "button";
          reviewButton.dataset.reviewNovelId = String(novel.id);
          reviewButton.innerHTML = `<i class="bi bi-chat-square-quote"></i> 映画レビュー`;
          actions.insertBefore(reviewButton, productionButton);
        }
        const deleteButton = document.createElement("button");
        deleteButton.className = "btn btn-sm btn-outline-danger cinema-novel-delete-button";
        deleteButton.type = "button";
        deleteButton.dataset.deleteNovelId = String(novel.id);
        deleteButton.innerHTML = `<i class="bi bi-trash"></i> 削除`;
        actions.appendChild(deleteButton);
      }
    });
  }

  function renderReviewResult(review) {
    if (!reviewResult) return;
    const character = review?.character || {};
    const imageUrl = character.thumbnail_asset?.media_url || "";
    const impressions = Array.isArray(review?.impressions) ? review.impressions : [];
    const impressionHtml = impressions.length ? `
      <div class="cinema-review-impressions">
        <strong>作品内キャラへの印象</strong>
        ${impressions.map((item) => `
          <div class="cinema-review-impression-item">
            <span>${escape(item.target_name || "")}</span>
            <p>${escape(item.impression_text || "")}</p>
            ${item.talk_hint ? `<small>${escape(item.talk_hint)}</small>` : ""}
          </div>
        `).join("")}
      </div>
    ` : "";
    reviewResult.innerHTML = `
      <article class="cinema-review-result-card">
        <div class="cinema-review-result-character">
          ${imageUrl ? `<img src="${escape(imageUrl)}" alt="">` : `<span>${escape(String(character.name || "?").slice(0, 1))}</span>`}
          <div>
            <strong>${escape(character.name || "")}</strong>
            <small>${escape(review?.rating_label || "レビュー済み")}</small>
          </div>
        </div>
        <p>${escape(review?.review_text || "")}</p>
        <div class="cinema-review-memory">AIメモ: ${escape(review?.memory_note || "")}</div>
        ${impressionHtml}
      </article>
    `;
  }

  function openReviewPanel(novelId) {
    const novels = window.__cinemaNovels || [];
    const novel = novels.find((item) => Number(item.id) === Number(novelId));
    if (!reviewPanel || !novel) return;
    activeReviewNovel = novel;
    reviewPanel.hidden = false;
    if (reviewTitle) reviewTitle.textContent = `映画レビュー / ${novel.title || ""}`;
    if (reviewResult) reviewResult.innerHTML = "";
    reviewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function createReview() {
    if (!activeReviewNovel || !reviewCharacterSelect || !createReviewButton || !reviewResult) return;
    const characterId = Number(reviewCharacterSelect.value || 0);
    if (!characterId) {
      reviewResult.innerHTML = `<div class="cinema-review-error">レビューするキャラクターを選択してください。</div>`;
      return;
    }
    const originalHtml = createReviewButton.innerHTML;
    createReviewButton.disabled = true;
    createReviewButton.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> レビュー中...`;
    try {
      const review = await api(`/api/v1/cinema-novels/${activeReviewNovel.id}/reviews`, {
        method: "POST",
        body: JSON.stringify({ character_id: characterId }),
      });
      renderReviewResult(review);
      await loadNovels();
    } catch (error) {
      reviewResult.innerHTML = `<div class="cinema-review-error">${escape(error.message || "レビューに失敗しました")}</div>`;
    } finally {
      createReviewButton.disabled = false;
      createReviewButton.innerHTML = originalHtml;
    }
  }

  async function deleteNovel(novelId) {
    const novel = (window.__cinemaNovels || []).find((item) => Number(item.id) === Number(novelId));
    const title = novel?.title || "このノベル";
    const ok = window.confirm(`「${title}」を削除します。レビュー投稿と映画レビュー由来のAIメモも非表示/無効化します。よろしいですか？`);
    if (!ok) return;
    const button = list?.querySelector(`[data-delete-novel-id="${CSS.escape(String(novelId))}"]`);
    const originalHtml = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> 削除中...`;
    }
    try {
      await api(`/api/v1/cinema-novels/${novelId}`, { method: "DELETE" });
      if (activeNovel && Number(activeNovel.id) === Number(novelId)) {
        activeNovel = null;
        if (chapterPanel) chapterPanel.hidden = true;
      }
      if (activeReviewNovel && Number(activeReviewNovel.id) === Number(novelId)) {
        activeReviewNovel = null;
        if (reviewPanel) reviewPanel.hidden = true;
      }
      await loadNovels();
    } catch (error) {
      window.alert(error.message || "削除に失敗しました");
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }
  }

  async function toggleNovelPublication(novelId, nextStatus) {
    const novel = (window.__cinemaNovels || []).find((item) => Number(item.id) === Number(novelId));
    const button = list?.querySelector(`[data-toggle-status-novel-id="${CSS.escape(String(novelId))}"]`);
    const originalHtml = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 更新中`;
    }
    try {
      await api(`/api/v1/cinema-novels/${novelId}/status`, {
        method: "PUT",
        body: JSON.stringify({
          status: nextStatus === "published" ? "published" : "draft",
          mobile_visible: Boolean(novel?.mobile_visible ?? true),
        }),
      });
      await loadNovels();
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(cleanErrorMessage(error.message))}</div>`;
      }
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }
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
    if (novelStatusSelect) novelStatusSelect.value = novel.status === "published" ? "published" : "draft";
    if (novelMobileVisibleCheck) novelMobileVisibleCheck.checked = Boolean(novel.mobile_visible);
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

  async function saveNovelStatus() {
    if (!activeNovel || !novelStatusSelect || !novelStatusSaveButton) return;
    const originalHtml = novelStatusSaveButton.innerHTML;
    novelStatusSaveButton.disabled = true;
    novelStatusSaveButton.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> 保存中`;
    try {
      const updated = await api(`/api/v1/cinema-novels/${activeNovel.id}/status`, {
        method: "PUT",
        body: JSON.stringify({
          status: novelStatusSelect.value,
          mobile_visible: Boolean(novelMobileVisibleCheck?.checked),
        }),
      });
      activeNovel = { ...activeNovel, status: updated.status, mobile_visible: updated.mobile_visible };
      await loadNovels();
    } catch (error) {
      if (chapterMeta) chapterMeta.innerHTML = `<span class="text-danger">${escape(error.message || "公開状態を保存できませんでした")}</span>`;
    } finally {
      novelStatusSaveButton.disabled = false;
      novelStatusSaveButton.innerHTML = originalHtml;
    }
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

  async function createNovelFromProduction({ openEditor = true } = {}) {
    if (!outlineForm) return null;
    const currentBody = productionFormBody();
    if (outlineResult) {
      outlineResult.hidden = false;
      outlineResult.innerHTML = `<div class="cinema-production-result-meta">1/5 DBキャラクターと世界観から企画案を作っています。</div>`;
    }
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
    if (openEditor) await openChapterProduction(saved.id);
    renderAutoBuildResult({ premise, outline, titleImage });
    return { saved, premise, outline, titleImage };
  }

  async function suggestProductionPremise() {
    if (!outlineForm || !suggestPremiseButton) return;
    suggestPremiseButton.disabled = true;
    suggestPremiseButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 自動生成中`;
    try {
      await createNovelFromProduction({ openEditor: true });
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(error.message)}</div>`;
      }
    } finally {
      suggestPremiseButton.disabled = false;
      suggestPremiseButton.innerHTML = suggestPremiseButtonDefaultHtml;
    }
  }

  async function createShortComic(options = {}) {
    if (!outlineForm || !createShortComicButton) return;
    syncComicLayoutDefaults();
    const body = productionFormBody();
    body.target_panel_count = Number(body.target_panel_count || 20);
    if (body.comic_layout === "page") body.target_page_count = body.target_panel_count;
    body.generate_images = true;
    const selectedSourceNovelId = Number(options.sourceNovelId || (useSourceNovelCheck?.checked ? sourceNovelSelect?.value : 0) || 0);
    if (useSourceNovelCheck?.checked && !selectedSourceNovelId && !options.sourceNovelId) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-warning">元にする小説を選択してください。</div>`;
      }
      return null;
    }
    if (selectedSourceNovelId) body.source_novel_id = selectedSourceNovelId;
    const selectedSourceNovel = (cinemaNovels || []).find((novel) => Number(novel.id) === selectedSourceNovelId);
    if (!body.title) body.title = options.sourceNovelTitle || selectedSourceNovel?.title || body.title;
    const manageButtons = options.manageButtons !== false;
    const originalHtml = createShortComicButton.innerHTML;
    if (manageButtons) {
      createShortComicButton.disabled = true;
      if (suggestPremiseButton) suggestPremiseButton.disabled = true;
      createShortComicButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 生成中`;
    }
    try {
      const job = await api(`/api/v1/projects/${projectId}/cinema-novels/short-comic-jobs`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      const novel = await waitShortComicJob(job);
      await loadNovels();
      if (outlineResult) {
        const scenes = novel.chapters?.[0]?.scene_json || [];
        const panelCount = scenes.length;
        const imageCount = scenes.filter((scene) => scene?.still_asset_id || scene?.background_asset_id || scene?.still_asset?.media_url || scene?.background_asset?.media_url).length;
        const comicPage = isComicPageNovel(novel);
        outlineResult.hidden = false;
        if (panelCount > 0 && imageCount === 0) {
          outlineResult.innerHTML = `
            <div class="alert alert-warning">
              本編画像がまだ反映されていません。${imageCount}/${panelCount} 画像。しばらく待ってから再読み込みしてください。
            </div>
            <pre>${escape(novel.title || "")}\n${escape(novel.subtitle || "")}</pre>
          `;
          return;
        }
        outlineResult.innerHTML = `
          <div class="cinema-production-result-meta">
            ${comicPage ? "漫画ページ" : "ショート漫画"}を作成しました。${panelCount}${comicPage ? "ページ" : "コマ"} / 画像つき
          </div>
          <pre>${escape(novel.title || "")}\n${escape(novel.subtitle || "")}</pre>
        `;
      }
      return novel;
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(cleanErrorMessage(error.message))}</div>`;
      }
      if (options.propagateError) throw error;
    } finally {
      if (manageButtons) {
        createShortComicButton.disabled = false;
        if (suggestPremiseButton) suggestPremiseButton.disabled = productionMode !== "novel";
        createShortComicButton.innerHTML = originalHtml;
      }
    }
  }

  async function createNovelAndShortComic() {
    if (!outlineForm || !createShortComicButton) return;
    const originalHtml = createShortComicButton.innerHTML;
    createShortComicButton.disabled = true;
    if (suggestPremiseButton) suggestPremiseButton.disabled = true;
    createShortComicButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ノベル生成中`;
    try {
      const novelResult = await createNovelFromProduction({ openEditor: false });
      if (!novelResult?.saved?.id) throw new Error("ノベルの作成結果を取得できませんでした。");
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="cinema-production-result-meta">ノベルが完成しました。本文を元にショート漫画を作成しています。</div>`;
      }
      createShortComicButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 漫画生成中`;
      const comicNovel = await createShortComic({
        sourceNovelId: novelResult.saved.id,
        sourceNovelTitle: novelResult.saved.title,
        manageButtons: false,
        propagateError: true,
      });
      await loadNovels();
      await openChapterProduction(novelResult.saved.id);
      if (outlineResult) {
        const scenes = comicNovel?.chapters?.[0]?.scene_json || [];
        const comicPage = isComicPageNovel(comicNovel);
        outlineResult.hidden = false;
        outlineResult.innerHTML = `
          <div class="cinema-production-result-meta">
            ノベルと${comicPage ? "漫画ページ" : "ショート漫画"}を作成しました。漫画はノベル本文を元にしています。${scenes.length}${comicPage ? "ページ" : "コマ"}
          </div>
          <pre>ノベル: ${escape(novelResult.saved.title || "")}\n漫画: ${escape(comicNovel?.title || "")}</pre>
        `;
      }
    } catch (error) {
      if (outlineResult) {
        outlineResult.hidden = false;
        outlineResult.innerHTML = `<div class="alert alert-danger">${escape(cleanErrorMessage(error.message))}</div>`;
      }
    } finally {
      createShortComicButton.disabled = false;
      if (suggestPremiseButton) suggestPremiseButton.disabled = productionMode !== "novel";
      createShortComicButton.innerHTML = originalHtml;
    }
  }

  function comicScenes() {
    return Array.isArray(activeComicChapter?.scene_json) ? activeComicChapter.scene_json : [];
  }

  function comicEditorItems() {
    const coverAsset = activeComicNovel?.poster_asset?.media_url ? activeComicNovel.poster_asset : activeComicNovel?.cover_asset;
    const endAsset = activeComicNovel?.comic_end_card_asset;
    return [
      {
        kind: "cover",
        label: "表紙",
        caption: activeComicNovel?.title || "表紙",
        imagePrompt: activeComicNovel?.description || activeComicNovel?.subtitle || "",
        asset: coverAsset || null,
        history: Array.isArray(activeComicNovel?.comic_cover_asset_history) ? activeComicNovel.comic_cover_asset_history : [],
      },
      ...comicScenes().map((scene, sceneIndex) => ({
        kind: "scene",
        label: scene?.comic_page ? `P${sceneIndex + 1}` : `${sceneIndex + 1}`,
        sceneIndex,
        scene,
        caption: comicSceneCaption(scene),
        imagePrompt: scene?.image_prompt || scene?.visual_focus || "",
        asset: scene?.still_asset?.media_url ? scene.still_asset : scene?.background_asset || null,
        history: Array.isArray(scene?.still_asset_history) ? scene.still_asset_history : [],
      })),
      {
        kind: "end_card",
        label: "END",
        caption: "Laplace City",
        imagePrompt: "Final cool end card, protagonist in a striking heroic pose, premium short-video closing thumbnail.",
        asset: endAsset || null,
        history: Array.isArray(activeComicNovel?.comic_end_card_asset_history) ? activeComicNovel.comic_end_card_asset_history : [],
      },
    ];
  }

  function comicItemImageUrl(item) {
    return item?.asset?.media_url || "";
  }

  function comicSceneCaption(scene) {
    return scene?.caption || scene?.text || scene?.page_title || "";
  }

  function selectedComicItem() {
    return comicEditorItems()[activeComicSceneIndex] || null;
  }

  function setComicEditorStatus(message, type = "") {
    if (!comicEditorStatus) return;
    comicEditorStatus.classList.toggle("text-danger", type === "danger");
    comicEditorStatus.classList.toggle("text-success", type === "success");
    comicEditorStatus.textContent = message || "";
  }

  function syncActiveComicChapterFromNovel() {
    if (!activeComicNovel) {
      activeComicChapter = null;
      return;
    }
    const chapters = Array.isArray(activeComicNovel.chapters) ? activeComicNovel.chapters : [];
    activeComicChapter = chapters[0] || null;
    const maxIndex = Math.max(0, comicEditorItems().length - 1);
    activeComicSceneIndex = Math.min(Math.max(0, activeComicSceneIndex), maxIndex);
  }

  function renderComicEditor() {
    if (!comicEditorPanel || !comicEditorThumbs || !comicEditorPreview) return;
    syncActiveComicChapterFromNovel();
    const items = comicEditorItems();
    const item = selectedComicItem();
    if (comicEditorTitle) {
      comicEditorTitle.textContent = activeComicNovel?.title ? `漫画編集室: ${activeComicNovel.title}` : "漫画編集室";
    }
    if (!items.length) {
      comicEditorThumbs.innerHTML = "";
      comicEditorPreview.innerHTML = `<div class="cinema-comic-editor-empty">編集できるコマがありません。</div>`;
      if (comicEditorHistory) comicEditorHistory.innerHTML = `<div class="cinema-comic-editor-history-empty">履歴はまだありません。</div>`;
      if (comicEditorCaption) comicEditorCaption.value = "";
      if (comicEditorImagePrompt) comicEditorImagePrompt.value = "";
      return;
    }
    comicEditorThumbs.innerHTML = items.map((item, index) => {
      const imageUrl = comicItemImageUrl(item);
      return `
        <button class="cinema-comic-editor-thumb ${index === activeComicSceneIndex ? "is-active" : ""}" type="button" data-comic-editor-scene-index="${index}">
          ${imageUrl ? `<img src="${escape(imageUrl)}" alt="">` : `<span class="cinema-comic-editor-noimage">No image</span>`}
          <strong>${escape(item.label || String(index + 1))}</strong>
          <small>${escape(item.caption || "").slice(0, 44)}</small>
        </button>
      `;
    }).join("");

    const imageUrl = comicItemImageUrl(item);
    comicEditorPreview.innerHTML = imageUrl
      ? `<img src="${escape(imageUrl)}" alt=""><p>${escape(item?.caption || "")}</p>`
      : `<div class="cinema-comic-editor-empty">このコマには画像がありません。再生成すると画像を作れます。</div>`;
    if (comicEditorCaption) comicEditorCaption.value = item?.caption || "";
    if (comicEditorImagePrompt) comicEditorImagePrompt.value = item?.imagePrompt || "";
    if (comicEditorEditPrompt) comicEditorEditPrompt.value = "";
    if (comicEditorHistory) {
      const history = Array.isArray(item?.history) ? item.history : [];
      comicEditorHistory.innerHTML = history.length ? history.map((asset, index) => `
        <button class="cinema-comic-editor-history-item" type="button" data-comic-history-asset-id="${asset.id}">
          <img src="${escape(asset.media_url || "")}" alt="">
          <span>履歴 ${index + 1}</span>
        </button>
      `).join("") : `<div class="cinema-comic-editor-history-empty">再生成すると前の画像がここに残ります。</div>`;
    }
    const sceneEditable = item?.kind === "scene";
    if (comicEditorAddAfterButton) comicEditorAddAfterButton.disabled = !activeComicChapter;
    if (comicEditorCopyAfterButton) comicEditorCopyAfterButton.disabled = !sceneEditable;
    if (comicEditorDeleteSceneButton) comicEditorDeleteSceneButton.disabled = !sceneEditable;
  }

  async function openComicEditor(novelId) {
    if (!comicEditorPanel) return;
    activeComicNovel = await api(`/api/v1/cinema-novels/${novelId}`);
    activeComicSceneIndex = 0;
    renderComicEditor();
    comicEditorPanel.hidden = false;
    setComicEditorStatus("");
    comicEditorPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function saveComicSceneText({ silent = false } = {}) {
    if (!activeComicNovel) return null;
    const item = selectedComicItem();
    if (!item) return null;
    if (item.kind !== "scene") {
      setComicEditorStatus("表紙とENDは、修正メモを書いて再生成するか、画像履歴から選んで反映できます。");
      return null;
    }
    if (!activeComicChapter) return null;
    if (!silent) {
      comicEditorSaveTextButton.disabled = true;
      comicEditorSaveTextButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 保存中`;
      setComicEditorStatus("保存しています...");
    }
    try {
      const result = await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-scenes`, {
        method: "PUT",
        body: JSON.stringify({
          chapter_id: activeComicChapter.id,
          scene_index: item.sceneIndex,
          caption: comicEditorCaption?.value || "",
          image_prompt: comicEditorImagePrompt?.value || "",
        }),
      });
      activeComicNovel = result.novel || activeComicNovel;
      activeComicChapter = result.chapter || activeComicChapter;
      renderComicEditor();
      if (!silent) setComicEditorStatus("保存しました。動画とEPUBにも反映されます。", "success");
      return result;
    } catch (error) {
      setComicEditorStatus(cleanErrorMessage(error.message), "danger");
      throw error;
    } finally {
      if (!silent) {
        comicEditorSaveTextButton.disabled = false;
        comicEditorSaveTextButton.innerHTML = `<i class="bi bi-save"></i> テキスト保存`;
      }
    }
  }

  async function selectComicHistoryImage(assetId) {
    if (!activeComicNovel || !assetId) return;
    const item = selectedComicItem();
    if (!item) return;
    setComicEditorStatus("履歴画像を反映しています...");
    try {
      const result = item.kind === "scene"
        ? await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-scenes`, {
          method: "PUT",
          body: JSON.stringify({
            chapter_id: activeComicChapter.id,
            scene_index: item.sceneIndex,
            selected_asset_id: assetId,
          }),
        })
        : await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-special-image`, {
          method: "PUT",
          body: JSON.stringify({
            kind: item.kind,
            selected_asset_id: assetId,
          }),
        });
      activeComicNovel = result.novel || activeComicNovel;
      activeComicChapter = result.chapter || activeComicNovel.chapters?.[0] || activeComicChapter;
      renderComicEditor();
      setComicEditorStatus("履歴画像を反映しました。動画とEPUBにもこの画像が使われます。", "success");
      await loadNovels();
    } catch (error) {
      setComicEditorStatus(cleanErrorMessage(error.message), "danger");
    }
  }

  async function mutateComicScene(operation) {
    if (!activeComicNovel || !activeComicChapter) return;
    const item = selectedComicItem();
    const scenes = comicScenes();
    const selectedSceneIndex = item?.kind === "scene"
      ? item.sceneIndex
      : item?.kind === "cover"
        ? -1
        : Math.max(0, scenes.length - 1);
    if ((operation === "copy_after" || operation === "delete") && item?.kind !== "scene") {
      setComicEditorStatus("表紙とENDはコマ操作の対象外です。", "danger");
      return;
    }
    if (operation === "delete" && !window.confirm("このコマを削除して、後ろのコマを前に詰めますか？")) return;
    const buttons = [comicEditorAddAfterButton, comicEditorCopyAfterButton, comicEditorDeleteSceneButton].filter(Boolean);
    buttons.forEach((button) => { button.disabled = true; });
    setComicEditorStatus("コマ構成を更新しています...");
    try {
      const result = await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-scenes/mutate`, {
        method: "POST",
        body: JSON.stringify({
          chapter_id: activeComicChapter.id,
          scene_index: selectedSceneIndex,
          operation,
          caption: comicEditorCaption?.value || "",
          image_prompt: comicEditorImagePrompt?.value || "",
        }),
      });
      activeComicNovel = result.novel || activeComicNovel;
      activeComicChapter = result.chapter || activeComicNovel.chapters?.[0] || activeComicChapter;
      activeComicSceneIndex = Math.max(1, Number(result.scene_index || 0) + 1);
      renderComicEditor();
      const message = operation === "delete" ? "コマを削除しました。" : operation === "copy_after" ? "コマをコピーしました。" : "コマを追加しました。";
      setComicEditorStatus(message, "success");
      await loadNovels();
    } catch (error) {
      setComicEditorStatus(cleanErrorMessage(error.message), "danger");
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
      renderComicEditor();
    }
  }

  async function regenerateComicScene() {
    if (!activeComicNovel) return;
    const item = selectedComicItem();
    if (!item) return;
    comicEditorRegenerateButton.disabled = true;
    comicEditorSaveTextButton.disabled = true;
    comicEditorRegenerateButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 再生成中`;
    setComicEditorStatus("このコマだけ画像を作り直しています...");
    try {
      const editPrompt = (comicEditorEditPrompt?.value || "").trim();
      const savedImagePrompt = comicEditorImagePrompt?.value || "";
      const savedCaption = comicEditorCaption?.value || "";
      if (item.kind === "scene") await saveComicSceneText({ silent: true });
      const refreshedItem = selectedComicItem() || item;
      const imagePrompt = [
        savedImagePrompt || refreshedItem.imagePrompt || "",
        editPrompt ? `Revision note: ${editPrompt}` : "",
      ].filter(Boolean).join("\n");
      const result = item.kind === "scene"
        ? await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-scenes/regenerate`, {
          method: "POST",
          body: JSON.stringify({
            chapter_id: activeComicChapter.id,
            scene_index: refreshedItem.sceneIndex,
            caption: savedCaption,
            image_prompt: imagePrompt,
          }),
        })
        : await api(`/api/v1/cinema-novels/${activeComicNovel.id}/comic-special-image/regenerate`, {
          method: "POST",
          body: JSON.stringify({
            kind: item.kind,
            caption: savedCaption,
            image_prompt: imagePrompt,
          }),
        });
      activeComicNovel = result.novel || activeComicNovel;
      activeComicChapter = result.chapter || activeComicNovel.chapters?.[0] || activeComicChapter;
      renderComicEditor();
      const created = (result.assets || []).length || (result.asset ? 1 : 0);
      const failed = (result.failed_assets || []).length;
      setComicEditorStatus(`再生成しました。作成 ${created} / 失敗 ${failed}`, failed ? "danger" : "success");
      await loadNovels();
    } catch (error) {
      setComicEditorStatus(cleanErrorMessage(error.message), "danger");
    } finally {
      comicEditorRegenerateButton.disabled = false;
      comicEditorSaveTextButton.disabled = false;
      comicEditorRegenerateButton.innerHTML = `<i class="bi bi-magic"></i> このコマを再生成`;
    }
  }

  importButton?.addEventListener("click", importAkagane);
  suggestPremiseButton?.addEventListener("click", suggestProductionPremise);
  createShortComicButton?.addEventListener("click", () => {
    if (productionMode === "both") {
      createNovelAndShortComic();
    } else {
      createShortComic();
    }
  });
  comicLayoutSelect?.addEventListener("change", syncComicLayoutDefaults);
  useSourceNovelCheck?.addEventListener("change", syncSourceNovelControls);
  bgmUploadInput?.addEventListener("change", () => {
    uploadBgmAsset(bgmUploadInput.files?.[0]);
  });
  productionModeButtons.forEach((button) => {
    button.addEventListener("click", () => setProductionMode(button.dataset.productionMode));
  });
  list.addEventListener("click", (event) => {
    const reviewButton = event.target.closest("[data-review-novel-id]");
    if (reviewButton) {
      event.preventDefault();
      openReviewPanel(Number(reviewButton.dataset.reviewNovelId));
      return;
    }
    const deleteButton = event.target.closest("[data-delete-novel-id]");
    if (deleteButton) {
      event.preventDefault();
      deleteNovel(Number(deleteButton.dataset.deleteNovelId));
      return;
    }
    const statusButton = event.target.closest("[data-toggle-status-novel-id]");
    if (statusButton) {
      event.preventDefault();
      toggleNovelPublication(Number(statusButton.dataset.toggleStatusNovelId), statusButton.dataset.nextStatus);
      return;
    }
    const exportButton = event.target.closest("[data-export-novel-id]");
    if (exportButton) {
      event.preventDefault();
      window.location.href = `/api/v1/cinema-novels/${Number(exportButton.dataset.exportNovelId)}/powerpoint`;
      return;
    }
    const epubButton = event.target.closest("[data-epub-novel-id]");
    if (epubButton) {
      event.preventDefault();
      window.location.href = `/api/v1/cinema-novels/${Number(epubButton.dataset.epubNovelId)}/epub`;
      return;
    }
    const verticalEpubButton = event.target.closest("[data-vertical-epub-novel-id]");
    if (verticalEpubButton) {
      event.preventDefault();
      window.location.href = `/api/v1/cinema-novels/${Number(verticalEpubButton.dataset.verticalEpubNovelId)}/epub?writing_mode=vertical`;
      return;
    }
    const videoButton = event.target.closest("[data-video-novel-id]");
    if (videoButton) {
      event.preventDefault();
      window.location.href = `/api/v1/cinema-novels/${Number(videoButton.dataset.videoNovelId)}/short-video${selectedBgmQuery()}`;
      return;
    }
    const comicEditorButton = event.target.closest("[data-comic-editor-novel-id]");
    if (comicEditorButton) {
      event.preventDefault();
      openComicEditor(Number(comicEditorButton.dataset.comicEditorNovelId)).catch((error) => {
        if (outlineResult) {
          outlineResult.hidden = false;
          outlineResult.innerHTML = `<div class="alert alert-danger">${escape(cleanErrorMessage(error.message))}</div>`;
        }
      });
      return;
    }
    const comicVideoButton = event.target.closest("[data-comic-video-novel-id]");
    if (comicVideoButton) {
      event.preventDefault();
      const novelId = Number(comicVideoButton.dataset.comicVideoNovelId);
      window.location.href = `/api/v1/cinema-novels/${novelId}/comic-short-video${selectedBgmQuery()}`;
      window.setTimeout(() => {
        loadNovels().catch(() => {});
      }, 8000);
      return;
    }
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
  novelStatusSaveButton?.addEventListener("click", saveNovelStatus);
  chapterSelect?.addEventListener("change", syncSelectedChapter);
  generateChapterDraftButton?.addEventListener("click", generateChapterDraft);
  applyChapterDraftButton?.addEventListener("click", applyChapterDraft);
  generateImagePlanButton?.addEventListener("click", generateImagePlan);
  generateChapterImagesButton?.addEventListener("click", generateChapterImages);
  closeChapterProductionButton?.addEventListener("click", () => {
    if (chapterPanel) chapterPanel.hidden = true;
  });
  reviewCloseButton?.addEventListener("click", () => {
    if (reviewPanel) reviewPanel.hidden = true;
  });
  comicEditorCloseButton?.addEventListener("click", () => {
    if (comicEditorPanel) comicEditorPanel.hidden = true;
  });
  comicEditorThumbs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-comic-editor-scene-index]");
    if (!button) return;
    activeComicSceneIndex = Number(button.dataset.comicEditorSceneIndex || 0);
    renderComicEditor();
    setComicEditorStatus("");
  });
  comicEditorHistory?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-comic-history-asset-id]");
    if (!button) return;
    selectComicHistoryImage(Number(button.dataset.comicHistoryAssetId || 0));
  });
  comicEditorAddAfterButton?.addEventListener("click", () => mutateComicScene("add_after"));
  comicEditorCopyAfterButton?.addEventListener("click", () => mutateComicScene("copy_after"));
  comicEditorDeleteSceneButton?.addEventListener("click", () => mutateComicScene("delete"));
  comicEditorSaveTextButton?.addEventListener("click", () => {
    saveComicSceneText().catch(() => {});
  });
  comicEditorRegenerateButton?.addEventListener("click", regenerateComicScene);
  createReviewButton?.addEventListener("click", createReview);
  outlineForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (productionMode === "both") {
      createNovelAndShortComic();
    } else if (productionMode === "comic") {
      createShortComic();
    } else {
      suggestProductionPremise();
    }
  });
  setProductionMode("novel");
  Promise.all([loadProductionCharacters(), loadBgmAssets(), loadNovels()]).catch((error) => {
    list.innerHTML = `<div class="alert alert-danger">${escape(error.message)}</div>`;
  });
})();
