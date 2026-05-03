(() => {
  const shell = document.querySelector("[data-session-id][data-project-id]");
  const projectId = Number(shell?.dataset.projectId || 0);
  const sessionId = Number(shell?.dataset.sessionId || 0);
  let currentSession = null;
  let composeVisible = true;
  let textboxVisible = true;
  let messageSortOrder = "desc";
  let novelPageState = { signature: "", index: 0, pages: [] };

  function latestDisplayMessage(messages) {
    const reversed = [...(messages || [])].reverse();
    return reversed.find((message) => message.sender_type === "character")
      || reversed.find((message) => message.sender_type === "gm")
      || reversed[0]
      || null;
  }

  function latestGmMessage(messages) {
    return [...(messages || [])].reverse().find((message) => message.sender_type === "gm") || null;
  }

  function mainCharacterName(session) {
    return session?.story?.character?.name
      || session?.story_snapshot_json?.character?.name
      || session?.story_snapshot?.character?.name
      || "キャラクター";
  }

  function renderState(state) {
    const json = state?.state_json || {};
    const game = json.game_state || {};
    const rel = json.relationship_state || {};
    const goal = json.goal_state || {};
    const event_state = json.event_state || {};
    const storyConfig = currentSession?.story?.config_json || currentSession?.story_snapshot_json?.config_json || {};
    const mainGoal = goal.main_goal || storyConfig.main_goal || storyConfig.goal || currentSession?.story?.description || "未設定";
    const currentGoal = goal.current_goal || storyConfig.current_goal || mainGoal;
    const clearConditions = Array.isArray(goal.clear_conditions) && goal.clear_conditions.length
      ? goal.clear_conditions
      : (Array.isArray(storyConfig.clear_conditions) ? storyConfig.clear_conditions : []);
    const location = game.location || "未設定";
    document.getElementById("storyLocationValue").textContent = location;
    document.getElementById("storyDangerValue").textContent = game.danger ?? 0;
    document.getElementById("storyAffectionValue").textContent = rel.affection ?? 0;
    document.getElementById("storyTensionValue").textContent = rel.tension ?? 0;
    document.getElementById("storyMainGoalValue").textContent = mainGoal;
    document.getElementById("storyCurrentGoalValue").textContent = currentGoal;
    const currentTurn = goal.current_turn || event_state?.turn_count || 0;
    const maxTurns = goal.max_turns || 10;
    const phaseLabel = goal.current_phase_label || "";
    document.getElementById("storyTurnPhaseValue").innerHTML = `
      <span>${NovelUI.escape(`${currentTurn}/${maxTurns}ターン`)}</span>
      ${phaseLabel ? `<span>${NovelUI.escape(phaseLabel)}</span>` : ""}
    `;
    document.getElementById("storyClearConditionList").innerHTML = clearConditions.length
      ? clearConditions.map((item) => `<span>${NovelUI.escape(item)}</span>`).join("")
      : "";

    const inventory = Array.isArray(game.inventory) ? game.inventory : [];
    document.getElementById("storyInventoryList").innerHTML = inventory.length
      ? inventory.map((item) => {
        const itemName = item.name || item.id || "item";
        const actionText = `所持品「${itemName}」を使う`;
        return `
          <button class="story-session-token-button" type="button" data-item-action="${NovelUI.escape(actionText)}" title="${NovelUI.escape(actionText)}">
            ${NovelUI.escape(itemName)}
          </button>
        `;
      }).join("")
      : '<span class="is-empty">なし</span>';
  }

  function renderActiveImage(session) {
    const frame = document.getElementById("storyStageFrame");
    const image = session?.active_image;
    const url = image?.media_url;
    const existing = frame.querySelector(".live-chat-stage-image");
    existing?.remove();
    if (!url) {
      if (!frame.querySelector(".empty-panel")) {
        frame.insertAdjacentHTML("afterbegin", '<div class="empty-panel">まだ画像がありません。</div>');
      }
      return;
    }
    frame.querySelector(".empty-panel")?.remove();
    frame.insertAdjacentHTML("afterbegin", `<img class="live-chat-stage-image" src="${NovelUI.escape(url)}" alt="現在の場面">`);
  }

  function latestStageMessages(messages) {
    const items = Array.isArray(messages) ? messages.filter((message) => (message?.message_text || "").trim()) : [];
    if (!items.length) return [];
    let start = items.length - 1;
    for (; start >= 0; start -= 1) {
      if (items[start].sender_type === "user") break;
    }
    if (start >= 0 && start < items.length - 1) {
      return items.slice(start + 1);
    }
    return items.slice(Math.max(0, start));
  }

  function splitNovelText(text) {
    const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
    if (!normalized) return [""];
    const maxLength = 260;
    const pages = [];
    let rest = normalized;
    while (rest.length > maxLength) {
      let index = rest.lastIndexOf("\n", maxLength);
      if (index < maxLength * 0.55) {
        index = Math.max(
          rest.lastIndexOf("。", maxLength),
          rest.lastIndexOf("、", maxLength),
          rest.lastIndexOf(" ", maxLength)
        );
      }
      if (index < maxLength * 0.55) index = maxLength;
      pages.push(rest.slice(0, index + 1).trim());
      rest = rest.slice(index + 1).trim();
    }
    if (rest) pages.push(rest);
    return pages;
  }

  function buildNovelPages(messages, state) {
    const stageMessages = latestStageMessages(messages);
    const pages = [];
    stageMessages.forEach((message) => {
      splitNovelText(message.message_text || "").forEach((text, pageIndex, pageList) => {
        pages.push({
          id: message.id,
          speaker: message.speaker_name || message.sender_type || "GM",
          text,
          subPage: pageList.length > 1 ? `${pageIndex + 1}/${pageList.length}` : "",
        });
      });
    });
    const choices = state?.state_json?.choice_state?.last_choices || [];
    if (choices.length) {
      pages.push({
        id: "choices",
        speaker: "NEXT ACTION",
        text: "",
        choices,
        isChoicePage: true,
      });
    }
    return pages.length ? pages : [{ id: "empty", speaker: "GM", text: "行動を選んでセッションを進めてください。" }];
  }

  function renderNovelPage() {
    const pages = novelPageState.pages || [];
    const index = Math.max(0, Math.min(novelPageState.index || 0, Math.max(0, pages.length - 1)));
    novelPageState.index = index;
    const page = pages[index] || {};
    const speaker = document.getElementById("storyNovelSpeaker");
    const text = document.getElementById("storyNovelText");
    const list = document.getElementById("storyNovelChoiceList");
    const counter = document.getElementById("storyNovelContinue");
    const pager = document.getElementById("storyNovelPager");
    const prev = document.getElementById("storyNovelPrevButton");
    const next = document.getElementById("storyNovelNextButton");
    speaker.textContent = page.speaker || "GM";
    text.textContent = page.isChoicePage ? "" : (page.text || "");
    if (page.isChoicePage && Array.isArray(page.choices) && page.choices.length) {
      list.hidden = false;
      list.innerHTML = `
        <div class="live-chat-novel-choice-copy">次の行動を選んでください</div>
        <div class="live-chat-novel-choice-buttons">
          ${page.choices.map((choice) => `
            <button class="live-chat-choice-button live-chat-novel-choice-button" type="button" data-choice-id="${NovelUI.escape(choice.id || "")}">
              ${NovelUI.escape(choice.label || "選択する")}
            </button>
          `).join("")}
        </div>
      `;
    } else {
      list.hidden = true;
      list.innerHTML = "";
    }
    const hasPager = pages.length > 1;
    counter.hidden = false;
    counter.textContent = `${index + 1} / ${pages.length}${page.subPage ? ` - ${page.subPage}` : ""}`;
    pager.hidden = !hasPager;
    prev.hidden = !hasPager;
    next.hidden = !hasPager;
    prev.disabled = !hasPager || index <= 0;
    next.disabled = !hasPager || index >= pages.length - 1;
  }

  function renderNovel(messages, state) {
    const pages = buildNovelPages(messages, state);
    const signature = pages.map((page) => `${page.id}:${page.subPage || ""}:${page.isChoicePage ? "choice" : ""}`).join("|");
    const isSame = novelPageState.signature === signature;
    novelPageState = {
      signature,
      pages,
      index: isSame ? Math.min(novelPageState.index, Math.max(0, pages.length - 1)) : 0,
    };
    renderNovelPage();
  }

  function renderSituation(messages) {
    const panel = document.getElementById("storySituationPanel");
    const text = document.getElementById("storySituationText");
    const latest = latestGmMessage(messages);
    if (!latest?.message_text) {
      panel.classList.add("is-hidden");
      text.textContent = "";
      return;
    }
    text.textContent = latest.message_text;
    panel.classList.remove("is-hidden");
  }

  function renderImageGallery(session) {
    const gallery = document.getElementById("storyImageGallery");
    const grid = document.getElementById("storyImageGalleryGrid");
    const count = document.getElementById("storyImageGalleryCount");
    const images = (session?.images || []).filter((image) => {
      const type = image?.visual_type || "";
      return image?.asset?.media_url && !["costume_initial", "costume_reference"].includes(type);
    });
    if (!images.length) {
      gallery.classList.add("is-hidden");
      grid.innerHTML = "";
      count.textContent = "0枚";
      return;
    }
    count.textContent = `${images.length}枚`;
    const activeAssetId = session?.active_image_id;
    grid.innerHTML = images.map((image) => {
      const url = image.asset.media_url;
      const isActive = Number(image.asset_id) === Number(activeAssetId);
      const title = image.subject || image.visual_type || "生成画像";
      return `
        <button class="story-image-gallery-thumb ${isActive ? "is-active" : ""}" type="button" data-gallery-src="${NovelUI.escape(url)}" title="${NovelUI.escape(title)}" aria-label="${NovelUI.escape(title)}を最大表示">
          <img src="${NovelUI.escape(url)}" alt="${NovelUI.escape(title)}" data-gallery-src="${NovelUI.escape(url)}">
          ${isActive ? '<span>表示中</span>' : ""}
        </button>
      `;
    }).join("");
    gallery.classList.remove("is-hidden");
  }

  function renderMessages(messages) {
    const list = document.getElementById("storyMessageList");
    const sortedMessages = [...(messages || [])];
    if (messageSortOrder === "desc") {
      sortedMessages.reverse();
    }
    list.innerHTML = sortedMessages.map((message) => `
      <article class="live-chat-message ${["user", "player"].includes(message.sender_type) ? "is-user" : ""}">
        <div class="live-chat-message-meta">
          <strong>${NovelUI.escape(message.speaker_name || message.sender_type)}</strong>
          <span>${NovelUI.escape(message.message_type || "")}</span>
        </div>
        <div class="live-chat-message-text">${NovelUI.escape(message.message_text || "")}</div>
      </article>
    `).join("");
  }

  function renderChoices(state) {
    const panel = document.getElementById("storyChoicePanel");
    panel.classList.add("is-hidden");
    panel.innerHTML = "";
  }

  function renderCostumes(session) {
    const costumes = session?.costumes || [];
    const selected = session?.selected_costume || costumes.find((item) => item.is_selected) || costumes[0] || null;
    const preview = document.getElementById("storyCostumePreview");
    const grid = document.getElementById("storyCostumeGrid");
    const previewUrl = selected?.asset?.media_url;
    preview.innerHTML = previewUrl
      ? `
        <button class="live-chat-costume-preview-button" type="button" data-costume-preview-src="${NovelUI.escape(previewUrl)}">
          <img src="${NovelUI.escape(previewUrl)}" alt="selected costume reference">
          <span>現在の衣装基準</span>
        </button>
      `
      : '<div class="empty-panel">衣装の基準画像がありません。</div>';
    if (!costumes.length) {
      grid.innerHTML = '<div class="empty-panel">衣装候補がありません。</div>';
      return;
    }
    grid.innerHTML = costumes.map((item) => {
      const mediaUrl = item.asset?.media_url;
      const label = item.visual_type === "costume_initial" || item.image_type === "costume_initial" ? "初期衣装" : "衣装";
      return `
        <div class="live-chat-costume-card ${item.is_selected ? "selected" : ""}">
          <button class="live-chat-costume-select" type="button" data-costume-id="${NovelUI.escape(item.id)}">
            ${mediaUrl ? `<img src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(label)}">` : "<span>No Image</span>"}
            <span class="live-chat-costume-card-label">${item.is_selected ? "選択中" : NovelUI.escape(label)}</span>
          </button>
        </div>
      `;
    }).join("");
  }

  async function loadSession() {
    currentSession = await NovelUI.api(`/api/v1/story-sessions/${sessionId}`);
    document.getElementById("storySessionTitle").textContent = currentSession.title || "セッション";
    document.getElementById("storyComposeHint").textContent = `${mainCharacterName(currentSession)}と話せます`;
    renderActiveImage(currentSession);
    renderState(currentSession.state);
    renderNovel(currentSession.messages, currentSession.state);
    renderSituation(currentSession.messages);
    renderImageGallery(currentSession);
    renderMessages(currentSession.messages);
    renderChoices(currentSession.state);
    renderCostumes(currentSession);
  }

  function setBusy(isBusy, label = "進行中") {
    const frame = document.getElementById("storyStageFrame");
    const buttons = document.querySelectorAll(
      "#storyNovelChoiceList button, #storyChoicePanel button, #storyInventoryList button, #storyImageGalleryGrid button, #storyComposeForm button, #storyRollButton, #storyGenerateImageButton, #storyAutoLineInlineButton, #storyToggleTextboxButton, #storyCostumeGrid button, #storyCostumePreview button"
    );
    frame.classList.toggle("is-loading", Boolean(isBusy));
    frame.dataset.loadingLabel = label;
    buttons.forEach((button) => {
      button.disabled = Boolean(isBusy);
    });
  }

  function setComposeVisible(visible) {
    composeVisible = Boolean(visible);
    const shell = document.getElementById("storyComposeShell");
    const headerButton = document.getElementById("storyToggleComposeButton");
    const choicePanel = document.getElementById("storyChoicePanel");
    shell?.classList.toggle("is-collapsed", !composeVisible);
    if (!composeVisible) {
      choicePanel?.classList.add("is-hidden");
    } else {
      renderChoices(currentSession?.state);
    }
    if (headerButton) {
      headerButton.textContent = composeVisible ? "行動欄を閉じる" : "行動欄を開く";
      headerButton.setAttribute("aria-expanded", String(composeVisible));
    }
  }

  function setTextboxVisible(visible) {
    textboxVisible = Boolean(visible);
    const novelBox = document.getElementById("storyNovelBox");
    const stageButton = document.getElementById("storyToggleTextboxButton");
    novelBox?.classList.toggle("is-hidden", !textboxVisible);
    if (stageButton) {
      stageButton.textContent = textboxVisible ? "テキストボックス非表示" : "テキストボックス表示";
      stageButton.setAttribute("aria-expanded", String(textboxVisible));
    }
  }

  function openImageLightbox(src) {
    const lightbox = document.getElementById("storyImageLightbox");
    const image = document.getElementById("storyImageLightboxImage");
    if (!lightbox || !image || !src) return;
    image.src = src;
    lightbox.classList.remove("is-hidden");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("live-chat-lightbox-open");
  }

  function closeImageLightbox() {
    const lightbox = document.getElementById("storyImageLightbox");
    const image = document.getElementById("storyImageLightboxImage");
    if (!lightbox || !image) return;
    lightbox.classList.add("is-hidden");
    lightbox.setAttribute("aria-hidden", "true");
    image.removeAttribute("src");
    document.body.classList.remove("live-chat-lightbox-open");
  }

  async function submitText(text) {
    const value = String(text || "").trim();
    if (!value) return;
    setBusy(true, "GMが裁定中");
    try {
      await NovelUI.api(`/api/v1/story-sessions/${sessionId}/messages`, {
        method: "POST",
        body: { message_text: value },
      });
      await loadSession();
    } finally {
      setBusy(false);
    }
  }

  async function executeChoice(choiceId) {
    if (!choiceId) return;
    const skipImage = document.getElementById("storySkipImageGeneration")?.checked ?? false;
    setBusy(true, skipImage ? "選択を反映中" : "選択と画像を反映中");
    try {
      const result = await NovelUI.api(`/api/v1/story-sessions/${sessionId}/choices/${choiceId}/execute`, {
        method: "POST",
        body: { generate_image: !skipImage },
      });
      if (result?.image_generation_error) {
        NovelUI.toast("場面は進行しましたが、画像生成に失敗しました。", "warning");
      }
      await loadSession();
    } finally {
      setBusy(false);
    }
  }

  async function generateImage(button) {
    setBusy(true, "画像生成中");
    try {
      await NovelUI.api(`/api/v1/story-sessions/${sessionId}/images`, {
        method: "POST",
        body: {},
      });
      await loadSession();
    } finally {
      setBusy(false);
    }
  }

  async function selectCostume(imageId) {
    if (!imageId) return;
    await NovelUI.api(`/api/v1/story-sessions/${sessionId}/costumes/${imageId}/select`, {
      method: "POST",
      body: {},
    });
    await loadSession();
    NovelUI.toast("衣装の基準画像を変更しました。");
  }

  document.getElementById("storyComposeForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("storyComposeInput");
    const text = input.value.trim();
    input.value = "";
    await submitText(text);
  });

  document.getElementById("storyChoicePanel").addEventListener("click", (event) => {
    const button = event.target.closest("[data-choice-id]");
    if (button) executeChoice(button.dataset.choiceId);
  });

  document.getElementById("storyNovelChoiceList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-choice-id]");
    if (button) executeChoice(button.dataset.choiceId);
  });

  document.getElementById("storyNovelPrevButton").addEventListener("click", () => {
    novelPageState.index = Math.max(0, (novelPageState.index || 0) - 1);
    renderNovelPage();
  });

  document.getElementById("storyNovelNextButton").addEventListener("click", () => {
    novelPageState.index = Math.min(Math.max(0, (novelPageState.pages || []).length - 1), (novelPageState.index || 0) + 1);
    renderNovelPage();
  });

  document.getElementById("storyInventoryList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-item-action]");
    if (!button) return;
    submitText(button.dataset.itemAction);
  });

  const skipImageGenerationCheckbox = document.getElementById("storySkipImageGeneration");
  const skipImageGenerationStorageKey = `story:${sessionId}:skip-image-generation`;
  const storedSkipImageGeneration = localStorage.getItem(skipImageGenerationStorageKey);
  if (storedSkipImageGeneration !== null) {
    skipImageGenerationCheckbox.checked = storedSkipImageGeneration === "true";
  }
  skipImageGenerationCheckbox.addEventListener("change", () => {
    localStorage.setItem(skipImageGenerationStorageKey, String(skipImageGenerationCheckbox.checked));
  });

  document.getElementById("storyImagePanel").addEventListener("click", (event) => {
    const image = event.target.closest(".live-chat-stage-image");
    if (!image) return;
    openImageLightbox(image.getAttribute("src"));
  });

  document.getElementById("storyImageGalleryGrid").addEventListener("click", (event) => {
    const target = event.target.closest("[data-gallery-src]");
    if (!target) return;
    openImageLightbox(target.dataset.gallerySrc);
  });

  document.getElementById("storyImageLightboxClose").addEventListener("click", closeImageLightbox);

  document.getElementById("storyImageLightbox").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) {
      closeImageLightbox();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const lightbox = document.getElementById("storyImageLightbox");
    if (lightbox && !lightbox.classList.contains("is-hidden")) {
      closeImageLightbox();
    }
  });

  document.getElementById("storyToggleLogButton").addEventListener("click", () => {
    const body = document.getElementById("storyLogBody");
    const button = document.getElementById("storyToggleLogButton");
    const willOpen = body.classList.contains("is-hidden");
    body.classList.toggle("is-hidden", !willOpen);
    button.setAttribute("aria-expanded", String(willOpen));
    button.textContent = willOpen ? "ログを閉じる" : "ログを開く";
  });

  document.getElementById("storyLogSortSelect").addEventListener("change", (event) => {
    messageSortOrder = event.target.value === "asc" ? "asc" : "desc";
    renderMessages(currentSession?.messages || []);
  });

  document.getElementById("storyToggleComposeButton").addEventListener("click", () => {
    setComposeVisible(!composeVisible);
  });

  document.getElementById("storyToggleTextboxButton").addEventListener("click", () => {
    setTextboxVisible(!textboxVisible);
  });

  document.getElementById("storyRollButton").addEventListener("click", async () => {
    setBusy(true, "サイコロ判定中");
    try {
      await NovelUI.api(`/api/v1/story-sessions/${sessionId}/rolls`, {
        method: "POST",
        body: { formula: "1d20", reason: "判定" },
      });
      await loadSession();
    } finally {
      setBusy(false);
    }
  });

  async function autoLine() {
    setBusy(true, "下書き生成中");
    try {
      const draft = await NovelUI.api(`/api/v1/story-sessions/${sessionId}/player-draft`, {
        method: "POST",
        body: {},
      });
      const input = document.getElementById("storyComposeInput");
      input.value = draft.message_text || "";
      input.focus();
    } finally {
      setBusy(false);
    }
  }

  document.getElementById("storyAutoLineInlineButton").addEventListener("click", autoLine);
  document.getElementById("storyGenerateImageButton").addEventListener("click", (event) => generateImage(event.currentTarget));
  document.getElementById("storyCostumeGrid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-costume-id]");
    if (button) selectCostume(button.dataset.costumeId).catch((error) => NovelUI.toast(error.message || "衣装の選択に失敗しました。", "danger"));
  });
  document.getElementById("storyCostumePreview").addEventListener("click", (event) => {
    const button = event.target.closest("[data-costume-preview-src]");
    if (button) openImageLightbox(button.dataset.costumePreviewSrc);
  });

  setComposeVisible(true);
  setTextboxVisible(true);
  loadSession().catch((error) => NovelUI.toast(error.message || "セッションを読み込めませんでした。", "danger"));
})();
