(function () {
  function createCostumeRoomController(options) {
    const {
      api,
      getSessionId,
      costumeForm,
      costumeGrid,
      costumePreview,
      generateCostumeButton,
      loadContext,
    } = options;

    function render(context) {
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

    function setLoading(active) {
      if (!generateCostumeButton) return;
      generateCostumeButton.disabled = active;
      generateCostumeButton.innerHTML = active
        ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>衣装生成中...'
        : "衣装を生成";
    }

    async function generateCostume() {
      const promptText = costumeForm.prompt_text.value.trim();
      if (!promptText) {
        NovelUI.toast("着替え指示を入力してください。", "warning");
        return;
      }
      setLoading(true);
      try {
        await api.generateCostume(getSessionId(), {
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
        setLoading(false);
      }
    }

    async function selectCostume(event) {
      if (event.target.closest("[data-delete-costume-id]")) return;
      const button = event.target.closest("[data-costume-id]");
      if (!button) return;
      try {
        await api.selectCostume(getSessionId(), button.dataset.costumeId);
        await loadContext();
        NovelUI.toast("衣装の基準画像を変更しました。");
      } catch (error) {
        NovelUI.toast(error.message || "衣装の選択に失敗しました。", "danger");
      }
    }

    function applySettings(settings) {
      if (settings?.default_quality && costumeForm?.quality) {
        costumeForm.quality.value = settings.default_quality;
      }
    }

    function bind() {
      costumeForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        await generateCostume();
      });
      costumeGrid?.addEventListener("click", selectCostume);
      costumePreview?.addEventListener("click", selectCostume);
    }

    return {
      applySettings,
      bind,
      render,
    };
  }

  window.LiveChatCostumeRoom = {
    createCostumeRoomController,
  };
})();
