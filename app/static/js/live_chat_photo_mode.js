(function () {
  function createPhotoModeController(options = {}) {
    const {
      api,
      sessionId,
      shell,
      imageForm,
      iconHtml,
      getReward,
      applyContext,
      loadContext,
      isInteractionLocked,
      onDeactivateConversation,
      onModeChanged,
    } = options;

    const toggleButton = document.getElementById("liveChatTogglePhotoModeButton");
    let active = false;
    let busy = false;

    function canUse(context) {
      const reward = getReward?.(context);
      return Boolean(reward?.clear_unlocked || reward?.closet_unlocked || reward?.event_claimed);
    }

    function updateAvailability(context) {
      if (!toggleButton) return;
      const available = canUse(context);
      toggleButton.hidden = !available;
      toggleButton.disabled = busy || !available;
      toggleButton.classList.toggle("is-clear-unlocked", available);
      toggleButton.setAttribute(
        "title",
        available ? (active ? "撮影モード中" : "撮影モード") : "好感度100で開放",
      );
      toggleButton.setAttribute(
        "aria-label",
        available ? (active ? "撮影モード中" : "撮影モード") : "撮影モードは好感度100で開放",
      );
      if (!available && active) {
        active = false;
        onModeChanged?.();
      }
    }

    function setActive(nextActive, { silent = false } = {}) {
      if (nextActive && !canUse()) {
        active = false;
        updateAvailability();
        onModeChanged?.();
        if (!silent) NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
        return false;
      }
      active = Boolean(nextActive);
      if (active) onDeactivateConversation?.();
      if (toggleButton) {
        toggleButton.classList.toggle("is-active", active);
        toggleButton.setAttribute("aria-pressed", active ? "true" : "false");
        toggleButton.setAttribute("title", active ? "撮影モード中" : "撮影モード");
        toggleButton.setAttribute("aria-label", active ? "撮影モード中" : "撮影モード");
      }
      updateAvailability();
      onModeChanged?.();
      return true;
    }

    function setLoading(nextActive) {
      busy = Boolean(nextActive);
      if (!toggleButton) return;
      toggleButton.disabled = busy || !canUse();
      toggleButton.innerHTML = busy
        ? '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>'
        : iconHtml;
    }

    async function generateShoot(promptText, poseStyle = "") {
      if (busy) return false;
      if (!canUse()) {
        NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
        setActive(false, { silent: true });
        return false;
      }
      const text = String(promptText || "").trim();
      if (!text) {
        NovelUI.toast("撮影したいポーズや構図を入力してください。", "warning");
        return false;
      }
      setLoading(true);
      shell?.setImageLoading(true, "auto");
      try {
        const result = await api.generatePhotoModeShoot(sessionId, {
          prompt_text: text,
          pose_style: poseStyle,
          photo_size: imageForm?.size?.value || "1536x1024",
          quality: imageForm?.quality?.value || "low",
        });
        if (isInteractionLocked?.()) return false;
        if (result?.context) {
          applyContext?.(result.context);
        } else {
          await loadContext?.();
        }
        return true;
      } catch (error) {
        NovelUI.toast(error.message || "撮影に失敗しました。", "danger");
        if (!isInteractionLocked?.()) await loadContext?.().catch?.(() => {});
        return false;
      } finally {
        if (!isInteractionLocked?.()) {
          setLoading(false);
          shell?.setImageLoading(false, "auto");
        }
      }
    }

    function bind() {
      toggleButton?.addEventListener("click", () => {
        window.LiveChatSound?.unlock?.();
        window.LiveChatSound?.play("shutter");
        if (!canUse()) {
          NovelUI.toast("撮影モードは好感度100クリア後に開放されます。", "warning");
          return;
        }
        setActive(!active);
        NovelUI.toast(active
          ? "撮影モードです。ポーズや構図を書いて送信してください。"
          : "撮影モードを解除しました。");
      });
    }

    return {
      bind,
      canUse,
      generateShoot,
      isActive: () => active,
      setActive,
      updateAvailability,
    };
  }

  window.LiveChatPhotoMode = {
    createPhotoModeController,
  };
})();
