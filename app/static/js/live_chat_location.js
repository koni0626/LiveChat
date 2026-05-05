(function () {
  function createLocationController(options = {}) {
    const {
      api,
      sessionId,
      shell,
      imageForm,
      getCurrentContext,
      applyContext,
      loadContext,
      isInteractionLocked,
      capturePlayerReaction,
    } = options;

    const movePanel = document.getElementById("liveChatLocationMovePanel");
    const servicePanel = document.getElementById("liveChatLocationServicePanel");
    const toggleMoveButton = document.getElementById("liveChatToggleLocationMoveButton");

    let moveVisible = false;
    let selectedMoveId = null;
    let moveBusy = false;
    let serviceBusy = false;

    function currentLocationId(context) {
      const location = context?.state?.state_json?.current_location;
      return Number(location?.id || 0);
    }

    function locationServicesForLocation(location) {
      return (Array.isArray(location?.services) ? location.services : []).filter((item) => item && item.status !== "archived");
    }

    function renderServicePanel() {
      if (!servicePanel) return;
      servicePanel.classList.add("is-hidden");
      servicePanel.innerHTML = "";
    }

    function close() {
      if (!moveVisible) return;
      moveVisible = false;
      selectedMoveId = null;
      renderMovePanel(getCurrentContext?.());
      renderServicePanel();
    }

    function renderMovePanel(context = getCurrentContext?.()) {
      if (!movePanel) return;
      const locations = Array.isArray(context?.world_map?.locations) ? context.world_map.locations : [];
      movePanel.classList.toggle("is-hidden", !moveVisible);
      toggleMoveButton?.setAttribute("aria-expanded", moveVisible ? "true" : "false");
      if (!moveVisible) return;
      if (!locations.length) {
        movePanel.innerHTML = '<div class="empty-panel">登録済みの施設がありません。ワールドマップで施設を追加すると、ここに移動先として表示されます。</div>';
        return;
      }
      const activeId = currentLocationId(context);
      const selectedId = Number(selectedMoveId || 0);
      movePanel.innerHTML = `
        <div class="live-chat-location-head">
          <div>
            <div class="eyebrow">Move</div>
            <h4>どこへ移動する？</h4>
          </div>
          <button class="btn btn-sm btn-outline-dark" type="button" data-location-move-close>閉じる</button>
        </div>
        <div class="live-chat-location-grid">
          ${locations.map((location) => {
            const isActive = Number(location.id) === activeId;
            const isSelected = Number(location.id) === selectedId;
            const services = locationServicesForLocation(location);
            const meta = [location.region, location.location_type, location.owner_character_name ? `${location.owner_character_name}関連` : ""]
              .filter(Boolean)
              .join(" / ");
            return `
              <div class="live-chat-location-entry${isSelected ? " is-selected" : ""}">
                <button class="live-chat-location-card${isActive ? " is-active" : ""}${isSelected ? " is-selected" : ""}" type="button" data-location-select-id="${location.id}" ${moveBusy || serviceBusy ? "disabled" : ""}>
                  <span class="live-chat-location-card-title">${NovelUI.escape(location.name || "名称未設定")}</span>
                  <span class="live-chat-location-card-meta">${NovelUI.escape(meta || "施設")}</span>
                  <span class="live-chat-location-card-desc">${NovelUI.escape(NovelUI.truncateText(location.description || "説明未設定", 120))}</span>
                  ${isActive ? '<span class="live-chat-location-card-current">現在地</span>' : ""}
                  <span class="live-chat-location-card-next">${isSelected ? "行き先を選択中" : "行き先を開く"}</span>
                </button>
                ${isSelected ? `
                  <div class="live-chat-location-destinations">
                    <div class="live-chat-location-destinations-title">${NovelUI.escape(location.name || "施設")}のどこへ行く？</div>
                    <button class="live-chat-location-destination-button" type="button" data-location-move-final-id="${location.id}" ${moveBusy ? "disabled" : ""}>
                      <span>施設全体へ移動</span>
                      <small>入口・広場・全体の雰囲気で移動する</small>
                    </button>
                    ${services.length ? services.map((service) => `
                      <button class="live-chat-location-destination-button" type="button" data-location-service-id="${service.id}" ${serviceBusy ? "disabled" : ""}>
                        <span>${NovelUI.escape(service.name || "行き先")}</span>
                        <small>${NovelUI.escape(service.service_type || "施設内")}</small>
                        ${service.summary ? `<em>${NovelUI.escape(NovelUI.truncateText(service.summary, 78))}</em>` : ""}
                      </button>
                    `).join("") : '<div class="live-chat-location-destination-empty">施設内の行き先はまだありません。</div>'}
                  </div>
                ` : ""}
              </div>
            `;
          }).join("")}
        </div>
      `;
    }

    async function moveToLocation(locationId, button = null) {
      if (!locationId || moveBusy) return;
      moveBusy = true;
      const originalHtml = button?.innerHTML;
      if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>移動中...';
      }
      shell?.setImageLoading(true, "auto");
      try {
        const result = await api.moveToLocation(sessionId, locationId, {
          size: imageForm?.size?.value || "1536x1024",
          quality: imageForm?.quality?.value || "low",
        });
        if (isInteractionLocked?.()) return;
        if (result?.context) {
          applyContext?.(result.context);
        } else {
          await loadContext?.();
        }
        moveVisible = false;
        selectedMoveId = null;
        window.LiveChatSound?.play("move");
        if (!isInteractionLocked?.()) await capturePlayerReaction?.();
        if (result?.image_generation_error) {
          NovelUI.toast(`移動しました。画像生成は失敗しました: ${result.image_generation_error}`, "warning");
        } else {
          NovelUI.toast("移動しました。");
        }
      } catch (error) {
        NovelUI.toast(error.message || "移動に失敗しました。", "danger");
        if (!isInteractionLocked?.()) await loadContext?.().catch?.(() => {});
      } finally {
        moveBusy = false;
        if (!isInteractionLocked?.() && button && originalHtml) {
          button.innerHTML = originalHtml;
          button.disabled = false;
        }
        if (!isInteractionLocked?.()) {
          shell?.setImageLoading(false, "auto");
          renderMovePanel(getCurrentContext?.());
          renderServicePanel();
        }
      }
    }

    async function selectService(serviceId, button = null) {
      if (!serviceId || serviceBusy) return;
      serviceBusy = true;
      const originalHtml = button?.innerHTML;
      if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>移動中...';
      }
      shell?.setImageLoading(true, "auto");
      try {
        const result = await api.selectLocationService(sessionId, serviceId, {
          size: imageForm?.size?.value || "1536x1024",
          quality: imageForm?.quality?.value || "low",
        });
        if (isInteractionLocked?.()) return;
        if (result?.context) {
          applyContext?.(result.context);
        } else {
          await loadContext?.();
        }
        moveVisible = false;
        selectedMoveId = null;
        window.LiveChatSound?.play("move");
        if (!isInteractionLocked?.()) await capturePlayerReaction?.();
        if (result?.image_generation_error) {
          NovelUI.toast(`サービスへ移動しました。画像生成は失敗しました: ${result.image_generation_error}`, "warning");
        } else {
          NovelUI.toast("サービスへ移動しました。");
        }
      } catch (error) {
        NovelUI.toast(error.message || "サービス移動に失敗しました。", "danger");
        if (!isInteractionLocked?.()) await loadContext?.().catch?.(() => {});
      } finally {
        serviceBusy = false;
        if (!isInteractionLocked?.() && button && originalHtml) {
          button.innerHTML = originalHtml;
          button.disabled = false;
        }
        if (!isInteractionLocked?.()) {
          shell?.setImageLoading(false, "auto");
          renderMovePanel(getCurrentContext?.());
          renderServicePanel();
        }
      }
    }

    function bind() {
      toggleMoveButton?.addEventListener("click", () => {
        moveVisible = !moveVisible;
        if (!moveVisible) selectedMoveId = null;
        renderMovePanel(getCurrentContext?.());
        renderServicePanel();
      });

      movePanel?.addEventListener("click", async (event) => {
        event.stopPropagation();
        const closeButton = event.target.closest("[data-location-move-close]");
        if (closeButton) {
          moveVisible = false;
          selectedMoveId = null;
          renderMovePanel(getCurrentContext?.());
          renderServicePanel();
          return;
        }
        const selectButton = event.target.closest("[data-location-select-id]");
        if (selectButton) {
          const id = Number(selectButton.dataset.locationSelectId || 0);
          selectedMoveId = selectedMoveId === id ? null : id;
          renderMovePanel(getCurrentContext?.());
          renderServicePanel();
          return;
        }
        const finalButton = event.target.closest("[data-location-move-final-id]");
        if (finalButton) {
          await moveToLocation(Number(finalButton.dataset.locationMoveFinalId || 0), finalButton);
          return;
        }
        const serviceButton = event.target.closest("[data-location-service-id]");
        if (serviceButton) {
          await selectService(Number(serviceButton.dataset.locationServiceId || 0), serviceButton);
        }
      });

      servicePanel?.addEventListener("click", async (event) => {
        event.stopPropagation();
        const button = event.target.closest("[data-location-service-id]");
        if (!button) return;
        await selectService(Number(button.dataset.locationServiceId || 0), button);
      });

      document.addEventListener("click", (event) => {
        if (!moveVisible) return;
        const target = event.target;
        if (movePanel?.contains(target) || toggleMoveButton?.contains(target)) return;
        close();
      });
    }

    return {
      bind,
      close,
      renderMovePanel,
      renderServicePanel,
    };
  }

  window.LiveChatLocation = {
    createLocationController,
  };
})();
