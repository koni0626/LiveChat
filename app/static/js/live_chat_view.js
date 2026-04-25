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

  function localizeEvaluationLabel(label, isRomance) {
    const text = String(label || "").trim();
    if (!text) {
      return isRomance ? "\u604b\u611b\u5ea6" : "\u9032\u884c\u5ea6";
    }
    const lowered = text.toLowerCase();
    if (lowered === "love progress") return "\u604b\u611b\u5ea6";
    if (lowered === "good progress") return "\u826f\u597d";
    if (lowered === "interest progress") return "\u95a2\u5fc3\u5ea6";
    if (lowered === "progress") return "\u9032\u884c\u5ea6";
    return text;
  }

  function localizeEvaluationReason(reason, isRomance) {
    const text = String(reason || "").trim();
    if (!text) return "";
    if (!/[A-Za-z]/.test(text)) {
      return text;
    }
    let localized = text;
    localized = localized.replace(/however/gi, "ただし");
    localized = localized.replace(/but/gi, "ただし");
    localized = localized.replace(/ and /gi, "、");
    localized = localized.replace(/The player /gi, "プレイヤーは");
    localized = localized.replace(/This /gi, "これにより");
    localized = localized.replace(/the exchange/gi, "会話");
    localized = localized.replace(/is becoming/gi, "は");
    localized = localized.replace(/is still/gi, "はまだ");
    localized = localized.replace(/mostly about/gi, "主に");
    localized = localized.replace(/more personal and attentive/gi, "より個人的で丁寧なものになっている");
    localized = localized.replace(/not yet strongly romantic/gi, "まだ強い恋愛段階ではない");
    localized = localized.replace(/progressing well/gi, "順調に進んでいる");
    localized = localized.replace(/matched her preference/gi, "好みに合う反応ができている");
    localized = localized.replace(/made her feel understood and delighted/gi, "理解されて嬉しいと感じさせている");
    localized = localized.replace(/increases interest and trust/gi, "関心と信頼が高まっている");
    localized = localized.replace(/responds well to/gi, "に好意的に反応している");
    localized = localized.replace(/is attracted by/gi, "に惹かれている");
    localized = localized.replace(/dislikes approach/gi, "の接し方は苦手");
    localized = localized.replace(/has taboo topic/gi, "にとって地雷話題は");
    localized = localized.replace(/feels boundary crossed by/gi, "は一線を越えたと感じやすい");
    localized = localized.replace(/likes /gi, "が好き");
    localized = localized.replace(/dislikes /gi, "が苦手");
    localized = localized.replace(/is interested in hobby /gi, "の趣味に関心がある");
    localized = localized.replace(/\s+/g, " ").trim();
    if (/[A-Za-z]/.test(localized)) {
      return isRomance
        ? "\u76f4\u8fd1\u306e\u4f1a\u8a71\u3068\u53cd\u5fdc\u304b\u3089\u3001\u604b\u611b\u5ea6\u304c\u3069\u306e\u7a0b\u5ea6\u9032\u3093\u3060\u304b\u3092\u8a55\u4fa1\u3057\u3066\u3044\u307e\u3059\u3002"
        : "\u76f4\u8fd1\u306e\u4f1a\u8a71\u3068\u53cd\u5fdc\u304b\u3089\u3001\u9032\u884c\u5ea6\u3092\u8a55\u4fa1\u3057\u3066\u3044\u307e\u3059\u3002";
    }
    return localized;
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

  function getLatestDisplayMessage(messages) {
    const items = Array.isArray(messages) ? [...messages] : [];
    for (let index = items.length - 1; index >= 0; index -= 1) {
      const item = items[index];
      const text = (item?.message_text || "").trim();
      if (text) return item;
    }
    return null;
  }

  function ensureNovelTextMeasurer(sourceElement) {
    let measurer = document.getElementById("liveChatNovelTextMeasure");
    if (!measurer) {
      measurer = document.createElement("div");
      measurer.id = "liveChatNovelTextMeasure";
      measurer.className = "live-chat-novel-text live-chat-novel-text-measure";
      document.body.appendChild(measurer);
    }
    const style = window.getComputedStyle(sourceElement);
    measurer.style.width = `${sourceElement.clientWidth}px`;
    measurer.style.font = style.font;
    measurer.style.lineHeight = style.lineHeight;
    measurer.style.letterSpacing = style.letterSpacing;
    measurer.style.whiteSpace = style.whiteSpace;
    return measurer;
  }

  function fitNovelPageBreak(text, start, end) {
    if (end >= text.length) return end;
    const min = Math.max(start + 1, start + Math.floor((end - start) * 0.6));
    for (let index = end; index > min; index -= 1) {
      const pair = text.slice(index - 1, index + 1);
      const ch = text[index - 1];
      if (pair === "\n\n") return index;
      if (" \n\u3001\u3002\uff01\uff1f!?\u30fb\u300d\u300f\uff09)".includes(ch)) return index;
    }
    return end;
  }

  function paginateNovelText(text, elements) {
    const { novelBox, novelText, novelSpeaker } = elements;
    if (!novelBox || !novelText || !novelSpeaker) return [String(text || "")];
    const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
    if (!normalized) return [""];

    const measurer = ensureNovelTextMeasurer(novelText);
    const boxStyle = window.getComputedStyle(novelBox);
    const paddingTop = parseFloat(boxStyle.paddingTop || "0");
    const paddingBottom = parseFloat(boxStyle.paddingBottom || "0");
    const gap = parseFloat(boxStyle.gap || "0");
    const cueHeight = 26;
    const availableHeight = Math.max(
      48,
      novelBox.clientHeight - paddingTop - paddingBottom - novelSpeaker.offsetHeight - gap - cueHeight
    );
    const pages = [];
    let start = 0;

    while (start < normalized.length) {
      let low = start + 1;
      let high = normalized.length;
      let best = low;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        measurer.textContent = normalized.slice(start, mid).trim();
        if (measurer.scrollHeight <= availableHeight) {
          best = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
      let end = fitNovelPageBreak(normalized, start, best);
      if (end <= start) {
        end = Math.min(normalized.length, start + 1);
      }
      pages.push(normalized.slice(start, end).trim());
      start = end;
      while (start < normalized.length && /\s/.test(normalized[start])) {
        start += 1;
      }
    }
    return pages.length ? pages : [normalized];
  }

  function resolveStageDimensions(selectedImage) {
    const asset = selectedImage?.asset || {};
    const width = Number(asset.width);
    const height = Number(asset.height);
    if (width > 0 && height > 0) {
      return { width, height };
    }
    const sizeText = String(selectedImage?.size || "").trim();
    const match = sizeText.match(/^(\d+)x(\d+)$/);
    if (match) {
      return { width: Number(match[1]), height: Number(match[2]) };
    }
    return { width: 1024, height: 1536 };
  }

  function applyStageDimensions(selectedImage, selectedImagePanel) {
    const dims = resolveStageDimensions(selectedImage);
    selectedImagePanel.style.setProperty("--stage-width", String(dims.width));
    selectedImagePanel.style.setProperty("--stage-height", String(dims.height));
    const viewportHeight = Math.max(window.innerHeight || 0, 720);
    const desktopOffset = 250;
    const mobileOffset = 320;
    const maxHeight = Math.max(
      window.innerWidth <= 1200 ? 360 : 420,
      viewportHeight - (window.innerWidth <= 1200 ? mobileOffset : desktopOffset)
    );
    const stageParent = selectedImagePanel.parentElement;
    const availableWidth = stageParent ? stageParent.clientWidth : selectedImagePanel.clientWidth;

    let width = Math.min(availableWidth, maxHeight * (dims.width / dims.height));
    let height = width * (dims.height / dims.width);

    if (height > maxHeight) {
      height = maxHeight;
      width = height * (dims.width / dims.height);
    }

    selectedImagePanel.style.width = `${Math.round(width)}px`;
    selectedImagePanel.style.height = "auto";
    selectedImagePanel.style.setProperty("--rendered-stage-height", `${Math.round(height)}px`);
  }

  function renderNovelPage(novelPageState, novelTextElement, cueElement) {
    if (!novelTextElement) return novelPageState;
    const pages = novelPageState.pages || [];
    const pageIndex = Math.max(0, Math.min(novelPageState.pageIndex || 0, Math.max(0, pages.length - 1)));
    const nextState = { ...novelPageState, pageIndex };
    novelTextElement.textContent = pages[pageIndex] || "";
    if (cueElement) {
      cueElement.hidden = !(pages.length > 1 && pageIndex < pages.length - 1);
    }
    return nextState;
  }

  function renderNovelBox(messages, options) {
    const {
      replyLoading,
      currentContext,
      novelPageState,
      novelElements,
    } = options;
    const item = getLatestDisplayMessage(messages);
    const { novelSpeaker, novelText, novelContinue, novelBox } = novelElements;
    if (!novelSpeaker || !novelText) {
      return novelPageState;
    }
    if (replyLoading) {
      const activeCharacter = (currentContext?.characters || [])[0] || {};
      novelSpeaker.textContent = activeCharacter.name || item?.speaker_name || "";
      novelText.innerHTML = `
        <span class="live-chat-typing" aria-label="\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u304c\u8003\u3048\u4e2d">
          <span class="live-chat-typing-dot"></span>
          <span class="live-chat-typing-dot"></span>
          <span class="live-chat-typing-dot"></span>
        </span>
      `;
      if (novelContinue) novelContinue.hidden = true;
      return { messageId: null, pages: [], pageIndex: 0 };
    }
    if (!item) {
      novelSpeaker.textContent = "";
      novelText.textContent = "\u307e\u3060\u30bb\u30ea\u30d5\u304c\u3042\u308a\u307e\u305b\u3093\u3002";
      if (novelContinue) novelContinue.hidden = true;
      return { messageId: null, pages: [], pageIndex: 0 };
    }
    novelSpeaker.textContent = item.speaker_name || "";
    const pages = paginateNovelText(item.message_text || "", {
      novelBox,
      novelText,
      novelSpeaker,
    });
    const isSameMessage = novelPageState.messageId === item.id;
    return renderNovelPage(
      {
        messageId: item.id,
        pages,
        pageIndex: isSameMessage ? Math.min(novelPageState.pageIndex, Math.max(0, pages.length - 1)) : 0,
      },
      novelText,
      novelContinue
    );
  }

  function renderMessages(messages, messageListElement) {
    if (!messageListElement) return;
    if (!messages.length) {
      messageListElement.innerHTML = '<div class="empty-panel">\u307e\u3060\u4f1a\u8a71\u30ed\u30b0\u304c\u3042\u308a\u307e\u305b\u3093\u3002</div>';
      return;
    }
    messageListElement.innerHTML = messages.map((item) => {
      const gift = item.state_snapshot_json?.gift;
      const giftMarkup = gift?.asset?.media_url ? `
        <div class="live-chat-gift-card">
          <img class="live-chat-gift-thumb" src="${gift.asset.media_url}" alt="${NovelUI.escape(gift.recognized_label || "gift")}">
          <div class="live-chat-gift-meta">
            <div class="live-chat-gift-label">${NovelUI.escape(gift.recognized_label || "\u8d08\u308a\u7269")}</div>
            ${gift.reaction_summary ? `<div class="live-chat-gift-reaction">${NovelUI.escape(gift.reaction_summary)}</div>` : ""}
          </div>
        </div>
      ` : "";
      return `
        <article class="live-chat-bubble ${item.sender_type === "user" ? "player" : "character"}" data-message-id="${item.id}">
          <div class="live-chat-bubble-head">
            <div class="live-chat-bubble-speaker">${NovelUI.escape(item.speaker_name || item.sender_type)}</div>
            <button class="live-chat-bubble-delete" type="button" data-delete-message-id="${item.id}" aria-label="\u30ed\u30b0\u3092\u524a\u9664" title="\u30ed\u30b0\u3092\u524a\u9664">\u524a\u9664</button>
          </div>
          <div class="live-chat-bubble-text">${NovelUI.escape(item.message_text || "")}</div>
          ${giftMarkup}
        </article>
      `;
    }).join("");
    messageListElement.scrollTop = messageListElement.scrollHeight;
  }

  function renderSelectedImage(selectedImage, options) {
    const {
      selectedImagePanel,
      evaluation,
      isRomance,
      score,
      progressDetailsVisible,
      textboxVisible,
      imageLoading,
      replyLoading,
      messagesVisible,
      novelSpeakerText,
      novelTextValue,
      currentMessageMarkup,
    } = options;
    applyStageDimensions(selectedImage, selectedImagePanel);
    const mediaUrl = selectedImage?.asset?.media_url;
    const evaluationMarkup = evaluation ? `
      <div class="live-chat-eval-badge ${isRomance ? "is-romance" : ""}" id="liveChatEvalBadge">
        <div class="live-chat-eval-head">
          <div>
            <div class="live-chat-eval-label">${NovelUI.escape(localizeEvaluationLabel(evaluation.label, isRomance))}</div>
            <div class="live-chat-eval-score">${isRomance ? "\u604b\u611b\u5ea6 " : ""}${score}</div>
          </div>
          <button class="live-chat-eval-toggle" id="liveChatEvalDetailButton" type="button">${progressDetailsVisible ? "\u8a73\u7d30\u3092\u9589\u3058\u308b" : "\u8a73\u7d30"}</button>
        </div>
        <div class="live-chat-eval-bar">
          <div class="live-chat-eval-fill ${isRomance ? "is-romance" : ""}" style="width:${score}%"></div>
        </div>
        ${evaluation.reason && progressDetailsVisible
          ? `<div class="live-chat-eval-reason">${NovelUI.escape(localizeEvaluationReason(evaluation.reason, isRomance))}</div>`
          : ""}
      </div>
    ` : "";
    const novelMarkup = `
      <div class="live-chat-novel-box ${textboxVisible ? "" : "is-hidden"}" id="liveChatNovelBox">
        <div class="live-chat-novel-speaker" id="liveChatNovelSpeaker">${NovelUI.escape(novelSpeakerText || "")}</div>
        <div class="live-chat-novel-text" id="liveChatNovelText">${NovelUI.escape(novelTextValue || "")}</div>
        <div class="live-chat-novel-continue" id="liveChatNovelContinue" hidden>Enter\u304b\u30af\u30ea\u30c3\u30af\u3067\u7d9a\u304d\u3092\u8aad\u3080</div>
      </div>
    `;
    const loadingHidden = replyLoading ? "" : "hidden";
    const messageMarkup = `
      <aside class="live-chat-message-wrap ${messagesVisible ? "" : "is-hidden"}" id="liveChatMessageWrap">
        <div class="live-chat-message-loading" id="liveChatReplyLoading" ${loadingHidden}>
          <div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div>
          <span>\u4f1a\u8a71\u30ed\u30b0\u3092\u6574\u7406\u3057\u3066\u3044\u307e\u3059...</span>
        </div>
        <div class="live-chat-message-panel" id="liveChatMessageList">${currentMessageMarkup}</div>
      </aside>
    `;
    const stageBody = !mediaUrl
      ? `<div class="empty-panel">\u307e\u3060\u753b\u50cf\u304c\u3042\u308a\u307e\u305b\u3093\u3002</div>`
      : `<img class="live-chat-stage-image" src="${mediaUrl}" alt="selected image">`;
    selectedImagePanel.innerHTML = `
      ${evaluationMarkup}
      <div class="live-chat-stage-frame ${imageLoading ? "is-loading" : ""}">
        ${stageBody}
        ${novelMarkup}
        ${messageMarkup}
      </div>
    `;
  }

  function renderImageGrid(images, imageGrid) {
    if (!imageGrid) return;
    if (!images.length) {
      imageGrid.innerHTML = '<div class="empty-panel">\u753b\u50cf\u5019\u88dc\u304c\u3042\u308a\u307e\u305b\u3093\u3002</div>';
      return;
    }
    const referenceItem = images.find((item) => item.is_reference);
    const referenceId = referenceItem?.id;
    imageGrid.innerHTML = images.map((item) => {
      const mediaUrl = item.asset?.media_url;
      const isReference = item.id === referenceId;
      return `
        <div class="live-chat-thumb-card ${item.is_selected ? "selected" : ""} ${isReference ? "reference" : ""}">
          <button class="live-chat-thumb ${item.is_selected ? "selected" : ""}" type="button" data-image-id="${item.id}">
            ${mediaUrl ? `<img src="${mediaUrl}" alt="thumb">` : `<span>No Image</span>`}
          </button>
          <label class="live-chat-thumb-reference">
            <input type="radio" name="liveChatReferenceImage" data-reference-image-id="${item.id}" ${isReference ? "checked" : ""}>
            <span>基準画像</span>
          </label>
        </div>
      `;
    }).join("");
  }

  window.LiveChatView = {
    formatJson,
    normalizeSelectedCharacterIds,
    renderNovelPage,
    renderNovelBox,
    renderMessages,
    renderSelectedImage,
    renderImageGrid,
  };
})();
