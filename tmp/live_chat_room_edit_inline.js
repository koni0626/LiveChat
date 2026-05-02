
(() => {
  const projectId = Number(1);
  const roomId = Number(document.querySelector(".live-chat-room-edit-page")?.dataset.roomId || 0);
  const roomForm = document.getElementById("liveChatRoomForm");
  if (!roomForm) return;
  const characterSelect = document.getElementById("liveChatRoomCharacterSelect");
  const outfitInput = document.getElementById("liveChatRoomOutfitInput");
  const outfitPicker = document.getElementById("liveChatRoomOutfitPicker");
  const outfitPickerController = window.OutfitPicker.create({
    characterSelect,
    input: outfitInput,
    picker: outfitPicker,
  });
  const objectivePreview = document.getElementById("liveChatRoomObjectivePreview");
  const objectiveEditButton = document.getElementById("liveChatRoomObjectiveEditButton");
  const objectiveGenerateButton = document.getElementById("liveChatRoomObjectiveGenerateButton");
  const objectiveModalElement = document.getElementById("liveChatRoomObjectiveModal");
  if (objectiveModalElement) document.body.appendChild(objectiveModalElement);
  const objectiveModal = objectiveModalElement ? new bootstrap.Modal(objectiveModalElement) : null;
  const objectiveMarkdownInput = document.getElementById("liveChatRoomObjectiveMarkdownInput");
  const objectiveMarkdownPreview = document.getElementById("liveChatRoomObjectiveMarkdownPreview");
  const objectiveApplyButton = document.getElementById("liveChatRoomObjectiveApplyButton");
  const proxyPlayerObjectivePreview = document.getElementById("liveChatRoomProxyPlayerObjectivePreview");
  const proxyPlayerObjectiveEditButton = document.getElementById("liveChatRoomProxyPlayerObjectiveEditButton");
  const proxyPlayerObjectiveModalElement = document.getElementById("liveChatRoomProxyPlayerObjectiveModal");
  if (proxyPlayerObjectiveModalElement) document.body.appendChild(proxyPlayerObjectiveModalElement);
  const proxyPlayerObjectiveModal = proxyPlayerObjectiveModalElement ? new bootstrap.Modal(proxyPlayerObjectiveModalElement) : null;
  const proxyPlayerObjectiveMarkdownInput = document.getElementById("liveChatRoomProxyPlayerObjectiveMarkdownInput");
  const proxyPlayerObjectiveMarkdownPreview = document.getElementById("liveChatRoomProxyPlayerObjectiveMarkdownPreview");
  const proxyPlayerObjectiveApplyButton = document.getElementById("liveChatRoomProxyPlayerObjectiveApplyButton");

  function escapeHtml(value) {
    return NovelUI.escape(value ?? "");
  }

  function renderInlineMarkdown(text) {
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function markdownToHtml(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let inList = false;
    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }
    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (!trimmed) {
        closeList();
        continue;
      }
      if (trimmed.startsWith("## ")) {
        closeList();
        html.push(`<h5>${renderInlineMarkdown(trimmed.slice(3))}</h5>`);
      } else if (trimmed.startsWith("# ")) {
        closeList();
        html.push(`<h4>${renderInlineMarkdown(trimmed.slice(2))}</h4>`);
      } else if (trimmed.startsWith("> ")) {
        closeList();
        html.push(`<blockquote>${renderInlineMarkdown(trimmed.slice(2))}</blockquote>`);
      } else if (trimmed.startsWith("- ")) {
        if (!inList) {
          html.push("<ul>");
          inList = true;
        }
        html.push(`<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`);
      } else {
        closeList();
        html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
      }
    }
    closeList();
    return html.join("") || '<p class="text-muted mb-0">まだ入力されていません。</p>';
  }

  function renderObjectivePreview() {
    objectivePreview.innerHTML = markdownToHtml(roomForm.conversation_objective.value);
  }

  function renderProxyPlayerObjectivePreview() {
    proxyPlayerObjectivePreview.innerHTML = markdownToHtml(roomForm.proxy_player_objective.value);
  }

  function openObjectiveEditor() {
    objectiveMarkdownInput.value = roomForm.conversation_objective.value || "";
    objectiveMarkdownPreview.innerHTML = markdownToHtml(objectiveMarkdownInput.value);
    objectiveModal.show();
    setTimeout(() => objectiveMarkdownInput.focus(), 180);
  }

  function applyObjectiveEditor() {
    roomForm.conversation_objective.value = objectiveMarkdownInput.value;
    renderObjectivePreview();
    objectiveModal.hide();
  }

  function openProxyPlayerObjectiveEditor() {
    proxyPlayerObjectiveMarkdownInput.value = roomForm.proxy_player_objective.value || "";
    proxyPlayerObjectiveMarkdownPreview.innerHTML = markdownToHtml(proxyPlayerObjectiveMarkdownInput.value);
    proxyPlayerObjectiveModal.show();
    setTimeout(() => proxyPlayerObjectiveMarkdownInput.focus(), 180);
  }

  function applyProxyPlayerObjectiveEditor() {
    roomForm.proxy_player_objective.value = proxyPlayerObjectiveMarkdownInput.value;
    renderProxyPlayerObjectivePreview();
    proxyPlayerObjectiveModal.hide();
  }

  function setObjectiveGenerating(active) {
    if (!objectiveGenerateButton) return;
    objectiveGenerateButton.disabled = active;
    objectiveGenerateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>生成中...'
      : '<i class="bi bi-stars"></i><span>自動生成</span>';
  }

  async function generateObjectiveDraft() {
    const characterId = Number(roomForm.character_id.value || 0);
    if (!characterId) {
      NovelUI.toast("先にキャラクターを選択してください。", "warning");
      characterSelect.focus();
      return;
    }
    setObjectiveGenerating(true);
    try {
      const draft = await NovelUI.api(`/api/v1/projects/${projectId}/chat/rooms/objective-draft`, {
        method: "POST",
        body: { character_id: characterId },
      });
      if (!roomForm.title.value.trim()) {
        roomForm.title.value = draft.title || "";
      }
      if (!roomForm.description.value.trim()) {
        roomForm.description.value = draft.description || "";
      }
      roomForm.conversation_objective.value = draft.conversation_objective || "";
      roomForm.proxy_player_objective.value = draft.proxy_player_objective || "";
      if (!roomForm.proxy_player_gender.value.trim()) {
        roomForm.proxy_player_gender.value = draft.proxy_player_gender || "";
      }
      if (!roomForm.proxy_player_speech_style.value.trim()) {
        roomForm.proxy_player_speech_style.value = draft.proxy_player_speech_style || "";
      }
      renderObjectivePreview();
      renderProxyPlayerObjectivePreview();
      NovelUI.toast("キャラクター設定から指示を自動生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "指示の自動生成に失敗しました。", "danger");
    } finally {
      setObjectiveGenerating(false);
    }
  }

  function fillRoom(room) {
    roomForm.title.value = room.title || "";
    roomForm.character_id.value = room.character_id || "";
    outfitInput.value = room.default_outfit_id || "";
    roomForm.status.value = room.status || "draft";
    roomForm.description.value = room.description || "";
    roomForm.conversation_objective.value = room.conversation_objective || "";
    roomForm.proxy_player_objective.value = room.proxy_player_objective || "";
    roomForm.proxy_player_gender.value = room.proxy_player_gender || "";
    roomForm.proxy_player_speech_style.value = room.proxy_player_speech_style || "";
    renderObjectivePreview();
    renderProxyPlayerObjectivePreview();
  }

  async function loadCharacters() {
    const data = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    const characters = Array.isArray(data) ? data : [];
    characterSelect.innerHTML = [
      '<option value="">キャラクターを選択</option>',
      ...characters.map((item) => `<option value="${item.id}">${NovelUI.escape(item.name || "Unnamed")}</option>`),
    ].join("");
  }

  async function loadOutfits(selectedOutfitId = "") {
    return outfitPickerController.load(selectedOutfitId);
  }

  async function loadRoom() {
    if (!roomId) return;
    const room = await NovelUI.api(`/api/v1/chat/rooms/${roomId}`);
    fillRoom(room);
    await loadOutfits(room.default_outfit_id || "");
  }

  async function saveRoom(event) {
    event.preventDefault();
    const body = {
      title: roomForm.title.value.trim(),
      character_id: Number(roomForm.character_id.value || 0),
      default_outfit_id: outfitInput.value ? Number(outfitInput.value) : null,
      status: roomForm.status.value,
      description: roomForm.description.value.trim(),
      conversation_objective: roomForm.conversation_objective.value.trim(),
      proxy_player_objective: roomForm.proxy_player_objective.value.trim(),
      proxy_player_gender: roomForm.proxy_player_gender.value.trim(),
      proxy_player_speech_style: roomForm.proxy_player_speech_style.value.trim(),
    };
    if (!body.conversation_objective) {
      NovelUI.toast("キャラクターへの指示を入力してください。", "warning");
      openObjectiveEditor();
      return;
    }
    const path = roomId
      ? `/api/v1/chat/rooms/${roomId}`
      : `/api/v1/projects/${projectId}/chat/rooms`;
    const method = roomId ? "PATCH" : "POST";
    const saved = await NovelUI.api(path, { method, body });
    NovelUI.toast(roomId ? "ルームを更新しました。" : "ルームを作成しました。");
    window.location.href = `/projects/${projectId}/live-chat/rooms`;
    return saved;
  }

  roomForm.addEventListener("submit", (event) => {
    saveRoom(event).catch((error) => NovelUI.toast(error.message || "ルーム保存に失敗しました。", "danger"));
  });

  objectiveEditButton?.addEventListener("click", openObjectiveEditor);
  objectiveGenerateButton?.addEventListener("click", generateObjectiveDraft);
  objectiveApplyButton?.addEventListener("click", applyObjectiveEditor);
  objectiveMarkdownInput?.addEventListener("input", () => {
    objectiveMarkdownPreview.innerHTML = markdownToHtml(objectiveMarkdownInput.value);
  });
  proxyPlayerObjectiveEditButton?.addEventListener("click", openProxyPlayerObjectiveEditor);
  proxyPlayerObjectiveApplyButton?.addEventListener("click", applyProxyPlayerObjectiveEditor);
  proxyPlayerObjectiveMarkdownInput?.addEventListener("input", () => {
    proxyPlayerObjectiveMarkdownPreview.innerHTML = markdownToHtml(proxyPlayerObjectiveMarkdownInput.value);
  });

  renderObjectivePreview();
  renderProxyPlayerObjectivePreview();
  loadCharacters()
    .then(() => roomId ? loadRoom() : loadOutfits(""))
    .catch((error) => NovelUI.toast(error.message || "ルーム設定の読み込みに失敗しました。", "danger"));
})();
