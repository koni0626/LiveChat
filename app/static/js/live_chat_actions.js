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

    document.getElementById("liveChatGenerateImageButton")?.addEventListener("click", async () => {
      try {
        await generateSessionImage(false, "generate");
        NovelUI.toast("\u753b\u50cf\u3092\u751f\u6210\u3057\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u753b\u50cf\u751f\u6210\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
    });

    document.getElementById("liveChatRegenerateImageButton")?.addEventListener("click", async () => {
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
      const button = event.target.closest("[data-image-id]");
      if (!button) return;
      try {
        await api.selectImage(getSessionId(), button.dataset.imageId);
        await loadContext();
        NovelUI.toast("\u8868\u793a\u753b\u50cf\u3092\u5207\u308a\u66ff\u3048\u307e\u3057\u305f\u3002");
      } catch (error) {
        NovelUI.toast(error.message || "\u753b\u50cf\u9078\u629e\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002", "danger");
      }
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
