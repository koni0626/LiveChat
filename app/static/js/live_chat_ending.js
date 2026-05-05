(function () {
  function createEndingController(options = {}) {
    const {
      selectedImagePanel,
      shell,
      applyContext,
      getCurrentContext,
      scheduleStageActionPosition,
    } = options;

    function wait(ms) {
      return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function getImageCreatedAtValue(image) {
      const candidates = [
        image?.created_at,
        image?.createdAt,
        image?.asset?.created_at,
        image?.asset?.createdAt,
        image?.state_json?.created_at,
      ];
      for (const value of candidates) {
        const time = Date.parse(value || "");
        if (Number.isFinite(time)) return time;
      }
      const id = Number(image?.id || image?.asset_id || image?.asset?.id || 0);
      return Number.isFinite(id) && id > 0 ? id : 0;
    }

    function getEndingStoryImageIds(story) {
      return new Set(
        ["opening", "ending"]
          .map((key) => story?.images?.[key]?.id)
          .filter(Boolean)
          .map((id) => String(id))
      );
    }

    function getEndingMemoryImages(context, eventImage, excludedImageIds = new Set()) {
      const eventImageId = String(eventImage?.id || "");
      const seen = new Set();
      return (Array.isArray(context?.images) ? context.images : [])
        .filter((image) => image?.asset?.media_url)
        .filter((image) => {
          const id = String(image?.id || image?.asset_id || image?.asset?.media_url || "");
          if (!id || seen.has(id) || excludedImageIds.has(id) || (eventImageId && id === eventImageId)) return false;
          seen.add(id);
          return true;
        })
        .sort((left, right) => getImageCreatedAtValue(left) - getImageCreatedAtValue(right));
    }

    function removeEndingReel() {
      selectedImagePanel?.querySelectorAll(".live-chat-ending-reel").forEach((item) => item.remove());
    }

    function removeStageFloatingHearts() {
      selectedImagePanel?.closest(".live-chat-stage")?.querySelectorAll(".live-chat-affinity-heart").forEach((item) => item.remove());
    }

    function ensureEndingBlackout() {
      if (!selectedImagePanel) return null;
      let blackout = selectedImagePanel.querySelector(".live-chat-ending-blackout");
      if (!blackout) {
        blackout = document.createElement("div");
        blackout.className = "live-chat-ending-blackout";
        blackout.setAttribute("aria-hidden", "true");
        selectedImagePanel.appendChild(blackout);
      }
      return blackout;
    }

    async function playEndingBlackoutIn() {
      const blackout = ensureEndingBlackout();
      if (!blackout) return null;
      window.requestAnimationFrame(() => blackout.classList.add("is-visible"));
      await wait(1350);
      return blackout;
    }

    async function revealEndingBlackout(blackout) {
      if (!blackout) return;
      blackout.classList.add("is-revealing");
      blackout.classList.remove("is-visible");
      await wait(2400);
      blackout.remove();
    }

    async function playEndingHeartbeat(blackout) {
      const target = blackout || ensureEndingBlackout();
      if (!target) return;
      target.classList.add("is-visible", "is-heartbeat");
      if (!target.querySelector(".live-chat-ending-heartbeat")) {
        const heart = document.createElement("div");
        heart.className = "live-chat-ending-heartbeat";
        heart.innerHTML = '<i class="bi bi-heart-fill" aria-hidden="true"></i>';
        target.appendChild(heart);
      }
      await wait(4200);
      target.classList.remove("is-heartbeat");
    }

    function splitEndingStoryText(story) {
      const body = String(story?.body || "").trim();
      const paragraphs = body
        .split(/\n{2,}|\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      return paragraphs.map((text) => ({ text }));
    }

    function splitEndingTextUnits(story) {
      const paragraphs = String(story?.body || "")
        .split(/\n{2,}|\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      const units = [];
      paragraphs.forEach((paragraph, paragraphIndex) => {
        const sentences = paragraph.match(/[^。！？!?]+[。！？!?]?/g) || [paragraph];
        sentences.forEach((sentence, sentenceIndex) => {
          const text = String(sentence || "").trim();
          if (text) units.push({ text, paragraphBreak: paragraphIndex > 0 && sentenceIndex === 0 });
        });
      });
      return units;
    }

    function splitLongEndingUnit(unit, maxLength = 120) {
      const text = String(unit?.text || "");
      if (text.length <= maxLength) return [unit];
      const chunks = [];
      for (let index = 0; index < text.length; index += maxLength) {
        chunks.push({
          text: text.slice(index, index + maxLength),
          paragraphBreak: index === 0 && Boolean(unit.paragraphBreak),
        });
      }
      return chunks;
    }

    function paginateEndingStoryText(story, layer) {
      const fallbackPages = splitEndingStoryText(story);
      if (!layer || !fallbackPages.length) return fallbackPages;
      const measure = document.createElement("section");
      measure.className = "live-chat-ending-story-box is-measuring";
      measure.innerHTML = "<p></p>";
      layer.appendChild(measure);
      const measureText = measure.querySelector("p");
      const fits = (text) => {
        measureText.textContent = text;
        return measure.scrollHeight <= measure.clientHeight + 1;
      };
      const units = splitEndingTextUnits(story).flatMap((unit) => splitLongEndingUnit(unit));
      const pages = [];
      let current = "";
      units.forEach((unit) => {
        const separator = unit.paragraphBreak && current ? "\n\n" : "";
        const next = current ? `${current}${separator}${unit.text}` : unit.text;
        if (current && !fits(next)) {
          pages.push({ text: current });
          current = unit.text;
        } else {
          current = next;
        }
        if (current && !fits(current)) {
          const chunks = splitLongEndingUnit({ text: current }, 80);
          current = "";
          chunks.forEach((chunk) => {
            if (current && !fits(`${current}${chunk.text}`)) {
              pages.push({ text: current });
              current = chunk.text;
            } else {
              current = `${current}${chunk.text}`;
            }
          });
        }
      });
      if (current) pages.push({ text: current });
      measure.remove();
      return pages.length ? pages : fallbackPages;
    }

    function storyImageForPage(story, index, total) {
      const opening = story?.images?.opening?.asset?.media_url;
      const ending = story?.images?.ending?.asset?.media_url;
      if (index >= Math.max(1, Math.floor(total / 2)) && ending) return ending;
      return opening || ending || "";
    }

    function waitForEndingStoryAdvance(layer, ms) {
      return new Promise((resolve) => {
        let done = false;
        let timer = null;
        const finish = (event) => {
          event?.preventDefault?.();
          event?.stopPropagation?.();
          if (done) return;
          done = true;
          window.clearTimeout(timer);
          layer.removeEventListener("click", finish);
          resolve();
        };
        layer.addEventListener("click", finish);
        timer = window.setTimeout(finish, ms);
      });
    }

    async function typeEndingStoryIntro(layer, title) {
      const label = "ショートストーリー";
      const storyTitle = String(title || "ふたりの記憶").trim();
      layer.innerHTML = `
        <div class="live-chat-ending-story-intro">
          <div class="live-chat-ending-story-intro-label"></div>
          <div class="live-chat-ending-story-intro-title"></div>
        </div>
      `;
      const labelElement = layer.querySelector(".live-chat-ending-story-intro-label");
      const titleElement = layer.querySelector(".live-chat-ending-story-intro-title");
      for (let index = 0; index <= label.length; index += 1) {
        labelElement.textContent = label.slice(0, index);
        await wait(72);
      }
      await wait(260);
      for (let index = 0; index <= storyTitle.length; index += 1) {
        titleElement.textContent = storyTitle.slice(0, index);
        await wait(54);
      }
      await waitForEndingStoryAdvance(layer, 1400);
    }

    async function playEndingShortStory(story) {
      if (!selectedImagePanel || !story || story.error) return;
      if (!String(story?.body || "").trim()) return;
      const layer = document.createElement("div");
      layer.className = "live-chat-ending-story";
      layer.setAttribute("aria-hidden", "true");
      selectedImagePanel.appendChild(layer);
      let pages = [];
      const renderPage = (index) => {
        const page = pages[index] || {};
        const mediaUrl = storyImageForPage(story, index, pages.length);
        layer.innerHTML = `
          ${mediaUrl ? `<img class="live-chat-ending-story-image" src="${NovelUI.escape(mediaUrl)}" alt="">` : ""}
          <div class="live-chat-ending-story-shade"></div>
          <section class="live-chat-ending-story-box">
            ${page.title ? `<h3>${NovelUI.escape(page.title)}</h3>` : ""}
            ${page.text ? `<p>${NovelUI.escape(page.text)}</p>` : ""}
          </section>
        `;
      };
      await wait(80);
      layer.classList.add("is-visible");
      await typeEndingStoryIntro(layer, story?.title);
      pages = paginateEndingStoryText(story, layer);
      if (!pages.length) {
        layer.remove();
        return;
      }
      const pageDuration = 60000;
      for (let index = 0; index < pages.length; index += 1) {
        renderPage(index);
        await wait(80);
        layer.classList.remove("is-turning");
        await waitForEndingStoryAdvance(layer, pageDuration);
        if (index < pages.length - 1) {
          layer.classList.add("is-turning");
          await wait(520);
        }
      }
      layer.classList.add("is-leaving");
      await wait(1200);
      layer.remove();
    }

    function playEndingMemoryReel(context, eventImage, shortStory) {
      const images = getEndingMemoryImages(context, eventImage, getEndingStoryImageIds(shortStory));
      if (!selectedImagePanel || !images.length) {
        return wait(900);
      }
      removeEndingReel();
      removeStageFloatingHearts();
      const reel = document.createElement("div");
      reel.className = "live-chat-ending-reel";
      reel.setAttribute("aria-hidden", "true");
      ["click", "pointerdown", "pointerup"].forEach((eventName) => {
        reel.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
        });
      });
      reel.innerHTML = `
        <div class="live-chat-ending-reel-vignette"></div>
        <div class="live-chat-ending-reel-track">
          ${images.map((image, index) => `
            <figure class="live-chat-ending-memory" style="--memory-tilt: ${index % 2 ? "2.2deg" : "-2deg"}">
              <img src="${NovelUI.escape(image.asset.media_url)}" alt="">
            </figure>
          `).join("")}
        </div>
      `;
      selectedImagePanel.appendChild(reel);
      return new Promise((resolve) => {
        let finished = false;
        const finish = () => {
          if (finished) return;
          finished = true;
          reel.classList.add("is-ending-black");
          window.setTimeout(() => {
            reel.remove();
            resolve();
          }, 1600);
        };
        const track = reel.querySelector(".live-chat-ending-reel-track");
        window.requestAnimationFrame(() => {
          const stageHeight = Math.max(1, selectedImagePanel.getBoundingClientRect().height);
          const trackHeight = Math.max(1, track?.scrollHeight || 0);
          const pixelsPerSecond = 90;
          const distance = trackHeight + stageHeight;
          const duration = (distance / pixelsPerSecond) * 1000;
          reel.style.setProperty("--ending-reel-distance", `${Math.round(distance)}px`);
          reel.style.setProperty("--ending-reel-duration", `${Math.round(duration)}ms`);
          reel.classList.add("is-visible");
          track?.addEventListener("animationend", finish, { once: true });
          window.setTimeout(finish, duration + 1300);
        });
      });
    }

    function renderEndingFinalImage(result) {
      const context = result?.context || getCurrentContext?.();
      const shouldRestoreBlackout = Boolean(selectedImagePanel?.querySelector(".live-chat-ending-blackout.is-visible"));
      if (context) applyContext?.(context, { force: true });
      if (result?.event_image) {
        shell?.renderSelectedImage(result.event_image, context || getCurrentContext?.());
        const frame = selectedImagePanel?.querySelector(".live-chat-stage-frame");
        frame?.classList.add("is-ending-final");
      }
      shell?.renderNovel((context || getCurrentContext?.())?.messages || [], context || getCurrentContext?.());
      if (shouldRestoreBlackout) {
        ensureEndingBlackout()?.classList.add("is-visible");
      }
      scheduleStageActionPosition?.();
    }

    async function playAffinityEndingSequence(result) {
      const context = result?.context || getCurrentContext?.();
      shell?.setImageLoading(false, "auto");
      const blackout = await playEndingBlackoutIn();
      await wait(350);
      await playEndingMemoryReel(context, result?.event_image, result?.short_story);
      await playEndingShortStory(result?.short_story);
      const heartbeatBlackout = selectedImagePanel?.querySelector(".live-chat-ending-blackout.is-visible") || blackout;
      await playEndingHeartbeat(heartbeatBlackout);
      renderEndingFinalImage(result);
      const finalBlackout = selectedImagePanel?.querySelector(".live-chat-ending-blackout.is-visible") || blackout;
      await wait(180);
      await revealEndingBlackout(finalBlackout);
    }

    return {
      playAffinityEndingSequence,
    };
  }

  window.LiveChatEnding = {
    createEndingController,
  };
})();
