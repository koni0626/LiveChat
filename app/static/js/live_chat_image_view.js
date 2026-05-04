(function () {
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
      textboxVisible,
      imageLoading,
      modeBadgeText,
      novelSpeakerText,
      novelTextValue,
    } = options;
    applyStageDimensions(selectedImage, selectedImagePanel);
    const mediaUrl = selectedImage?.asset?.media_url;
    const previousMediaUrl = selectedImagePanel.querySelector(".live-chat-stage-image")?.getAttribute("src") || "";
    const shouldFadeInImage = Boolean(mediaUrl && previousMediaUrl && previousMediaUrl !== mediaUrl);
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
      : `<img class="live-chat-stage-image ${shouldFadeInImage ? "is-entering" : "is-visible"}" src="${mediaUrl}" alt="selected image">`;
    const modeBadgeMarkup = modeBadgeText
      ? `<div class="live-chat-mode-badge">${NovelUI.escape(modeBadgeText)}</div>`
      : "";
    selectedImagePanel.innerHTML = `
      <div class="live-chat-stage-frame ${imageLoading ? "is-loading" : ""}">
        ${modeBadgeMarkup}
        ${stageBody}
        ${novelMarkup}
      </div>
    `;
    const stageImage = selectedImagePanel.querySelector(".live-chat-stage-image");
    if (stageImage) {
      stageImage.addEventListener("load", () => {
        applyNaturalStageDimensions(selectedImagePanel, stageImage.naturalWidth, stageImage.naturalHeight);
        if (stageImage.classList.contains("is-entering")) {
          window.requestAnimationFrame(() => stageImage.classList.add("is-visible"));
        }
      }, { once: true });
      if (stageImage.complete && stageImage.naturalWidth > 0 && stageImage.naturalHeight > 0) {
        applyNaturalStageDimensions(selectedImagePanel, stageImage.naturalWidth, stageImage.naturalHeight);
        if (stageImage.classList.contains("is-entering")) {
          window.requestAnimationFrame(() => stageImage.classList.add("is-visible"));
        }
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
