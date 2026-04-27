(function () {
  function createShellController(options) {
    const {
      view,
      selectedImagePanel,
      toggleMessagesButton,
      toggleTextboxButton,
      sendButton,
      composeInput,
      generateImageButton,
      regenerateImageButton,
      imageLightbox,
      imageLightboxImage,
      imageLightboxClose,
      getMessageListElement,
      getNovelElements,
      onGiftInteractionChange,
    } = options;
    const defaultSendButtonHtml = sendButton ? sendButton.innerHTML : "";

    const state = {
      messagesVisible: false,
      messageSortOrder: "desc",
      messageSearchQuery: "",
      progressDetailsVisible: false,
      textboxVisible: true,
      imageLoading: false,
      replyLoading: false,
      novelPageState: { messageId: null, pages: [], pageIndex: 0 },
      currentContext: null,
      selectedImage: null,
    };

    function renderNovel(messages, currentContext) {
      state.novelPageState = view.renderNovelBox(messages, {
        replyLoading: state.replyLoading,
        currentContext,
        novelPageState: state.novelPageState,
        novelElements: getNovelElements(),
      });
      return state.novelPageState;
    }

    function setReplyLoading(active, currentContext, options = {}) {
      const changed = state.replyLoading !== active;
      state.replyLoading = active;
      const loading = document.getElementById("liveChatReplyLoading");
      if (loading) loading.hidden = !active;
      if (sendButton) {
        sendButton.disabled = active;
        sendButton.innerHTML = defaultSendButtonHtml;
      }
      if (composeInput) composeInput.disabled = active;
      if (typeof onGiftInteractionChange === "function") {
        onGiftInteractionChange(active);
      }
      if (options.render === false || (!changed && !active)) {
        return;
      }
      renderNovel(currentContext?.messages || [], currentContext);
    }

    function setImageLoading(active, mode = "generate") {
      state.imageLoading = active;
      const loadingLabel = mode === "regenerate"
        ? "\u3082\u3046\u4e00\u679a\u3001\u9b45\u305b\u5834\u3092\u4ed5\u7acb\u3066\u4e2d..."
        : (mode === "auto" ? "\u6b21\u306e\u5834\u9762\u3092\u30c9\u30e9\u30de\u30c1\u30c3\u30af\u306b\u64ae\u5f71\u4e2d..." : "\u3068\u3063\u3066\u304a\u304d\u306e\u4e00\u679a\u3092\u751f\u6210\u4e2d...");
      if (generateImageButton) {
        generateImageButton.disabled = active;
        generateImageButton.innerHTML = active
          ? `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${loadingLabel}`
          : "\u753b\u50cf\u3092\u751f\u6210";
      }
      if (regenerateImageButton) {
        regenerateImageButton.disabled = active;
        regenerateImageButton.innerHTML = active && mode === "regenerate"
          ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>\u518d\u751f\u6210\u4e2d...'
          : "\u518d\u751f\u6210";
      }
      const frame = selectedImagePanel?.querySelector(".live-chat-stage-frame");
      if (frame) {
        frame.classList.toggle("is-loading", active);
        if (active) {
          frame.dataset.loadingLabel = loadingLabel;
        } else {
          delete frame.dataset.loadingLabel;
        }
      }
    }

    function setMessagesVisible(visible) {
      state.messagesVisible = visible;
      const panel = document.getElementById("liveChatLogBody");
      if (panel) {
        panel.classList.toggle("is-hidden", !visible);
      }
      if (toggleMessagesButton) {
        toggleMessagesButton.textContent = visible ? "\u30ed\u30b0\u3092\u9589\u3058\u308b" : "\u30ed\u30b0\u3092\u958b\u304f";
        toggleMessagesButton.setAttribute("aria-expanded", visible ? "true" : "false");
      }
      if (state.currentContext) {
        renderMessages(state.currentContext.messages || [], state.currentContext);
      }
    }

    function setProgressDetailsVisible(visible) {
      state.progressDetailsVisible = visible;
      if (state.currentContext) {
        renderSelectedImage(state.selectedImage, state.currentContext);
        renderMessages(state.currentContext.messages || [], state.currentContext);
      }
    }

    function setTextboxVisible(visible) {
      state.textboxVisible = visible;
      const box = document.getElementById("liveChatNovelBox");
      if (box) {
        box.classList.toggle("is-hidden", !visible);
      }
      if (toggleTextboxButton) {
        toggleTextboxButton.textContent = visible ? "\u30c6\u30ad\u30b9\u30c8\u30dc\u30c3\u30af\u30b9\u975e\u8868\u793a" : "\u30c6\u30ad\u30b9\u30c8\u30dc\u30c3\u30af\u30b9\u8868\u793a";
      }
      if (state.currentContext) {
        renderSelectedImage(state.selectedImage, state.currentContext);
        renderMessages(state.currentContext.messages || [], state.currentContext);
      }
    }

    function renderSelectedImage(selectedImage, currentContext) {
      state.selectedImage = selectedImage;
      state.currentContext = currentContext;
      const evaluation = currentContext?.state?.state_json?.conversation_evaluation || null;
      const isRomance = (evaluation?.theme || "general") === "romance";
      const score = Math.max(0, Math.min(100, Number(evaluation?.score || 0)));
      const novelElements = getNovelElements();
      view.renderSelectedImage(selectedImage, {
        selectedImagePanel,
        evaluation,
        isRomance,
        score,
        progressDetailsVisible: state.progressDetailsVisible,
        textboxVisible: state.textboxVisible,
        imageLoading: state.imageLoading,
        replyLoading: state.replyLoading,
        novelSpeakerText: "",
        novelTextValue: "",
      });
    }

    function renderMessages(messages, currentContext) {
      view.renderMessages(messages, getMessageListElement(), {
        sortOrder: state.messageSortOrder,
        searchQuery: state.messageSearchQuery,
      });
      renderNovel(messages, currentContext);
    }

    function renderImageGrid(images) {
      view.renderImageGrid(images, document.getElementById("liveChatImageGrid"));
    }

    function openImageLightbox() {
      if (!imageLightbox || !imageLightboxImage) return;
      const stageImage = selectedImagePanel?.querySelector(".live-chat-stage-image");
      const src = stageImage?.getAttribute("src");
      if (!src) return;
      imageLightboxImage.src = src;
      imageLightbox.classList.remove("is-hidden");
      imageLightbox.setAttribute("aria-hidden", "false");
      document.body.classList.add("live-chat-lightbox-open");
    }

    function closeImageLightbox() {
      if (!imageLightbox || !imageLightboxImage) return;
      imageLightbox.classList.add("is-hidden");
      imageLightbox.setAttribute("aria-hidden", "true");
      imageLightboxImage.removeAttribute("src");
      document.body.classList.remove("live-chat-lightbox-open");
    }

    function advanceNovelPage() {
      const pages = state.novelPageState.pages || [];
      if (!state.textboxVisible || state.novelPageState.pageIndex >= pages.length - 1) {
        return false;
      }
      const novelElements = getNovelElements();
      state.novelPageState.pageIndex += 1;
      state.novelPageState = view.renderNovelPage(
        state.novelPageState,
        novelElements.novelText,
        novelElements.novelContinue,
        novelElements
      );
      return true;
    }

    function retreatNovelPage() {
      const pages = state.novelPageState.pages || [];
      if (!state.textboxVisible || !pages.length || state.novelPageState.pageIndex <= 0) {
        return false;
      }
      const novelElements = getNovelElements();
      state.novelPageState.pageIndex -= 1;
      state.novelPageState = view.renderNovelPage(
        state.novelPageState,
        novelElements.novelText,
        novelElements.novelContinue,
        novelElements
      );
      return true;
    }

    function bindNovelAdvanceEvents() {
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && imageLightbox && !imageLightbox.classList.contains("is-hidden")) {
          closeImageLightbox();
          return;
        }
        if (event.key !== "Enter") return;
        const activeElement = document.activeElement;
        if (activeElement && ["TEXTAREA", "INPUT", "SELECT"].includes(activeElement.tagName)) {
          return;
        }
        if (advanceNovelPage()) {
          event.preventDefault();
        }
      });

      document.addEventListener("click", (event) => {
        if (event.target.closest("#liveChatNovelPrevButton")) {
          retreatNovelPage();
          return;
        }
        if (event.target.closest("#liveChatNovelNextButton")) {
          advanceNovelPage();
          return;
        }
        const novelBox = event.target.closest("#liveChatNovelBox");
        if (!novelBox) return;
        if (event.target.closest("button, a, input, textarea, select, label")) return;
        advanceNovelPage();
      });
    }

    function bindImageLightboxEvents() {
      selectedImagePanel?.addEventListener("click", (event) => {
        const stageImage = event.target.closest(".live-chat-stage-image");
        if (!stageImage) return;
        openImageLightbox();
      });
      imageLightboxClose?.addEventListener("click", closeImageLightbox);
      imageLightbox?.addEventListener("click", (event) => {
        if (event.target === imageLightbox) {
          closeImageLightbox();
        }
      });
    }

    function bindToggleButtons() {
      toggleMessagesButton?.addEventListener("click", () => {
        setMessagesVisible(!state.messagesVisible);
      });
      document.getElementById("liveChatLogSortSelect")?.addEventListener("change", (event) => {
        state.messageSortOrder = event.target.value === "asc" ? "asc" : "desc";
        if (state.currentContext) {
          renderMessages(state.currentContext.messages || [], state.currentContext);
        }
      });
      document.getElementById("liveChatLogSearchInput")?.addEventListener("input", (event) => {
        state.messageSearchQuery = event.target.value || "";
        if (state.currentContext) {
          renderMessages(state.currentContext.messages || [], state.currentContext);
        }
      });
      toggleTextboxButton?.addEventListener("click", () => {
        setTextboxVisible(!state.textboxVisible);
      });
      document.addEventListener("click", (event) => {
        if (!event.target.closest("#liveChatEvalDetailButton")) return;
        setProgressDetailsVisible(!state.progressDetailsVisible);
      });
    }

    function initialize() {
      setMessagesVisible(false);
      setProgressDetailsVisible(false);
      setTextboxVisible(true);
      bindToggleButtons();
      bindNovelAdvanceEvents();
      bindImageLightboxEvents();
    }

    return {
      initialize,
      getState: () => ({ ...state }),
      renderNovel,
      renderSelectedImage,
      renderMessages,
      renderImageGrid,
      setReplyLoading,
      setImageLoading,
      setMessagesVisible,
      setProgressDetailsVisible,
      setTextboxVisible,
    };
  }

  window.LiveChatShell = {
    createShellController,
  };
})();
