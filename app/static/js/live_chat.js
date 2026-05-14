(function () {
  const root = document.querySelector(".live-chat-shell[data-session-id]");
  if (!root) return;

  const {
    LiveChatApi,
    LiveChatView,
    LiveChatActions,
    LiveChatShell,
    LiveChatCostumeRoom,
    LiveChatEnding,
    LiveChatShortStoryPanel,
    LiveChatCharacterGuide,
    LiveChatReplyEffects,
    LiveChatInventory,
    LiveChatLocation,
    LiveChatPhotoMode,
    LiveChatComposer,
  } = window;
  if (!LiveChatApi || !LiveChatView || !LiveChatActions || !LiveChatShell || !LiveChatCostumeRoom || !LiveChatEnding || !LiveChatShortStoryPanel || !LiveChatCharacterGuide || !LiveChatReplyEffects || !LiveChatInventory || !LiveChatLocation || !LiveChatPhotoMode || !LiveChatComposer) {
    throw new Error("LiveChat dependencies are not loaded");
  }

  const sessionId = Number(root.dataset.sessionId || 0);
  const projectId = Number(document.body?.dataset?.projectId || 0);
  const isSuperuser = root.dataset.isSuperuser === "true";
  const canManageProject = root.dataset.canManageProject === "true";
  const createCinemaNovelButton = document.getElementById("liveChatCreateCinemaNovelButton");
  const stateBoard = document.getElementById("liveChatStateBoard");
  const memoryBoard = document.getElementById("liveChatMemoryBoard");
  const selectedImagePanel = document.getElementById("liveChatSelectedImagePanel");
  const stageElement = document.querySelector(".live-chat-stage");
  const stageActions = document.querySelector(".live-chat-stage-actions");
  const stageActionsHandle = document.getElementById("liveChatStageActionsHandle");
  const composeForm = document.getElementById("liveChatComposeForm");
  const composeInput = document.getElementById("liveChatComposeInput");
  const logCard = document.getElementById("liveChatLogCard");
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
  const sceneSuggestionBar = document.getElementById("liveChatSceneSuggestionBar");
  const photoOpportunityBar = document.getElementById("liveChatPhotoOpportunityBar");
  const lccdPanel = document.getElementById("liveChatLccdPanel");
  const toggleLccdButton = document.getElementById("liveChatToggleLccdButton");
  const costumeTicketBadge = document.getElementById("liveChatCostumeTicketBadge");
  const costumeTicketCount = document.getElementById("liveChatCostumeTicketCount");
  const conversationModeButton = document.getElementById("liveChatConversationModeButton");
  const lccdCloseButton = document.getElementById("liveChatLccdCloseButton");
  const lccdForm = document.getElementById("liveChatLccdForm");
  const lccdGenerateButton = document.getElementById("liveChatLccdGenerateButton");
  const objectiveInitial = document.getElementById("liveChatObjectiveInitial");
  const objectiveList = document.getElementById("liveChatObjectiveList");
  const objectiveCount = document.getElementById("liveChatObjectiveDebugCount");
  const affinityCard = document.getElementById("liveChatAffinityCard");
  const affinityList = document.getElementById("liveChatAffinityList");
  const affinityOriginalParent = affinityCard?.parentElement || null;
  const affinityOriginalNextSibling = affinityCard?.nextElementSibling || null;
  const cameraToggleButton = document.getElementById("liveChatCameraToggleButton");
  const cameraStatus = document.getElementById("liveChatCameraStatus");
  const cameraStatusText = document.getElementById("liveChatCameraStatusText");
  const cameraVideo = document.getElementById("liveChatCameraVideo");
  const cameraCanvas = document.getElementById("liveChatCameraCanvas");
  const galleryCard = document.getElementById("liveChatGalleryCard");
  const galleryBody = document.getElementById("liveChatGalleryBody");
  const galleryToggleButton = document.getElementById("liveChatGalleryToggleButton");
  const galleryCount = document.getElementById("liveChatGalleryCount");
  const cameraFeatureEnabled = false;

  let currentContext = null;
  let costumeRoomController = null;
  let composerController = null;
  let userDefaultImageSettings = {};
  let cameraEnabled = false;
  let cameraStream = null;
  let cameraBusy = false;
  let lccdVisible = false;
  let lccdBusy = false;
  let lccdEnterBusy = false;
  let conversationModeActive = true;
  let affinityScoresInitialized = false;
  const lastAffinityScores = new Map();
  const affinityRewardClaiming = new Set();
  let idleTalkTimer = null;
  let idleTalkBusy = false;
  let idleTalksSincePlayerInput = 0;
  let endingInProgress = false;
  let interactionEpoch = 0;
  const stageActionIcons = {
    dressUp: '<i class="bi bi-person-standing-dress" aria-hidden="true"></i>',
    conversation: '<i class="bi bi-chat-dots-fill" aria-hidden="true"></i>',
    photoMode: '<i class="bi bi-camera-fill" aria-hidden="true"></i>',
    cameraOn: '<i class="bi bi-webcam-fill" aria-hidden="true"></i>',
    cameraOff: '<i class="bi bi-webcam" aria-hidden="true"></i>',
  };

  function isMobileViewport() {
    return window.matchMedia("(max-width: 767.98px)").matches;
  }

  function currentImageSize() {
    if (isMobileViewport()) {
      return userDefaultImageSettings?.mobile_default_size || "1024x1536";
    }
    return imageForm?.size?.value || userDefaultImageSettings?.default_size || "1536x1024";
  }

  function configuredImageSizeForViewport() {
    return isMobileViewport()
      ? (userDefaultImageSettings?.mobile_default_size || "1024x1536")
      : (userDefaultImageSettings?.default_size || "1536x1024");
  }

  function syncAffinityCardPlacement() {
    if (!affinityCard || !affinityOriginalParent) return;
    if (isMobileViewport()) {
      if (affinityCard.parentElement !== composeForm?.parentElement) {
        logCard?.parentElement?.insertBefore(affinityCard, logCard);
      } else if (logCard && affinityCard.nextElementSibling !== logCard) {
        logCard.parentElement.insertBefore(affinityCard, logCard);
      }
      affinityCard.classList.add("is-mobile-inline");
      return;
    }
    if (affinityCard.parentElement !== affinityOriginalParent) {
      affinityOriginalParent.insertBefore(affinityCard, affinityOriginalNextSibling);
    }
    affinityCard.classList.remove("is-mobile-inline");
  }

  function imageGenerationOptions(overrides = {}) {
    return {
      size: currentImageSize(),
      quality: imageForm?.quality?.value || userDefaultImageSettings?.default_quality || "low",
      client_viewport: isMobileViewport() ? "mobile" : "desktop",
      ...overrides,
    };
  }

  const idleTalkEnabled = false;
  const idleTalkMinMs = 10000;
  const idleTalkMaxMs = 30000;
  const stageActionsStorageKey = `liveChatStageActionsPosition:${sessionId}`;
  let stageActionsPosition = loadStageActionsPosition();
  let stageActionsDragState = null;

  function hasActiveSceneChoices() {
    const choiceState = currentContext?.state?.state_json?.scene_choices || {};
    if (choiceState.allow_free_text || String(choiceState.source || "").startsWith("learning_live_chat")) return false;
    return Array.isArray(choiceState.choices) && choiceState.choices.length > 0;
  }

  function currentSceneSuggestions(context = currentContext) {
    const stateJson = context?.state?.state_json || {};
    const choiceState = stateJson.scene_choices || {};
    if (!choiceState.allow_free_text && !String(choiceState.source || "").startsWith("learning_live_chat") && Array.isArray(choiceState.choices) && choiceState.choices.length > 0) {
      return [];
    }
    const suggestionState = stateJson.scene_suggestions || {};
    return Array.isArray(suggestionState.suggestions)
      ? suggestionState.suggestions.filter((item) => item && (item.label || item.message_text)).slice(0, 3)
      : [];
  }

  function currentPhotoOpportunities(context = currentContext) {
    const stateJson = context?.state?.state_json || {};
    const choiceState = stateJson.scene_choices || {};
    if (!choiceState.allow_free_text && !String(choiceState.source || "").startsWith("learning_live_chat") && Array.isArray(choiceState.choices) && choiceState.choices.length > 0) {
      return [];
    }
    const opportunityState = stateJson.photo_opportunities || {};
    return Array.isArray(opportunityState.opportunities)
      ? opportunityState.opportunities.filter((item) => item && (item.label || item.shot_instruction)).slice(0, 3)
      : [];
  }

  function isInteractionLocked() {
    return endingInProgress;
  }

  function isStaleInteraction(epoch) {
    return endingInProgress || epoch !== interactionEpoch;
  }

  function beginEndingInteraction() {
    endingInProgress = true;
    interactionEpoch += 1;
    document.body.classList.add("live-chat-ending-in-progress");
    window.LiveChatSound?.play("ending");
  }

  function endEndingInteraction() {
    endingInProgress = false;
    document.body.classList.remove("live-chat-ending-in-progress");
  }

  function isAllowedDuringEnding(target) {
    return Boolean(target?.closest?.(".live-chat-ending-story"));
  }

  function isLockableInteractionTarget(target) {
    if (!target?.closest) return false;
    return Boolean(target.closest([
      ".live-chat-image-panel",
      ".live-chat-stage-frame",
      ".live-chat-stage-image",
      ".live-chat-compose",
      ".live-chat-stage-actions",
      ".live-chat-location-panel",
      ".live-chat-location-service-panel",
      ".live-chat-lccd-panel",
      ".live-chat-inventory-panel",
      ".live-chat-choice-panel",
      ".live-chat-reply-effect",
      ".live-chat-ending-reel",
      ".live-chat-ending-blackout",
      "#liveChatImageForm",
      "#liveChatImageUploadForm",
      "#liveChatCostumeForm",
      "#liveChatClosetSelectButton",
      "#liveChatRegenerateImageButton",
      "[data-scene-choice-id]",
      "[data-reply-effect-image]",
    ].join(",")));
  }

  function blockEndingInteraction(event) {
    if (!endingInProgress || isAllowedDuringEnding(event.target) || !isLockableInteractionTarget(event.target)) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation?.();
  }

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
    const stageFrame = selectedImagePanel?.querySelector(".live-chat-stage-frame");
    const boundsRect = isMobileViewport() && stageFrame
      ? stageFrame.getBoundingClientRect()
      : stageRect;
    const actionsRect = stageActions.getBoundingClientRect();
    const minX = Math.max(12, boundsRect.left - stageRect.left + 12);
    const minY = Math.max(12, boundsRect.top - stageRect.top + 12);
    const maxX = Math.max(minX, boundsRect.right - stageRect.left - actionsRect.width - 12);
    const maxY = Math.max(minY, boundsRect.bottom - stageRect.top - actionsRect.height - 12);
    return {
      x: Math.min(Math.max(minX, x), maxX),
      y: Math.min(Math.max(minY, y), maxY),
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

  const endingController = LiveChatEnding.createEndingController({
    selectedImagePanel,
    shell,
    applyContext,
    getCurrentContext: () => currentContext,
    scheduleStageActionPosition,
  });
  const shortStoryPanel = LiveChatShortStoryPanel.createShortStoryPanel({
    getCurrentContext: () => currentContext,
  });
  const characterGuideController = LiveChatCharacterGuide.createCharacterGuideController({
    getActiveCharacters: (context) => activeCharacters(context),
    onPrompt: sendCharacterGuidePrompt,
  });
  const replyEffectsController = LiveChatReplyEffects.createReplyEffectsController({
    selectedImagePanel,
    imageForm,
    generateSessionImage,
    getActiveCharacters: () => activeCharacters(currentContext),
    getPhotoOpportunities: () => currentPhotoOpportunities(currentContext),
    hasSceneChoices: hasActiveSceneChoices,
    isInteractionLocked,
    onMoodChange: (speakerName, mood) => characterGuideController.setMood(speakerName, mood),
  });
  const inventoryController = LiveChatInventory.createInventoryController({
    api: LiveChatApi,
    projectId,
    sessionId,
    shell,
    selectedImagePanel,
    getCurrentContext: () => currentContext,
    getTargetCharacterId: () => activeCharacterId(currentContext),
    loadContext,
    isInteractionLocked,
    playAffinityFeedback,
    getImageGenerationOptions: imageGenerationOptions,
  });
  const locationController = LiveChatLocation.createLocationController({
    api: LiveChatApi,
    sessionId,
    shell,
    imageForm,
    getImageGenerationOptions: imageGenerationOptions,
    getCurrentContext: () => currentContext,
    applyContext,
    loadContext,
    isInteractionLocked,
    capturePlayerReaction: capturePlayerReactionIfEnabled,
  });
  const photoModeController = LiveChatPhotoMode.createPhotoModeController({
    api: LiveChatApi,
    sessionId,
    shell,
    imageForm,
    getImageGenerationOptions: imageGenerationOptions,
    iconHtml: stageActionIcons.photoMode,
    canBypassAffinityLock: isSuperuser || canManageProject,
    getReward: (context) => activeAffinityReward(context || currentContext),
    applyContext,
    loadContext,
    isInteractionLocked,
    onDeactivateConversation: () => setConversationModeActive(false, { keepPhotoMode: true }),
    onModeChanged: () => {
      refreshModeBadge();
      refreshComposePlaceholder();
    },
  });
  composerController = LiveChatComposer.createComposerController({
    api: LiveChatApi,
    sessionId,
    form: composeForm,
    input: composeInput,
    shell,
    imageForm,
    getImageGenerationOptions: imageGenerationOptions,
    getCurrentContext: () => currentContext,
    isPhotoModeActive: () => photoModeController.isActive(),
    generatePhotoShoot: (promptText) => photoModeController.generateShoot(promptText),
    loadContext,
    capturePlayerReaction: capturePlayerReactionIfEnabled,
    playAffinityFeedback,
    triggerReplyEffect: (effect) => {
      if (endingInProgress) {
        replyEffectsController.hide?.();
        return;
      }
      if (effect) {
        replyEffectsController.trigger(effect);
      } else {
        replyEffectsController.hide?.();
      }
    },
    onActivity: () => {
      idleTalksSincePlayerInput = 0;
    },
    clearIdleTalkTimer,
    scheduleIdleTalk,
    isInteractionLocked,
  });

  function setPanelExpanded(card, body, button, expanded) {
    if (!card || !body || !button) return;
    card.classList.toggle("is-collapsed", !expanded);
    body.hidden = !expanded;
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    const label = button.querySelector("span");
    if (label) label.textContent = expanded ? "閉じる" : "開く";
  }

  function togglePanel(card, body, button) {
    setPanelExpanded(card, body, button, card?.classList.contains("is-collapsed"));
  }

  function updateGalleryCount(images) {
    if (!galleryCount) return;
    const count = Array.isArray(images) ? images.length : 0;
    galleryCount.textContent = `${count}枚`;
  }

  function applyContext(context, options = {}) {
    if (!options.force && endingInProgress) return false;
    currentContext = context;
    const title = context.session.title || "\u30e9\u30a4\u30d6\u30c1\u30e3\u30c3\u30c8";
    document.getElementById("liveChatTitle").textContent = title;
    const roomGenre = context?.room?.genre
      || context?.session?.room_snapshot_json?.genre
      || context?.session?.settings_json?.live_chat_genre
      || context?.state?.state_json?.live_chat_genre
      || "romance";
    const isLearningMode = roomGenre === "learning";
    root.classList.toggle("is-learning-mode", isLearningMode);
    document.body.classList.toggle("live-chat-learning-mode", isLearningMode);

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
    updateGalleryCount(context.images || []);
    costumeRoomController?.render(context);
    renderSceneChoices(context);
    renderSceneSuggestions(context);
    renderPhotoOpportunities(context);
    locationController.renderMovePanel(context);
    locationController.renderServicePanel();
    renderLccdPanel();
    updateLccdAvailability(context);
    photoModeController.updateAvailability(context);
    renderObjectiveNotes(context);
    characterGuideController.render(context);
    renderCharacterAffinity(context);
    composerController?.render(context);
    renderPlayerReaction(context);
    shortStoryPanel.renderSavedShortStories(context);
    inventoryController.render();
    return true;
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

  function activeAffinityReward(context = currentContext) {
    const characterId = activeCharacterId(context);
    if (!characterId) return null;
    return (context?.affinity_rewards || {})[String(characterId)] || null;
  }

  function canUseLccd(context = currentContext) {
    return false;
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

  function triggerAffinityHeartBurst(delta = 1) {
    const stage = selectedImagePanel?.closest(".live-chat-stage");
    if (!stage) return;
    window.LiveChatSound?.play("affinity");
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
    window.LiveChatSound?.play("affinityMilestone");
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
    beginEndingInteraction();
    clearIdleTalkTimer();
    replyEffectsController.hide?.();
    shell.setImageLoading(true, "ending");
    shell.setReplyLoading(true, currentContext, { render: false });
    try {
      const result = await LiveChatApi.claimAffinityReward(
        sessionId,
        characterId,
        imageGenerationOptions({ quality: "medium" })
      );
      if (!result?.claimed) {
        if (result?.context) applyContext(result.context, { force: true });
        return;
      }
      triggerAffinityMaxHeartBurst();
      await endingController.playAffinityEndingSequence(result);
      if (result?.letter) NovelUI.refreshLetterBadge?.();
      NovelUI.toast(
        result?.reward_replayed
          ? "好感度100達成。エンディングを再生しました。"
          : "好感度100達成。衣装チケットを1枚獲得しました。"
      );
    } catch (error) {
      NovelUI.toast(error.message || "好感度100報酬を受け取れませんでした。", "danger");
    } finally {
      shell.setImageLoading(false, currentContext);
      shell.setReplyLoading(false, currentContext);
      endEndingInteraction();
      affinityRewardClaiming.delete(key);
    }
  }

  async function debugAffinityClearShortcut() {
    if (!LiveChatApi.debugAffinityClear) return;
    const password = window.prompt("DEBUG password");
    if (!password) return;
    beginEndingInteraction();
    clearIdleTalkTimer();
    replyEffectsController.hide?.();
    shell.setImageLoading(true, "ending");
    shell.setReplyLoading(true, currentContext, { render: false });
    try {
      const result = await LiveChatApi.debugAffinityClear(
        sessionId,
        imageGenerationOptions({ password, quality: "medium" })
      );
      triggerAffinityMaxHeartBurst();
      await endingController.playAffinityEndingSequence(result);
      if (result?.letter) NovelUI.refreshLetterBadge?.();
      NovelUI.toast("デバッグ: 好感度100クリアにしました。");
    } catch (error) {
      NovelUI.toast(error.message || "デバッグクリアに失敗しました。", "danger");
    } finally {
      shell.setImageLoading(false, currentContext);
      shell.setReplyLoading(false, currentContext);
      endEndingInteraction();
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
      const sessionEndings = context?.state?.state_json?.affinity_100_endings || {};
      const sessionEnding = sessionEndings[String(characterId)] || {};
      const previous = lastAffinityScores.get(String(characterId));
      if (
        affinityScoresInitialized
        &&
        score >= 100
        && !sessionEnding.played_at
        && (previous === undefined || previous < 100)
      ) {
        claimAffinityReward(characterId);
      }
      if (!affinityScoresInitialized) return;
      if (previous !== undefined && score > previous) {
        if (
          (previous < 60 && score >= 60)
          || (previous < 80 && score >= 80)
          || (previous < 100 && score >= 100)
        ) {
          window.LiveChatSound?.play("affinityMilestone");
        }
        triggerAffinityHeartBurst(score - previous);
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
    const cleanAffinityNote = (note) => String(note || "")
      .replace(/^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\s*[:：-]?\s*/, "")
      .trim();
    const rows = characters
      .map((character) => {
        const memory = memoryMap[String(character.id)] || {};
        const score = Math.max(0, Math.min(100, Number(memory.affinity_score || 0)));
        const label = memory.affinity_label || "警戒";
        const closenessLevel = Math.max(0, Math.min(5, Number(memory.physical_closeness_level || 0)));
        const closenessLevelLabel = closenessLevel >= 5 ? "Max" : String(closenessLevel);
        const closenessLabel = memory.physical_closeness_label || "距離を保つ";
        const note = cleanAffinityNote(memory.affinity_notes);
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

  function sendCharacterGuidePrompt(messageText) {
    const text = String(messageText || "").trim();
    if (!text) return;
    if (shell.getState?.().replyLoading) {
      NovelUI.toast("返信の処理が終わってから話しかけてください。", "warning");
      return;
    }
    photoModeController.setActive(false, { silent: true });
    setConversationModeActive(true);
    composerController?.submitText(text);
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
    if (endingInProgress) return;
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
    const epoch = interactionEpoch;
    const context = await LiveChatApi.loadContext(sessionId);
    if (isStaleInteraction(epoch)) return null;
    applyContext(context);
    await inventoryController.loadItems();
    if (isStaleInteraction(epoch)) return context;
    scheduleIdleTalk();
    return context;
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
    return Boolean(composerController?.hasPendingText());
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
    const epoch = interactionEpoch;
    idleTalkBusy = true;
    idleTalksSincePlayerInput += 1;
    try {
      shell.setReplyLoading(true, currentContext);
      const result = await LiveChatApi.postIdleMessage(sessionId);
      if (isStaleInteraction(epoch)) return;
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      if (!isStaleInteraction(epoch)) await capturePlayerReactionIfEnabled();
    } catch (error) {
      idleTalksSincePlayerInput = Math.max(0, idleTalksSincePlayerInput - 1);
      NovelUI.toast(error.message || "自動発話に失敗しました。", "warning");
      scheduleIdleTalk();
    } finally {
      idleTalkBusy = false;
      if (!isStaleInteraction(epoch)) shell.setReplyLoading(false, currentContext);
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
        imageForm.size.value = configuredImageSizeForViewport();
      }
    } catch (error) {
      userDefaultImageSettings = {};
    }
  }

  async function generateSessionImage(useExistingPrompt = false, mode = "generate", overrides = {}) {
    const epoch = interactionEpoch;
    shell.setImageLoading(true, mode);
    try {
      const body = imageGenerationOptions(overrides);
      if (useExistingPrompt) {
        body.prompt_text = imageForm.prompt_text.value;
        body.use_existing_prompt = true;
      }
      const generatedImage = await LiveChatApi.generateSessionImage(sessionId, body);
      if (isStaleInteraction(epoch)) return null;
      if (generatedImage?.asset?.media_url) {
        window.LiveChatSound?.play("imageDone");
        currentContext = {
          ...(currentContext || {}),
          selected_image: generatedImage,
          images: [generatedImage, ...((currentContext?.images || []).filter((item) => item.id !== generatedImage.id))],
        };
        shell.renderSelectedImage(generatedImage, currentContext);
        scheduleStageActionPosition();
        shell.renderImageGrid(currentContext.images || []);
        updateGalleryCount(currentContext.images || []);
      }
      await loadContext();
      return generatedImage;
    } finally {
      if (!isStaleInteraction(epoch)) {
        shell.setImageLoading(false, mode);
      }
    }
  }

  async function createCinemaNovelFromSession() {
    if (!createCinemaNovelButton || createCinemaNovelButton.disabled) return;
    const originalHtml = createCinemaNovelButton.innerHTML;
    createCinemaNovelButton.disabled = true;
    createCinemaNovelButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>ノベル化中...';
    try {
      const novel = await LiveChatApi.createCinemaNovel(sessionId, {});
      NovelUI.toast("チャット内容からノベルを作成しました。");
      window.location.href = `/projects/${projectId}/cinema-novels/${novel.id}`;
    } catch (error) {
      NovelUI.toast(error.message || "ノベル化に失敗しました。", "danger");
      createCinemaNovelButton.disabled = false;
      createCinemaNovelButton.innerHTML = originalHtml;
    }
  }

  function renderSceneChoices(context) {
    if (!sceneChoicePanel) return;
    sceneChoicePanel.classList.add("is-hidden");
    sceneChoicePanel.innerHTML = "";
  }

  function renderSceneSuggestions(context) {
    if (!sceneSuggestionBar) return;
    const suggestions = currentSceneSuggestions(context);
    sceneSuggestionBar.classList.toggle("is-hidden", suggestions.length === 0);
    sceneSuggestionBar.innerHTML = suggestions.map((suggestion) => {
      const type = String(suggestion.type || "talk").toLowerCase();
      const icon = type === "photo" ? "bi-camera" : type === "action" ? "bi-stars" : "bi-chat-dots";
      return `
        <button
          class="live-chat-scene-suggestion"
          type="button"
          data-scene-suggestion-id="${NovelUI.escape(suggestion.id || "")}"
          data-scene-suggestion-type="${NovelUI.escape(type)}"
          title="${NovelUI.escape(suggestion.message_text || suggestion.label || "")}"
        >
          <i class="bi ${icon}" aria-hidden="true"></i>
          <span>${NovelUI.escape(suggestion.label || suggestion.message_text || "")}</span>
        </button>
      `;
    }).join("");
  }

  function renderPhotoOpportunities(context) {
    if (!photoOpportunityBar) return;
    photoOpportunityBar.classList.add("is-hidden");
    photoOpportunityBar.innerHTML = "";
  }

  function renderLccdPanel() {
    if (!lccdPanel) return;
    lccdPanel.classList.add("is-hidden");
    toggleLccdButton?.setAttribute("aria-expanded", "false");
  }

  function currentModeBadgeText() {
    if (photoModeController.isActive()) return "撮影モード";
    if (conversationModeActive) return "会話モード";
    if (isCurrentLocationLccd()) return "お着替えモード";
    return "";
  }

  function refreshModeBadge() {
    shell.setModeBadgeText?.(currentModeBadgeText());
  }

  function refreshComposePlaceholder() {
    composerController?.refreshPlaceholder();
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
  function setConversationModeActive(active, { keepPhotoMode = false } = {}) {
    conversationModeActive = active;
    if (active && !keepPhotoMode) {
      photoModeController.setActive(false, { silent: true });
    }
    if (!conversationModeButton) return;
    conversationModeButton.classList.toggle("is-active", active);
    conversationModeButton.setAttribute("aria-pressed", active ? "true" : "false");
    conversationModeButton.setAttribute("title", active ? "会話モード中" : "会話モード");
    conversationModeButton.setAttribute("aria-label", active ? "会話モード中" : "会話モード");
    refreshModeBadge();
    refreshComposePlaceholder();
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

  setPanelExpanded(galleryCard, galleryBody, galleryToggleButton, false);
  syncAffinityCardPlacement();
  composerController.bind();
  shortStoryPanel.bind();
  createCinemaNovelButton?.addEventListener("click", createCinemaNovelFromSession);
  galleryToggleButton?.addEventListener("click", () => togglePanel(galleryCard, galleryBody, galleryToggleButton));

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
    canBypassAffinityLock: isSuperuser || canManageProject,
    loadContext,
    isInteractionLocked,
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

  characterGuideController.bind();
  replyEffectsController.bind();
  inventoryController.bind();
  locationController.bind();

  document.addEventListener("click", blockEndingInteraction, true);
  document.addEventListener("submit", blockEndingInteraction, true);
  document.addEventListener("keydown", (event) => {
    if (!endingInProgress || isAllowedDuringEnding(event.target)) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    blockEndingInteraction(event);
  }, true);

  toggleLccdButton?.addEventListener("click", () => {
    if (!conversationModeActive && !photoModeController.isActive() && isCurrentLocationLccd()) {
      composerController?.focus();
      return;
    }
    setConversationModeActive(false);
    photoModeController.setActive(false, { silent: true });
    refreshModeBadge();
    enterLccdRoom();
  });

  conversationModeButton?.addEventListener("click", () => {
    photoModeController.setActive(false, { silent: true });
    setConversationModeActive(true);
    NovelUI.toast("会話モードです。通常どおり会話しながら進行します。");
    composerController?.focus();
  });

  photoModeController.bind();

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
    window.LiveChatSound?.unlock?.();
    window.LiveChatSound?.play("shutter");
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

  sceneSuggestionBar?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-scene-suggestion-id]");
    if (!button || endingInProgress) return;
    const suggestions = currentSceneSuggestions();
    const suggestion = suggestions.find((item) => String(item.id || "") === String(button.dataset.sceneSuggestionId || ""));
    if (!suggestion) return;
    const messageText = String(suggestion.message_text || suggestion.label || "").trim();
    if (!messageText) return;
    window.LiveChatSound?.unlock?.();
    window.LiveChatSound?.play("choice");
    button.disabled = true;
    try {
      await composerController?.submitText(messageText);
      sceneSuggestionBar.classList.add("is-hidden");
    } finally {
      button.disabled = false;
    }
  });

  photoOpportunityBar?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-photo-opportunity-id]");
    if (!button || endingInProgress) return;
    const opportunities = currentPhotoOpportunities();
    const opportunity = opportunities.find((item) => String(item.id || "") === String(button.dataset.photoOpportunityId || ""));
    if (!opportunity) return;
    const instruction = String(opportunity.shot_instruction || opportunity.label || "").trim();
    if (!instruction) return;
    window.LiveChatSound?.unlock?.();
    window.LiveChatSound?.play("shutter");
    button.disabled = true;
    try {
      const ok = await photoModeController.generateShoot(instruction, opportunity.pose_style || "シャッターチャンス");
      if (ok) {
        photoOpportunityBar.classList.add("is-hidden");
        NovelUI.toast("シャッターチャンスを撮影しました。");
      }
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-scene-choice-id]");
    if (!button) return;
    if (endingInProgress) {
      event.preventDefault();
      return;
    }
    window.LiveChatSound?.unlock?.();
    window.LiveChatSound?.play("choice");
    setSceneChoiceLoading(true, button);
    shell.setImageLoading(true, "auto");
    const epoch = interactionEpoch;
    try {
      const result = await LiveChatApi.executeSceneChoice(sessionId, button.dataset.sceneChoiceId, imageGenerationOptions());
      if (isStaleInteraction(epoch)) return;
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      if (!isStaleInteraction(epoch)) await capturePlayerReactionIfEnabled();
      idleTalksSincePlayerInput = 0;
      if (!isStaleInteraction(epoch)) {
        scheduleIdleTalk();
        NovelUI.toast("選択した場面を生成しました。");
      }
    } catch (error) {
      NovelUI.toast(error.message || "選択肢の実行に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      if (!isStaleInteraction(epoch)) {
        setSceneChoiceLoading(false);
        shell.setImageLoading(false, "auto");
      }
    }
  });

  shell.initialize();

  loadDefaultImageSettings().then(loadContext).catch((error) => {
    NovelUI.toast(error.message || "\u30e9\u30a4\u30d6\u30c1\u30e3\u30c3\u30c8\u753b\u9762\u306e\u521d\u671f\u5316\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
  });

  window.addEventListener("resize", () => {
    syncAffinityCardPlacement();
    if (currentContext) {
      shell.renderSelectedImage(currentContext.selected_image, currentContext);
      scheduleStageActionPosition();
      shell.renderNovel(currentContext.messages || [], currentContext);
    }
  });
})();

