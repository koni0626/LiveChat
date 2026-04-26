(function () {
  function normalizeMessageSortValue(item) {
    const createdAt = Date.parse(item?.created_at || "");
    if (Number.isFinite(createdAt)) return createdAt;
    return Number(item?.id || 0);
  }

  function prepareDisplayMessages(messages, options = {}) {
    const source = (Array.isArray(messages) ? [...messages] : [])
      .sort((a, b) => normalizeMessageSortValue(a) - normalizeMessageSortValue(b));
    const query = String(options.searchQuery || "").trim().toLowerCase();
    let filtered = source;
    if (query) {
      const hitIndex = source.findIndex((item) => {
        const text = `${item?.speaker_name || ""}\n${item?.message_text || ""}`.toLowerCase();
        return text.includes(query);
      });
      filtered = hitIndex >= 0 ? source.slice(hitIndex) : [];
    }
    const direction = options.sortOrder === "asc" ? 1 : -1;
    return filtered.sort((a, b) => (normalizeMessageSortValue(a) - normalizeMessageSortValue(b)) * direction);
  }

  function renderMessages(messages, messageListElement, options = {}) {
    if (!messageListElement) return;
    const displayMessages = prepareDisplayMessages(messages, options);
    if (!messages.length) {
      messageListElement.innerHTML = '<div class="empty-panel">まだ会話ログがありません。</div>';
      return;
    }
    if (!displayMessages.length) {
      messageListElement.innerHTML = '<div class="empty-panel">検索に一致するログがありません。</div>';
      return;
    }
    messageListElement.innerHTML = displayMessages.map((item) => {
      const gift = item.state_snapshot_json?.gift;
      const giftMarkup = gift?.asset?.media_url ? `
        <div class="live-chat-gift-card">
          <img class="live-chat-gift-thumb" src="${gift.asset.media_url}" alt="${NovelUI.escape(gift.recognized_label || "gift")}">
          <div class="live-chat-gift-meta">
            <div class="live-chat-gift-label">${NovelUI.escape(gift.recognized_label || "贈り物")}</div>
            ${gift.reaction_summary ? `<div class="live-chat-gift-reaction">${NovelUI.escape(gift.reaction_summary)}</div>` : ""}
          </div>
        </div>
      ` : "";
      return `
        <article class="live-chat-bubble ${item.sender_type === "user" ? "player" : "character"}" data-message-id="${item.id}">
          <div class="live-chat-bubble-head">
            <div class="live-chat-bubble-speaker">${NovelUI.escape(item.speaker_name || item.sender_type)}</div>
            <button class="live-chat-bubble-delete" type="button" data-delete-message-id="${item.id}" aria-label="ログを削除" title="ログを削除">削除</button>
          </div>
          <div class="live-chat-bubble-text">${NovelUI.escape(item.message_text || "")}</div>
          ${giftMarkup}
        </article>
      `;
    }).join("");
    messageListElement.scrollTop = 0;
  }

  window.LiveChatLogView = {
    renderMessages,
  };
})();
