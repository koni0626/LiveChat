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
    } = options;

    const shellElement = document.getElementById("liveChatComposeShell");
    const toggleButton = document.getElementById("liveChatToggleComposeButton");
    const proxyButton = document.getElementById("liveChatProxyMessageButton");
    let visible = true;

    const placeholders = {
      chat: "メッセージを入力。メッセージを作成ボタンで代理メッセージも作れます。",
      photo: "例: ネオンの逆光を背に少し振り返り、こちらへ視線を向ける。背景を大きくぼかした縦構図で、Xで映える一枚にする。",
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
      input.placeholder = isPhotoMode() ? placeholders.photo : placeholders.chat;
    }

    function hasPendingText() {
      return Boolean(form?.message_text?.value?.trim());
    }

    function focus() {
      form?.message_text?.focus();
    }

    function submitText(text) {
      const value = String(text || "").trim();
      if (!value || !form?.message_text) return;
      form.message_text.value = value;
      markActivity();
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }
    }

    async function submitMessage(rawMessage) {
      let handledBySpecialMode = false;
      shell?.setReplyLoading(true, currentContext());
      if (isPhotoMode()) {
        await generatePhotoShoot?.(rawMessage);
        handledBySpecialMode = true;
      } else {
        const result = await api.postMessage(sessionId, buildMessagePayload(rawMessage));
        if (result?.new_letter) {
          NovelUI.toast("キャラクターからメールが届きました。");
          NovelUI.refreshLetterBadge?.();
        }
        playAffinityFeedback?.(result?.affinity_feedback);
        shell?.setReplyLoading(false, currentContext(), { render: false });
        await loadContext?.();
        triggerReplyEffect?.(result?.reply_effect);
        await capturePlayerReaction?.();
        if (result?.deferred_processing) {
          window.setTimeout(() => {
            NovelUI.refreshLetterBadge?.();
          }, 3500);
        }
      }
      form.message_text.value = "";
      markActivity();
      if (!handledBySpecialMode) {
        NovelUI.toast("メッセージを送信しました。");
      }
    }

    async function handleSubmit(event) {
      event.preventDefault();
      clearIdleTalkTimer?.();
      const rawMessage = form?.message_text?.value?.trim() || "";
      try {
        if (!rawMessage) {
          NovelUI.toast("送信するメッセージを入力するか、メッセージを作成ボタンで代理文を作成してください。", "warning");
          focus();
          scheduleIdleTalk?.();
          return;
        }
        await submitMessage(rawMessage);
      } catch (error) {
        NovelUI.toast(error.message || "メッセージ送信に失敗しました。", "danger");
      } finally {
        shell?.setReplyLoading(false, currentContext());
      }
    }

    async function generateProxyMessage() {
      if (!proxyButton) return;
      const originalText = proxyButton.textContent;
      try {
        proxyButton.disabled = true;
        proxyButton.textContent = "作成中...";
        const proxy = await api.generateProxyPlayerMessage(sessionId, {
          purpose: isPhotoMode() ? "photo_mode" : "chat",
        });
        if (form?.message_text) form.message_text.value = proxy?.message_text || "";
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

    function bind() {
      form?.addEventListener("submit", handleSubmit);
      input?.addEventListener("input", markActivity);
      input?.addEventListener("focus", () => scheduleIdleTalk?.());
      proxyButton?.addEventListener("click", generateProxyMessage);
      toggleButton?.addEventListener("click", () => setVisible(!visible));
      setVisible(true);
      refreshPlaceholder();
    }

    return {
      bind,
      buildMessagePayload,
      focus,
      hasPendingText,
      refreshPlaceholder,
      setVisible,
      submitText,
    };
  }

  window.LiveChatComposer = {
    createComposerController,
  };
})();
