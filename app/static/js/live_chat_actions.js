(function () {
  function bindSessionMetaForm(options) {
    const {
      sessionMetaForm,
      sessionCharacterSelect,
      api,
      getSessionId,
      getCurrentContext,
      applyContext,
      generateSessionImage,
    } = options;

    sessionMetaForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const updated = await api.updateSession(getSessionId(), {
          title: sessionMetaForm.title.value,
          player_name: sessionMetaForm.player_name.value,
          settings_json: {
            ...((getCurrentContext()?.session?.settings_json) || {}),
            conversation_objective: sessionMetaForm.conversation_objective.value,
            selected_character_ids: sessionCharacterSelect.value ? [Number(sessionCharacterSelect.value)] : [],
          },
        });
        applyContext(updated);
        await generateSessionImage(false, "generate");
        NovelUI.toast("セッション設定を保存し、画像を生成しました。");
      } catch (error) {
        NovelUI.toast(error.message || "セッション設定の保存に失敗しました。", "danger");
      }
    });
  }

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

    document.getElementById("liveChatGenerateImageButton").addEventListener("click", async () => {
      try {
        await generateSessionImage(false, "generate");
        NovelUI.toast("画像を生成しました。");
      } catch (error) {
        NovelUI.toast(error.message || "画像生成に失敗しました。", "danger");
      }
    });

    document.getElementById("liveChatRegenerateImageButton").addEventListener("click", async () => {
      try {
        await generateSessionImage(true, "regenerate");
        NovelUI.toast("プロンプトを元に画像を再生成しました。");
      } catch (error) {
        NovelUI.toast(error.message || "画像の再生成に失敗しました。", "danger");
      }
    });

    uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fileInput = document.getElementById("liveChatImageUploadInput");
      if (!fileInput.files.length) {
        NovelUI.toast("画像ファイルを選択してください。", "warning");
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
        NovelUI.toast("画像をアップロードしました。");
      } catch (error) {
        NovelUI.toast(error.message || "画像アップロードに失敗しました。", "danger");
      }
    });

    imageGrid.addEventListener("click", async (event) => {
      if (event.target.closest("[data-reference-image-id]")) {
        return;
      }
      const button = event.target.closest("[data-image-id]");
      if (!button) return;
      try {
        await api.selectImage(getSessionId(), button.dataset.imageId);
        await loadContext();
        NovelUI.toast("表示画像を切り替えました。");
      } catch (error) {
        NovelUI.toast(error.message || "画像選択に失敗しました。", "danger");
      }
    });

    imageGrid.addEventListener("change", async (event) => {
      const checkbox = event.target.closest("[data-reference-image-id]");
      if (!checkbox) return;
      try {
        await api.setReferenceImage(getSessionId(), checkbox.dataset.referenceImageId, checkbox.checked);
        await loadContext();
        NovelUI.toast(checkbox.checked ? "基準画像に追加しました。" : "基準画像から外しました。");
      } catch (error) {
        checkbox.checked = !checkbox.checked;
        NovelUI.toast(error.message || "基準画像の更新に失敗しました。", "danger");
      }
    });

    selectedImagePanel.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-delete-message-id]");
      if (!button) return;
      const messageId = Number(button.dataset.deleteMessageId);
      if (!messageId || !window.confirm("このログを削除しますか？")) return;
      try {
        await api.deleteMessage(getSessionId(), messageId);
        await loadContext();
        NovelUI.toast("ログを削除しました。");
      } catch (error) {
        NovelUI.toast(error.message || "ログの削除に失敗しました。", "danger");
      }
    });

    document.getElementById("liveChatReloadImagesButton").addEventListener("click", () => {
      loadContext().catch((error) => {
        NovelUI.toast(error.message || "画像一覧の再読込に失敗しました。", "danger");
      });
    });
  }

  window.LiveChatActions = {
    bindSessionMetaForm,
    bindImageActions,
  };
})();
