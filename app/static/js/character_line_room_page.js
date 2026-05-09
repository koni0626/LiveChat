(() => {
  const root = document.querySelector("[data-character-line-room]");
  if (!root) return;

  const roomId = Number(root.dataset.characterLineRoom || 0);
  const roomTitle = document.getElementById("lineRoomTitle");
  const roomMeta = document.getElementById("lineRoomMeta");
  const phoneTitle = document.getElementById("linePhoneTitle");
  const phoneStatus = document.getElementById("linePhoneStatus");
  const participantsList = document.getElementById("lineParticipantList");
  const messageList = document.getElementById("lineMessageList");
  const typing = document.getElementById("lineTypingIndicator");
  const typingName = document.getElementById("lineTypingName");
  const form = document.getElementById("lineComposerForm");
  const input = document.getElementById("lineMessageInput");
  const photoInput = document.getElementById("linePhotoInput");
  const photoPreview = document.getElementById("linePhotoPreview");
  const turnsInput = document.getElementById("lineTurnsInput");
  const sendButton = document.getElementById("lineSendButton");
  const escapeText = (value) => NovelUI.escape(value ?? "");

  let room = null;
  let participants = [];
  let busy = false;

  function avatarHtml(character, className = "line-avatar") {
    const url = character?.thumbnail_asset?.media_url;
    const name = character?.name || "?";
    if (url) return `<img class="${className}" src="${escapeText(url)}" alt="${escapeText(name)}">`;
    return `<div class="${className}">${escapeText(name.slice(0, 1) || "?")}</div>`;
  }

  function renderParticipants() {
    if (!participants.length) {
      participantsList.innerHTML = '<div class="empty-panel mb-0">参加キャラクターがいません。</div>';
      return;
    }
    participantsList.innerHTML = participants.map((character) => `
      <div class="line-participant">
        ${avatarHtml(character, "line-avatar line-avatar-small")}
        <div>
          <div class="line-participant-name">${escapeText(character.name || "Character")}</div>
          <div class="line-participant-sub">${escapeText(character.nickname || "参加中")}</div>
        </div>
      </div>
    `).join("");
  }

  function renderMessage(message, options = {}) {
    const isPlayer = message.sender_type === "player";
    const character = message.character || participants.find((item) => Number(item.id) === Number(message.character_id));
    const name = isPlayer ? "あなた" : (character?.name || "Character");
    const imageUrl = message.image_asset?.media_url || message.image_preview_url || "";
    const row = document.createElement("div");
    row.className = `line-message-row ${isPlayer ? "is-player" : "is-character"}${options.pending ? " is-pending" : ""}`;
    if (options.pending) row.dataset.pendingMessage = "true";
    row.dataset.messageId = message.id || `local-${Date.now()}`;
    row.innerHTML = `
      ${isPlayer ? "" : avatarHtml(character, "line-avatar")}
      <div class="line-message-stack">
        <div class="line-message-name">${escapeText(name)}</div>
        ${imageUrl ? `<img class="line-message-image" src="${escapeText(imageUrl)}" alt="${escapeText(message.image_observation?.label || "写真")}">` : ""}
        <div class="line-bubble">${escapeText(message.body || "")}</div>
        ${message.image_observation?.short_description ? `<div class="line-image-caption">${escapeText(message.image_observation.short_description)}</div>` : ""}
      </div>
    `;
    messageList.appendChild(row);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function renderMessages(messages) {
    messageList.innerHTML = "";
    if (!messages.length) {
      messageList.innerHTML = '<div class="line-empty-chat">最初のテーマを送ると、キャラクターたちが順番に話し始めます。</div>';
      return;
    }
    messages.forEach((message) => renderMessage(message));
  }

  function setTyping(character) {
    const currentAvatar = document.getElementById("lineTypingAvatar");
    typingName.textContent = `${character?.name || "誰か"} が入力中`;
    if (currentAvatar) {
      const url = character?.thumbnail_asset?.media_url;
      currentAvatar.className = "line-avatar line-avatar-small";
      currentAvatar.textContent = url ? "" : String(character?.name || "?").slice(0, 1);
      currentAvatar.style.backgroundImage = url ? `url("${url}")` : "";
    }
    typing.hidden = false;
    messageList.scrollTop = messageList.scrollHeight;
  }

  function clearTyping() {
    typing.hidden = true;
  }

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function revealMessages(messages) {
    for (const message of messages) {
      const character = message.character || participants.find((item) => Number(item.id) === Number(message.character_id));
      setTyping(character);
      await wait(520);
      clearTyping();
      renderMessage(message);
      await wait(120);
    }
  }

  function setBusy(value) {
    busy = value;
    sendButton.disabled = value;
    input.disabled = value;
    photoInput.disabled = value;
    turnsInput.disabled = value;
    phoneStatus.textContent = value ? "入力中..." : `${participants.length} members`;
  }

  function renderPhotoPreview() {
    const file = photoInput.files?.[0];
    if (!file) {
      photoPreview.hidden = true;
      photoPreview.innerHTML = "";
      return;
    }
    const url = URL.createObjectURL(file);
    photoPreview.hidden = false;
    photoPreview.innerHTML = `
      <img src="${url}" alt="選択した写真">
      <div>
        <div class="line-photo-preview-name">${escapeText(file.name)}</div>
        <button class="btn btn-sm btn-outline-dark" type="button" id="linePhotoClearButton">
          <i class="bi bi-x-lg"></i>
          <span>解除</span>
        </button>
      </div>
    `;
    photoPreview.querySelector("#linePhotoClearButton")?.addEventListener("click", () => {
      photoInput.value = "";
      renderPhotoPreview();
    });
  }

  function imageFileFromEvent(event) {
    const files = [...(event.dataTransfer?.files || [])];
    return files.find((file) => String(file.type || "").startsWith("image/")) || null;
  }

  function setPhotoFile(file) {
    if (!file || !photoInput) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    photoInput.files = transfer.files;
    renderPhotoPreview();
  }

  async function loadRoom() {
    const payload = await NovelUI.api(`/api/v1/line/rooms/${roomId}`);
    room = payload.room;
    participants = Array.isArray(payload.participants) ? payload.participants : [];
    roomTitle.textContent = room?.title || "LINE";
    phoneTitle.textContent = room?.title || "LINE";
    roomMeta.textContent = `${participants.length}人のルーム`;
    phoneStatus.textContent = `${participants.length} members`;
    renderParticipants();
    renderMessages(Array.isArray(payload.messages) ? payload.messages : []);
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    const body = input.value.trim();
    const file = photoInput.files?.[0] || null;
    if (!body && !file) return;
    const turns = Math.max(4, Math.min(Number(turnsInput.value || 20), 40));
    const localImageUrl = file ? URL.createObjectURL(file) : "";
    input.value = "";
    photoInput.value = "";
    renderPhotoPreview();
    if (messageList.querySelector(".line-empty-chat")) messageList.innerHTML = "";
    renderMessage({ sender_type: "player", body: body || "写真を送信", image_preview_url: localImageUrl }, { pending: true });
    setBusy(true);
    try {
      let result;
      if (file) {
        const formData = new FormData();
        formData.append("body", body);
        formData.append("turns", String(turns));
        formData.append("file", file);
        const response = await fetch(`/api/v1/line/rooms/${roomId}/messages`, {
          method: "POST",
          body: formData,
          credentials: "same-origin",
          cache: "no-store",
        });
        const payload = await response.json().catch(() => ({}));
        result = payload && typeof payload === "object" && "data" in payload ? payload.data : payload;
        if (!response.ok) throw new Error(result?.message || payload?.message || `HTTP ${response.status}`);
      } else {
        result = await NovelUI.api(`/api/v1/line/rooms/${roomId}/messages`, {
          method: "POST",
          body: { body, turns },
        });
      }
      const pendingRow = messageList.querySelector("[data-pending-message='true']");
      if (pendingRow) pendingRow.remove();
      if (result.player_message) renderMessage(result.player_message);
      await revealMessages(Array.isArray(result.messages) ? result.messages : []);
      if (result.room) {
        room = result.room;
        roomMeta.textContent = room.last_theme ? `最新テーマ: ${room.last_theme}` : `${participants.length}人のルーム`;
      }
    } catch (error) {
      NovelUI.toast(error.message || "LINE会話の生成に失敗しました。", "danger");
      await loadRoom().catch(() => {});
    } finally {
      if (localImageUrl) URL.revokeObjectURL(localImageUrl);
      clearTyping();
      setBusy(false);
      input.focus();
    }
  });

  photoInput?.addEventListener("change", renderPhotoPreview);

  form?.addEventListener("dragenter", (event) => {
    if (!imageFileFromEvent(event)) return;
    event.preventDefault();
    form.classList.add("is-dragging-image");
  });

  form?.addEventListener("dragover", (event) => {
    if (!imageFileFromEvent(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    form.classList.add("is-dragging-image");
  });

  form?.addEventListener("dragleave", (event) => {
    if (form.contains(event.relatedTarget)) return;
    form.classList.remove("is-dragging-image");
  });

  form?.addEventListener("drop", (event) => {
    const file = imageFileFromEvent(event);
    if (!file) return;
    event.preventDefault();
    form.classList.remove("is-dragging-image");
    setPhotoFile(file);
  });

  loadRoom().catch((error) => {
    NovelUI.toast(error.message || "LINEルームの読み込みに失敗しました。", "danger");
  });
})();
