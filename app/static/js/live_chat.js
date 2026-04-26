(function () {
  const root = document.querySelector(".live-chat-shell[data-session-id]");
  if (!root) return;

  const { LiveChatApi, LiveChatView, LiveChatGift, LiveChatActions, LiveChatShell } = window;
  if (!LiveChatApi || !LiveChatView || !LiveChatGift || !LiveChatActions || !LiveChatShell) {
    throw new Error("LiveChat dependencies are not loaded");
  }

  const sessionId = Number(root.dataset.sessionId || 0);
  const projectId = Number(document.body?.dataset?.projectId || 0);
  const stateBoard = document.getElementById("liveChatStateBoard");
  const memoryBoard = document.getElementById("liveChatMemoryBoard");
  const selectedImagePanel = document.getElementById("liveChatSelectedImagePanel");
  const composeForm = document.getElementById("liveChatComposeForm");
  const composeInput = document.getElementById("liveChatComposeInput");
  const composeShell = document.getElementById("liveChatComposeShell");
  const toggleComposeButton = document.getElementById("liveChatToggleComposeButton");
  const imageForm = document.getElementById("liveChatImageForm");
  const uploadForm = document.getElementById("liveChatImageUploadForm");
  const costumeForm = document.getElementById("liveChatCostumeForm");
  const costumeGrid = document.getElementById("liveChatCostumeGrid");
  const costumePreview = document.getElementById("liveChatCostumePreview");
  const generateCostumeButton = document.getElementById("liveChatGenerateCostumeButton");
  const sceneChoicePanel = document.getElementById("liveChatSceneChoicePanel");

  let currentContext = null;
  let giftController = null;
  let composeVisible = true;
  let userDefaultImageSettings = {};

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

    shell.renderMessages(context.messages || [], context);
    shell.renderSelectedImage(context.selected_image, context);
    shell.renderImageGrid(context.images || []);
    renderCostumeRoom(context);
    renderSceneChoices(context);
  }

  async function loadContext() {
    const context = await LiveChatApi.loadContext(sessionId);
    applyContext(context);
  }

  async function loadDefaultImageSettings() {
    try {
      const settings = await LiveChatApi.loadSettings();
      userDefaultImageSettings = settings || {};
      if (settings?.default_quality && imageForm.quality) {
        imageForm.quality.value = settings.default_quality;
      }
      if (settings?.default_quality && costumeForm?.quality) {
        costumeForm.quality.value = settings.default_quality;
      }
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

  function renderCostumeRoom(context) {
    const costumes = context.costumes || [];
    const selectedCostume = context.selected_costume || costumes.find((item) => item.is_selected) || costumes[0] || null;
    if (costumePreview) {
      const mediaUrl = selectedCostume?.asset?.media_url;
      costumePreview.innerHTML = mediaUrl
        ? `
          <button class="live-chat-costume-preview-button" type="button" data-costume-id="${selectedCostume.id}">
            <img src="${mediaUrl}" alt="selected costume reference">
            <span>現在の衣装基準</span>
          </button>
        `
        : '<div class="empty-panel">衣装の基準画像がありません。</div>';
    }
    if (!costumeGrid) return;
    if (!costumes.length) {
      costumeGrid.innerHTML = '<div class="empty-panel">衣装候補がありません。</div>';
      return;
    }
    costumeGrid.innerHTML = costumes.map((item) => {
      const mediaUrl = item.asset?.media_url;
      const label = item.image_type === "costume_initial" ? "初期衣装" : "衣装";
      return `
        <div class="live-chat-costume-card ${item.is_selected ? "selected" : ""}">
          <button class="live-chat-costume-select" type="button" data-costume-id="${item.id}">
            ${mediaUrl ? `<img src="${mediaUrl}" alt="${label}">` : "<span>No Image</span>"}
            <span class="live-chat-costume-card-label">${item.is_selected ? "選択中" : label}</span>
          </button>
        </div>
      `;
    }).join("");
  }

  function setCostumeLoading(active) {
    if (!generateCostumeButton) return;
    generateCostumeButton.disabled = active;
    generateCostumeButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>衣装生成中...'
      : "衣装を生成";
  }

  function renderSceneChoices(context) {
    if (!sceneChoicePanel) return;
    sceneChoicePanel.classList.add("is-hidden");
    sceneChoicePanel.innerHTML = "";
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
    const rawMessage = composeForm.message_text.value.trim();
    try {
      shell.setReplyLoading(true, currentContext);
      if (giftController?.hasSelectedGift()) {
        const uploaded = await giftController.uploadGiftImage(rawMessage);
        if (!uploaded) {
          throw new Error("\u8d08\u308a\u7269\u753b\u50cf\u306e\u9001\u4fe1\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002");
        }
      } else {
        const result = await LiveChatApi.postMessage(sessionId, {
          message_text: rawMessage || "\u8a71\u3092\u9032\u3081\u3066",
          auto_reply: true,
        });
        if (result?.new_letter) {
          NovelUI.toast("\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u304b\u3089\u304a\u624b\u7d19\u304c\u5c4a\u304d\u307e\u3057\u305f\u3002");
          NovelUI.refreshLetterBadge?.();
        }
        if (result?.input_intent?.intent !== "dialogue" && result?.generated_image) {
          NovelUI.toast("\u5834\u9762\u6307\u793a\u3092\u53cd\u6620\u3057\u3066\u753b\u50cf\u3092\u751f\u6210\u3057\u307e\u3057\u305f\u3002");
        }
        await loadContext();
      }
      composeForm.message_text.value = "";
      NovelUI.toast("\u30e1\u30c3\u30bb\u30fc\u30b8\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f\u3002");
    } catch (error) {
      NovelUI.toast(error.message || "\u30e1\u30c3\u30bb\u30fc\u30b8\u9001\u4fe1\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
    } finally {
      shell.setReplyLoading(false, currentContext);
    }
  });

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

  document.getElementById("liveChatRefreshContextButton")?.addEventListener("click", () => {
    loadContext().catch((error) => {
      NovelUI.toast(error.message || "\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
    });
  });

  toggleComposeButton?.addEventListener("click", () => {
    setComposeVisible(!composeVisible);
  });

  costumeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const promptText = costumeForm.prompt_text.value.trim();
    if (!promptText) {
      NovelUI.toast("着替え指示を入力してください。", "warning");
      return;
    }
    setCostumeLoading(true);
    try {
      await LiveChatApi.generateCostume(sessionId, {
        prompt_text: promptText,
        size: costumeForm.size.value,
        quality: costumeForm.quality.value,
      });
      costumeForm.prompt_text.value = "";
      await loadContext();
      NovelUI.toast("衣装を生成し、基準画像に設定しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装生成に失敗しました。", "danger");
    } finally {
      setCostumeLoading(false);
    }
  });

  const handleCostumeSelect = async (event) => {
    if (event.target.closest("[data-delete-costume-id]")) return;
    const button = event.target.closest("[data-costume-id]");
    if (!button) return;
    try {
      await LiveChatApi.selectCostume(sessionId, button.dataset.costumeId);
      await loadContext();
      NovelUI.toast("衣装の基準画像を変更しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装の選択に失敗しました。", "danger");
    }
  };

  costumeGrid?.addEventListener("click", handleCostumeSelect);
  costumePreview?.addEventListener("click", handleCostumeSelect);

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-scene-choice-id]");
    if (!button) return;
    setSceneChoiceLoading(true, button);
    try {
      const result = await LiveChatApi.executeSceneChoice(sessionId, button.dataset.sceneChoiceId);
      if (result?.context) {
        applyContext(result.context);
      } else {
        await loadContext();
      }
      NovelUI.toast("選択した場面を生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "選択肢の実行に失敗しました。", "danger");
      await loadContext().catch(() => {});
    } finally {
      setSceneChoiceLoading(false);
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
      shell.renderNovel(currentContext.messages || [], currentContext);
    }
  });
})();
