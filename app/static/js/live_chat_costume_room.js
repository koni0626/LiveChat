(function () {
  function createCostumeRoomController(options) {
    const {
      api,
      getSessionId,
      costumeForm,
      costumeGrid,
      costumePreview,
      generateCostumeButton,
      closetSelectButton,
      closetSelectModalElement,
      closetPicker,
      loadContext,
    } = options;

    const closetSelectModal = closetSelectModalElement ? new bootstrap.Modal(closetSelectModalElement) : null;
    if (closetSelectModalElement) {
      document.body.appendChild(closetSelectModalElement);
    }

    function render(context) {
      const costumes = context?.costumes || [];
      const selectedCostume = context?.selected_costume || costumes.find((item) => item.is_selected) || costumes[0] || null;
      const closetPayload = context?.closet_outfits || {};
      const closetLocked = Boolean(closetPayload.locked);
      const closetOutfits = Array.isArray(closetPayload.outfits) ? closetPayload.outfits : [];
      const selectedOutfit = closetOutfits.find((outfit) => outfit.is_selected_for_session) || null;
      const selectedMediaUrl = selectedOutfit?.thumbnail_asset?.media_url
        || selectedOutfit?.asset?.media_url
        || selectedCostume?.asset?.media_url
        || "";
      const selectedLabel = selectedOutfit?.name
        || (selectedCostume?.image_type === "costume_initial" ? "基準画像" : "選択中");

      closetSelectButton?.setAttribute("hidden", "hidden");

      if (costumePreview) {
        costumePreview.classList.toggle("is-clear-unlocked", !closetLocked);
        if (closetLocked) {
          costumePreview.innerHTML = `
            <div class="live-chat-costume-slider is-locked">
              ${selectedMediaUrl ? `<img src="${NovelUI.escape(selectedMediaUrl)}" alt="costume reference">` : '<i class="bi bi-lock-fill" aria-hidden="true"></i>'}
              <div class="live-chat-costume-lock-label">好感度100で開放</div>
            </div>
          `;
        } else {
          costumePreview.innerHTML = `
            <button class="live-chat-costume-preview-button" type="button" data-open-closet-picker="true">
              ${selectedMediaUrl ? `<img src="${NovelUI.escape(selectedMediaUrl)}" alt="${NovelUI.escape(selectedLabel || "costume")}">` : "<span>No Image</span>"}
              <span class="live-chat-costume-card-label">${NovelUI.escape(selectedLabel || "選択中")}</span>
              <small>クリックして作成済み衣装から選択</small>
            </button>
          `;
        }
      }

      if (!costumeGrid || costumeGrid.hidden) return;
      if (!costumes.length) {
        costumeGrid.innerHTML = '<div class="empty-panel">衣装候補がありません。</div>';
        return;
      }
      costumeGrid.innerHTML = costumes.map((item) => {
        const mediaUrl = item.asset?.media_url;
        const label = item.image_type === "costume_initial" ? "初期衣装" : "衣装";
        return `
          <div class="live-chat-costume-card ${item.is_selected ? "selected" : ""}">
            <button class="live-chat-costume-select" type="button" data-costume-id="${NovelUI.escape(item.id)}">
              ${mediaUrl ? `<img src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(label)}">` : "<span>No Image</span>"}
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

    function renderClosetPicker(payload) {
      if (!closetPicker) return;
      const outfits = payload?.outfits || [];
      if (payload?.locked) {
        closetPicker.innerHTML = '<div class="empty-panel">クローゼット選択は好感度100で開放されます。</div>';
        return;
      }
      if (!outfits.length) {
        closetPicker.innerHTML = '<div class="empty-panel">このキャラクターのクローゼット衣装がありません。</div>';
        return;
      }
      closetPicker.innerHTML = outfits.map((outfit) => {
        const mediaUrl = outfit.thumbnail_asset?.media_url || outfit.asset?.media_url || "";
        const tags = Array.isArray(outfit.tags) ? outfit.tags.slice(0, 3) : [];
        return `
          <article class="live-chat-closet-card ${outfit.is_selected_for_session ? "selected" : ""}"
            role="button"
            tabindex="0"
            data-closet-outfit-id="${NovelUI.escape(outfit.id)}"
            aria-label="${NovelUI.escape(outfit.name || "costume")}">
            <div class="live-chat-closet-image">
              ${mediaUrl ? `<img src="${NovelUI.escape(mediaUrl)}" alt="">` : "<span>No Image</span>"}
              ${outfit.is_selected_for_session ? '<span class="live-chat-closet-selected">選択中</span>' : ""}
            </div>
            <div class="live-chat-closet-body">
              <div class="live-chat-closet-meta">
                <span>${NovelUI.escape(outfit.usage_scene || "outfit")}</span>
              </div>
              <h4>${NovelUI.escape(outfit.name || "衣装")}</h4>
              <details>
                <summary>説明</summary>
                <p>${NovelUI.escape(outfit.description || "説明はありません。")}</p>
              </details>
              <div class="live-chat-closet-tags">
                ${tags.map((tag) => `<span>${NovelUI.escape(tag)}</span>`).join("")}
              </div>
            </div>
          </article>
        `;
      }).join("");
    }

    async function openClosetPicker() {
      if (!closetSelectModal || !closetPicker) return;
      closetPicker.innerHTML = '<div class="empty-panel"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>クローゼット衣装を読み込み中です。</div>';
      closetSelectModal.show();
      try {
        renderClosetPicker(await api.loadClosetOutfits(getSessionId()));
      } catch (error) {
        closetPicker.innerHTML = '<div class="empty-panel">クローゼット衣装を読み込めませんでした。</div>';
        NovelUI.toast(error.message || "クローゼット衣装の読み込みに失敗しました。", "danger");
      }
    }

    async function selectClosetOutfit(button) {
      if (!button) return;
      if (button.classList.contains("selected") || button.dataset.loading === "true") return;
      button.dataset.loading = "true";
      button.classList.add("is-loading");
      try {
        await api.selectClosetOutfit(getSessionId(), button.dataset.closetOutfitId);
        await loadContext();
        renderClosetPicker(await api.loadClosetOutfits(getSessionId()));
        NovelUI.toast("クローゼット衣装をこのルームの基準にしました。");
      } catch (error) {
        delete button.dataset.loading;
        button.classList.remove("is-loading");
        NovelUI.toast(error.message || "クローゼット衣装の選択に失敗しました。", "danger");
      }
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
      if (event.target.closest("[data-open-closet-picker]")) {
        await openClosetPicker();
        return;
      }
      const closetButton = event.target.closest("[data-closet-outfit-id]");
      if (closetButton) {
        await selectClosetOutfit(closetButton);
        return;
      }
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
      if (costumeGrid && !costumeGrid.hidden) {
        costumeGrid.addEventListener("click", selectCostume);
      }
      costumePreview?.addEventListener("click", selectCostume);
      closetSelectButton?.addEventListener("click", openClosetPicker);
      closetPicker?.addEventListener("click", (event) => selectClosetOutfit(event.target.closest("[data-closet-outfit-id]")));
      closetPicker?.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const card = event.target.closest("[data-closet-outfit-id]");
        if (!card) return;
        event.preventDefault();
        selectClosetOutfit(card);
      });
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
