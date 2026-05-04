(function () {
  const root = document.querySelector(".live-chat-shell[data-session-id]");
  if (!root) return;

  const { LiveChatApi, LiveChatView, LiveChatActions, LiveChatShell, LiveChatCostumeRoom } = window;
  if (!LiveChatApi || !LiveChatView || !LiveChatActions || !LiveChatShell || !LiveChatCostumeRoom) {
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
  const locationServicePanel = document.getElementById("liveChatLocationServicePanel");
  const toggleLocationMoveButton = document.getElementById("liveChatToggleLocationMoveButton");
  const lccdPanel = document.getElementById("liveChatLccdPanel");
  const toggleLccdButton = document.getElementById("liveChatToggleLccdButton");
  const costumeTicketBadge = document.getElementById("liveChatCostumeTicketBadge");
  const costumeTicketCount = document.getElementById("liveChatCostumeTicketCount");
  const conversationModeButton = document.getElementById("liveChatConversationModeButton");
  const togglePhotoModeButton = document.getElementById("liveChatTogglePhotoModeButton");
  const toggleInventoryButton = document.getElementById("liveChatToggleInventoryButton");
  const inventoryPanel = document.getElementById("liveChatInventoryPanel");
  const inventoryList = document.getElementById("liveChatInventoryList");
  const inventoryGenerateButton = document.getElementById("liveChatInventoryGenerateButton");
  const inventoryCloseButton = document.getElementById("liveChatInventoryCloseButton");
  const inventoryPromptInput = document.getElementById("liveChatInventoryPromptInput");
  const lccdCloseButton = document.getElementById("liveChatLccdCloseButton");
  const lccdForm = document.getElementById("liveChatLccdForm");
  const lccdGenerateButton = document.getElementById("liveChatLccdGenerateButton");
  const objectiveInitial = document.getElementById("liveChatObjectiveInitial");
  const objectiveList = document.getElementById("liveChatObjectiveList");
  const objectiveCount = document.getElementById("liveChatObjectiveDebugCount");
  const affinityCard = document.getElementById("liveChatAffinityCard");
  const affinityList = document.getElementById("liveChatAffinityList");
  const intelRail = document.getElementById("liveChatIntelRail");
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
  let costumeRoomController = null;
  let composeVisible = true;
  let userDefaultImageSettings = {};
  let cameraEnabled = false;
  let cameraStream = null;
  let cameraBusy = false;
  let locationMoveVisible = false;
  let selectedLocationMoveId = null;
  let locationMoveBusy = false;
  let locationServiceBusy = false;
  let lccdVisible = false;
  let lccdBusy = false;
  let lccdEnterBusy = false;
  let conversationModeActive = true;
  let photoModeActive = false;
  let photoModeBusy = false;
  let inventoryVisible = false;
  let inventoryBusy = false;
  let inventoryItems = [];
  let affinityScoresInitialized = false;
  const lastAffinityScores = new Map();
  const affinityRewardClaiming = new Set();
  let currentShortStory = null;
  const composePlaceholders = {
    chat: "メッセージを入力。メッセージを作成ボタンで代理メッセージも作れます。",
    photo: "例: ネオンの逆光を背に少し振り返り、こちらへ視線を向ける。背景を大きくぼかした縦構図で、Xで映える一枚にする。",
  };
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
    onGiftInteractionChange: () => {},
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
    renderLocationServicePanel(context);
    renderLccdPanel();
    updateLccdAvailability(context);
    updatePhotoModeAvailability(context);
    renderObjectiveNotes(context);
    renderCharacterAffinity(context);
    renderCharacterIntelRail(context);
    renderPlayerReaction(context);
    renderSavedShortStories(context);
    renderInventoryPanel();
  }

  function activeCharacterId(context = currentContext) {
    const session = context?.session || {};
    const state = context?.state?.state_json || {};
    const roomSnapshot = session.room_snapshot_json || {};
    const room = context?.room || {};
    const settings = session.settings_json || {};
    const characters = context?.characters || [];
    const projectCharacters = context?.project_characters || [];
    const availableCharacters = [...characters, ...projectCharacters];
    const candidates = [
      roomSnapshot.character_id,
      room.character_id,
      Array.isArray(state.active_character_ids) ? state.active_character_ids[0] : null,
      Array.isArray(settings.selected_character_ids) ? settings.selected_character_ids[0] : null,
      settings.selected_character_id,
      characters[0]?.id,
    ];
    const characterId = candidates
      .map((value) => Number(value || 0))
      .find((value) => Number.isFinite(value) && value > 0);
    if (characterId && availableCharacters.some((character) => Number(character.id || 0) === characterId)) {
      return characterId;
    }
    const names = [
      roomSnapshot.character_name,
      roomSnapshot.name,
      roomSnapshot.nickname,
      room.character_name,
      room.name,
      room.nickname,
    ].map((value) => String(value || "").trim()).filter(Boolean);
    const replacement = availableCharacters.find((character) => {
      const characterNames = [
        character.name,
        character.nickname,
      ].map((value) => String(value || "").trim()).filter(Boolean);
      return characterNames.some((name) => names.includes(name));
    });
    if (replacement?.id) return Number(replacement.id);
    return characterId || null;
  }

  function activeCharacters(context = currentContext) {
    const characters = Array.isArray(context?.characters) ? context.characters : [];
    const characterId = activeCharacterId(context);
    if (!characterId) return characters;
    const filtered = characters.filter((character) => Number(character.id || 0) === Number(characterId));
    return filtered;
  }

  function inventoryTargetCharacterId() {
    return activeCharacterId(currentContext);
  }

  function activeAffinityReward(context = currentContext) {
    const characterId = activeCharacterId(context);
    if (!characterId) return null;
    return (context?.affinity_rewards || {})[String(characterId)] || null;
  }

  function canUseLccd(context = currentContext) {
    return false;
  }

  function canUsePhotoMode(context = currentContext) {
    const reward = activeAffinityReward(context);
    return Boolean(reward?.clear_unlocked || reward?.closet_unlocked || reward?.event_claimed);
  }

  function updateLccdAvailability(context = currentContext) {
    if (!toggleLccdButton) return;
    const reward = activeAffinityReward(context);
    const ticketCount = Number(reward?.costume_ticket_balance || 0);
    const available = false;
    if (costumeTicketBadge) {
      costumeTicketBadge.hidden = true;
      costumeTicketBadge.classList.toggle("is-visible", false);
      costumeTicketBadge.setAttribute("title", `衣装チケット: ${ticketCount}枚`);
      costumeTicketBadge.setAttribute("aria-label", `衣装チケット ${ticketCount}枚`);
    }
    if (costumeTicketCount) {
      costumeTicketCount.textContent = String(ticketCount);
    }
    toggleLccdButton.hidden = true;
    toggleLccdButton.classList.toggle("is-ticket-ready", available);
    toggleLccdButton.setAttribute(
      "title",
      reward?.lccd_unlocked_for_session ? "お着替え部屋" : `お着替えチケット: ${ticketCount}`,
    );
    toggleLccdButton.setAttribute(
      "aria-label",
      reward?.lccd_unlocked_for_session ? "お着替え部屋" : `お着替えチケット ${ticketCount}枚`,
    );
    if (!available && lccdVisible) {
      lccdVisible = false;
      renderLccdPanel();
    }
  }

  function updatePhotoModeAvailability(context = currentContext) {
    if (!togglePhotoModeButton) return;
    const available = canUsePhotoMode(context);
    togglePhotoModeButton.hidden = !available;
    togglePhotoModeButton.disabled = photoModeBusy || !available;
    togglePhotoModeButton.classList.toggle("is-clear-unlocked", available);
    togglePhotoModeButton.setAttribute(
      "title",
      available ? (photoModeActive ? "撮影モード中" : "撮影モード") : "好感度100で開放",
    );
    togglePhotoModeButton.setAttribute(
      "aria-label",
      available ? (photoModeActive ? "撮影モード中" : "撮影モード") : "撮影モードは好感度100で開放",
    );
    if (!available && photoModeActive) {
      photoModeActive = false;
      setConversationModeActive(true);
    }
  }

  function setInventoryVisible(visible) {
    inventoryVisible = Boolean(visible);
    renderInventoryPanel();
    if (inventoryVisible) {
      loadInventoryItems();
    }
  }

  function renderInventoryPanel() {
    if (!inventoryPanel || !inventoryList) return;
    inventoryPanel.classList.toggle("is-hidden", !inventoryVisible);
    toggleInventoryButton?.setAttribute("aria-expanded", inventoryVisible ? "true" : "false");
    toggleInventoryButton?.classList.toggle("is-active", inventoryVisible);
    if (!inventoryVisible) return;
    if (inventoryBusy) {
      inventoryList.innerHTML = '<div class="live-chat-inventory-empty">Loading...</div>';
      return;
    }
    if (!inventoryItems.length) {
      inventoryList.innerHTML = '<div class="live-chat-inventory-empty">アイテムがありません。生成してからステージ画像へドラッグしてください。</div>';
      return;
    }
    inventoryList.innerHTML = inventoryItems.map((item) => {
      const imageUrl = item.asset?.media_url || "";
      return `
        <button class="live-chat-inventory-item" type="button" draggable="true" data-inventory-item-id="${item.id}" title="${NovelUI.escape(item.description || item.name || "")}">
          ${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="${NovelUI.escape(item.name || "item")}">` : '<i class="bi bi-gift"></i>'}
          <span>${NovelUI.escape(item.name || "Item")}</span>
        </button>
      `;
    }).join("");
  }

  async function loadInventoryItems() {
    if (!projectId) return;
    inventoryBusy = true;
    renderInventoryPanel();
    try {
      const payload = await LiveChatApi.loadInventory(projectId);
      inventoryItems = Array.isArray(payload?.items) ? payload.items : [];
    } catch (error) {
      NovelUI.toast(error.message || "インベントリーを読み込めませんでした。", "warning");
    } finally {
      inventoryBusy = false;
      renderInventoryPanel();
    }
  }

  async function generateInventoryItem() {
    if (!projectId || inventoryBusy) return;
    inventoryBusy = true;
    inventoryGenerateButton.disabled = true;
    renderInventoryPanel();
    try {
      const prompt = inventoryPromptInput?.value?.trim() || "";
      const body = {
        session_id: sessionId,
        character_id: inventoryTargetCharacterId(),
        size: "1024x1024",
      };
      if (prompt) body.prompt = prompt;
      const result = await LiveChatApi.generateInventoryItem(projectId, body);
      if (result?.points?.balance !== undefined) NovelUI.setPointsBalance(result.points.balance);
      if (result?.item) inventoryItems = [result.item, ...inventoryItems.filter((item) => item.id !== result.item.id)];
      NovelUI.toast("アイテムを生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "アイテム生成に失敗しました。", "danger");
    } finally {
      inventoryBusy = false;
      inventoryGenerateButton.disabled = false;
      renderInventoryPanel();
    }
  }

  async function giveInventoryItem(itemId) {
    if (!itemId || shell.getState().replyLoading) return;
    const item = inventoryItems.find((entry) => Number(entry.id) === Number(itemId));
    shell.setReplyLoading(true, currentContext);
    try {
      const result = await LiveChatApi.giveInventoryItem(sessionId, itemId, {
        character_id: inventoryTargetCharacterId(),
        message_text: item?.name ? `${item.name}を渡した。` : "アイテムを渡した。",
      });
      playAffinityFeedback(result?.affinity_feedback);
      inventoryItems = inventoryItems.filter((entry) => Number(entry.id) !== Number(itemId));
      NovelUI.toast("アイテムを渡しました。");
      await loadContext();
    } catch (error) {
      NovelUI.toast(error.message || "アイテムを渡せませんでした。", "danger");
    } finally {
      shell.setReplyLoading(false, currentContext);
      renderInventoryPanel();
    }
  }

  function triggerAffinityHeartBurst(delta = 1) {
    const stage = selectedImagePanel?.closest(".live-chat-stage");
    if (!stage) return;
    const count = Math.max(3, Math.min(9, Math.ceil(Number(delta || 1) / 2) + 2));
    for (let index = 0; index < count; index += 1) {
      const heart = document.createElement("span");
      heart.className = "live-chat-affinity-heart";
      heart.innerHTML = '<i class="bi bi-heart-fill" aria-hidden="true"></i>';
      heart.style.setProperty("--heart-x", `${Math.round((Math.random() - 0.5) * 130)}px`);
      heart.style.setProperty("--heart-y", `${Math.round(70 + Math.random() * 90)}px`);
      heart.style.setProperty("--heart-delay", `${index * 70}ms`);
      heart.style.setProperty("--heart-scale", `${0.82 + Math.random() * 0.55}`);
      stage.appendChild(heart);
      window.setTimeout(() => heart.remove(), 1500 + index * 70);
    }
  }

  function triggerAffinityMaxHeartBurst() {
    const stage = selectedImagePanel?.closest(".live-chat-stage");
    if (!stage) return;
    for (let index = 0; index < 34; index += 1) {
      const heart = document.createElement("span");
      heart.className = "live-chat-affinity-heart is-max-reward";
      heart.innerHTML = '<i class="bi bi-heart-fill" aria-hidden="true"></i>';
      heart.style.setProperty("--heart-x", `${Math.round((Math.random() - 0.5) * 260)}px`);
      heart.style.setProperty("--heart-y", `${Math.round(110 + Math.random() * 190)}px`);
      heart.style.setProperty("--heart-delay", `${index * 45}ms`);
      heart.style.setProperty("--heart-scale", `${0.9 + Math.random() * 1.05}`);
      stage.appendChild(heart);
      window.setTimeout(() => heart.remove(), 2200 + index * 45);
    }
  }

  function playAffinityFeedback(feedback) {
    const events = Array.isArray(feedback) ? feedback : [];
    events.forEach((event) => {
      const delta = Number(event?.affinity_delta || event?.physical_closeness_delta || 1);
      const previousScore = Number(event?.previous_score || 0);
      const nextScore = Number(event?.next_score || 0);
      const alreadyHandledByScoreIncrease = nextScore > previousScore && nextScore < 100;
      if (alreadyHandledByScoreIncrease) return;
      if (delta > 0 || event?.at_max) {
        triggerAffinityHeartBurst(Math.max(1, delta || 1));
      }
    });
  }

  async function claimAffinityReward(characterId) {
    const key = String(characterId || "");
    if (!key || affinityRewardClaiming.has(key)) return;
    affinityRewardClaiming.add(key);
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.claimAffinityReward(sessionId, characterId);
      triggerAffinityMaxHeartBurst();
      window.setTimeout(() => {
        if (result?.context) applyContext(result.context);
        if (result?.event_image) shell.renderSelectedImage(result.event_image, result.context || currentContext);
      }, 1250);
      if (result?.letter) NovelUI.refreshLetterBadge?.();
      NovelUI.toast("好感度100達成。衣装チケットを1枚獲得しました。");
    } catch (error) {
      NovelUI.toast(error.message || "好感度100報酬を受け取れませんでした。", "danger");
    } finally {
      window.setTimeout(() => shell.setImageLoading(false, currentContext), 1300);
      affinityRewardClaiming.delete(key);
    }
  }

  async function debugAffinityClearShortcut() {
    if (!LiveChatApi.debugAffinityClear) return;
    const password = window.prompt("DEBUG password");
    if (!password) return;
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.debugAffinityClear(sessionId, { password });
      triggerAffinityMaxHeartBurst();
      window.setTimeout(() => {
        if (result?.context) applyContext(result.context);
        if (result?.event_image) shell.renderSelectedImage(result.event_image, result.context || currentContext);
      }, 1250);
      if (result?.letter) NovelUI.refreshLetterBadge?.();
      NovelUI.toast("デバッグ: 好感度100クリアにしました。");
    } catch (error) {
      NovelUI.toast(error.message || "デバッグクリアに失敗しました。", "danger");
    } finally {
      window.setTimeout(() => shell.setImageLoading(false, currentContext), 1300);
    }
  }

  function detectAffinityIncreases(context) {
    const memoryMap = context?.character_user_memories || {};
    const visibleCharacterIds = new Set(activeCharacters(context).map((character) => String(character.id)));
    const nextScores = new Map();
    Object.entries(memoryMap).forEach(([characterId, memory]) => {
      if (visibleCharacterIds.size && !visibleCharacterIds.has(String(characterId))) return;
      const score = Math.max(0, Math.min(100, Number(memory?.affinity_score || 0)));
      nextScores.set(String(characterId), score);
      if (!affinityScoresInitialized) return;
      const previous = lastAffinityScores.get(String(characterId));
      if (previous !== undefined && score > previous) {
        triggerAffinityHeartBurst(score - previous);
      }
      const reward = (context?.affinity_rewards || {})[String(characterId)] || {};
      if (
        score >= 100
        && !reward.event_claimed
        && (previous === undefined || previous < 100)
      ) {
        claimAffinityReward(characterId);
      }
    });
    lastAffinityScores.clear();
    nextScores.forEach((score, characterId) => lastAffinityScores.set(characterId, score));
    affinityScoresInitialized = true;
  }

  function renderCharacterAffinity(context) {
    if (!affinityCard || !affinityList) return;
    detectAffinityIncreases(context);
    const characters = activeCharacters(context);
    const memoryMap = context?.character_user_memories || {};
    const rows = characters
      .map((character) => {
        const memory = memoryMap[String(character.id)] || {};
        const score = Math.max(0, Math.min(100, Number(memory.affinity_score || 0)));
        const label = memory.affinity_label || "警戒";
        const closenessLevel = Math.max(0, Math.min(5, Number(memory.physical_closeness_level || 0)));
        const closenessLevelLabel = closenessLevel >= 5 ? "Max" : String(closenessLevel);
        const closenessLabel = memory.physical_closeness_label || "距離を保つ";
        const note = memory.affinity_notes || "";
        const toneClass = score >= 70 ? "is-high" : score >= 40 ? "is-mid" : "is-low";
        return {
          name: character.name || character.nickname || "Character",
          score,
          label,
          closenessLevel,
          closenessLevelLabel,
          closenessLabel,
          note,
          toneClass,
        };
    });
    affinityCard.hidden = rows.length === 0;
    if (!rows.length) {
      affinityList.innerHTML = "";
      return;
    }
    affinityList.innerHTML = rows.map((row) => `
      <article class="live-chat-affinity-item ${row.toneClass}">
        <div class="live-chat-affinity-item-head">
          <div>
            <h4>${NovelUI.escape(row.name)}からあなたへ</h4>
            <span>${NovelUI.escape(row.label)}</span>
          </div>
          <strong><span>${row.score}</span><small>/100</small></strong>
        </div>
        <div class="live-chat-affinity-meter" aria-label="${NovelUI.escape(row.name)} 好感度 ${row.score}">
          <span style="width: ${row.score}%"></span>
        </div>
        <div class="live-chat-affinity-foot">
          <span>距離感 Lv.${row.closenessLevelLabel}</span>
          <span>${NovelUI.escape(row.closenessLabel)}</span>
        </div>
        ${row.note ? `<p>${NovelUI.escape(row.note)}</p>` : ""}
      </article>
    `).join("");
  }

  function characterAssetUrl(character) {
    return character?.bromide_asset?.media_url
      || character?.thumbnail_asset?.media_url
      || character?.base_asset?.media_url
      || "";
  }

  function renderCharacterIntelRail(context) {
    if (!intelRail) return;
    const hints = ((context?.character_intel || {}).available_hints || []);
    const characters = new Map((context?.project_characters || []).map((character) => [Number(character.id), character]));
    const byTarget = [];
    const seenTargets = new Set();
    hints.forEach((hint) => {
      const targetId = Number(hint.target_character_id || 0);
      if (!targetId || seenTargets.has(targetId)) return;
      seenTargets.add(targetId);
      byTarget.push(hint);
    });
    intelRail.classList.toggle("is-hidden", byTarget.length === 0);
    if (!byTarget.length) {
      intelRail.innerHTML = "";
      return;
    }
    intelRail.innerHTML = byTarget.slice(0, 6).map((hint) => {
      const character = characters.get(Number(hint.target_character_id || 0)) || {};
      const imageUrl = characterAssetUrl(character);
      const name = hint.target_character_name || character.name || "Character";
      return `
        <button class="live-chat-intel-button" type="button"
          data-source-character-id="${Number(hint.source_character_id || 0)}"
          data-target-character-id="${Number(hint.target_character_id || 0)}"
          data-topic="${NovelUI.escape(hint.topic || "")}"
          title="${NovelUI.escape(name)}の情報">
          ${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="${NovelUI.escape(name)}">` : '<i class="bi bi-person-heart" aria-hidden="true"></i>'}
          <span class="live-chat-intel-dot" aria-hidden="true"></span>
        </button>
      `;
    }).join("");
  }

  async function revealCharacterIntelHint(button) {
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      const result = await LiveChatApi.revealCharacterIntel(sessionId, {
        source_character_id: Number(button.dataset.sourceCharacterId || 0),
        target_character_id: Number(button.dataset.targetCharacterId || 0),
        topic: button.dataset.topic || "",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
    } catch (error) {
      NovelUI.toast(error.message || "キャラクター情報を開示できませんでした。", "danger");
      button.disabled = false;
    }
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
    await loadInventoryItems();
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

  function currentLocationServiceId(context) {
    const service = context?.state?.state_json?.current_location_service;
    return Number(service?.id || 0);
  }

  function currentLocationServices(context) {
    const stateLocation = context?.state?.state_json?.current_location;
    if (Array.isArray(stateLocation?.services)) return stateLocation.services;
    const locationId = Number(stateLocation?.id || 0);
    const locations = Array.isArray(context?.world_map?.locations) ? context.world_map.locations : [];
    const location = locations.find((item) => Number(item.id) === locationId);
    return Array.isArray(location?.services) ? location.services : [];
  }

  function locationServicesForLocation(location) {
    return (Array.isArray(location?.services) ? location.services : []).filter((item) => item && item.status !== "archived");
  }

  function renderLocationServicePanel(context) {
    if (!locationServicePanel) return;
    locationServicePanel.classList.add("is-hidden");
    locationServicePanel.innerHTML = "";
  }

  function closeLocationMovePanel() {
    if (!locationMoveVisible) return;
    locationMoveVisible = false;
    selectedLocationMoveId = null;
    renderLocationMovePanel(currentContext);
    renderLocationServicePanel(currentContext);
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
    const selectedId = Number(selectedLocationMoveId || 0);
    locationMovePanel.innerHTML = `
      <div class="live-chat-location-head">
        <div>
          <div class="eyebrow">Move</div>
          <h4>どこへ移動する？</h4>
        </div>
        <button class="btn btn-sm btn-outline-dark" type="button" data-location-move-close>閉じる</button>
      </div>
      <div class="live-chat-location-grid">
        ${locations.map((location) => {
          const isActive = Number(location.id) === activeId;
          const isSelected = Number(location.id) === selectedId;
          const services = locationServicesForLocation(location);
          const meta = [location.region, location.location_type, location.owner_character_name ? `${location.owner_character_name}関連` : ""]
            .filter(Boolean)
            .join(" / ");
          return `
            <div class="live-chat-location-entry${isSelected ? " is-selected" : ""}">
              <button class="live-chat-location-card${isActive ? " is-active" : ""}${isSelected ? " is-selected" : ""}" type="button" data-location-select-id="${location.id}" ${locationMoveBusy || locationServiceBusy ? "disabled" : ""}>
                <span class="live-chat-location-card-title">${NovelUI.escape(location.name || "名称未設定")}</span>
                <span class="live-chat-location-card-meta">${NovelUI.escape(meta || "施設")}</span>
                <span class="live-chat-location-card-desc">${NovelUI.escape(NovelUI.truncateText(location.description || "説明未設定", 120))}</span>
                ${isActive ? '<span class="live-chat-location-card-current">現在地</span>' : ""}
                <span class="live-chat-location-card-next">${isSelected ? "行き先を選択中" : "行き先を開く"}</span>
              </button>
              ${isSelected ? `
                <div class="live-chat-location-destinations">
                  <div class="live-chat-location-destinations-title">${NovelUI.escape(location.name || "施設")}のどこへ行く？</div>
                  <button class="live-chat-location-destination-button" type="button" data-location-move-final-id="${location.id}" ${locationMoveBusy ? "disabled" : ""}>
                    <span>施設全体へ移動</span>
                    <small>入口・広場・全体の雰囲気で移動する</small>
                  </button>
                  ${services.length ? services.map((service) => `
                    <button class="live-chat-location-destination-button" type="button" data-location-service-id="${service.id}" ${locationServiceBusy ? "disabled" : ""}>
                      <span>${NovelUI.escape(service.name || "行き先")}</span>
                      <small>${NovelUI.escape(service.service_type || "施設内")}</small>
                      ${service.summary ? `<em>${NovelUI.escape(NovelUI.truncateText(service.summary, 78))}</em>` : ""}
                    </button>
                  `).join("") : '<div class="live-chat-location-destination-empty">施設内の行き先はまだありません。</div>'}
                </div>
              ` : ""}
            </div>
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
      locationMoveVisible = false;
      selectedLocationMoveId = null;
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
      renderLocationServicePanel(currentContext);
    }
  }

  async function selectLocationService(serviceId, button = null) {
    if (!serviceId || locationServiceBusy) return;
    locationServiceBusy = true;
    const originalHtml = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>移動中...';
    }
    shell.setImageLoading(true, "auto");
    try {
      const result = await LiveChatApi.selectLocationService(sessionId, serviceId, {
        size: imageForm?.size?.value || "1536x1024",
        quality: imageForm?.quality?.value || "low",
      });
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      locationMoveVisible = false;
      selectedLocationMoveId = null;
      await capturePlayerReactionIfEnabled();
      if (result?.image_generation_error) {
        NovelUI.toast(`サービスへ移動しました。画像生成は失敗しました: ${result.image_generation_error}`, "warning");
      } else {
        NovelUI.toast("サービスへ移動しました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "サービス移動に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      locationServiceBusy = false;
      if (button && originalHtml) {
        button.innerHTML = originalHtml;
        button.disabled = false;
      }
      shell.setImageLoading(false, "auto");
      renderLocationMovePanel(currentContext);
      renderLocationServicePanel(currentContext);
    }
  }

  function renderLccdPanel() {
    if (!lccdPanel) return;
    lccdPanel.classList.add("is-hidden");
    toggleLccdButton?.setAttribute("aria-expanded", "false");
  }

  function currentModeBadgeText() {
    if (photoModeActive) return "撮影モード";
    if (conversationModeActive) return "会話モード";
    if (isCurrentLocationLccd()) return "お着替えモード";
    return "";
  }

  function refreshModeBadge() {
    shell.setModeBadgeText?.(currentModeBadgeText());
  }

  function refreshComposePlaceholder() {
    if (!composeInput) return;
    composeInput.placeholder = photoModeActive ? composePlaceholders.photo : composePlaceholders.chat;
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
    NovelUI.toast("チャットルーム内でのお着替え部屋は廃止されました。クローゼットで衣装を作成してください。", "warning");
  }

  function setLccdLoading(active) {
    lccdBusy = active;
    if (!lccdGenerateButton) return;
    lccdGenerateButton.disabled = active;
    lccdGenerateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>衣装を生成中...'
      : "衣装を生成";
  }

  async function generateLccdCostume() {
    NovelUI.toast("チャットルーム内での衣装生成は廃止されました。クローゼットで衣装を作成してください。", "warning");
  }
  function setPhotoModeActive(active) {
    if (active && !canUsePhotoMode()) {
      photoModeActive = false;
      updatePhotoModeAvailability(currentContext);
      refreshComposePlaceholder();
      NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
      return;
    }
    photoModeActive = active;
    if (active) {
      conversationModeActive = false;
      conversationModeButton?.classList.toggle("is-active", false);
      conversationModeButton?.setAttribute("aria-pressed", "false");
      conversationModeButton?.setAttribute("title", "会話モード");
      conversationModeButton?.setAttribute("aria-label", "会話モード");
    }
    if (!togglePhotoModeButton) return;
    togglePhotoModeButton.classList.toggle("is-active", active);
    togglePhotoModeButton.setAttribute("aria-pressed", active ? "true" : "false");
    togglePhotoModeButton.setAttribute("title", active ? "撮影モード中" : "撮影モード");
    togglePhotoModeButton.setAttribute("aria-label", active ? "撮影モード中" : "撮影モード");
    updatePhotoModeAvailability(currentContext);
    refreshModeBadge();
    refreshComposePlaceholder();
  }

  function setConversationModeActive(active) {
    conversationModeActive = active;
    if (active) {
      photoModeActive = false;
      togglePhotoModeButton?.classList.toggle("is-active", false);
      togglePhotoModeButton?.setAttribute("aria-pressed", "false");
      togglePhotoModeButton?.setAttribute("title", "撮影モード");
      togglePhotoModeButton?.setAttribute("aria-label", "撮影モード");
    }
    if (!conversationModeButton) return;
    conversationModeButton.classList.toggle("is-active", active);
    conversationModeButton.setAttribute("aria-pressed", active ? "true" : "false");
    conversationModeButton.setAttribute("title", active ? "会話モード中" : "会話モード");
    conversationModeButton.setAttribute("aria-label", active ? "会話モード中" : "会話モード");
    refreshModeBadge();
    refreshComposePlaceholder();
  }

  function setPhotoModeLoading(active) {
    photoModeBusy = active;
    if (!togglePhotoModeButton) return;
    togglePhotoModeButton.disabled = active || !canUsePhotoMode();
    togglePhotoModeButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'
      : stageActionIcons.photoMode;
  }

  async function generatePhotoModeShoot(promptText, poseStyle = "") {
    if (photoModeBusy) return;
    if (!canUsePhotoMode()) {
      NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
      setConversationModeActive(true);
      return;
    }
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
    let handledBySpecialMode = false;
    try {
      if (!rawMessage) {
        NovelUI.toast("送信するメッセージを入力するか、メッセージを作成ボタンで代理文を作成してください。", "warning");
        composeForm.message_text.focus();
        scheduleIdleTalk();
        return;
      }
      shell.setReplyLoading(true, currentContext);
      if (photoModeActive) {
        await generatePhotoModeShoot(rawMessage);
        handledBySpecialMode = true;
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
        playAffinityFeedback(result?.affinity_feedback);
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
      if (!handledBySpecialMode) {
        NovelUI.toast("\u30e1\u30c3\u30bb\u30fc\u30b8\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f\u3002");
      }
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
      const proxy = await LiveChatApi.generateProxyPlayerMessage(sessionId, {
        purpose: photoModeActive ? "photo_mode" : "chat",
      });
      composeForm.message_text.value = proxy?.message_text || "";
      idleTalksSincePlayerInput = 0;
      scheduleIdleTalk();
      composeForm.message_text.focus();
      NovelUI.toast(photoModeActive
        ? "撮影用プロンプトを作成しました。内容を確認して送信してください。"
        : "代理プレイヤーのメッセージを作成しました。内容を確認して送信してください。");
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

  document.addEventListener("keydown", (event) => {
    if (!event.ctrlKey || !event.shiftKey || event.key.toLowerCase() !== "d") return;
    event.preventDefault();
    debugAffinityClearShortcut();
  });

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
    if (!locationMoveVisible) selectedLocationMoveId = null;
    renderLocationMovePanel(currentContext);
    renderLocationServicePanel(currentContext);
  });

  toggleInventoryButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    setInventoryVisible(!inventoryVisible);
  });

  inventoryPanel?.addEventListener("click", (event) => {
    if (event.target.closest("#liveChatInventoryCloseButton")) {
      event.preventDefault();
      event.stopPropagation();
      setInventoryVisible(false);
      return;
    }
    event.stopPropagation();
  });

  inventoryCloseButton?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    setInventoryVisible(false);
  });

  inventoryGenerateButton?.addEventListener("click", generateInventoryItem);

  intelRail?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-target-character-id]");
    if (!button) return;
    revealCharacterIntelHint(button);
  });

  inventoryList?.addEventListener("dragstart", (event) => {
    const itemButton = event.target.closest("[data-inventory-item-id]");
    if (!itemButton) return;
    event.dataTransfer.setData("text/plain", itemButton.dataset.inventoryItemId);
    event.dataTransfer.effectAllowed = "move";
  });

  selectedImagePanel?.addEventListener("dragover", (event) => {
    if (!event.dataTransfer.types.includes("text/plain")) return;
    event.preventDefault();
    selectedImagePanel.classList.add("is-inventory-dragover");
  });

  selectedImagePanel?.addEventListener("dragleave", () => {
    selectedImagePanel.classList.remove("is-inventory-dragover");
  });

  selectedImagePanel?.addEventListener("drop", async (event) => {
    const itemId = Number(event.dataTransfer.getData("text/plain") || 0);
    if (!itemId) return;
    event.preventDefault();
    selectedImagePanel.classList.remove("is-inventory-dragover");
    await giveInventoryItem(itemId);
  });

  locationMovePanel?.addEventListener("click", async (event) => {
    event.stopPropagation();
    const closeButton = event.target.closest("[data-location-move-close]");
    if (closeButton) {
      locationMoveVisible = false;
      selectedLocationMoveId = null;
      renderLocationMovePanel(currentContext);
      renderLocationServicePanel(currentContext);
      return;
    }
    const selectButton = event.target.closest("[data-location-select-id]");
    if (selectButton) {
      const id = Number(selectButton.dataset.locationSelectId || 0);
      selectedLocationMoveId = selectedLocationMoveId === id ? null : id;
      renderLocationMovePanel(currentContext);
      renderLocationServicePanel(currentContext);
      return;
    }
    const finalButton = event.target.closest("[data-location-move-final-id]");
    if (finalButton) {
      await moveToLocation(Number(finalButton.dataset.locationMoveFinalId || 0), finalButton);
      return;
    }
    const serviceButton = event.target.closest("[data-location-service-id]");
    if (serviceButton) {
      await selectLocationService(Number(serviceButton.dataset.locationServiceId || 0), serviceButton);
    }
  });

  locationServicePanel?.addEventListener("click", async (event) => {
    event.stopPropagation();
    const button = event.target.closest("[data-location-service-id]");
    if (!button) return;
    await selectLocationService(Number(button.dataset.locationServiceId || 0), button);
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
    if (!canUsePhotoMode()) {
      NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
      return;
    }
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

  document.addEventListener("click", (event) => {
    if (!locationMoveVisible) return;
    const target = event.target;
    if (locationMovePanel?.contains(target) || toggleLocationMoveButton?.contains(target)) return;
    closeLocationMovePanel();
  });

  shell.initialize();
  setComposeVisible(true);
  refreshComposePlaceholder();

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

