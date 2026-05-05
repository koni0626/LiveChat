(function () {
  function bindImageActions(options) {
    const {
      api,
      getSessionId,
      imageForm,
      uploadForm,
      imageGrid,
      selectedImagePanel,
      loadContext,
      generateSessionImage,
    } = options;

    let imageClickTimer = null;
    let imageLongPressTimer = null;
    let imageLongPressPointerId = null;
    let imageLongPressStart = null;
    let suppressNextImageClick = false;
    let selectingImage = false;
    const imageLongPressMs = 650;

    function playShutter() {
      window.LiveChatSound?.unlock?.();
      window.LiveChatSound?.play("shutter");
    }

    function isMobilePointer(event) {
      return event?.pointerType === "touch" || event?.pointerType === "pen" || window.matchMedia?.("(max-width: 767.98px)")?.matches;
    }

    function clearImageLongPress() {
      window.clearTimeout(imageLongPressTimer);
      imageLongPressTimer = null;
      imageLongPressPointerId = null;
      imageLongPressStart = null;
      imageGrid?.querySelectorAll(".live-chat-thumb.is-long-pressing").forEach((item) => {
        item.classList.remove("is-long-pressing");
      });
    }

    async function selectGalleryImage(button) {
      const imageId = Number(button?.dataset?.imageId || 0);
      if (!imageId || selectingImage) return;
      selectingImage = true;
      button.classList.add("is-selecting");
      button.disabled = true;
      try {
        await api.selectImage(getSessionId(), imageId);
        await loadContext();
        NovelUI.toast("現在の画像に戻しました。");
      } catch (error) {
        NovelUI.toast(error.message || "現在の画像への変更に失敗しました。", "danger");
      } finally {
        selectingImage = false;
        if (button.isConnected) {
          button.disabled = false;
          button.classList.remove("is-selecting");
        }
      }
    }

    function openGalleryLightbox(button) {
      const src = button.dataset.imageUrl || button.querySelector("img")?.getAttribute("src") || "";
      const lightbox = document.getElementById("liveChatImageLightbox");
      const lightboxImage = document.getElementById("liveChatImageLightboxImage");
      if (src && lightbox && lightboxImage) {
        lightboxImage.src = src;
        lightbox.classList.remove("is-hidden");
        lightbox.setAttribute("aria-hidden", "false");
        document.body.classList.add("live-chat-lightbox-open");
      }
    }

    document.getElementById("liveChatGenerateImageButton")?.addEventListener("click", async () => {
      playShutter();
      try {
        await generateSessionImage(false, "generate");
        NovelUI.toast("\u753b\u50cf\u3092\u751f\u6210\u3057\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u753b\u50cf\u751f\u6210\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
    });

    document.getElementById("liveChatRegenerateImageButton")?.addEventListener("click", async () => {
      playShutter();
      try {
        await generateSessionImage(true, "regenerate");
        NovelUI.toast("\u30d7\u30ed\u30f3\u30d7\u30c8\u3092\u5143\u306b\u753b\u50cf\u3092\u518d\u751f\u6210\u3057\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u753b\u50cf\u306e\u518d\u751f\u6210\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
    });

    uploadForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fileInput = document.getElementById("liveChatImageUploadInput");
      if (!fileInput?.files.length) {
        NovelUI.toast("\u753b\u50cf\u30d5\u30a1\u30a4\u30eb\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044\u3002", "warning");
        return;
      }
      const body = new FormData();
      body.set("file", fileInput.files[0]);
      body.set("prompt_text", imageForm.prompt_text.value);
      body.set("size", imageForm.size.value);
      body.set("quality", "external");
      try {
        await api.uploadImage(getSessionId(), body);
        fileInput.value = "";
        await loadContext();
        NovelUI.toast("\u753b\u50cf\u3092\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9\u3057\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u753b\u50cf\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
    });

    imageGrid?.addEventListener("click", async (event) => {
      if (event.target.closest(".live-chat-thumb-download")) return;
      const button = event.target.closest("[data-image-id]");
      if (!button) return;
      if (suppressNextImageClick) {
        suppressNextImageClick = false;
        return;
      }
      window.clearTimeout(imageClickTimer);
      imageClickTimer = window.setTimeout(() => openGalleryLightbox(button), 220);
    });

    imageGrid?.addEventListener("dblclick", async (event) => {
      if (event.target.closest(".live-chat-thumb-download")) return;
      const button = event.target.closest("[data-image-id]");
      if (!button) return;
      event.preventDefault();
      window.clearTimeout(imageClickTimer);
      await selectGalleryImage(button);
    });

    imageGrid?.addEventListener("pointerdown", (event) => {
      if (!isMobilePointer(event) || event.target.closest(".live-chat-thumb-download")) return;
      const button = event.target.closest("[data-image-id]");
      if (!button) return;
      clearImageLongPress();
      imageLongPressPointerId = event.pointerId;
      imageLongPressStart = { x: event.clientX, y: event.clientY };
      button.classList.add("is-long-pressing");
      button.setPointerCapture?.(event.pointerId);
      imageLongPressTimer = window.setTimeout(async () => {
        suppressNextImageClick = true;
        clearImageLongPress();
        await selectGalleryImage(button);
        window.setTimeout(() => {
          suppressNextImageClick = false;
        }, 420);
      }, imageLongPressMs);
    });

    imageGrid?.addEventListener("pointermove", (event) => {
      if (imageLongPressPointerId !== event.pointerId || !imageLongPressStart) return;
      const deltaX = Math.abs(event.clientX - imageLongPressStart.x);
      const deltaY = Math.abs(event.clientY - imageLongPressStart.y);
      if (deltaX > 12 || deltaY > 12) clearImageLongPress();
    });

    ["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
      imageGrid?.addEventListener(eventName, (event) => {
        if (imageLongPressPointerId === event.pointerId) clearImageLongPress();
      });
    });

    const handleMessageDelete = async (event) => {
      const button = event.target.closest("[data-delete-message-id]");
      if (!button) return;
      const messageId = Number(button.dataset.deleteMessageId);
      if (!messageId || !window.confirm("\u3053\u306e\u30ed\u30b0\u3092\u524a\u9664\u3057\u307e\u3059\u304b\uff1f")) return;
      try {
        await api.deleteMessage(getSessionId(), messageId);
        await loadContext();
        NovelUI.toast("\u30ed\u30b0\u3092\u524a\u9664\u3057\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u30ed\u30b0\u306e\u524a\u9664\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
    };

    selectedImagePanel?.addEventListener("click", handleMessageDelete);
    document.getElementById("liveChatMessageList")?.addEventListener("click", handleMessageDelete);

    document.getElementById("liveChatReloadImagesButton")?.addEventListener("click", () => {
      loadContext().catch((error) => {
        NovelUI.toast(error.message || "\u753b\u50cf\u4e00\u89a7\u306e\u518d\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      });
    });
  }

  window.LiveChatActions = {
    bindImageActions,
  };
})();
