(function () {
  function createCharacterGuideController(options = {}) {
    const {
      guide = document.getElementById("liveChatCharacterGuide"),
      list = document.getElementById("liveChatCharacterGuideList"),
      getActiveCharacters,
      onPrompt,
    } = options;

    const moodState = new Map();
    let currentContext = null;

    function characterAssetUrl(character) {
      return character?.bromide_asset?.media_url
        || character?.thumbnail_asset?.media_url
        || character?.base_asset?.media_url
        || "";
    }

    function compactText(value, limit = 74) {
      const text = String(value || "").replace(/\s+/g, " ").trim();
      if (!text) return "";
      return text.length > limit ? `${text.slice(0, limit - 1)}...` : text;
    }

    function normalizeList(value) {
      if (Array.isArray(value)) {
        return value.map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object") return item.name || item.label || item.text || item.title || "";
          return "";
        }).map((item) => String(item || "").trim()).filter(Boolean);
      }
      return String(value || "")
        .split(/[\n,、/]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    function guideFacts(character) {
      const profile = character?.memory_profile && typeof character.memory_profile === "object"
        ? character.memory_profile
        : {};
      const favoriteItems = normalizeList(character?.favorite_items);
      const likes = normalizeList(profile.likes);
      const hobbies = normalizeList(profile.hobbies);
      return [...favoriteItems, ...likes, ...hobbies].filter((item, index, array) => array.indexOf(item) === index).slice(0, 3);
    }

    function guidePrompts(character) {
      const name = character?.nickname || character?.name || "キャラクター";
      return [
        { icon: "bi-clock-history", text: `${name}、最近何してた？` },
        { icon: "bi-chat-heart", text: `${name}は何の話が好き？` },
        { icon: "bi-briefcase", text: `${name}のお仕事や普段の役目の話、聞かせて` },
        { icon: "bi-emoji-smile", text: `${name}、今どんな気分？` },
        { icon: "bi-geo-alt", text: `${name}はこの場所をどう思う？` },
        { icon: "bi-stars", text: `${name}の好きなものを教えて` },
      ];
    }

    function render(context = currentContext) {
      currentContext = context;
      if (!guide || !list) return;
      const characters = typeof getActiveCharacters === "function" ? getActiveCharacters(context) : [];
      guide.hidden = characters.length === 0;
      if (!characters.length) {
        list.innerHTML = "";
        return;
      }
      const memoryMap = context?.character_user_memories || {};
      list.innerHTML = characters.map((character, index) => {
        const name = character.name || character.nickname || "Character";
        const imageUrl = characterAssetUrl(character);
        const intro = compactText(
          character.introduction_text
            || character.character_summary
            || character.feed_profile_text
            || character.personality
            || "",
        );
        const facts = guideFacts(character);
        const memory = memoryMap[String(character.id)] || {};
        const affinityLabel = memory.affinity_label || "";
        const mood = moodState.get(name) || moodState.get(character.nickname || "") || null;
        const prompts = guidePrompts(character);
        return `
          <article class="live-chat-character-guide-item ${index === 0 ? "is-open" : ""}" data-character-guide-id="${Number(character.id || 0)}">
            <button class="live-chat-character-guide-toggle" type="button" data-character-guide-toggle aria-expanded="${index === 0 ? "true" : "false"}">
              <span class="live-chat-character-guide-avatar">
                ${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="${NovelUI.escape(name)}">` : '<i class="bi bi-person-heart" aria-hidden="true"></i>'}
              </span>
              <span class="live-chat-character-guide-summary">
                <strong>${NovelUI.escape(name)}</strong>
                <span>${NovelUI.escape(intro || affinityLabel || "話題を選んで話しかける")}</span>
              </span>
              <i class="bi bi-chevron-down live-chat-character-guide-caret" aria-hidden="true"></i>
            </button>
            <div class="live-chat-character-guide-body">
              ${mood ? `<div class="live-chat-character-guide-mood is-${NovelUI.escape(mood.emotion || "neutral")}"><i class="bi bi-activity" aria-hidden="true"></i><span>${NovelUI.escape(mood.label || "反応している")}</span></div>` : ""}
              ${facts.length ? `<div class="live-chat-character-guide-facts">${facts.map((fact) => `<span>${NovelUI.escape(fact)}</span>`).join("")}</div>` : ""}
              <div class="live-chat-character-guide-prompts">
                ${prompts.map((prompt) => `
                  <button class="live-chat-character-guide-prompt" type="button" data-character-guide-prompt="${NovelUI.escape(prompt.text)}" title="${NovelUI.escape(prompt.text)}">
                    <i class="bi ${NovelUI.escape(prompt.icon)}" aria-hidden="true"></i>
                    <span>${NovelUI.escape(prompt.text)}</span>
                  </button>
                `).join("")}
              </div>
            </div>
          </article>
        `;
      }).join("");
    }

    function setMood(speakerName, mood) {
      const key = String(speakerName || "").trim();
      if (!key) return;
      moodState.set(key, {
        emotion: mood?.emotion || "neutral",
        label: mood?.label || "反応している",
      });
      render(currentContext);
    }

    function bind() {
      list?.addEventListener("click", (event) => {
        const promptButton = event.target.closest("[data-character-guide-prompt]");
        if (promptButton) {
          onPrompt?.(promptButton.dataset.characterGuidePrompt || "");
          return;
        }
        const toggleButton = event.target.closest("[data-character-guide-toggle]");
        if (!toggleButton) return;
        const item = toggleButton.closest(".live-chat-character-guide-item");
        if (!item) return;
        const isOpen = !item.classList.contains("is-open");
        item.classList.toggle("is-open", isOpen);
        toggleButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });
    }

    return {
      bind,
      render,
      setMood,
    };
  }

  window.LiveChatCharacterGuide = {
    createCharacterGuideController,
  };
})();
