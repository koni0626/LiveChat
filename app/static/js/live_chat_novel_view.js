(function () {
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
      if (" \n、。！？!?・」』）)".includes(ch)) return index;
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
    const cueHeight = 36;
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

  function renderNovelPage(novelPageState, novelTextElement, cueElement, novelElements = {}) {
    if (!novelTextElement) return novelPageState;
    const pages = novelPageState.pages || [];
    const pageIndex = Math.max(0, Math.min(novelPageState.pageIndex || 0, Math.max(0, pages.length - 1)));
    const nextState = { ...novelPageState, pageIndex };
    const choices = Array.isArray(nextState.choices) ? nextState.choices : [];
    const isChoicePage = choices.length > 0 && pageIndex === pages.length - 1 && nextState.choicePage === true;
    const showChoices = choices.length > 0 && pageIndex === pages.length - 1;
    novelTextElement.textContent = isChoicePage ? "" : (pages[pageIndex] || "");
    if (novelElements.novelChoiceList) {
      novelElements.novelChoiceList.hidden = !showChoices;
      novelElements.novelChoiceList.innerHTML = showChoices
        ? `
          <div class="live-chat-novel-choice-copy">次の行動を選んでください</div>
          <div class="live-chat-novel-choice-buttons">
            ${choices.map((choice) => `
              <button class="live-chat-choice-button live-chat-novel-choice-button" type="button" data-scene-choice-id="${NovelUI.escape(choice.id)}">
                ${NovelUI.escape(choice.label)}
              </button>
            `).join("")}
          </div>
        `
        : "";
    }
    const showPager = pages.length > 1;
    if (cueElement) {
      cueElement.hidden = !showPager;
      cueElement.textContent = showPager ? `${pageIndex + 1} / ${pages.length}` : "";
    }
    if (novelElements.novelPager) {
      novelElements.novelPager.hidden = !showPager;
    }
    if (novelElements.novelPrevButton) {
      novelElements.novelPrevButton.disabled = !showPager || pageIndex <= 0;
      novelElements.novelPrevButton.hidden = !showPager;
    }
    if (novelElements.novelNextButton) {
      novelElements.novelNextButton.disabled = !showPager || pageIndex >= pages.length - 1;
      novelElements.novelNextButton.hidden = !showPager;
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
    const { novelSpeaker, novelText, novelChoiceList, novelContinue, novelBox, novelPrevButton, novelNextButton } = novelElements;
    if (!novelSpeaker || !novelText) {
      return novelPageState;
    }
    if (replyLoading) {
      const activeCharacter = (currentContext?.characters || [])[0] || {};
      novelSpeaker.textContent = activeCharacter.name || item?.speaker_name || "";
      novelText.innerHTML = `
        <span class="live-chat-typing" aria-label="キャラクターが考え中">
          <span class="live-chat-typing-dot"></span>
          <span class="live-chat-typing-dot"></span>
          <span class="live-chat-typing-dot"></span>
        </span>
      `;
      if (novelContinue) novelContinue.hidden = true;
      if (novelElements.novelPager) novelElements.novelPager.hidden = true;
      if (novelChoiceList) {
        novelChoiceList.hidden = true;
        novelChoiceList.innerHTML = "";
      }
      if (novelPrevButton) novelPrevButton.disabled = true;
      if (novelPrevButton) novelPrevButton.hidden = true;
      if (novelNextButton) novelNextButton.disabled = true;
      if (novelNextButton) novelNextButton.hidden = true;
      return { messageId: null, pages: [], pageIndex: 0 };
    }
    if (!item) {
      novelSpeaker.textContent = "";
      novelText.textContent = "まだセリフがありません。";
      if (novelContinue) novelContinue.hidden = true;
      if (novelElements.novelPager) novelElements.novelPager.hidden = true;
      if (novelChoiceList) {
        novelChoiceList.hidden = true;
        novelChoiceList.innerHTML = "";
      }
      if (novelPrevButton) novelPrevButton.disabled = true;
      if (novelPrevButton) novelPrevButton.hidden = true;
      if (novelNextButton) novelNextButton.disabled = true;
      if (novelNextButton) novelNextButton.hidden = true;
      return { messageId: null, pages: [], pageIndex: 0 };
    }
    novelSpeaker.textContent = item.speaker_name || "";
    const pages = paginateNovelText(item.message_text || "", {
      novelBox,
      novelText,
      novelSpeaker,
    });
    const choiceState = currentContext?.state?.state_json?.scene_choices || {};
    const choices = Array.isArray(choiceState.choices) ? choiceState.choices : [];
    const choiceSignature = choices.map((choice) => `${choice.id}:${choice.label}`).join("|");
    const choiceNeedsOwnPage = choices.length > 0 && pages.length > 1;
    const displayPages = choiceNeedsOwnPage ? [...pages, ""] : pages;
    const isSameMessage = novelPageState.messageId === item.id && novelPageState.choiceSignature === choiceSignature;
    return renderNovelPage(
      {
        messageId: item.id,
        pages: displayPages,
        choices,
        choicePage: choiceNeedsOwnPage,
        choiceSignature,
        pageIndex: isSameMessage ? Math.min(novelPageState.pageIndex, Math.max(0, displayPages.length - 1)) : 0,
      },
      novelText,
      novelContinue,
      novelElements
    );
  }

  window.LiveChatNovelView = {
    renderNovelPage,
    renderNovelBox,
  };
})();
