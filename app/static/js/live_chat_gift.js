(function () {
  function createGiftController(options) {
    const {
      giftUploadInput,
      giftDropTarget,
      giftPreview,
      giftPreviewImage,
      giftSelectedNameDisplay,
      giftSelectedName,
      giftClearButton,
      giftSelectButton,
      api,
      getSessionId,
      canInteract,
      onUploaded,
    } = options;

    let selectedGiftFile = null;
    let selectedGiftPreviewUrl = null;

    function syncGiftLabel(text) {
      if (giftSelectedNameDisplay) {
        giftSelectedNameDisplay.textContent = text;
      }
      if (giftSelectedName) {
        giftSelectedName.textContent = text;
      }
    }

    function clearSelectedGiftFile() {
      selectedGiftFile = null;
      if (giftUploadInput) {
        giftUploadInput.value = "";
      }
      if (selectedGiftPreviewUrl) {
        URL.revokeObjectURL(selectedGiftPreviewUrl);
        selectedGiftPreviewUrl = null;
      }
      if (giftPreviewImage) {
        giftPreviewImage.removeAttribute("src");
      }
      if (giftPreview) {
        giftPreview.classList.add("is-hidden");
      }
      if (giftDropTarget) {
        giftDropTarget.classList.remove("is-dragover");
      }
      syncGiftLabel("添付画像はありません。");
    }

    function setSelectedGiftFile(file) {
      if (!file) {
        clearSelectedGiftFile();
        return;
      }
      selectedGiftFile = file;
      if (selectedGiftPreviewUrl) {
        URL.revokeObjectURL(selectedGiftPreviewUrl);
      }
      selectedGiftPreviewUrl = URL.createObjectURL(file);
      if (giftPreviewImage) {
        giftPreviewImage.src = selectedGiftPreviewUrl;
      }
      if (giftPreview) {
        giftPreview.classList.remove("is-hidden");
      }
      syncGiftLabel(file.name || "選択中の画像");
    }

    async function uploadGiftImage(messageText = "") {
      if (!selectedGiftFile) {
        NovelUI.toast("贈り物画像を選んでください。", "warning");
        return false;
      }
      const body = new FormData();
      body.set("file", selectedGiftFile);
      if (messageText && String(messageText).trim()) {
        body.set("message_text", String(messageText).trim());
      }
      try {
        await api.uploadGift(getSessionId(), body);
        clearSelectedGiftFile();
        if (typeof onUploaded === "function") {
          await onUploaded();
        }
        return true;
      } catch (error) {
        NovelUI.toast(error.message || "贈り物画像の送信に失敗しました。", "danger");
        return false;
      }
    }

    function handleFiles(fileList) {
      if (!fileList || !fileList.length) {
        return;
      }
      setSelectedGiftFile(fileList[0]);
    }

    function bindDropTarget() {
      if (!giftDropTarget) {
        return;
      }
      ["dragenter", "dragover"].forEach((eventName) => {
        giftDropTarget.addEventListener(eventName, (event) => {
          event.preventDefault();
          if (!canInteract()) {
            return;
          }
          giftDropTarget.classList.add("is-dragover");
        });
      });
      ["dragleave", "drop"].forEach((eventName) => {
        giftDropTarget.addEventListener(eventName, (event) => {
          event.preventDefault();
          giftDropTarget.classList.remove("is-dragover");
        });
      });
      giftDropTarget.addEventListener("drop", (event) => {
        if (!canInteract()) {
          return;
        }
        handleFiles(event.dataTransfer?.files);
      });
    }

    function bind() {
      giftUploadInput?.addEventListener("change", () => {
        if (!canInteract()) {
          return;
        }
        handleFiles(giftUploadInput.files);
      });
      giftClearButton?.addEventListener("click", clearSelectedGiftFile);
      giftSelectButton?.addEventListener("click", () => {
        if (!canInteract()) {
          return;
        }
        giftUploadInput?.click();
      });
      bindDropTarget();
    }

    function setInteractionDisabled(disabled) {
      if (giftDropTarget) {
        giftDropTarget.classList.toggle("is-disabled", disabled);
      }
      if (giftSelectButton) {
        giftSelectButton.disabled = disabled;
      }
      if (giftClearButton) {
        giftClearButton.disabled = disabled;
      }
    }

    return {
      bind,
      hasSelectedGift: () => Boolean(selectedGiftFile),
      uploadGiftImage,
      clearSelectedGiftFile,
      setInteractionDisabled,
    };
  }

  window.LiveChatGift = {
    createGiftController,
  };
})();
