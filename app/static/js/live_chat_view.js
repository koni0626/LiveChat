(function () {
  function formatJson(value) {
    if (!value) return "{}";
    if (typeof value === "string") {
      try {
        return JSON.stringify(JSON.parse(value), null, 2);
      } catch (_) {
        return value;
      }
    }
    return JSON.stringify(value, null, 2);
  }

  function normalizeSelectedCharacterIds(settingsJson) {
    if (!settingsJson || typeof settingsJson !== "object") {
      return [];
    }
    const source = Array.isArray(settingsJson.selected_character_ids)
      ? settingsJson.selected_character_ids
      : (settingsJson.selected_character_id ? [settingsJson.selected_character_id] : []);
    return source
      .map((value) => Number(value))
      .filter((value, index, array) => Number.isInteger(value) && value > 0 && array.indexOf(value) === index);
  }

  window.LiveChatView = {
    formatJson,
    normalizeSelectedCharacterIds,
    renderNovelPage: window.LiveChatNovelView.renderNovelPage,
    renderNovelBox: window.LiveChatNovelView.renderNovelBox,
    renderMessages: window.LiveChatLogView.renderMessages,
    renderSelectedImage: window.LiveChatImageView.renderSelectedImage,
    renderImageGrid: window.LiveChatImageView.renderImageGrid,
  };
})();
