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
  const sessionMetaForm = document.getElementById("liveChatSessionMetaForm");
  const sessionCharacterSelect = document.getElementById("liveChatSessionCharacterSelect");
  const objectiveInput = document.getElementById("liveChatSessionObjectiveInput");
  const objectivePreview = document.getElementById("liveChatObjectivePreview");
  const objectiveEditButton = document.getElementById("liveChatObjectiveEditButton");
  const objectiveModalElement = document.getElementById("liveChatObjectiveModal");
  const objectiveMarkdownInput = document.getElementById("liveChatObjectiveMarkdownInput");
  const objectiveMarkdownPreview = document.getElementById("liveChatObjectiveMarkdownPreview");
  const objectiveApplyButton = document.getElementById("liveChatObjectiveApplyButton");
  const composeForm = document.getElementById("liveChatComposeForm");
  const composeInput = document.getElementById("liveChatComposeInput");
  const composeShell = document.getElementById("liveChatComposeShell");
  const toggleComposeButton = document.getElementById("liveChatToggleComposeButton");
  const imageForm = document.getElementById("liveChatImageForm");
  const uploadForm = document.getElementById("liveChatImageUploadForm");

  let currentContext = null;
  let giftController = null;
  let composeVisible = true;
  let userDefaultImageSettings = {};
  if (objectiveModalElement) {
    document.body.appendChild(objectiveModalElement);
  }
  const objectiveModal = objectiveModalElement ? new bootstrap.Modal(objectiveModalElement) : null;

  function escapeHtml(value) {
    return NovelUI.escape(value ?? "");
  }

  function renderInlineMarkdown(value) {
    return escapeHtml(value)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  }

  function markdownToHtml(markdown) {
    const lines = String(markdown || "").split(/\r?\n/);
    const html = [];
    let listOpen = false;

    function closeList() {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
    }

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        closeList();
        return;
      }
      if (trimmed.startsWith("## ")) {
        closeList();
        html.push(`<h5>${renderInlineMarkdown(trimmed.slice(3))}</h5>`);
        return;
      }
      if (trimmed.startsWith("# ")) {
        closeList();
        html.push(`<h4>${renderInlineMarkdown(trimmed.slice(2))}</h4>`);
        return;
      }
      if (trimmed.startsWith("> ")) {
        closeList();
        html.push(`<blockquote>${renderInlineMarkdown(trimmed.slice(2))}</blockquote>`);
        return;
      }
      if (/^[-*]\s+/.test(trimmed)) {
        if (!listOpen) {
          html.push("<ul>");
          listOpen = true;
        }
        html.push(`<li>${renderInlineMarkdown(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
        return;
      }
      closeList();
      html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
    });

    closeList();
    return html.join("") || '<p class="text-secondary mb-0">まだ入力されていません。</p>';
  }

  function summarizeMarkdown(markdown) {
    const text = String(markdown || "")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/^[-*]\s+/gm, "")
      .replace(/^>\s+/gm, "")
      .replace(/[*_`>#-]/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!text) return "まだ入力されていません。";
    return text.length > 180 ? `${text.slice(0, 180)}...` : text;
  }

  function renderObjectivePreview() {
    if (!objectivePreview || !objectiveInput) return;
    objectivePreview.textContent = summarizeMarkdown(objectiveInput.value);
  }

  function getMessageListElement() {
    return document.getElementById("liveChatMessageList");
  }

  function getNovelElements() {
    return {
      novelBox: document.getElementById("liveChatNovelBox"),
      novelSpeaker: document.getElementById("liveChatNovelSpeaker"),
      novelText: document.getElementById("liveChatNovelText"),
      novelContinue: document.getElementById("liveChatNovelContinue"),
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
    sessionMetaForm.title.value = context.session.title || "";
    sessionMetaForm.player_name.value = context.session.player_name || "";
    objectiveInput.value = context.session.settings_json?.conversation_objective || "";
    renderObjectivePreview();

    LiveChatApi.loadSessionCharacterOptions(Number(context?.project?.id || projectId || 0))
      .then((list) => {
        sessionCharacterSelect.innerHTML = [
          '<option value="">\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u3092\u9078\u629e</option>',
          ...list.map((item) => `<option value="${item.id}">${NovelUI.escape(item.name || "Unnamed")}</option>`),
        ].join("");
        const selectedIds = LiveChatView.normalizeSelectedCharacterIds(context.session.settings_json);
        sessionCharacterSelect.value = selectedIds.length ? String(selectedIds[0]) : "";
        sessionCharacterSelect.disabled = true;
        sessionCharacterSelect.title = "\u4f5c\u6210\u6e08\u307f\u30bb\u30c3\u30b7\u30e7\u30f3\u306e\u8a71\u3059\u76f8\u624b\u306f\u5909\u66f4\u3067\u304d\u307e\u305b\u3093\u3002";
      })
      .catch((error) => {
        NovelUI.toast(error.message || "\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u4e00\u89a7\u306e\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      });

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
      await LiveChatApi.generateSessionImage(sessionId, body);
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
        await LiveChatApi.postMessage(sessionId, {
          message_text: rawMessage || "\u8a71\u3092\u9032\u3081\u3066",
          auto_reply: true,
        });
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

  LiveChatActions.bindSessionMetaForm({
    sessionMetaForm,
    sessionCharacterSelect,
    api: LiveChatApi,
    getSessionId: () => sessionId,
    getCurrentContext: () => currentContext,
    applyContext,
    generateSessionImage,
  });

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

  document.getElementById("liveChatRefreshContextButton").addEventListener("click", () => {
    loadContext().catch((error) => {
      NovelUI.toast(error.message || "\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
    });
  });

  toggleComposeButton?.addEventListener("click", () => {
    setComposeVisible(!composeVisible);
  });

  objectiveEditButton?.addEventListener("click", () => {
    if (!objectiveModal || !objectiveMarkdownInput || !objectiveMarkdownPreview || !objectiveInput) return;
    objectiveMarkdownInput.value = objectiveInput.value || "";
    objectiveMarkdownPreview.innerHTML = markdownToHtml(objectiveMarkdownInput.value);
    objectiveModal.show();
    setTimeout(() => objectiveMarkdownInput.focus(), 180);
  });

  objectiveMarkdownInput?.addEventListener("input", () => {
    if (!objectiveMarkdownPreview) return;
    objectiveMarkdownPreview.innerHTML = markdownToHtml(objectiveMarkdownInput.value);
  });

  objectiveApplyButton?.addEventListener("click", () => {
    if (!objectiveInput || !objectiveMarkdownInput) return;
    objectiveInput.value = objectiveMarkdownInput.value || "";
    renderObjectivePreview();
    objectiveModal?.hide();
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
