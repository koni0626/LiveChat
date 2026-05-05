(function () {
  function createComposerController(options = {}) {
    const {
      api,
      sessionId,
      form = document.getElementById("liveChatComposeForm"),
      input = document.getElementById("liveChatComposeInput"),
      shell,
      imageForm,
      getCurrentContext,
      isPhotoModeActive,
      generatePhotoShoot,
      loadContext,
      capturePlayerReaction,
      playAffinityFeedback,
      triggerReplyEffect,
      onActivity,
      clearIdleTalkTimer,
      scheduleIdleTalk,
      isInteractionLocked,
    } = options;

    const shellElement = document.getElementById("liveChatComposeShell");
    const toggleButton = document.getElementById("liveChatToggleComposeButton");
    const proxyButton = document.getElementById("liveChatProxyMessageButton");
    const modeButtons = Array.from(document.querySelectorAll("[data-composer-mode]"));
    const actionPanel = document.getElementById("liveChatActionPanel");
    const actionButtons = Array.from(document.querySelectorAll("[data-action-id]"));
    const actionChip = document.getElementById("liveChatActionChip");
    const actionChipLabel = document.getElementById("liveChatActionChipLabel");
    const actionClearButton = document.getElementById("liveChatActionClearButton");
    let visible = true;
    let composeMode = "chat";
    let selectedAction = null;

    const actionDefinitions = {
      smile_at: { id: "smile_at", label: "微笑みかける", minAffinity: 0 },
      wave: { id: "wave", label: "手を振る", minAffinity: 0 },
      cheer: { id: "cheer", label: "応援する", minAffinity: 0 },
      gaze_at: { id: "gaze_at", label: "見つめる", minAffinity: 0 },
      move_closer: { id: "move_closer", label: "近くに寄る", minAffinity: 20 },
      sit_next: { id: "sit_next", label: "隣に座る", minAffinity: 20 },
      hold_hands: { id: "hold_hands", label: "手をつなぐ", minAffinity: 40 },
      pat_head: { id: "pat_head", label: "頭をなでる", minAffinity: 40 },
      hug_softly: { id: "hug_softly", label: "そっと抱きしめる", minAffinity: 60 },
      snuggle: { id: "snuggle", label: "寄り添う", minAffinity: 60 },
      touch_cheek: { id: "touch_cheek", label: "頬に触れる", minAffinity: 80 },
      interlace_fingers: { id: "interlace_fingers", label: "指を絡める", minAffinity: 80 },
    };

    const placeholders = {
      chat: "メッセージを入力。メッセージを作成ボタンで代理メッセージも作れます。",
      action: "アクションに添える一言があれば入力。そのまま送信もできます。",
      photo: "例: ネオンの通路を背に少し振り返り、こちらへ視線を向ける。背景を大きくぼかした縦構図で、SNSで映える一枚にする。",
    };

    function currentContext() {
      return getCurrentContext?.();
    }

    function isPhotoMode() {
      return Boolean(isPhotoModeActive?.());
    }

    function markActivity() {
      onActivity?.();
      scheduleIdleTalk?.();
    }

    function currentTargetCharacterId() {
      const context = currentContext() || {};
      const characters = context.characters || context.project_characters || [];
      if (characters.length !== 1) return null;
      const parsed = Number.parseInt(characters[0]?.id, 10);
      return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    }

    function currentAffinityScore() {
      const context = currentContext() || {};
      const memories = context.character_user_memories || {};
      const targetCharacterId = currentTargetCharacterId();
      const memory = targetCharacterId ? memories[String(targetCharacterId)] || memories[targetCharacterId] : null;
      if (memory) return Math.max(0, Math.min(100, Number(memory.affinity_score || 0)));
      const scores = Object.values(memories)
        .map((item) => Number(item?.affinity_score || 0))
        .filter((score) => Number.isFinite(score));
      return scores.length ? Math.max(...scores.map((score) => Math.max(0, Math.min(100, score)))) : 0;
    }

    function isActionUnlocked(action) {
      return currentAffinityScore() >= Number(action?.minAffinity || 0);
    }

    function buildActionIntent(action) {
      if (!action || !isActionUnlocked(action)) return null;
      const intent = {
        type: "action",
        id: action.id,
        label: action.label,
      };
      const targetCharacterId = currentTargetCharacterId();
      if (targetCharacterId) intent.target_character_id = targetCharacterId;
      return intent;
    }

    function buildMessagePayload(messageText, playerIntent = null) {
      const normalizedIntent = playerIntent || {
        type: "message",
        id: "free_text",
        label: "メッセージ",
      };
      return {
        message_text: messageText,
        player_intent: normalizedIntent,
        auto_reply: true,
        size: imageForm?.size?.value || "1536x1024",
        quality: imageForm?.quality?.value || "low",
        skip_auto_image: true,
      };
    }

    function setVisible(nextVisible) {
      visible = Boolean(nextVisible);
      shellElement?.classList.toggle("is-collapsed", !visible);
      if (toggleButton) {
        toggleButton.textContent = visible ? "メッセージ欄を閉じる" : "メッセージ欄を開く";
        toggleButton.setAttribute("aria-expanded", visible ? "true" : "false");
      }
    }

    function refreshPlaceholder() {
      if (!input) return;
      if (isPhotoMode()) {
        input.placeholder = placeholders.photo;
      } else if (selectedAction) {
        input.placeholder = placeholders.action;
      } else {
        input.placeholder = placeholders.chat;
      }
    }

    function setComposeMode(mode) {
      composeMode = mode === "action" ? "action" : "chat";
      modeButtons.forEach((button) => {
        const active = button.dataset.composerMode === composeMode;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      });
      actionPanel?.classList.toggle("is-hidden", composeMode !== "action");
    }

    function renderActionAvailability() {
      const score = currentAffinityScore();
      const lockedActions = Object.values(actionDefinitions)
        .filter((action) => Number(action.minAffinity || 0) > score)
        .sort((a, b) => a.minAffinity - b.minAffinity);
      const nextUnlock = lockedActions.length ? lockedActions[0].minAffinity : null;
      actionButtons.forEach((button) => {
        const action = actionDefinitions[button.dataset.actionId];
        if (!action) return;
        const unlocked = isActionUnlocked(action);
        const showLocked = !unlocked && action.minAffinity === nextUnlock;
        button.hidden = !unlocked && !showLocked;
        button.disabled = !unlocked;
        button.classList.toggle("is-locked", !unlocked);
        button.dataset.lockLabel = !unlocked ? `好感度${action.minAffinity}で解放` : "";
        button.setAttribute(
          "aria-label",
          unlocked ? action.label : `${action.label}、好感度${action.minAffinity}で解放`,
        );
      });
      if (selectedAction && !isActionUnlocked(selectedAction)) clearSelectedAction();
    }

    function renderSelectedAction() {
      renderActionAvailability();
      actionButtons.forEach((button) => {
        button.classList.toggle("is-selected", Boolean(selectedAction && button.dataset.actionId === selectedAction.id));
      });
      actionChip?.classList.toggle("is-hidden", !selectedAction);
      if (actionChipLabel) actionChipLabel.textContent = selectedAction ? selectedAction.label : "";
      refreshPlaceholder();
    }

    function selectAction(actionId) {
      const action = actionDefinitions[actionId];
      if (!action) return;
      if (!isActionUnlocked(action)) {
        NovelUI.toast(`${action.label}は好感度${action.minAffinity}で解放されます。`, "warning");
        return;
      }
      selectedAction = action;
      setComposeMode("action");
      renderSelectedAction();
      markActivity();
      focus();
    }

    function clearSelectedAction() {
      selectedAction = null;
      renderSelectedAction();
    }

    function hasPendingText() {
      return Boolean(form?.message_text?.value?.trim() || selectedAction);
    }

    function focus() {
      form?.message_text?.focus();
    }

    function submitText(text) {
      const value = String(text || "").trim();
      if (!value || !form?.message_text) return;
      clearSelectedAction();
      form.message_text.value = value;
      markActivity();
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }
    }

    async function submitMessage(rawMessage, playerIntent = null) {
      let handledBySpecialMode = false;
      shell?.setReplyLoading(true, currentContext());
      if (isPhotoMode()) {
        await generatePhotoShoot?.(rawMessage);
        handledBySpecialMode = true;
      } else {
        const result = await api.postMessage(sessionId, buildMessagePayload(rawMessage, playerIntent));
        if (isInteractionLocked?.()) return;
        if (result?.new_letter) {
          NovelUI.toast("キャラクターからメールが届きました。");
          NovelUI.refreshLetterBadge?.();
        }
        playAffinityFeedback?.(result?.affinity_feedback);
        shell?.setReplyLoading(false, currentContext(), { render: false });
        await loadContext?.();
        if (isInteractionLocked?.()) return;
        triggerReplyEffect?.(result?.reply_effect);
        await capturePlayerReaction?.();
        if (isInteractionLocked?.()) return;
        if (result?.deferred_processing) {
          window.setTimeout(() => {
            NovelUI.refreshLetterBadge?.();
          }, 3500);
        }
      }
      form.message_text.value = "";
      clearSelectedAction();
      markActivity();
      if (!handledBySpecialMode) {
        NovelUI.toast(playerIntent?.type === "action" ? "アクションを送りました。" : "メッセージを送信しました。");
      }
    }

    async function handleSubmit(event) {
      event.preventDefault();
      if (isInteractionLocked?.()) return;
      clearIdleTalkTimer?.();
      const rawMessage = form?.message_text?.value?.trim() || "";
      const playerIntent = selectedAction ? buildActionIntent(selectedAction) : null;
      const messageText = rawMessage || (selectedAction ? selectedAction.label : "");
      try {
        if (!messageText) {
          NovelUI.toast("送信するメッセージを入力するか、アクションを選んでください。", "warning");
          focus();
          scheduleIdleTalk?.();
          return;
        }
        if (selectedAction && !playerIntent) {
          NovelUI.toast(`${selectedAction.label}はまだ解放されていません。`, "warning");
          return;
        }
        triggerReplyEffect?.(null);
        await submitMessage(messageText, playerIntent);
      } catch (error) {
        NovelUI.toast(error.message || "メッセージ送信に失敗しました。", "danger");
      } finally {
        if (!isInteractionLocked?.()) {
          shell?.setReplyLoading(false, currentContext());
        }
      }
    }

    async function generateProxyMessage() {
      if (isInteractionLocked?.()) return;
      if (!proxyButton) return;
      const originalText = proxyButton.textContent;
      try {
        proxyButton.disabled = true;
        proxyButton.textContent = "作成中...";
        const proxy = await api.generateProxyPlayerMessage(sessionId, {
          purpose: isPhotoMode() ? "photo_mode" : "chat",
        });
        clearSelectedAction();
        if (form?.message_text) form.message_text.value = proxy?.message_text || "";
        setComposeMode("chat");
        markActivity();
        focus();
        NovelUI.toast(isPhotoMode()
          ? "撮影用プロンプトを作成しました。内容を確認して送信してください。"
          : "代理プレイヤーのメッセージを作成しました。内容を確認して送信してください。");
      } catch (error) {
        NovelUI.toast(error.message || "代理メッセージの作成に失敗しました。", "danger");
      } finally {
        proxyButton.disabled = false;
        proxyButton.textContent = originalText;
      }
    }

    function render() {
      renderSelectedAction();
    }

    function bind() {
      form?.addEventListener("submit", handleSubmit);
      input?.addEventListener("input", markActivity);
      input?.addEventListener("focus", () => scheduleIdleTalk?.());
      proxyButton?.addEventListener("click", generateProxyMessage);
      toggleButton?.addEventListener("click", () => setVisible(!visible));
      modeButtons.forEach((button) => {
        button.addEventListener("click", () => setComposeMode(button.dataset.composerMode));
      });
      actionButtons.forEach((button) => {
        button.addEventListener("click", () => selectAction(button.dataset.actionId));
      });
      actionClearButton?.addEventListener("click", clearSelectedAction);
      setVisible(true);
      setComposeMode("chat");
      renderSelectedAction();
      refreshPlaceholder();
    }

    return {
      bind,
      buildMessagePayload,
      focus,
      hasPendingText,
      refreshPlaceholder,
      render,
      setVisible,
      submitText,
    };
  }

  window.LiveChatComposer = {
    createComposerController,
  };
})();
