(function () {
  function createInventoryController(options = {}) {
    const {
      api,
      projectId,
      sessionId,
      shell,
      selectedImagePanel,
      getCurrentContext,
      getTargetCharacterId,
      loadContext,
      isInteractionLocked,
      playAffinityFeedback,
      getImageGenerationOptions,
    } = options;

    const panel = document.getElementById("liveChatInventoryPanel");
    const list = document.getElementById("liveChatInventoryList");
    const toggleButton = document.getElementById("liveChatToggleInventoryButton");
    const closeButton = document.getElementById("liveChatInventoryCloseButton");
    const generateButton = document.getElementById("liveChatInventoryGenerateButton");
    const promptInput = document.getElementById("liveChatInventoryPromptInput");
    const modal = document.getElementById("liveChatInventoryModal");
    const modalBackdrop = document.getElementById("liveChatInventoryModalBackdrop");
    const modalCloseButton = document.getElementById("liveChatInventoryModalClose");
    const modalImage = document.getElementById("liveChatInventoryModalImage");
    const modalFallback = document.getElementById("liveChatInventoryModalFallback");
    const modalTitle = document.getElementById("liveChatInventoryModalTitle");
    const modalDescription = document.getElementById("liveChatInventoryModalDescription");

    let visible = false;
    let busy = false;
    let items = [];
    let activeModalItemId = null;
    let draggingInventoryItem = false;
    let longPressState = null;
    let suppressNextItemClick = false;
    let mobileGiftPendingItemId = null;
    const longPressDelayMs = 620;
    const longPressMoveTolerance = 12;

    function getItemImageUrl(item) {
      return item?.asset?.media_url || item?.image_asset?.media_url || item?.media_url || item?.image_url || "";
    }

    function getItemDescription(item) {
      return item?.description || item?.summary || item?.prompt || item?.name || "説明はまだありません。";
    }

    function setModalVisible(nextVisible) {
      if (!modal) return;
      modal.classList.toggle("is-hidden", !nextVisible);
      modal.setAttribute("aria-hidden", nextVisible ? "false" : "true");
      document.body.classList.toggle("live-chat-inventory-modal-open", nextVisible);
      if (!nextVisible) activeModalItemId = null;
    }

    function openItemModal(itemId) {
      const item = items.find((entry) => Number(entry.id) === Number(itemId));
      if (!item || !modal) return;
      const imageUrl = getItemImageUrl(item);
      activeModalItemId = item.id;
      if (modalTitle) modalTitle.textContent = item.name || "Item";
      if (modalDescription) modalDescription.textContent = getItemDescription(item);
      if (modalImage) {
        modalImage.alt = item.name || "Inventory item";
        modalImage.src = imageUrl || "";
        modalImage.classList.toggle("is-hidden", !imageUrl);
      }
      modalFallback?.classList.toggle("is-hidden", Boolean(imageUrl));
      setModalVisible(true);
      window.requestAnimationFrame(() => modalCloseButton?.focus());
    }

    function closeItemModal() {
      if (!modal || modal.classList.contains("is-hidden")) return;
      const itemId = activeModalItemId;
      setModalVisible(false);
      const activeButton = list?.querySelector(`[data-inventory-item-id="${itemId}"]`);
      activeButton?.focus();
    }

    function setVisible(nextVisible) {
      visible = Boolean(nextVisible);
      render();
      if (visible) {
        loadItems();
      }
    }

    function render() {
      if (!panel || !list) return;
      panel.classList.toggle("is-hidden", !visible);
      toggleButton?.setAttribute("aria-expanded", visible ? "true" : "false");
      toggleButton?.classList.toggle("is-active", visible);
      if (!visible) return;
      if (busy) {
        list.innerHTML = '<div class="live-chat-inventory-empty">Loading...</div>';
        return;
      }
      if (!items.length) {
        list.innerHTML = '<div class="live-chat-inventory-empty">アイテムがありません。生成してからステージ画像へドラッグしてください。スマホでは長押しで渡せます。</div>';
        return;
      }
      list.innerHTML = items.map((item) => {
        const imageUrl = getItemImageUrl(item);
        const isMobileGifting = Number(mobileGiftPendingItemId || 0) === Number(item.id);
        return `
          <button class="live-chat-inventory-item${isMobileGifting ? " is-gifting" : ""}" type="button" draggable="${isMobileGifting ? "false" : "true"}" data-inventory-item-id="${item.id}" title="${NovelUI.escape(item.description || item.name || "")}" ${isMobileGifting ? "disabled" : ""}>
            ${isMobileGifting
              ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span><span>プレゼント中...</span>'
              : `${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="${NovelUI.escape(item.name || "item")}">` : '<i class="bi bi-gift"></i>'}<span>${NovelUI.escape(item.name || "Item")}</span>`}
          </button>
        `;
      }).join("");
    }

    async function loadItems() {
      if (!projectId) return;
      busy = true;
      render();
      try {
        const payload = await api.loadInventory(projectId);
        items = Array.isArray(payload?.items) ? payload.items : [];
      } catch (error) {
        NovelUI.toast(error.message || "インベントリーを読み込めませんでした。", "warning");
      } finally {
        busy = false;
        render();
      }
    }

    async function generateItem() {
      if (!projectId || busy) return;
      busy = true;
      if (generateButton) generateButton.disabled = true;
      render();
      try {
        const prompt = promptInput?.value?.trim() || "";
        const body = {
          session_id: sessionId,
          character_id: getTargetCharacterId?.(),
          ...getImageGenerationOptions?.(),
          size: "1024x1024",
        };
        if (prompt) body.prompt = prompt;
        const result = await api.generateInventoryItem(projectId, body);
        if (result?.points?.balance !== undefined) NovelUI.setPointsBalance(result.points.balance);
        if (result?.item) items = [result.item, ...items.filter((item) => item.id !== result.item.id)];
        window.LiveChatSound?.play("itemDone");
        NovelUI.toast("アイテムを生成しました。");
      } catch (error) {
        NovelUI.toast(error.message || "アイテム生成に失敗しました。", "danger");
      } finally {
        busy = false;
        if (generateButton) generateButton.disabled = false;
        render();
      }
    }

    async function giveItem(itemId, options = {}) {
      if (!itemId || shell?.getState?.().replyLoading) return;
      const isMobileLongPress = Boolean(options.mobileLongPress);
      const item = items.find((entry) => Number(entry.id) === Number(itemId));
      if (isMobileLongPress) {
        mobileGiftPendingItemId = Number(itemId);
        closeItemModal();
        render();
      }
      shell?.setReplyLoading(true, getCurrentContext?.());
      try {
        const result = await api.giveInventoryItem(sessionId, itemId, {
          character_id: getTargetCharacterId?.(),
          ...getImageGenerationOptions?.(),
          message_text: item?.name ? `${item.name}を渡した。` : "アイテムを渡した。",
        });
        if (isInteractionLocked?.()) return;
        playAffinityFeedback?.(result?.affinity_feedback);
        items = items.filter((entry) => Number(entry.id) !== Number(itemId));
        NovelUI.toast("アイテムを渡しました。");
        await loadContext?.();
        if (isMobileLongPress) {
          setVisible(false);
        }
      } catch (error) {
        NovelUI.toast(error.message || "アイテムを渡せませんでした。", "danger");
      } finally {
        if (isMobileLongPress) {
          mobileGiftPendingItemId = null;
        }
        if (!isInteractionLocked?.()) {
          shell?.setReplyLoading(false, getCurrentContext?.());
          render();
        }
      }
    }

    function clearLongPressState() {
      if (longPressState?.timerId) {
        window.clearTimeout(longPressState.timerId);
      }
      longPressState?.button?.classList.remove("is-long-pressing");
      longPressState = null;
    }

    function isTouchLikePointer(event) {
      return event.pointerType === "touch" || event.pointerType === "pen";
    }

    function beginItemLongPress(event) {
      const itemButton = event.target.closest("[data-inventory-item-id]");
      if (!itemButton || !isTouchLikePointer(event) || event.button > 0) return;
      clearLongPressState();
      const itemId = Number(itemButton.dataset.inventoryItemId || 0);
      if (!itemId) return;
      longPressState = {
        itemId,
        button: itemButton,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        timerId: window.setTimeout(async () => {
          const state = longPressState;
          if (!state || state.itemId !== itemId) return;
          suppressNextItemClick = true;
          draggingInventoryItem = false;
          itemButton.classList.remove("is-long-pressing");
          itemButton.releasePointerCapture?.(event.pointerId);
          longPressState = null;
          await giveItem(itemId, { mobileLongPress: true });
          window.setTimeout(() => {
            suppressNextItemClick = false;
          }, 360);
        }, longPressDelayMs),
      };
      itemButton.classList.add("is-long-pressing");
      itemButton.setPointerCapture?.(event.pointerId);
    }

    function moveItemLongPress(event) {
      if (!longPressState || longPressState.pointerId !== event.pointerId) return;
      const deltaX = Math.abs(event.clientX - longPressState.startX);
      const deltaY = Math.abs(event.clientY - longPressState.startY);
      if (deltaX > longPressMoveTolerance || deltaY > longPressMoveTolerance) {
        clearLongPressState();
      }
    }

    function bind() {
      toggleButton?.addEventListener("click", (event) => {
        event.stopPropagation();
        setVisible(!visible);
      });

      panel?.addEventListener("click", (event) => {
        if (event.target.closest("#liveChatInventoryCloseButton")) {
          event.preventDefault();
          event.stopPropagation();
          setVisible(false);
          return;
        }
        event.stopPropagation();
      });

      closeButton?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        setVisible(false);
      });

      generateButton?.addEventListener("click", generateItem);

      list?.addEventListener("click", (event) => {
        if (draggingInventoryItem || suppressNextItemClick) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        const itemButton = event.target.closest("[data-inventory-item-id]");
        if (!itemButton) return;
        event.preventDefault();
        openItemModal(itemButton.dataset.inventoryItemId);
      });

      list?.addEventListener("pointerdown", beginItemLongPress);
      list?.addEventListener("pointermove", moveItemLongPress);
      list?.addEventListener("pointerup", () => clearLongPressState());
      list?.addEventListener("pointercancel", () => clearLongPressState());
      list?.addEventListener("pointerleave", () => clearLongPressState());
      list?.addEventListener("contextmenu", (event) => {
        if (!event.target.closest("[data-inventory-item-id]") || !(window.navigator?.maxTouchPoints || 0)) return;
        event.preventDefault();
      });

      modalBackdrop?.addEventListener("click", closeItemModal);
      modalCloseButton?.addEventListener("click", closeItemModal);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeItemModal();
      });

      list?.addEventListener("dragstart", (event) => {
        const itemButton = event.target.closest("[data-inventory-item-id]");
        if (!itemButton) return;
        draggingInventoryItem = true;
        event.dataTransfer.setData("text/plain", itemButton.dataset.inventoryItemId);
        event.dataTransfer.effectAllowed = "move";
      });

      list?.addEventListener("dragend", () => {
        window.setTimeout(() => {
          draggingInventoryItem = false;
        }, 0);
      });

      selectedImagePanel?.addEventListener("dragover", (event) => {
        if (!event.dataTransfer.types.includes("text/plain")) return;
        event.preventDefault();
        selectedImagePanel.classList.add("is-inventory-dragover");
      });

      selectedImagePanel?.addEventListener("dragleave", () => {
        selectedImagePanel.classList.remove("is-inventory-dragover");
      });

      selectedImagePanel?.addEventListener("drop", async (event) => {
        const itemId = Number(event.dataTransfer.getData("text/plain") || 0);
        if (!itemId) return;
        event.preventDefault();
        selectedImagePanel.classList.remove("is-inventory-dragover");
        await giveItem(itemId);
        draggingInventoryItem = false;
      });
    }

    return {
      bind,
      render,
      loadItems,
      setVisible,
    };
  }

  window.LiveChatInventory = {
    createInventoryController,
  };
})();
