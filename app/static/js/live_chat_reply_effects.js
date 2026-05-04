(function () {
  function createReplyEffectsController(options = {}) {
    const {
      selectedImagePanel,
      imageForm,
      generateSessionImage,
      getActiveCharacters,
      onMoodChange,
    } = options;

    let latestVisualMomentHint = "";
    let replyEffectTimer = null;

    function normalize(effect) {
      if (!effect || typeof effect !== "object") return null;
      const allowed = new Set(["neutral", "happy", "shy", "thinking", "surprised", "sad", "angry", "excited", "lonely", "relieved"]);
      const emotion = allowed.has(String(effect.emotion || "").toLowerCase())
        ? String(effect.emotion).toLowerCase()
        : "neutral";
      const intensity = Math.max(1, Math.min(5, Number(effect.reaction_intensity || 2)));
      return {
        speakerName: String(effect.speaker_name || "").trim(),
        emotion,
        intensity,
        moodLabel: String(effect.mood_label || "").trim() || "反応している",
        visualMomentHint: String(effect.visual_moment_hint || "").trim(),
        showNovelSpotlight: Boolean(effect.show_novel_spotlight),
        suggestImage: Boolean(effect.suggest_image),
      };
    }

    function icon(emotion) {
      return {
        happy: "bi-stars",
        shy: "bi-heart-fill",
        thinking: "bi-three-dots",
        surprised: "bi-exclamation-lg",
        sad: "bi-cloud-drizzle",
        angry: "bi-lightning-charge-fill",
        excited: "bi-stars",
        lonely: "bi-moon-stars",
        relieved: "bi-brightness-alt-high",
        neutral: "bi-chat-heart",
      }[emotion] || "bi-chat-heart";
    }

    function ensureLayer() {
      const stage = selectedImagePanel?.closest(".live-chat-stage");
      if (!stage) return null;
      let layer = stage.querySelector(".live-chat-reply-effect");
      if (!layer) {
        layer = document.createElement("div");
        layer.className = "live-chat-reply-effect";
        stage.appendChild(layer);
      }
      return layer;
    }

    function triggerParticles(emotion, intensity) {
      const stage = selectedImagePanel?.closest(".live-chat-stage");
      if (!stage) return;
      const count = Math.max(4, Math.min(14, intensity * 2 + 2));
      for (let index = 0; index < count; index += 1) {
        const particle = document.createElement("span");
        particle.className = `live-chat-reply-particle is-${emotion}`;
        particle.innerHTML = `<i class="bi ${icon(emotion)}" aria-hidden="true"></i>`;
        particle.style.setProperty("--particle-x", `${Math.round((Math.random() - 0.5) * 260)}px`);
        particle.style.setProperty("--particle-y", `${Math.round(50 + Math.random() * 160)}px`);
        particle.style.setProperty("--particle-delay", `${index * 55}ms`);
        particle.style.setProperty("--particle-scale", `${0.78 + Math.random() * 0.75}`);
        stage.appendChild(particle);
        window.setTimeout(() => particle.remove(), 1450 + index * 55);
      }
    }

    function trigger(effect) {
      const normalized = normalize(effect);
      if (!normalized) return;
      const fallbackName = getActiveCharacters?.()?.[0]?.name || "";
      const key = normalized.speakerName || fallbackName;
      if (key) {
        onMoodChange?.(key, {
          emotion: normalized.emotion,
          label: normalized.moodLabel,
        });
      }
      const stage = selectedImagePanel?.closest(".live-chat-stage");
      if (stage) {
        stage.classList.remove(
          "is-reply-happy",
          "is-reply-shy",
          "is-reply-thinking",
          "is-reply-surprised",
          "is-reply-sad",
          "is-reply-angry",
          "is-reply-excited",
          "is-reply-lonely",
          "is-reply-relieved",
          "is-reply-neutral",
        );
        stage.classList.add(`is-reply-${normalized.emotion}`);
        window.setTimeout(() => stage.classList.remove(`is-reply-${normalized.emotion}`), 1400 + normalized.intensity * 260);
      }
      const layer = ensureLayer();
      if (layer) {
        latestVisualMomentHint = normalized.visualMomentHint;
        layer.className = `live-chat-reply-effect is-visible is-${normalized.emotion}`;
        layer.innerHTML = `
          <div class="live-chat-reply-effect-badge">
            <i class="bi ${icon(normalized.emotion)}" aria-hidden="true"></i>
            <span>${NovelUI.escape(normalized.moodLabel)}</span>
          </div>
          ${normalized.suggestImage && normalized.visualMomentHint ? `
            <button class="live-chat-reply-effect-image" type="button" data-reply-effect-image title="シャッターチャンス" aria-label="シャッターチャンス">
              <i class="bi bi-camera-fill" aria-hidden="true"></i>
            </button>
          ` : ""}
        `;
        window.clearTimeout(replyEffectTimer);
        replyEffectTimer = window.setTimeout(() => {
          layer.classList.remove("is-visible");
        }, normalized.suggestImage ? 9000 : 3600 + normalized.intensity * 400);
      }
      triggerParticles(normalized.emotion, normalized.intensity);
      if (normalized.showNovelSpotlight) {
        const novelBox = document.getElementById("liveChatNovelBox");
        novelBox?.classList.remove("is-reply-spotlight");
        window.requestAnimationFrame(() => novelBox?.classList.add("is-reply-spotlight"));
        window.setTimeout(() => novelBox?.classList.remove("is-reply-spotlight"), 1800);
      }
    }

    async function generateImageFromLatestHint() {
      const prompt = String(latestVisualMomentHint || "").trim();
      if (!prompt) {
        NovelUI.toast("画像化できる表情メモがありません。", "warning");
        return;
      }
      if (imageForm?.prompt_text) imageForm.prompt_text.value = prompt;
      try {
        await generateSessionImage?.(false, "auto", { prompt_text: prompt });
        NovelUI.toast("シャッターチャンスを撮影しました。");
      } catch (error) {
        NovelUI.toast(error.message || "今の表情の画像化に失敗しました。", "danger");
      }
    }

    function bind() {
      selectedImagePanel?.closest(".live-chat-stage")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-reply-effect-image]");
        if (!button) return;
        event.preventDefault();
        generateImageFromLatestHint();
      });
    }

    return {
      bind,
      trigger,
      generateImageFromLatestHint,
    };
  }

  window.LiveChatReplyEffects = {
    createReplyEffectsController,
  };
})();
