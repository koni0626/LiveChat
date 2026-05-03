(function () {
  const root = document.querySelector(".live-chat-shell[data-session-id]");
  if (!root) return;

  const { LiveChatApi, LiveChatView, LiveChatGift, LiveChatActions, LiveChatShell, LiveChatCostumeRoom } = window;
  if (!LiveChatApi || !LiveChatView || !LiveChatGift || !LiveChatActions || !LiveChatShell || !LiveChatCostumeRoom) {
    throw new Error("LiveChat dependencies are not loaded");
  }

  const sessionId = Number(root.dataset.sessionId || 0);
  const projectId = Number(document.body?.dataset?.projectId || 0);
  const stateBoard = document.getElementById("liveChatStateBoard");
  const memoryBoard = document.getElementById("liveChatMemoryBoard");
  const selectedImagePanel = document.getElementById("liveChatSelectedImagePanel");
  const stageElement = document.querySelector(".live-chat-stage");
  const stageActions = document.querySelector(".live-chat-stage-actions");
  const stageActionsHandle = document.getElementById("liveChatStageActionsHandle");
  const composeForm = document.getElementById("liveChatComposeForm");
  const composeInput = document.getElementById("liveChatComposeInput");
  const composeShell = document.getElementById("liveChatComposeShell");
  const toggleComposeButton = document.getElementById("liveChatToggleComposeButton");
  const proxyMessageButton = document.getElementById("liveChatProxyMessageButton");
  const imageForm = document.getElementById("liveChatImageForm");
  const uploadForm = document.getElementById("liveChatImageUploadForm");
  const costumeForm = document.getElementById("liveChatCostumeForm");
  const costumeGrid = document.getElementById("liveChatCostumeGrid");
  const costumePreview = document.getElementById("liveChatCostumePreview");
  const generateCostumeButton = document.getElementById("liveChatGenerateCostumeButton");
  const closetSelectButton = document.getElementById("liveChatClosetSelectButton");
  const closetSelectModalElement = document.getElementById("liveChatClosetSelectModal");
  const closetPicker = document.getElementById("liveChatClosetPicker");
  const sceneChoicePanel = document.getElementById("liveChatSceneChoicePanel");
  const locationMovePanel = document.getElementById("liveChatLocationMovePanel");
  const toggleLocationMoveButton = document.getElementById("liveChatToggleLocationMoveButton");
  const lccdPanel = document.getElementById("liveChatLccdPanel");
  const toggleLccdButton = document.getElementById("liveChatToggleLccdButton");
  const conversationModeButton = document.getElementById("liveChatConversationModeButton");
  const togglePhotoModeButton = document.getElementById("liveChatTogglePhotoModeButton");
  const lccdCloseButton = document.getElementById("liveChatLccdCloseButton");
  const lccdForm = document.getElementById("liveChatLccdForm");
  const lccdGenerateButton = document.getElementById("liveChatLccdGenerateButton");
  const objectiveInitial = document.getElementById("liveChatObjectiveInitial");
  const objectiveList = document.getElementById("liveChatObjectiveList");
  const objectiveCount = document.getElementById("liveChatObjectiveDebugCount");
  const cameraToggleButton = document.getElementById("liveChatCameraToggleButton");
  const cameraStatus = document.getElementById("liveChatCameraStatus");
  const cameraStatusText = document.getElementById("liveChatCameraStatusText");
  const cameraVideo = document.getElementById("liveChatCameraVideo");
  const cameraCanvas = document.getElementById("liveChatCameraCanvas");
  const shortStoryButton = document.getElementById("liveChatGenerateShortStoryButton");
  const shortStoryToneSelect = document.getElementById("liveChatShortStoryToneSelect");
  const shortStoryLengthSelect = document.getElementById("liveChatShortStoryLengthSelect");
  const shortStoryInstructionInput = document.getElementById("liveChatShortStoryInstructionInput");
  const shortStoryImagesCheckbox = document.getElementById("liveChatShortStoryImagesCheckbox");
  const saveShortStoryButton = document.getElementById("liveChatSaveShortStoryButton");
  const shortStoryResult = document.getElementById("liveChatShortStoryResult");
  const savedShortStories = document.getElementById("liveChatSavedShortStories");
  const savedShortStoryList = document.getElementById("liveChatSavedShortStoryList");
  const shortStoryMeta = document.getElementById("liveChatShortStoryMeta");
  const shortStoryTitle = document.getElementById("liveChatShortStoryTitle");
  const shortStorySynopsis = document.getElementById("liveChatShortStorySynopsis");
  const shortStoryBody = document.getElementById("liveChatShortStoryBody");
  const shortStoryAfterword = document.getElementById("liveChatShortStoryAfterword");
  const shortStoryOpeningImageWrap = document.getElementById("liveChatShortStoryOpeningImageWrap");
  const shortStoryOpeningImage = document.getElementById("liveChatShortStoryOpeningImage");
  const shortStoryEndingImageWrap = document.getElementById("liveChatShortStoryEndingImageWrap");
  const shortStoryEndingImage = document.getElementById("liveChatShortStoryEndingImage");
  const cameraFeatureEnabled = false;

  let currentContext = null;
  let giftController = null;
  let costumeRoomController = null;
  let composeVisible = true;
  let userDefaultImageSettings = {};
  let cameraEnabled = false;
  let cameraStream = null;
  let cameraBusy = false;
  let locationMoveVisible = false;
  let locationMoveBusy = false;
  let lccdVisible = false;
  let lccdBusy = false;
  let lccdEnterBusy = false;
  let conversationModeActive = true;
  let photoModeActive = false;
  let photoModeBusy = false;
  let currentShortStory = null;
  let idleTalkTimer = null;
  let idleTalkBusy = false;
  let idleTalksSincePlayerInput = 0;
  const stageActionIcons = {
    dressUp: '<i class="bi bi-person-standing-dress" aria-hidden="true"></i>',
    conversation: '<i class="bi bi-chat-dots-fill" aria-hidden="true"></i>',
    photoMode: '<i class="bi bi-camera-fill" aria-hidden="true"></i>',
    cameraOn: '<i class="bi bi-webcam-fill" aria-hidden="true"></i>',
    cameraOff: '<i class="bi bi-webcam" aria-hidden="true"></i>',
  };
  const idleTalkEnabled = false;
  const idleTalkMinMs = 10000;
  const idleTalkMaxMs = 30000;
  const stageActionsStorageKey = `liveChatStageActionsPosition:${sessionId}`;
  let stageActionsPosition = loadStageActionsPosition();
  let stageActionsDragState = null;

  function loadStageActionsPosition() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(stageActionsStorageKey) || "null");
      if (Number.isFinite(parsed?.x) && Number.isFinite(parsed?.y)) {
        return { x: parsed.x, y: parsed.y };
      }
    } catch (_error) {
      // Ignore corrupt saved UI positions.
    }
    return null;
  }

  function persistStageActionsPosition(position) {
    try {
      window.localStorage.setItem(stageActionsStorageKey, JSON.stringify(position));
    } catch (_error) {
      // localStorage can be unavailable in restricted browser contexts.
    }
  }

  function clampStageActionsPosition(x, y) {
    if (!stageElement || !stageActions) return { x: 12, y: 12 };
    const stageRect = stageElement.getBoundingClientRect();
    const actionsRect = stageActions.getBoundingClientRect();
    const maxX = Math.max(12, stageRect.width - actionsRect.width - 12);
    const maxY = Math.max(12, stageRect.height - actionsRect.height - 12);
    return {
      x: Math.min(Math.max(12, x), maxX),
      y: Math.min(Math.max(12, y), maxY),
    };
  }

  function applyStageActionsPosition(position, { persist = false } = {}) {
    if (!stageElement || !stageActions || !position) return;
    const clamped = clampStageActionsPosition(position.x, position.y);
    stageActionsPosition = clamped;
    stageElement.style.setProperty("--stage-actions-left", `${Math.round(clamped.x)}px`);
    stageElement.style.setProperty("--stage-actions-top", `${Math.round(clamped.y)}px`);
    stageElement.style.setProperty("--stage-actions-right", "auto");
    if (persist) {
      persistStageActionsPosition(clamped);
    }
  }

  function positionStageActions() {
    if (!stageElement || !selectedImagePanel || !stageActions) return;
    if (stageActionsPosition) {
      applyStageActionsPosition(stageActionsPosition);
      return;
    }
    const stageRect = stageElement.getBoundingClientRect();
    const stageFrame = selectedImagePanel.querySelector(".live-chat-stage-frame");
    const anchorRect = (stageFrame || selectedImagePanel).getBoundingClientRect();
    if (!stageRect.width || !anchorRect.width) return;
    const top = Math.max(12, anchorRect.top - stageRect.top + 16);
    const right = Math.max(12, stageRect.right - anchorRect.right + 16);
    stageElement.style.setProperty("--stage-actions-left", "auto");
    stageElement.style.setProperty("--stage-actions-top", `${Math.round(top)}px`);
    stageElement.style.setProperty("--stage-actions-right", `${Math.round(right)}px`);
  }

  function scheduleStageActionPosition() {
    window.requestAnimationFrame(positionStageActions);
    window.setTimeout(positionStageActions, 160);
  }

  function beginStageActionsDrag(event) {
    if (!stageElement || !stageActions) return;
    event.preventDefault();
    const stageRect = stageElement.getBoundingClientRect();
    const actionsRect = stageActions.getBoundingClientRect();
    const current = stageActionsPosition || {
      x: actionsRect.left - stageRect.left,
      y: actionsRect.top - stageRect.top,
    };
    stageActionsDragState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: current.x,
      originY: current.y,
    };
    stageActions.classList.add("is-dragging");
    stageActionsHandle?.setPointerCapture?.(event.pointerId);
  }

  function moveStageActionsDrag(event) {
    if (!stageActionsDragState) return;
    const next = {
      x: stageActionsDragState.originX + event.clientX - stageActionsDragState.startX,
      y: stageActionsDragState.originY + event.clientY - stageActionsDragState.startY,
    };
    applyStageActionsPosition(next);
  }

  function endStageActionsDrag(event) {
    if (!stageActionsDragState) return;
    stageActionsHandle?.releasePointerCapture?.(stageActionsDragState.pointerId);
    stageActionsDragState = null;
    stageActions?.classList.remove("is-dragging");
    if (stageActionsPosition) {
      applyStageActionsPosition(stageActionsPosition, { persist: true });
    }
  }

  function moveStageActionsByKeyboard(event) {
    const deltaByKey = {
      ArrowLeft: [-16, 0],
      ArrowRight: [16, 0],
      ArrowUp: [0, -16],
      ArrowDown: [0, 16],
    };
    const delta = deltaByKey[event.key];
    if (!delta || !stageElement || !stageActions) return;
    event.preventDefault();
    const stageRect = stageElement.getBoundingClientRect();
    const actionsRect = stageActions.getBoundingClientRect();
    const current = stageActionsPosition || {
      x: actionsRect.left - stageRect.left,
      y: actionsRect.top - stageRect.top,
    };
    applyStageActionsPosition(
      {
        x: current.x + delta[0],
        y: current.y + delta[1],
      },
      { persist: true },
    );
  }

  function getMessageListElement() {
    return document.getElementById("liveChatMessageList");
  }

  function getNovelElements() {
    return {
      novelBox: document.getElementById("liveChatNovelBox"),
      novelSpeaker: document.getElementById("liveChatNovelSpeaker"),
      novelText: document.getElementById("liveChatNovelText"),
      novelChoiceList: document.getElementById("liveChatNovelChoiceList"),
      novelContinue: document.getElementById("liveChatNovelContinue"),
      novelPager: document.getElementById("liveChatNovelPager"),
      novelPrevButton: document.getElementById("liveChatNovelPrevButton"),
      novelNextButton: document.getElementById("liveChatNovelNextButton"),
    };
  }

  const shell = LiveChatShell.createShellController({
    view: LiveChatView,
    selectedImagePanel,
    toggleMessagesButton: document.getElementById("liveChatToggleMessagesButton"),
    toggleTextboxButton: document.getElementById("liveChatToggleTextboxButton"),
    sendButton: document.getElementById("liveChatSendButton"),
    composeInput,
    generateImageButton: document.getElementById("liveChatGenerateImageButton"),
    regenerateImageButton: document.getElementById("liveChatRegenerateImageButton"),
    imageLightbox: document.getElementById("liveChatImageLightbox"),
    imageLightboxImage: document.getElementById("liveChatImageLightboxImage"),
    imageLightboxClose: document.getElementById("liveChatImageLightboxClose"),
    getMessageListElement,
    getNovelElements,
    onGiftInteractionChange: (disabled) => giftController?.setInteractionDisabled(disabled),
  });

  function applyContext(context) {
    currentContext = context;
    const title = context.session.title || "\u30e9\u30a4\u30d6\u30c1\u30e3\u30c3\u30c8";
    document.getElementById("liveChatTitle").textContent = title;

    if (stateBoard) {
      stateBoard.textContent = LiveChatView.formatJson(context.state.state_json || {});
    }
    if (memoryBoard) {
      memoryBoard.textContent = LiveChatView.formatJson((context.state.state_json || {}).session_memory || {});
    }
    imageForm.prompt_text.value = context.state.visual_prompt_text || "";

    shell.renderSelectedImage(context.selected_image, context);
    scheduleStageActionPosition();
    refreshModeBadge();
    shell.renderMessages(context.messages || [], context);
    shell.renderImageGrid(context.images || []);
    costumeRoomController?.render(context);
    renderSceneChoices(context);
    renderLocationMovePanel(context);
    renderLccdPanel();
    renderObjectiveNotes(context);
    renderPlayerReaction(context);
    renderSavedShortStories(context);
  }

  function getInitialObjective(context) {
    const session = context?.session || {};
    const roomSnapshot = session.room_snapshot_json || {};
    if (roomSnapshot && typeof roomSnapshot === "object" && roomSnapshot.conversation_objective) {
      return roomSnapshot.conversation_objective;
    }
    const room = context?.room || {};
    if (room && typeof room === "object" && room.conversation_objective) {
      return room.conversation_objective;
    }
    const settings = session.settings_json || {};
    if (settings && typeof settings === "object") {
      return settings.conversation_objective || settings.session_objective || "";
    }
    return "";
  }

  function renderObjectiveNotes(context) {
    if (!objectiveInitial || !objectiveList || !objectiveCount) return;
    const initialObjective = String(getInitialObjective(context) || "").trim();
    const notes = Array.isArray(context?.session_objective_notes) ? context.session_objective_notes : [];
    objectiveCount.textContent = `${notes.length} items`;
    objectiveInitial.innerHTML = `
      <div class="live-chat-objective-label">初期目的</div>
      <div class="live-chat-objective-text">${NovelUI.escape(initialObjective || "初期目的は未設定です。")}</div>
    `;
    if (!notes.length) {
      objectiveList.innerHTML = '<div class="live-chat-objective-empty">まだDirectionAIの目的メモはありません。</div>';
      return;
    }
    objectiveList.innerHTML = notes.map((note) => {
      const scope = note.character_name || "セッション全体";
      const source = note.source_type === "manual" ? "手動" : "DirectionAI";
      return `
        <article class="live-chat-objective-item">
          <div class="live-chat-objective-item-head">
            <span class="live-chat-objective-scope">${NovelUI.escape(scope)}</span>
            <span class="live-chat-objective-priority">P${Number(note.priority || 0)}</span>
            <span class="live-chat-objective-source">${NovelUI.escape(source)}</span>
          </div>
          <h6>${NovelUI.escape(note.title || "目的メモ")}</h6>
          <p>${NovelUI.escape(note.note || "")}</p>
        </article>
      `;
    }).join("");
  }

  function reactionLabel(reaction) {
    const moodLabels = {
      amused: "楽しそう",
      engaged: "興味あり",
      neutral: "普通",
      confused: "迷っていそう",
      uncomfortable: "困っていそう",
      unknown: "不明",
    };
    const mood = moodLabels[reaction?.mood] || "不明";
    const note = reaction?.short_note ? `: ${reaction.short_note}` : "";
    return `${mood}${note}`;
  }

  function renderPlayerReaction(context) {
    if (!cameraFeatureEnabled) return;
    if (!cameraStatusText || !cameraStatus) return;
    const reaction = context?.state?.state_json?.player_visible_reaction;
    if (cameraEnabled) {
      cameraStatus.classList.add("is-on");
      cameraStatusText.textContent = reaction ? `カメラON / 最後の反応 ${reactionLabel(reaction)}` : "カメラON / 次のキャラ発話後に反応を見ます";
    } else {
      cameraStatus.classList.remove("is-on");
      cameraStatusText.textContent = reaction ? `カメラOFF / 最後の反応 ${reactionLabel(reaction)}` : "カメラはOFFです";
    }
  }

  function renderShortStory(story) {
    if (!shortStoryResult || !shortStoryTitle || !shortStoryBody) return;
    currentShortStory = story;
    const paragraphs = String(story?.body || "")
      .split(/\n{2,}|\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    shortStoryTitle.textContent = story?.title || "チャットから生まれた短編";
    if (shortStorySynopsis) {
      shortStorySynopsis.textContent = story?.synopsis || "";
      shortStorySynopsis.hidden = !story?.synopsis;
    }
    shortStoryBody.innerHTML = paragraphs.length
      ? paragraphs.map((line) => `<p>${NovelUI.escape(line)}</p>`).join("")
      : '<p>本文を生成できませんでした。</p>';
    if (shortStoryAfterword) {
      shortStoryAfterword.textContent = story?.afterword || "";
      shortStoryAfterword.hidden = !story?.afterword;
    }
    if (shortStoryMeta) {
      const count = Number(story?.source_message_count || 0);
      shortStoryMeta.textContent = count ? `${count}件のログから生成` : "チャットログから生成";
    }
    renderShortStoryImage(shortStoryOpeningImageWrap, shortStoryOpeningImage, story?.images?.opening);
    renderShortStoryImage(shortStoryEndingImageWrap, shortStoryEndingImage, story?.images?.ending);
    if (saveShortStoryButton) {
      saveShortStoryButton.disabled = Boolean(story?.saved_at);
      saveShortStoryButton.textContent = story?.saved_at ? "保存済み" : "保存";
    }
    shortStoryResult.classList.remove("is-hidden");
  }

  function renderSavedShortStories(context) {
    if (!savedShortStories || !savedShortStoryList) return;
    const stories = context?.session?.settings_json?.saved_short_stories;
    if (!Array.isArray(stories) || !stories.length) {
      savedShortStories.classList.add("is-hidden");
      savedShortStoryList.innerHTML = "";
      return;
    }
    savedShortStories.classList.remove("is-hidden");
    savedShortStoryList.innerHTML = stories.slice().reverse().map((story, index) => {
      const title = story?.title || "無題の短編";
      const count = Number(story?.source_message_count || 0);
      const source = count ? `${count}件` : "保存済み";
      return `
        <button class="live-chat-saved-short-story" type="button" data-saved-short-story-index="${stories.length - 1 - index}">
          <span>${NovelUI.escape(title)}</span>
          <small>${NovelUI.escape(source)}</small>
        </button>
      `;
    }).join("");
  }

  function renderShortStoryImage(wrap, image, item) {
    const mediaUrl = item?.asset?.media_url;
    if (!wrap || !image) return;
    if (!mediaUrl) {
      image.removeAttribute("src");
      wrap.classList.add("is-hidden");
      return;
    }
    image.src = mediaUrl;
    wrap.classList.remove("is-hidden");
  }

  async function generateShortStory() {
    if (!shortStoryButton) return;
    const originalText = shortStoryButton.textContent;
    const payload = {
      tone: shortStoryToneSelect?.value || "",
      length: shortStoryLengthSelect?.value || "",
      instruction: shortStoryInstructionInput?.value || "",
      generate_images: shortStoryImagesCheckbox?.checked !== false,
    };
    try {
      shortStoryButton.disabled = true;
      if (saveShortStoryButton) saveShortStoryButton.disabled = true;
      shortStoryButton.innerHTML = payload.generate_images
        ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>本文と画像を作成中...'
        : '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>作成中...';
      const story = await LiveChatApi.generateShortStory(sessionId, payload);
      renderShortStory(story);
      NovelUI.toast("ショートストーリーを作成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ショートストーリーの作成に失敗しました。", "danger");
    } finally {
      shortStoryButton.disabled = false;
      shortStoryButton.textContent = originalText;
    }
  }

  async function saveShortStory() {
    if (!saveShortStoryButton || !currentShortStory) return;
    const originalText = saveShortStoryButton.textContent;
    try {
      saveShortStoryButton.disabled = true;
      saveShortStoryButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>保存中...';
      const result = await LiveChatApi.saveShortStory(sessionId, currentShortStory);
      currentShortStory = result?.saved_story || currentShortStory;
      saveShortStoryButton.textContent = "保存済み";
      if (currentContext) {
        const settings = currentContext.session.settings_json || {};
        const saved = Array.isArray(settings.saved_short_stories) ? settings.saved_short_stories : [];
        settings.saved_short_stories = [...saved, currentShortStory].slice(-20);
        currentContext.session.settings_json = settings;
        renderSavedShortStories(currentContext);
      }
      NovelUI.toast("ショートストーリーを保存しました。");
    } catch (error) {
      saveShortStoryButton.disabled = false;
      saveShortStoryButton.textContent = originalText;
      NovelUI.toast(error.message || "ショートストーリーの保存に失敗しました。", "danger");
    }
  }

  function showSavedShortStory(event) {
    const button = event.target.closest("[data-saved-short-story-index]");
    if (!button || !currentContext) return;
    const stories = currentContext.session?.settings_json?.saved_short_stories;
    const index = Number(button.dataset.savedShortStoryIndex);
    if (!Array.isArray(stories) || !stories[index]) return;
    renderShortStory(stories[index]);
  }

  async function setCameraEnabled(enabled) {
    if (!cameraFeatureEnabled) {
      cameraEnabled = false;
      return;
    }
    if (!enabled) {
      cameraEnabled = false;
      cameraToggleButton?.setAttribute("aria-pressed", "false");
      if (cameraToggleButton) {
        cameraToggleButton.innerHTML = stageActionIcons.cameraOff;
        cameraToggleButton.setAttribute("aria-label", "カメラOFF");
        cameraToggleButton.setAttribute("title", "カメラOFF");
      }
      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
        cameraStream = null;
      }
      if (cameraVideo) {
        cameraVideo.srcObject = null;
        cameraVideo.hidden = true;
      }
      renderPlayerReaction(currentContext);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      NovelUI.toast("このブラウザではカメラを使用できません。", "warning");
      return;
    }
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      if (cameraVideo) {
        cameraVideo.srcObject = cameraStream;
        cameraVideo.hidden = false;
        await cameraVideo.play();
      }
      cameraEnabled = true;
      cameraToggleButton?.setAttribute("aria-pressed", "true");
      if (cameraToggleButton) {
        cameraToggleButton.innerHTML = stageActionIcons.cameraOn;
        cameraToggleButton.setAttribute("aria-label", "カメラON");
        cameraToggleButton.setAttribute("title", "カメラON");
      }
      renderPlayerReaction(currentContext);
    } catch (error) {
      cameraEnabled = false;
      NovelUI.toast(error.message || "カメラを開始できませんでした。", "danger");
      await setCameraEnabled(false);
    }
  }

  async function capturePlayerReactionIfEnabled() {
    if (!cameraFeatureEnabled) return;
    if (!cameraEnabled || cameraBusy || !cameraVideo || !cameraCanvas) return;
    if (!cameraVideo.videoWidth || !cameraVideo.videoHeight) return;
    cameraBusy = true;
    try {
      const maxWidth = 512;
      const scale = Math.min(1, maxWidth / cameraVideo.videoWidth);
      cameraCanvas.width = Math.max(1, Math.round(cameraVideo.videoWidth * scale));
      cameraCanvas.height = Math.max(1, Math.round(cameraVideo.videoHeight * scale));
      const context2d = cameraCanvas.getContext("2d");
      context2d.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
      const blob = await new Promise((resolve) => cameraCanvas.toBlob(resolve, "image/jpeg", 0.72));
      if (!blob) return;
      const formData = new FormData();
      formData.append("file", blob, "player-reaction.jpg");
      const reaction = await LiveChatApi.analyzePlayerReaction(sessionId, formData);
      currentContext = {
        ...(currentContext || {}),
        state: {
          ...((currentContext || {}).state || {}),
          state_json: {
            ...(((currentContext || {}).state || {}).state_json || {}),
            player_visible_reaction: reaction,
          },
        },
      };
      renderPlayerReaction(currentContext);
    } catch (error) {
      NovelUI.toast(error.message || "カメラ反応の判定に失敗しました。", "warning");
    } finally {
      cameraBusy = false;
    }
  }

  async function loadContext() {
    const context = await LiveChatApi.loadContext(sessionId);
    applyContext(context);
    scheduleIdleTalk();
  }

  function randomIdleTalkDelay() {
    return idleTalkMinMs + Math.floor(Math.random() * (idleTalkMaxMs - idleTalkMinMs + 1));
  }

  function clearIdleTalkTimer() {
    if (idleTalkTimer) {
      window.clearTimeout(idleTalkTimer);
      idleTalkTimer = null;
    }
  }

  function hasPendingPlayerText() {
    return Boolean(composeForm?.message_text?.value?.trim());
  }

  function canRunIdleTalk() {
    if (!idleTalkEnabled) return false;
    if (!currentContext || !sessionId) return false;
    if (idleTalkBusy || shell.getState().replyLoading) return false;
    if (document.hidden || hasPendingPlayerText()) return false;
    if (giftController?.hasSelectedGift()) return false;
    if (idleTalksSincePlayerInput >= 1) return false;
    return true;
  }

  function scheduleIdleTalk() {
    clearIdleTalkTimer();
    if (!idleTalkEnabled) return;
    if (idleTalksSincePlayerInput >= 1) return;
    idleTalkTimer = window.setTimeout(triggerIdleTalk, randomIdleTalkDelay());
  }

  async function triggerIdleTalk() {
    if (!canRunIdleTalk()) {
      scheduleIdleTalk();
      return;
    }
    idleTalkBusy = true;
    idleTalksSincePlayerInput += 1;
    try {
      shell.setReplyLoading(true, currentContext);
      const result = await LiveChatApi.postIdleMessage(sessionId);
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      await capturePlayerReactionIfEnabled();
    } catch (error) {
      idleTalksSincePlayerInput = Math.max(0, idleTalksSincePlayerInput - 1);
      NovelUI.toast(error.message || "自動発話に失敗しました。", "warning");
      scheduleIdleTalk();
    } finally {
      idleTalkBusy = false;
      shell.setReplyLoading(false, currentContext);
    }
  }

  async function loadDefaultImageSettings() {
    try {
      const settings = await LiveChatApi.loadSettings();
      userDefaultImageSettings = settings || {};
      if (settings?.default_quality && imageForm.quality) {
        imageForm.quality.value = settings.default_quality;
      }
      costumeRoomController?.applySettings(settings);
      if (settings?.default_size && imageForm.size) {
        imageForm.size.value = settings.default_size;
      }
    } catch (error) {
      userDefaultImageSettings = {};
    }
  }

  async function generateSessionImage(useExistingPrompt = false, mode = "generate", overrides = {}) {
    shell.setImageLoading(true, mode);
    try {
      const body = {
        size: imageForm.size.value,
        quality: imageForm.quality.value,
        ...overrides,
      };
      if (useExistingPrompt) {
        body.prompt_text = imageForm.prompt_text.value;
        body.use_existing_prompt = true;
      }
      const generatedImage = await LiveChatApi.generateSessionImage(sessionId, body);
      if (generatedImage?.asset?.media_url) {
        currentContext = {
          ...(currentContext || {}),
          selected_image: generatedImage,
          images: [generatedImage, ...((currentContext?.images || []).filter((item) => item.id !== generatedImage.id))],
        };
        shell.renderSelectedImage(generatedImage, currentContext);
        scheduleStageActionPosition();
        shell.renderImageGrid(currentContext.images || []);
      }
      await loadContext();
    } finally {
      shell.setImageLoading(false, mode);
    }
  }

  function setComposeVisible(visible) {
    composeVisible = visible;
    if (composeShell) {
      composeShell.classList.toggle("is-collapsed", !visible);
    }
    if (toggleComposeButton) {
      toggleComposeButton.textContent = visible ? "\u30e1\u30c3\u30bb\u30fc\u30b8\u6b04\u3092\u9589\u3058\u308b" : "\u30e1\u30c3\u30bb\u30fc\u30b8\u6b04\u3092\u958b\u304f";
      toggleComposeButton.setAttribute("aria-expanded", visible ? "true" : "false");
    }
  }

  function renderSceneChoices(context) {
    if (!sceneChoicePanel) return;
    sceneChoicePanel.classList.add("is-hidden");
    sceneChoicePanel.innerHTML = "";
  }

  function currentLocationId(context) {
    const location = context?.state?.state_json?.current_location;
    return Number(location?.id || 0);
  }

  function renderLocationMovePanel(context) {
    if (!locationMovePanel) return;
    const locations = Array.isArray(context?.world_map?.locations) ? context.world_map.locations : [];
    locationMovePanel.classList.toggle("is-hidden", !locationMoveVisible);
    if (toggleLocationMoveButton) {
      toggleLocationMoveButton.setAttribute("aria-expanded", locationMoveVisible ? "true" : "false");
    }
    if (!locationMoveVisible) return;
    if (!locations.length) {
      locationMovePanel.innerHTML = '<div class="empty-panel">登録済みの施設がありません。ワールドマップで施設を追加すると、ここに移動先として表示されます。</div>';
      return;
    }
    const activeId = currentLocationId(context);
    locationMovePanel.innerHTML = `
      <div class="live-chat-location-head">
        <div>
          <div class="eyebrow">Move</div>
          <h4>移動する</h4>
        </div>
        <button class="btn btn-sm btn-outline-dark" type="button" data-location-move-close>閉じる</button>
      </div>
      <div class="live-chat-location-grid">
        ${locations.map((location) => {
          const isActive = Number(location.id) === activeId;
          const meta = [location.region, location.location_type, location.owner_character_name ? `${location.owner_character_name}関連` : ""]
            .filter(Boolean)
            .join(" / ");
          return `
            <button class="live-chat-location-card${isActive ? " is-active" : ""}" type="button" data-location-move-id="${location.id}" ${locationMoveBusy ? "disabled" : ""}>
              <span class="live-chat-location-card-title">${NovelUI.escape(location.name || "名称未設定")}</span>
              <span class="live-chat-location-card-meta">${NovelUI.escape(meta || "施設")}</span>
              <span class="live-chat-location-card-desc">${NovelUI.escape(NovelUI.truncateText(location.description || "説明未設定", 120))}</span>
              ${isActive ? '<span class="live-chat-location-card-current">現在地</span>' : ""}
            </button>
          `;
        }).join("")}
      </div>
    `;
  }

  async function moveToLocation(locationId, button = null) {
    if (!locationId || locationMoveBusy) return;
    locationMoveBusy = true;
    const originalHtml = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>移動中...';
    }
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.moveToLocation(sessionId, locationId, {
        size: imageForm?.size?.value || "1536x1024",
        quality: imageForm?.quality?.value || "low",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      await capturePlayerReactionIfEnabled();
      if (result?.image_generation_error) {
        NovelUI.toast(`移動しました。画像生成は失敗しました: ${result.image_generation_error}`, "warning");
      } else {
        NovelUI.toast("移動しました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "移動に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      locationMoveBusy = false;
      if (button && originalHtml) {
        button.innerHTML = originalHtml;
        button.disabled = false;
      }
      shell.setImageLoading(false, "auto");
      renderLocationMovePanel(currentContext);
    }
  }

  function renderLccdPanel() {
    if (!lccdPanel) return;
    lccdPanel.classList.add("is-hidden");
    toggleLccdButton?.setAttribute("aria-expanded", "false");
  }

  function currentModeBadgeText() {
    if (conversationModeActive) return "会話モード";
    if (photoModeActive) return "撮影モード";
    if (isCurrentLocationLccd()) return "お着替えモード";
    return "";
  }

  function refreshModeBadge() {
    shell.setModeBadgeText?.(currentModeBadgeText());
  }

  function isCurrentLocationLccd() {
    const location = currentContext?.state?.state_json?.current_location;
    return String(location?.id || "") === "lccd";
  }

  function setLccdEnterLoading(active) {
    lccdEnterBusy = active;
    if (!toggleLccdButton) return;
    toggleLccdButton.disabled = active;
    toggleLccdButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'
      : stageActionIcons.dressUp;
    toggleLccdButton.setAttribute("aria-label", active ? "お着替えへ移動中" : "お着替え");
    toggleLccdButton.setAttribute("title", active ? "お着替えへ移動中" : "お着替え");
  }

  async function enterLccdRoom() {
    if (lccdEnterBusy) return;
    locationMoveVisible = false;
    lccdVisible = false;
    renderLocationMovePanel(currentContext);
    renderLccdPanel();
    setLccdEnterLoading(true);
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.enterLccdRoom(sessionId, {
        size: imageForm?.size?.value || "1536x1024",
        quality: imageForm?.quality?.value || "low",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      lccdVisible = false;
      renderLccdPanel();
      if (result?.image_generation_error) {
        NovelUI.toast(`お着替えへ移動しました。背景画像は失敗しました: ${result.image_generation_error}`, "warning");
      } else {
        NovelUI.toast("お着替えへ移動しました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "お着替えへの移動に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      setLccdEnterLoading(false);
      shell.setImageLoading(false, "auto");
      renderLccdPanel();
    }
  }

  function setLccdLoading(active) {
    lccdBusy = active;
    if (!lccdGenerateButton) return;
    lccdGenerateButton.disabled = active;
    lccdGenerateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>衣装を生成中...'
      : "衣装を生成";
  }

  async function generateLccdCostume(promptText, poseStyle = "") {
    if (lccdBusy) return;
    promptText = String(promptText || "").trim();
    if (!promptText) {
      NovelUI.toast("衣装の希望を入力してください。", "warning");
      return;
    }
    setLccdLoading(true);
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.generateLccdCostume(sessionId, {
        prompt_text: promptText,
        pose_style: poseStyle,
        costume_size: "1024x1536",
        quality: imageForm?.quality?.value || "low",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      if (result?.photo_generation_error) {
        NovelUI.toast(`衣装は保存しました。撮影カットは失敗しました: ${result.photo_generation_error}`, "warning");
      } else {
        NovelUI.toast("お着替えで衣装と撮影カットを生成しました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "お着替え撮影に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      setLccdLoading(false);
      shell.setImageLoading(false, "auto");
      renderLccdPanel();
    }
  }

  function setPhotoModeActive(active) {
    photoModeActive = active;
    if (!togglePhotoModeButton) return;
    togglePhotoModeButton.classList.toggle("is-active", active);
    togglePhotoModeButton.setAttribute("aria-pressed", active ? "true" : "false");
    togglePhotoModeButton.setAttribute("title", active ? "撮影モード中" : "撮影モード");
    togglePhotoModeButton.setAttribute("aria-label", active ? "撮影モード中" : "撮影モード");
    refreshModeBadge();
  }

  function setConversationModeActive(active) {
    conversationModeActive = active;
    if (!conversationModeButton) return;
    conversationModeButton.classList.toggle("is-active", active);
    conversationModeButton.setAttribute("aria-pressed", active ? "true" : "false");
    conversationModeButton.setAttribute("title", active ? "会話モード中" : "会話モード");
    conversationModeButton.setAttribute("aria-label", active ? "会話モード中" : "会話モード");
    refreshModeBadge();
  }

  function setPhotoModeLoading(active) {
    photoModeBusy = active;
    if (!togglePhotoModeButton) return;
    togglePhotoModeButton.disabled = active;
    togglePhotoModeButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'
      : stageActionIcons.photoMode;
  }

  async function generatePhotoModeShoot(promptText, poseStyle = "") {
    if (photoModeBusy) return;
    promptText = String(promptText || "").trim();
    if (!promptText) {
      NovelUI.toast("撮影したいポーズや構図を入力してください。", "warning");
      return;
    }
    setPhotoModeLoading(true);
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.generatePhotoModeShoot(sessionId, {
        prompt_text: promptText,
        pose_style: poseStyle,
        photo_size: imageForm?.size?.value || "1536x1024",
        quality: imageForm?.quality?.value || "low",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      NovelUI.toast("現在の背景と衣装のまま、撮影カットを生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "撮影に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      setPhotoModeLoading(false);
      shell.setImageLoading(false, "auto");
    }
  }

  function setSceneChoiceLoading(active, activeButton = null) {
    document.querySelectorAll("[data-scene-choice-id]").forEach((button) => {
      button.disabled = active;
      if (active && button === activeButton) {
        button.dataset.originalText = button.textContent;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>場面を作成中...';
      } else if (!active && button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
        delete button.dataset.originalText;
      }
    });
  }

  composeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearIdleTalkTimer();
    const rawMessage = composeForm.message_text.value.trim();
    try {
      if (!rawMessage && !giftController?.hasSelectedGift()) {
        NovelUI.toast("送信するメッセージを入力するか、メッセージを作成ボタンで代理文を作成してください。", "warning");
        composeForm.message_text.focus();
        scheduleIdleTalk();
        return;
      }
      shell.setReplyLoading(true, currentContext);
      if (giftController?.hasSelectedGift()) {
        const uploaded = await giftController.uploadGiftImage(rawMessage);
        if (!uploaded) {
          throw new Error("\u8d08\u308a\u7269\u753b\u50cf\u306e\u9001\u4fe1\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002");
        }
      } else if (!conversationModeActive && photoModeActive) {
        await generatePhotoModeShoot(rawMessage);
      } else if (!conversationModeActive && isCurrentLocationLccd()) {
        await generateLccdCostume(rawMessage);
      } else {
        const result = await LiveChatApi.postMessage(sessionId, {
          message_text: rawMessage,
          auto_reply: true,
          size: imageForm?.size?.value || "1536x1024",
          quality: imageForm?.quality?.value || "low",
          skip_auto_image: true,
        });
        if (result?.new_letter) {
          NovelUI.toast("\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u304b\u3089\u30e1\u30fc\u30eb\u304c\u5c4a\u304d\u307e\u3057\u305f\u3002");
          NovelUI.refreshLetterBadge?.();
        }
        shell.setReplyLoading(false, currentContext, { render: false });
        await loadContext();
        await capturePlayerReactionIfEnabled();
        if (result?.deferred_processing) {
          window.setTimeout(() => {
            NovelUI.refreshLetterBadge?.();
          }, 3500);
        }
      }
      composeForm.message_text.value = "";
      idleTalksSincePlayerInput = 0;
      scheduleIdleTalk();
      NovelUI.toast("\u30e1\u30c3\u30bb\u30fc\u30b8\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f\u3002");
    } catch (error) {
      NovelUI.toast(error.message || "\u30e1\u30c3\u30bb\u30fc\u30b8\u9001\u4fe1\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
    } finally {
      shell.setReplyLoading(false, currentContext);
    }
  });

  composeInput?.addEventListener("input", () => {
    idleTalksSincePlayerInput = 0;
    scheduleIdleTalk();
  });

  composeInput?.addEventListener("focus", () => {
    scheduleIdleTalk();
  });

  proxyMessageButton?.addEventListener("click", async () => {
    const originalText = proxyMessageButton.textContent;
    try {
      proxyMessageButton.disabled = true;
      proxyMessageButton.textContent = "作成中...";
      const proxy = await LiveChatApi.generateProxyPlayerMessage(sessionId);
      composeForm.message_text.value = proxy?.message_text || "";
      idleTalksSincePlayerInput = 0;
      scheduleIdleTalk();
      composeForm.message_text.focus();
      NovelUI.toast("代理プレイヤーのメッセージを作成しました。内容を確認して送信してください。");
    } catch (error) {
      NovelUI.toast(error.message || "代理メッセージの作成に失敗しました。", "danger");
    } finally {
      proxyMessageButton.disabled = false;
      proxyMessageButton.textContent = originalText;
    }
  });

  shortStoryButton?.addEventListener("click", generateShortStory);
  saveShortStoryButton?.addEventListener("click", saveShortStory);
  savedShortStoryList?.addEventListener("click", showSavedShortStory);

  giftController = LiveChatGift.createGiftController({
    giftUploadInput: document.getElementById("liveChatGiftUploadInput"),
    giftDropTarget: document.getElementById("liveChatGiftDropTarget"),
    giftPreview: document.getElementById("liveChatGiftPreview"),
    giftPreviewImage: document.getElementById("liveChatGiftPreviewImage"),
    giftSelectedNameDisplay: document.getElementById("liveChatGiftSelectedNameDisplay"),
    giftSelectedName: document.getElementById("liveChatGiftSelectedName"),
    giftClearButton: document.getElementById("liveChatGiftClearButton"),
    giftSelectButton: document.getElementById("liveChatGiftSelectButton"),
    api: LiveChatApi,
    getSessionId: () => sessionId,
    canInteract: () => !shell.getState().replyLoading,
    onUploaded: loadContext,
  });
  giftController.bind();

  costumeRoomController = LiveChatCostumeRoom.createCostumeRoomController({
    api: LiveChatApi,
    getSessionId: () => sessionId,
    costumeForm,
    costumeGrid,
    costumePreview,
    generateCostumeButton,
    closetSelectButton,
    closetSelectModalElement,
    closetPicker,
    loadContext,
  });
  costumeRoomController.bind();

  LiveChatActions.bindImageActions({
    api: LiveChatApi,
    getSessionId: () => sessionId,
    imageForm,
    uploadForm,
    imageGrid: document.getElementById("liveChatImageGrid"),
    selectedImagePanel,
    loadContext,
    generateSessionImage,
  });

  stageActionsHandle?.addEventListener("pointerdown", beginStageActionsDrag);
  stageActionsHandle?.addEventListener("pointermove", moveStageActionsDrag);
  stageActionsHandle?.addEventListener("pointerup", endStageActionsDrag);
  stageActionsHandle?.addEventListener("pointercancel", endStageActionsDrag);
  stageActionsHandle?.addEventListener("keydown", moveStageActionsByKeyboard);

  document.getElementById("liveChatRefreshContextButton")?.addEventListener("click", () => {
    loadContext().catch((error) => {
      NovelUI.toast(error.message || "\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
    });
  });

  toggleComposeButton?.addEventListener("click", () => {
    setComposeVisible(!composeVisible);
  });

  toggleLocationMoveButton?.addEventListener("click", () => {
    locationMoveVisible = !locationMoveVisible;
    renderLocationMovePanel(currentContext);
  });

  locationMovePanel?.addEventListener("click", async (event) => {
    const closeButton = event.target.closest("[data-location-move-close]");
    if (closeButton) {
      locationMoveVisible = false;
      renderLocationMovePanel(currentContext);
      return;
    }
    const button = event.target.closest("[data-location-move-id]");
    if (!button) return;
    await moveToLocation(Number(button.dataset.locationMoveId || 0), button);
  });

  toggleLccdButton?.addEventListener("click", () => {
    if (!conversationModeActive && !photoModeActive && isCurrentLocationLccd()) {
      composeForm?.message_text?.focus();
      return;
    }
    setConversationModeActive(false);
    setPhotoModeActive(false);
    refreshModeBadge();
    enterLccdRoom();
  });

  conversationModeButton?.addEventListener("click", () => {
    setPhotoModeActive(false);
    setConversationModeActive(true);
    NovelUI.toast("会話モードです。通常どおり会話しながら進行します。");
    composeForm?.message_text?.focus();
  });

  togglePhotoModeButton?.addEventListener("click", () => {
    setConversationModeActive(false);
    setPhotoModeActive(!photoModeActive);
    if (!photoModeActive) {
      setConversationModeActive(true);
    }
    refreshModeBadge();
    NovelUI.toast(photoModeActive
      ? "撮影モードです。ポーズや構図を書いて送信してください。"
      : "撮影モードを解除しました。");
    composeForm?.message_text?.focus();
  });

  lccdCloseButton?.addEventListener("click", () => {
    lccdVisible = false;
    renderLccdPanel();
  });

  lccdForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const promptText = lccdForm.prompt_text.value.trim();
    await generateLccdCostume(promptText, lccdForm.pose_style.value);
    lccdForm.prompt_text.value = "";
  });

  cameraToggleButton?.addEventListener("click", () => {
    if (!cameraFeatureEnabled) return;
    setCameraEnabled(!cameraEnabled);
  });

  window.addEventListener("beforeunload", () => {
    clearIdleTalkTimer();
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearIdleTalkTimer();
    } else {
      scheduleIdleTalk();
    }
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-scene-choice-id]");
    if (!button) return;
    setSceneChoiceLoading(true, button);
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.executeSceneChoice(sessionId, button.dataset.sceneChoiceId);
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      await capturePlayerReactionIfEnabled();
      idleTalksSincePlayerInput = 0;
      scheduleIdleTalk();
      NovelUI.toast("選択した場面を生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "選択肢の実行に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      setSceneChoiceLoading(false);
      shell.setImageLoading(false, "auto");
    }
  });

  shell.initialize();
  setComposeVisible(true);

  loadDefaultImageSettings().then(loadContext).catch((error) => {
    NovelUI.toast(error.message || "\u30e9\u30a4\u30d6\u30c1\u30e3\u30c3\u30c8\u753b\u9762\u306e\u521d\u671f\u5316\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
  });

  window.addEventListener("resize", () => {
    if (currentContext) {
      shell.renderSelectedImage(currentContext.selected_image, currentContext);
      scheduleStageActionPosition();
      shell.renderNovel(currentContext.messages || [], currentContext);
    }
  });
})();
