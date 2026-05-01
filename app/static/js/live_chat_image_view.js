(function () {
  function localizeEvaluationLabel(label, isRomance) {
    const text = String(label || "").trim();
    if (!text) {
      return isRomance ? "恋愛度" : "進行度";
    }
    const lowered = text.toLowerCase();
    if (lowered === "love progress") return "恋愛度";
    if (lowered === "good progress") return "良好";
    if (lowered === "interest progress") return "関心度";
    if (lowered === "progress") return "進行度";
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
        ? "直近の会話と反応から、恋愛度がどの程度進んだかを評価しています。"
        : "直近の会話と反応から、進行度を評価しています。";
    }
    return localized;
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

  function applyNaturalStageDimensions(selectedImagePanel, naturalWidth, naturalHeight) {
    const widthNum = Number(naturalWidth);
    const heightNum = Number(naturalHeight);
    if (!selectedImagePanel || !(widthNum > 0) || !(heightNum > 0)) return;
    selectedImagePanel.style.setProperty("--stage-width", String(widthNum));
    selectedImagePanel.style.setProperty("--stage-height", String(heightNum));
    const viewportHeight = Math.max(window.innerHeight || 0, 720);
    const desktopOffset = 250;
    const mobileOffset = 320;
    const maxHeight = Math.max(
      window.innerWidth <= 1200 ? 360 : 420,
      viewportHeight - (window.innerWidth <= 1200 ? mobileOffset : desktopOffset)
    );
    const stageParent = selectedImagePanel.parentElement;
    const availableWidth = stageParent ? stageParent.clientWidth : selectedImagePanel.clientWidth;

    let width = Math.min(availableWidth, maxHeight * (widthNum / heightNum));
    let height = width * (heightNum / widthNum);

    if (height > maxHeight) {
      height = maxHeight;
      width = height * (widthNum / heightNum);
    }

    selectedImagePanel.style.width = `${Math.round(width)}px`;
    selectedImagePanel.style.height = "auto";
    selectedImagePanel.style.setProperty("--rendered-stage-height", `${Math.round(height)}px`);
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
      novelSpeakerText,
      novelTextValue,
    } = options;
    applyStageDimensions(selectedImage, selectedImagePanel);
    const mediaUrl = selectedImage?.asset?.media_url;
    const evaluationMarkup = evaluation ? `
      <div class="live-chat-eval-badge ${isRomance ? "is-romance" : ""}" id="liveChatEvalBadge">
        <div class="live-chat-eval-head">
          <div>
            <div class="live-chat-eval-label">${NovelUI.escape(localizeEvaluationLabel(evaluation.label, isRomance))}</div>
            <div class="live-chat-eval-score">${isRomance ? "恋愛度 " : ""}${score}</div>
          </div>
          <button class="live-chat-eval-toggle" id="liveChatEvalDetailButton" type="button">${progressDetailsVisible ? "詳細を閉じる" : "詳細"}</button>
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
        <div class="live-chat-novel-choice-list" id="liveChatNovelChoiceList" hidden></div>
        <div class="live-chat-novel-footer">
          <div class="live-chat-novel-continue" id="liveChatNovelContinue" hidden></div>
          <div class="live-chat-novel-pager" id="liveChatNovelPager" aria-label="セリフページ送り" hidden>
            <button class="live-chat-novel-page-button" type="button" id="liveChatNovelPrevButton">Prev</button>
            <button class="live-chat-novel-page-button" type="button" id="liveChatNovelNextButton">Next</button>
          </div>
        </div>
      </div>
    `;
    const stageBody = !mediaUrl
      ? '<div class="empty-panel">まだ画像がありません。</div>'
      : `<img class="live-chat-stage-image" src="${mediaUrl}" alt="selected image">`;
    selectedImagePanel.innerHTML = `
      ${evaluationMarkup}
      <div class="live-chat-stage-frame ${imageLoading ? "is-loading" : ""}">
        ${stageBody}
        ${novelMarkup}
      </div>
    `;
    const stageImage = selectedImagePanel.querySelector(".live-chat-stage-image");
    if (stageImage) {
      stageImage.addEventListener("load", () => {
        applyNaturalStageDimensions(selectedImagePanel, stageImage.naturalWidth, stageImage.naturalHeight);
      }, { once: true });
      if (stageImage.complete && stageImage.naturalWidth > 0 && stageImage.naturalHeight > 0) {
        applyNaturalStageDimensions(selectedImagePanel, stageImage.naturalWidth, stageImage.naturalHeight);
      }
    }
  }

  function renderImageGrid(images, imageGrid) {
    if (!imageGrid) return;
    if (!images.length) {
      imageGrid.innerHTML = '<div class="empty-panel">画像候補がありません。</div>';
      return;
    }
    imageGrid.innerHTML = images.map((item) => {
      const mediaUrl = item.asset?.media_url;
      return `
        <div class="live-chat-thumb-card ${item.is_selected ? "selected" : ""}">
          <button class="live-chat-thumb ${item.is_selected ? "selected" : ""}" type="button" data-image-id="${item.id}">
            ${mediaUrl ? `<img src="${mediaUrl}" alt="thumb">` : "<span>No Image</span>"}
          </button>
        </div>
      `;
    }).join("");
  }

  window.LiveChatImageView = {
    renderSelectedImage,
    renderImageGrid,
  };
})();
