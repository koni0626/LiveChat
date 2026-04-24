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
  const composeForm = document.getElementById("liveChatComposeForm");
  const composeInput = document.getElementById("liveChatComposeInput");
  const imageForm = document.getElementById("liveChatImageForm");
  const uploadForm = document.getElementById("liveChatImageUploadForm");

  let currentContext = null;
  let giftController = null;

  function getMessageListElement() {
    return document.getElementById("liveChatMessageList");
  }

  function getNovelElements() {
    return {
      novelBox: document.getElementById("liveChatNovelBox"),
      novelSpeaker: document.getElementById("liveChatNovelSpeaker"),
      novelText: document.getElementById("liveChatNovelText"),
      novelContinue: document.getElementById("liveChatNovelContinue"),
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
    getMessageListElement,
    getNovelElements,
    onGiftInteractionChange: (disabled) => giftController?.setInteractionDisabled(disabled),
  });

  function applyContext(context) {
    currentContext = context;
    const title = context.session.title || "ライブ会話";
    document.getElementById("liveChatTitle").textContent = title;
    sessionMetaForm.title.value = context.session.title || "";
    sessionMetaForm.player_name.value = context.session.player_name || "";
    sessionMetaForm.conversation_objective.value = context.session.settings_json?.conversation_objective || "";

    LiveChatApi.loadSessionCharacterOptions(Number(context?.project?.id || projectId || 0))
      .then((list) => {
        sessionCharacterSelect.innerHTML = [
          '<option value="">キャラクターを選択</option>',
          ...list.map((item) => `<option value="${item.id}">${NovelUI.escape(item.name || "Unnamed")}</option>`),
        ].join("");
        const selectedIds = LiveChatView.normalizeSelectedCharacterIds(context.session.settings_json);
        sessionCharacterSelect.value = selectedIds.length ? String(selectedIds[0]) : "";
      })
      .catch((error) => {
        NovelUI.toast(error.message || "キャラクター一覧の読込に失敗しました。", "danger");
      });

    stateBoard.textContent = LiveChatView.formatJson(context.state.state_json || {});
    memoryBoard.textContent = LiveChatView.formatJson((context.state.state_json || {}).session_memory || {});
    imageForm.prompt_text.value = context.state.visual_prompt_text || "";

    shell.renderMessages(context.messages || [], context);
    shell.renderSelectedImage(context.selected_image, context);
    shell.renderImageGrid(context.images || []);
  }

  async function loadContext() {
    const context = await LiveChatApi.loadContext(sessionId);
    applyContext(context);
  }

  async function generateSessionImage(useExistingPrompt = false, mode = "generate") {
    shell.setImageLoading(true, mode);
    try {
      const body = {
        size: imageForm.size.value,
        quality: imageForm.quality.value,
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

  composeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const rawMessage = composeForm.message_text.value.trim();
    try {
      shell.setReplyLoading(true, currentContext);
      if (giftController?.hasSelectedGift()) {
        const uploaded = await giftController.uploadGiftImage(rawMessage);
        if (!uploaded) {
          throw new Error("贈り物画像の送信に失敗しました。");
        }
      } else {
        await LiveChatApi.postMessage(sessionId, {
          message_text: rawMessage || "話を進めて",
          auto_reply: document.getElementById("liveChatAutoReplyCheck").checked,
        });
        await loadContext();
      }
      composeForm.message_text.value = "";
      NovelUI.toast("メッセージを送信しました。");
    } catch (error) {
      NovelUI.toast(error.message || "メッセージ送信に失敗しました。", "danger");
    } finally {
      shell.setReplyLoading(false, currentContext);
    }
  });

  giftController = LiveChatGift.createGiftController({
    giftUploadInput: document.getElementById("liveChatGiftUploadInput"),
    giftDropzone: document.getElementById("liveChatGiftDropzone"),
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

  document.getElementById("liveChatExtractStateButton").addEventListener("click", async () => {
    try {
      const state = await LiveChatApi.extractState(sessionId);
      stateBoard.textContent = LiveChatView.formatJson(state.state_json || {});
      await loadContext();
      NovelUI.toast("表示状態を更新しました。");
    } catch (error) {
      NovelUI.toast(error.message || "表示状態の更新に失敗しました。", "danger");
    }
  });

  document.getElementById("liveChatRefreshContextButton").addEventListener("click", () => {
    loadContext().catch((error) => {
      NovelUI.toast(error.message || "読込に失敗しました。", "danger");
    });
  });

  shell.initialize();

  loadContext().catch((error) => {
    NovelUI.toast(error.message || "ライブ会話画面の初期化に失敗しました。", "danger");
  });

  window.addEventListener("resize", () => {
    if (currentContext) {
      shell.renderSelectedImage(currentContext.selected_image, currentContext);
      shell.renderNovel(currentContext.messages || [], currentContext);
    }
  });
})();
