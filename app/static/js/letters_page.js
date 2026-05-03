(() => {
  const listHost = document.getElementById("letterList");
  const countLabel = document.getElementById("letterCountLabel");
  const refreshButton = document.getElementById("letterRefreshButton");
  const modalElement = document.getElementById("letterModal");
  document.body.appendChild(modalElement);
  const modal = new bootstrap.Modal(modalElement);
  const modalTitle = document.getElementById("letterModalTitle");
  const modalFrom = document.getElementById("letterModalFrom");
  const modalBody = document.getElementById("letterModalBody");
  const modalImageWrap = document.getElementById("letterModalImageWrap");
  const modalImage = document.getElementById("letterModalImage");
  const returnLink = document.getElementById("letterReturnLink");
  const archiveButton = document.getElementById("letterArchiveButton");
  let currentLetterId = null;

  function letterImage(letter) {
    return letter.image_asset?.media_url || letter.sender_character?.thumbnail_asset?.media_url || letter.sender_character?.base_asset?.media_url || "";
  }

  function normalizeLetterText(value) {
    return String(value || "")
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trim();
  }

  function renderEmpty() {
    listHost.innerHTML = `
      <div class="empty-panel letter-empty">
        <i class="bi bi-envelope-open"></i>
        <div>
          <strong>まだメールは届いていません。</strong>
          <p>ライブチャットで印象的な会話が進むと、キャラクターからここにメールが届きます。</p>
        </div>
      </div>
    `;
  }

  function renderLetters(letters) {
    countLabel.textContent = `${letters.length} letters`;
    if (!letters.length) {
      renderEmpty();
      return;
    }
    listHost.innerHTML = letters.map((letter) => {
      const imageUrl = letterImage(letter);
      const senderName = letter.sender_character?.name || "Character";
      const isUnread = letter.status === "unread";
      return `
        <article class="letter-card ${isUnread ? "is-unread" : ""}" data-letter-id="${letter.id}">
          <div class="letter-card-thumb">
            ${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="">` : `<i class="bi bi-envelope-heart"></i>`}
          </div>
          <div class="letter-card-copy">
            <div class="letter-card-meta">
              <span>${NovelUI.escape(senderName)}</span>
              ${isUnread ? `<span class="letter-unread-badge">NEW</span>` : ""}
            </div>
            <h4>${NovelUI.escape(letter.subject || "あなたへ")}</h4>
            <p>${NovelUI.escape(letter.summary || letter.trigger_reason || "キャラクターからメールが届いています。")}</p>
          </div>
        </article>
      `;
    }).join("");
  }

  async function loadLetters() {
    const letters = await NovelUI.api("/api/v1/letters");
    renderLetters(Array.isArray(letters) ? letters : []);
  }

  async function openLetter(letterId) {
    currentLetterId = letterId;
    const letter = await NovelUI.api(`/api/v1/letters/${letterId}`);
    await NovelUI.api(`/api/v1/letters/${letterId}/read`, { method: "POST", body: {} });
    const imageUrl = letterImage(letter);
    modalTitle.textContent = letter.subject || "あなたへ";
    modalFrom.textContent = `${letter.sender_character?.name || "Character"} から`;
    modalBody.textContent = normalizeLetterText(letter.body);
    returnLink.href = letter.return_url || "#";
    if (imageUrl) {
      modalImage.src = imageUrl;
      modalImageWrap.classList.remove("d-none");
    } else {
      modalImage.removeAttribute("src");
      modalImageWrap.classList.add("d-none");
    }
    modal.show();
    await loadLetters();
    NovelUI.refreshLetterBadge?.();
  }

  listHost.addEventListener("click", (event) => {
    const card = event.target.closest("[data-letter-id]");
    if (!card) return;
    openLetter(Number(card.dataset.letterId)).catch((error) => {
      NovelUI.toast(error.message || "メールを開けませんでした。", "danger");
    });
  });

  archiveButton.addEventListener("click", async () => {
    if (!currentLetterId) return;
    await NovelUI.api(`/api/v1/letters/${currentLetterId}`, { method: "DELETE" });
    NovelUI.toast("メールを削除しました。");
    modal.hide();
    currentLetterId = null;
    await loadLetters();
    NovelUI.refreshLetterBadge?.();
  });

  refreshButton.addEventListener("click", () => {
    loadLetters().catch((error) => {
      NovelUI.toast(error.message || "メールの読み込みに失敗しました。", "danger");
    });
  });

  loadLetters().catch((error) => {
    NovelUI.toast(error.message || "メールの読み込みに失敗しました。", "danger");
  });
})();
