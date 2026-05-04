(function () {
  function createShortStoryPanel(options = {}) {
    const { getCurrentContext } = options;
    const card = document.getElementById("liveChatShortStoryCard");
    const bodyPanel = document.getElementById("liveChatShortStoryBodyPanel");
    const toggleButton = document.getElementById("liveChatShortStoryToggleButton");
    const countBadge = document.getElementById("liveChatShortStoryCount");
    const result = document.getElementById("liveChatShortStoryResult");
    const savedStories = document.getElementById("liveChatSavedShortStories");
    const savedStoryList = document.getElementById("liveChatSavedShortStoryList");
    const meta = document.getElementById("liveChatShortStoryMeta");
    const title = document.getElementById("liveChatShortStoryTitle");
    const synopsis = document.getElementById("liveChatShortStorySynopsis");
    const storyBody = document.getElementById("liveChatShortStoryBody");
    const afterword = document.getElementById("liveChatShortStoryAfterword");
    const openingImageWrap = document.getElementById("liveChatShortStoryOpeningImageWrap");
    const openingImage = document.getElementById("liveChatShortStoryOpeningImage");
    const endingImageWrap = document.getElementById("liveChatShortStoryEndingImageWrap");
    const endingImage = document.getElementById("liveChatShortStoryEndingImage");

    let currentShortStory = null;

    function setExpanded(expanded) {
      if (!card || !bodyPanel || !toggleButton) return;
      card.classList.toggle("is-collapsed", !expanded);
      bodyPanel.hidden = !expanded;
      toggleButton.setAttribute("aria-expanded", expanded ? "true" : "false");
      const label = toggleButton.querySelector("span");
      if (label) label.textContent = expanded ? "閉じる" : "開く";
    }

    function toggleExpanded() {
      setExpanded(card?.classList.contains("is-collapsed"));
    }

    function updateCount(stories) {
      if (!countBadge) return;
      const count = Array.isArray(stories) ? stories.length : 0;
      countBadge.textContent = count ? `${count}編 解放済み` : "未解放";
      card?.classList.toggle("has-ending-bonus", count > 0);
    }

    function renderShortStoryImage(wrap, image, item) {
      const mediaUrl = item?.asset?.media_url;
      if (!wrap || !image) return;
      if (!mediaUrl) {
        image.removeAttribute("src");
        wrap.classList.add("is-hidden");
        return;
      }
      image.src = mediaUrl;
      wrap.classList.remove("is-hidden");
    }

    function renderShortStory(story) {
      if (!result || !title || !storyBody) return;
      currentShortStory = story;
      const paragraphs = String(story?.body || "")
        .split(/\n{2,}|\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      title.textContent = story?.title || "チャットから生まれた短編";
      if (synopsis) {
        synopsis.textContent = "";
        synopsis.hidden = true;
      }
      storyBody.innerHTML = paragraphs.length
        ? paragraphs.map((line) => `<p>${NovelUI.escape(line)}</p>`).join("")
        : '<p>本文を生成できませんでした。</p>';
      if (afterword) {
        afterword.textContent = story?.afterword || "";
        afterword.hidden = !story?.afterword;
      }
      if (meta) {
        const count = Number(story?.source_message_count || 0);
        meta.textContent = count ? `${count}件のログから生成` : "チャットログから生成";
      }
      renderShortStoryImage(openingImageWrap, openingImage, story?.images?.opening);
      renderShortStoryImage(endingImageWrap, endingImage, story?.images?.ending);
      result.classList.remove("is-hidden");
    }

    function renderSavedShortStories(context) {
      if (!savedStories || !savedStoryList) return;
      const stories = context?.session?.settings_json?.saved_short_stories;
      updateCount(stories);
      if (!Array.isArray(stories) || !stories.length) {
        savedStories.classList.add("is-hidden");
        savedStoryList.innerHTML = "";
        result?.classList.add("is-hidden");
        currentShortStory = null;
        setExpanded(false);
        return;
      }
      savedStories.classList.remove("is-hidden");
      savedStoryList.innerHTML = stories.slice().reverse().map((story, index) => {
        const storyTitle = story?.title || "無題の短編";
        const count = Number(story?.source_message_count || 0);
        const source = count ? `${count}件` : "保存済み";
        return `
          <button class="live-chat-saved-short-story" type="button" data-saved-short-story-index="${stories.length - 1 - index}">
            <span>${NovelUI.escape(storyTitle)}</span>
            <small>${NovelUI.escape(source)}</small>
          </button>
        `;
      }).join("");
      const latestStory = stories[stories.length - 1];
      if (latestStory && currentShortStory?.id !== latestStory.id) {
        renderShortStory(latestStory);
        setExpanded(true);
      }
    }

    function showSavedShortStory(event) {
      const button = event.target.closest("[data-saved-short-story-index]");
      if (!button) return;
      const stories = getCurrentContext?.()?.session?.settings_json?.saved_short_stories;
      const index = Number(button.dataset.savedShortStoryIndex);
      if (!Array.isArray(stories) || !stories[index]) return;
      renderShortStory(stories[index]);
      setExpanded(true);
    }

    function bind() {
      setExpanded(false);
      toggleButton?.addEventListener("click", toggleExpanded);
      savedStoryList?.addEventListener("click", showSavedShortStory);
    }

    return {
      bind,
      renderSavedShortStories,
      renderShortStory,
      setExpanded,
    };
  }

  window.LiveChatShortStoryPanel = {
    createShortStoryPanel,
  };
})();
