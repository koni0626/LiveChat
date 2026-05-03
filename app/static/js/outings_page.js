(() => {
  const projectId = document.body.dataset.projectId;
  const form = document.getElementById("outingStartForm");
  const characterSelect = document.getElementById("outingCharacterSelect");
  const locationSelect = document.getElementById("outingLocationSelect");
  const outfitSelect = document.getElementById("outingOutfitSelect");
  const moodInput = document.getElementById("outingMoodInput");
  const startButton = document.getElementById("outingStartButton");
  const refreshButton = document.getElementById("outingRefreshButton");
  const currentHost = document.getElementById("outingCurrent");
  const loadingBox = document.getElementById("outingLoading");
  const loadingTitle = document.getElementById("outingLoadingTitle");
  const loadingText = document.getElementById("outingLoadingText");
  const titleLabel = document.getElementById("outingTitle");
  const statusLabel = document.getElementById("outingStatus");
  const historyHost = document.getElementById("outingHistory");
  const historyCount = document.getElementById("outingHistoryCount");
  const galleryHost = document.getElementById("outingGallery");
  const galleryCount = document.getElementById("outingGalleryCount");
  const imageModalElement = document.getElementById("outingImageModal");
  document.body.appendChild(imageModalElement);
  const imageModal = new bootstrap.Modal(imageModalElement);
  const imageModalTitle = document.getElementById("outingImageModalTitle");
  const imageModalImage = document.getElementById("outingImageModalImage");
  const toggleTextboxButton = document.getElementById("outingToggleTextboxButton");
  let currentOuting = null;
  let isBusy = false;
  let outingNovelPageState = { pages: [], pageIndex: 0 };
  let textboxVisible = true;
  const mobilePagerMediaQuery = window.matchMedia("(max-width: 767.98px)");

  function isMobileOutingView() {
    return mobilePagerMediaQuery.matches;
  }

  function setLoading(active, title = "準備中", text = "おでかけの場面を作っています。") {
    isBusy = Boolean(active);
    loadingTitle.textContent = title;
    loadingText.textContent = text;
    form.classList.toggle("is-busy", active);
    startButton.disabled = active || !characterSelect.value || !locationSelect.value;
    refreshButton.disabled = active;
    const stageFrame = currentHost.querySelector(".outing-stage-frame");
    if (stageFrame) {
      stageFrame.classList.toggle("is-loading", active);
      stageFrame.dataset.loadingLabel = active ? title : "";
    } else if (active && !currentOuting) {
      renderLoadingStage(title);
    }
    currentHost.querySelectorAll("[data-choice-id]").forEach((button) => {
      button.disabled = active;
    });
    loadingBox.classList.toggle("d-none", !active || Boolean(currentHost.querySelector(".outing-stage-frame")));
  }

  function renderLoadingStage(title = "Loading") {
    currentHost.innerHTML = `
      <div class="outing-chat-stage">
        <div class="live-chat-image-panel outing-image-panel">
          <div class="live-chat-stage-frame outing-stage-frame is-loading" data-loading-label="${NovelUI.escape(title)}">
            <div class="outing-stage-placeholder">
              <i class="bi bi-image"></i>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function imageForCharacter(character) {
    return character?.thumbnail_asset?.media_url || character?.base_asset?.media_url || "";
  }

  function imageForLocation(location) {
    return location?.image_asset?.media_url || "";
  }

  function optionLabel(item, fallback) {
    const meta = [item?.region, item?.location_type].filter(Boolean).join(" / ");
    return `${item?.name || fallback}${meta ? ` - ${meta}` : ""}`;
  }

  function renderSelects(data) {
    const characters = Array.isArray(data?.characters) ? data.characters : [];
    const locations = Array.isArray(data?.locations) ? data.locations : [];
    const outfits = Array.isArray(data?.outfits) ? data.outfits : [];
    characterSelect.innerHTML = characters.length
      ? characters.map((item) => `<option value="${item.id}">${NovelUI.escape(item.name || "Character")}</option>`).join("")
      : `<option value="">キャラクターがありません</option>`;
    locationSelect.innerHTML = locations.length
      ? locations.map((item) => `<option value="${item.id}">${NovelUI.escape(optionLabel(item, "施設"))}</option>`).join("")
      : `<option value="">施設がありません</option>`;
    renderOutfitOptions(outfits);
    startButton.disabled = isBusy || !characters.length || !locations.length;
  }

  function renderOutfitOptions(outfits) {
    const characterId = Number(characterSelect.value || 0);
    const filtered = outfits.filter((item) => Number(item.character_id) === characterId);
    outfitSelect.dataset.outfits = JSON.stringify(outfits);
    outfitSelect.innerHTML = '<option value="auto">おまかせ</option><option value="base">基準画像</option>' + filtered.map((item) => {
      const label = item.name || "衣装";
      return `<option value="${item.id}">${NovelUI.escape(label)}</option>`;
    }).join("");
  }

  function renderHistoryLoading() {
    historyHost.innerHTML = `
      <div class="empty-panel outing-loading-panel">
        <div class="spinner-border spinner-border-sm" aria-hidden="true"></div>
        <div>
          <strong>読み込み中</strong>
          <p>おでかけの候補と思い出を集めています。</p>
        </div>
      </div>
    `;
  }

  function renderEmptyCurrent(message = "まだ約束はありません。") {
    titleLabel.textContent = "おでかけ";
    statusLabel.textContent = "standby";
    currentHost.innerHTML = `
      <div class="empty-panel outing-empty">
        <i class="bi bi-signpost-2"></i>
        <div>
          <strong>待ち合わせ前です。</strong>
          <p>${NovelUI.escape(message)}</p>
        </div>
      </div>
    `;
    renderGallery(null);
  }

  function renderCurrent(outing) {
    currentOuting = outing;
    titleLabel.textContent = outing?.title || "Outing";
    statusLabel.textContent = outing?.status === "completed" ? "completed" : `step ${Number(outing?.current_step || 0) + 1}/${outing?.max_steps || 3}`;
    const steps = Array.isArray(outing?.steps) ? outing.steps : [];
    const step = steps[steps.length - 1];
    if (!step) {
      renderEmptyCurrent();
      return;
    }
    const sceneImage = step.image_asset?.media_url || "";
    const choices = Array.isArray(outing.choices) ? outing.choices : [];
    const sceneTitle = step.scene_title || outing.title || "Outing";
    const speaker = outing.character?.name || "Character";
    const narrationText = step.narration || "";
    const characterLine = step.character_line || "";
    const novelText = narrationText || characterLine;
    currentHost.innerHTML = `
      <div class="outing-chat-stage">
        <div class="live-chat-image-panel outing-image-panel">
          <div class="live-chat-stage-frame outing-stage-frame">
            ${sceneImage ? `
              <button class="outing-stage-image-button" type="button" data-image-url="${NovelUI.escape(sceneImage)}" data-image-title="${NovelUI.escape(sceneTitle)}">
                <img class="live-chat-stage-image outing-stage-image" src="${NovelUI.escape(sceneImage)}" alt="">
              </button>
            ` : `
              <div class="outing-stage-placeholder">
                <i class="bi bi-image"></i>
              </div>
            `}
            <div class="outing-stage-title">${NovelUI.escape(sceneTitle)}</div>
            <div class="live-chat-novel-box outing-novel-box ${outing.status === "completed" ? "is-completed" : ""}">
              <div class="live-chat-novel-speaker">${NovelUI.escape(speaker)}</div>
              <div class="live-chat-novel-text outing-novel-text">${NovelUI.escape(novelText)}</div>
              ${characterLine ? `<div class="outing-character-line">${NovelUI.escape(characterLine)}</div>` : ""}
              ${outing.status === "completed" ? renderMemory(outing) : renderChoices(choices)}
              <div class="live-chat-novel-footer outing-novel-footer">
                <div class="live-chat-novel-continue outing-novel-continue"></div>
                <div class="live-chat-novel-pager outing-novel-pager" aria-label="Outing text pages">
                  <button class="live-chat-novel-page-button" type="button" data-outing-page="prev">Prev</button>
                  <button class="live-chat-novel-page-button" type="button" data-outing-page="next">Next</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    setupOutingNovelPagination(novelText);
    setTextboxVisible(textboxVisible);
    renderGallery(outing);
  }

  function setTextboxVisible(visible) {
    textboxVisible = Boolean(visible);
    const novelBox = currentHost.querySelector(".outing-novel-box");
    if (novelBox) {
      novelBox.classList.toggle("is-hidden", !textboxVisible);
    }
    if (toggleTextboxButton) {
      toggleTextboxButton.textContent = textboxVisible ? "テキストボックス非表示" : "テキストボックス表示";
      toggleTextboxButton.setAttribute("aria-expanded", String(textboxVisible));
    }
  }

  function ensureOutingTextMeasurer(sourceElement) {
    let measurer = document.getElementById("outingNovelTextMeasure");
    if (!measurer) {
      measurer = document.createElement("div");
      measurer.id = "outingNovelTextMeasure";
      measurer.className = "live-chat-novel-text live-chat-novel-text-measure outing-novel-text";
      document.body.appendChild(measurer);
    }
    const style = window.getComputedStyle(sourceElement);
    measurer.style.width = `${sourceElement.clientWidth}px`;
    measurer.style.font = style.font;
    measurer.style.lineHeight = style.lineHeight;
    measurer.style.letterSpacing = style.letterSpacing;
    measurer.style.whiteSpace = style.whiteSpace;
    return measurer;
  }

  function fitOutingPageBreak(text, start, end) {
    if (end >= text.length) return end;
    const min = Math.max(start + 1, start + Math.floor((end - start) * 0.6));
    for (let index = end; index > min; index -= 1) {
      const pair = text.slice(index - 1, index + 1);
      const ch = text[index - 1];
      if (pair === "\n\n") return index;
      if (" \n、。！？,.!?）)]」』".includes(ch)) return index;
    }
    return end;
  }

  function paginateOutingNovelText(text) {
    const novelBox = currentHost.querySelector(".outing-novel-box");
    const novelText = currentHost.querySelector(".outing-novel-text");
    const novelSpeaker = currentHost.querySelector(".live-chat-novel-speaker");
    const choiceList = currentHost.querySelector(".outing-choice-list");
    const memoryBox = currentHost.querySelector(".outing-memory-box");
    const characterLine = currentHost.querySelector(".outing-character-line");
    const footer = currentHost.querySelector(".outing-novel-footer");
    const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
    if (!novelBox || !novelText || !novelSpeaker || !normalized) return [normalized || ""];
    if (isMobileOutingView()) return [normalized];
    const measurer = ensureOutingTextMeasurer(novelText);
    const boxStyle = window.getComputedStyle(novelBox);
    const paddingTop = parseFloat(boxStyle.paddingTop || "0");
    const paddingBottom = parseFloat(boxStyle.paddingBottom || "0");
    const gap = parseFloat(boxStyle.gap || "0");
    const choiceReserve = choiceList ? Math.min(choiceList.scrollHeight || 0, 132) : 0;
    const memoryReserve = memoryBox ? Math.min(memoryBox.scrollHeight || 0, 128) : 0;
    const lineReserve = characterLine ? Math.min(characterLine.scrollHeight || 0, 86) : 0;
    const footerReserve = footer ? Math.max(footer.offsetHeight, 28) : 28;
    const availableHeight = Math.max(
      48,
      novelBox.clientHeight - paddingTop - paddingBottom - novelSpeaker.offsetHeight - gap - footerReserve - choiceReserve - memoryReserve - lineReserve
    );
    const pages = [];
    let start = 0;
    while (start < normalized.length) {
      let low = start + 1;
      let high = normalized.length;
      let best = low;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        measurer.textContent = normalized.slice(start, mid).trim();
        if (measurer.scrollHeight <= availableHeight) {
          best = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
      let end = fitOutingPageBreak(normalized, start, best);
      if (end <= start) end = Math.min(normalized.length, start + 1);
      pages.push(normalized.slice(start, end).trim());
      start = end;
      while (start < normalized.length && /\s/.test(normalized[start])) start += 1;
    }
    return pages.length ? pages : [normalized];
  }

  function renderOutingNovelPage() {
    const novelText = currentHost.querySelector(".outing-novel-text");
    const choiceList = currentHost.querySelector(".outing-choice-list");
    const footer = currentHost.querySelector(".outing-novel-footer");
    const cue = currentHost.querySelector(".outing-novel-continue");
    const pager = currentHost.querySelector(".outing-novel-pager");
    const prevButton = currentHost.querySelector('[data-outing-page="prev"]');
    const nextButton = currentHost.querySelector('[data-outing-page="next"]');
    const pages = outingNovelPageState.pages || [""];
    const pageIndex = Math.max(0, Math.min(outingNovelPageState.pageIndex || 0, pages.length - 1));
    outingNovelPageState.pageIndex = pageIndex;
    if (novelText) novelText.textContent = pages[pageIndex] || "";
    const showPager = !isMobileOutingView() && pages.length > 1;
    if (footer) footer.hidden = !showPager;
    if (pager) pager.hidden = !showPager;
    if (cue) {
      cue.hidden = !showPager;
      cue.textContent = showPager ? `${pageIndex + 1} / ${pages.length}` : "";
    }
    if (prevButton) {
      prevButton.hidden = !showPager;
      prevButton.disabled = !showPager || pageIndex <= 0;
    }
    if (nextButton) {
      nextButton.hidden = !showPager;
      nextButton.disabled = !showPager || pageIndex >= pages.length - 1;
    }
    if (choiceList) {
      choiceList.hidden = showPager && pageIndex < pages.length - 1;
      if (isMobileOutingView()) choiceList.hidden = false;
    }
  }

  function setupOutingNovelPagination(text) {
    const choiceList = currentHost.querySelector(".outing-choice-list");
    if (choiceList) choiceList.hidden = false;
    outingNovelPageState = {
      pages: paginateOutingNovelText(text),
      pageIndex: 0,
    };
    renderOutingNovelPage();
  }

  window.addEventListener("resize", () => {
    renderOutingNovelPage();
  });

  function moveOutingNovelPage(delta) {
    const pages = outingNovelPageState.pages || [];
    if (!pages.length) return false;
    const nextIndex = Math.max(0, Math.min((outingNovelPageState.pageIndex || 0) + delta, pages.length - 1));
    if (nextIndex === outingNovelPageState.pageIndex) return false;
    outingNovelPageState.pageIndex = nextIndex;
    renderOutingNovelPage();
    return true;
  }

  function renderGallery(outing) {
    const steps = Array.isArray(outing?.steps) ? outing.steps : [];
    const images = steps
      .map((step, index) => ({
        index,
        title: step.scene_title || `Step ${index + 1}`,
        url: step.image_asset?.media_url || "",
      }))
      .filter((item) => item.url);
    galleryCount.textContent = `${images.length} images`;
    if (!images.length) {
      galleryHost.innerHTML = `
        <div class="empty-panel">
          <i class="bi bi-images"></i>
          <div>
            <strong>このおでかけの画像はまだありません。</strong>
            <p>おでかけを進めると、生成されたイベントCGがここに並びます。</p>
          </div>
        </div>
      `;
      return;
    }
    galleryHost.innerHTML = images.map((image) => `
      <button class="outing-gallery-card" type="button" data-image-url="${NovelUI.escape(image.url)}" data-image-title="${NovelUI.escape(image.title)}">
        <img src="${NovelUI.escape(image.url)}" alt="">
        <span>${NovelUI.escape(image.title)}</span>
      </button>
    `).join("");
  }

  function renderChoices(choices) {
    if (!choices.length) return "";
    return `
      <div class="live-chat-novel-choice-list outing-choice-list">
        <div class="live-chat-novel-choice-copy">Choice</div>
        <div class="live-chat-novel-choice-buttons">
          ${choices.map((choice) => `
            <button class="live-chat-novel-choice-button outing-choice-button" type="button" data-choice-id="${NovelUI.escape(choice.id)}">
              <span>${NovelUI.escape(choice.label)}</span>
              <i class="bi bi-chevron-right"></i>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderMemory(outing) {
    return `
      <div class="outing-memory-box">
        <div class="eyebrow">Memory</div>
        <strong>${NovelUI.escape(outing.memory_title || "今日の思い出")}</strong>
        <p>${NovelUI.escape(outing.memory_summary || "おでかけの思い出が残りました。")}</p>
      </div>
    `;
  }

  function renderHistory(outings) {
    const list = Array.isArray(outings) ? outings : [];
    historyCount.textContent = `${list.length} outings`;
    if (!list.length) {
      historyHost.innerHTML = `
        <div class="empty-panel">
          <i class="bi bi-journal-heart"></i>
          <div>
            <strong>思い出はまだありません。</strong>
            <p>最初の寄り道を待っています。</p>
          </div>
        </div>
      `;
      return;
    }
    historyHost.innerHTML = list.map((outing) => `
      <article class="outing-history-card" data-outing-id="${outing.id}">
        <div class="outing-history-thumb">
          ${imageForLocation(outing.location) ? `<img src="${NovelUI.escape(imageForLocation(outing.location))}" alt="">` : `<i class="bi bi-signpost"></i>`}
        </div>
        <div>
          <div class="outing-history-meta">
            <span>${NovelUI.escape(outing.character?.name || "Character")}</span>
            <span>${NovelUI.escape(outing.status || "")}</span>
          </div>
          <h4>${NovelUI.escape(outing.memory_title || outing.title || "おでかけ")}</h4>
          <p>${NovelUI.escape(outing.memory_summary || outing.summary || "")}</p>
        </div>
      </article>
    `).join("");
  }

  async function loadOptions() {
    renderHistoryLoading();
    setLoading(true, "読み込み中", "キャラクター、施設、思い出を準備しています。");
    const data = await NovelUI.api(`/api/v1/projects/${projectId}/outings/options`);
    renderSelects(data);
    renderHistory(data.recent_outings || []);
    if (!currentOuting) renderEmptyCurrent();
    setLoading(false);
  }

  async function refreshHistory() {
    const outings = await NovelUI.api(`/api/v1/projects/${projectId}/outings`);
    renderHistory(outings);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setLoading(true, "おでかけ準備中", "最初の場面とイベントCGを生成しています。画像生成が入るため少し時間がかかります。");
    try {
      const outing = await NovelUI.api(`/api/v1/projects/${projectId}/outings`, {
        method: "POST",
        body: {
          character_id: Number(characterSelect.value),
          location_id: Number(locationSelect.value),
          outfit_id: /^\d+$/.test(outfitSelect.value) ? Number(outfitSelect.value) : null,
          outfit_mode: outfitSelect.value === "base" ? "base" : outfitSelect.value === "auto" ? "auto" : "selected",
          mood: moodInput.value.trim(),
        },
      });
      renderCurrent(outing);
      await refreshHistory();
      NovelUI.toast("おでかけを開始しました。");
    } catch (error) {
      NovelUI.toast(error.message || "おでかけを開始できませんでした。", "danger");
    } finally {
      setLoading(false);
    }
  });

  currentHost.addEventListener("click", async (event) => {
    const pageButton = event.target.closest("[data-outing-page]");
    if (pageButton) {
      moveOutingNovelPage(pageButton.dataset.outingPage === "prev" ? -1 : 1);
      return;
    }
    const button = event.target.closest("[data-choice-id]");
    if (!button || !currentOuting || isBusy) return;
    setLoading(true, "次の場面へ", "選択に合わせて本文とイベントCGを更新しています。");
    try {
      const outing = await NovelUI.api(`/api/v1/outings/${currentOuting.id}/choose`, {
        method: "POST",
        body: { choice_id: button.dataset.choiceId },
      });
      renderCurrent(outing);
      await refreshHistory();
      if (outing.status === "completed") {
        NovelUI.refreshLetterBadge?.();
        NovelUI.toast("おでかけの余韻がメールに届きました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "選択肢を進められませんでした。", "danger");
    } finally {
      setLoading(false);
    }
  });

  currentHost.addEventListener("click", (event) => {
    const button = event.target.closest("[data-image-url]");
    if (!button || !button.dataset.imageUrl) return;
    imageModalTitle.textContent = button.dataset.imageTitle || "おでかけ画像";
    imageModalImage.src = button.dataset.imageUrl;
    imageModalImage.alt = button.dataset.imageTitle || "";
    imageModal.show();
  });

  galleryHost.addEventListener("click", (event) => {
    const button = event.target.closest("[data-image-url]");
    if (!button || !button.dataset.imageUrl) return;
    imageModalTitle.textContent = button.dataset.imageTitle || "おでかけ画像";
    imageModalImage.src = button.dataset.imageUrl;
    imageModalImage.alt = button.dataset.imageTitle || "";
    imageModal.show();
  });

  historyHost.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-outing-id]");
    if (!card || isBusy) return;
    setLoading(true, "思い出を開いています", "保存されたおでかけを読み込んでいます。");
    try {
      const outing = await NovelUI.api(`/api/v1/outings/${card.dataset.outingId}`);
      renderCurrent(outing);
    } catch (error) {
      NovelUI.toast(error.message || "おでかけを開けませんでした。", "danger");
    } finally {
      setLoading(false);
    }
  });

  refreshButton.addEventListener("click", () => {
    loadOptions().catch((error) => {
      setLoading(false);
      NovelUI.toast(error.message || "読み込みに失敗しました。", "danger");
    });
  });

  characterSelect.addEventListener("change", () => {
    const outfits = JSON.parse(outfitSelect.dataset.outfits || "[]");
    renderOutfitOptions(outfits);
  });

  loadOptions().catch((error) => {
    setLoading(false);
    renderEmptyCurrent("読み込みに失敗しました。");
    NovelUI.toast(error.message || "おでかけ情報を読み込めませんでした。", "danger");
  });

  toggleTextboxButton?.addEventListener("click", () => {
    setTextboxVisible(!textboxVisible);
  });
})();
