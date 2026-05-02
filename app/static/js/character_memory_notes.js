(function () {
  const root = document.querySelector("[data-character-editor]");
  if (!root) return;

  const characterId = root.dataset.characterId ? Number(root.dataset.characterId) : null;
  const canManageProject = root.dataset.canManageProject !== "false";
  const form = document.getElementById("characterMemoryNoteForm");
  const list = document.getElementById("characterMemoryNoteList");
  if (!form || !list) return;

  const categories = {
    preference: "好み",
    habit: "癖",
    value: "価値観",
    weakness: "弱点",
    relationship: "関係性",
    foreshadowing: "伏線",
    fun_fact: "面白い設定",
    other: "その他",
  };

  const sources = {
    manual: "手動追加",
    live_chat_ai: "チャットAI抽出",
  };

  function endpoint(noteId) {
    const base = `/api/v1/characters/${characterId}/memory-notes`;
    return noteId ? `${base}/${noteId}` : base;
  }

  function optionList(selected) {
    return Object.entries(categories)
      .map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`)
      .join("");
  }

  function formatDate(value) {
    if (!value) return "日時なし";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "日時なし";
    return date.toLocaleString("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function confidenceLabel(value) {
    const confidence = Number(value);
    if (!Number.isFinite(confidence)) return "信頼度 -";
    return `信頼度 ${Math.round(confidence * 100)}%`;
  }

  function renderEmpty(message) {
    list.innerHTML = `
      <div class="character-memory-note-empty">
        <i class="bi bi-journal-sparkle"></i>
        <span>${NovelUI.escape(message)}</span>
      </div>
    `;
  }

  function renderNotes(notes) {
    if (!characterId) {
      form.hidden = true;
      renderEmpty("キャラクター保存後にAIメモを追加できます。");
      return;
    }
    form.hidden = !canManageProject;
    if (!notes.length) {
      renderEmpty("まだAIメモはありません。会話で増えた面白い設定や、手動で残したい設定がここに表示されます。");
      return;
    }
    list.innerHTML = notes
      .map((note) => {
        const disabledClass = note.enabled ? "" : " is-disabled";
        const sourceLabel = sources[note.source_type] || note.source_type || "出所不明";
        const statusLabel = note.enabled ? "有効" : "無効";
        const pinnedLabel = note.pinned ? "優先" : "通常";
        return `
          <article class="character-memory-note-item${disabledClass}" data-note-id="${note.id}">
            <div class="character-memory-note-item-head">
              <select class="form-select form-select-sm" data-field="category" ${canManageProject ? "" : "disabled"}>
                ${optionList(note.category || "other")}
              </select>
              <span class="character-memory-note-source">${NovelUI.escape(sourceLabel)}</span>
              <span class="character-memory-note-meta">${NovelUI.escape(confidenceLabel(note.confidence))}</span>
              <span class="character-memory-note-meta">更新 ${NovelUI.escape(formatDate(note.updated_at || note.created_at))}</span>
            </div>
            <textarea class="form-control" rows="3" data-field="note" ${canManageProject ? "" : "disabled"}>${NovelUI.escape(note.note || "")}</textarea>
            <div class="character-memory-note-summary" aria-label="メモ状態">
              <span>${NovelUI.escape(statusLabel)}</span>
              <span>${NovelUI.escape(pinnedLabel)}</span>
              <span>${NovelUI.escape(categories[note.category] || "その他")}</span>
            </div>
            <div class="character-memory-note-actions">
              <label class="form-check">
                <input class="form-check-input" type="checkbox" data-field="enabled" ${note.enabled ? "checked" : ""} ${canManageProject ? "" : "disabled"}>
                <span class="form-check-label">有効</span>
              </label>
              <label class="form-check">
                <input class="form-check-input" type="checkbox" data-field="pinned" ${note.pinned ? "checked" : ""} ${canManageProject ? "" : "disabled"}>
                <span class="form-check-label">優先</span>
              </label>
              <button class="btn btn-outline-light btn-sm" type="button" data-action="save-note" ${canManageProject ? "" : "disabled"}>
                <i class="bi bi-check2"></i>
                <span>更新</span>
              </button>
              <button class="btn btn-outline-danger btn-sm" type="button" data-action="delete-note" ${canManageProject ? "" : "disabled"}>
                <i class="bi bi-trash"></i>
                <span>削除</span>
              </button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  async function loadNotes() {
    if (!characterId) {
      renderNotes([]);
      return;
    }
    const notes = await NovelUI.api(endpoint());
    renderNotes(Array.isArray(notes) ? notes : []);
  }

  function payloadFromItem(item) {
    return {
      category: item.querySelector('[data-field="category"]')?.value || "other",
      note: item.querySelector('[data-field="note"]')?.value || "",
      enabled: Boolean(item.querySelector('[data-field="enabled"]')?.checked),
      pinned: Boolean(item.querySelector('[data-field="pinned"]')?.checked),
    };
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!characterId || !canManageProject) return;
    const body = Object.fromEntries(new FormData(form).entries());
    body.pinned = Boolean(form.querySelector('[name="pinned"]')?.checked);
    if (!String(body.note || "").trim()) {
      NovelUI.toast("メモを入力してください。", "warning");
      return;
    }
    try {
      await NovelUI.api(endpoint(), { method: "POST", body });
      form.reset();
      await loadNotes();
      NovelUI.toast("AIメモを追加しました。");
    } catch (error) {
      NovelUI.toast(error.message || "AIメモの追加に失敗しました。", "danger");
    }
  });

  list.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button || !canManageProject) return;
    const item = button.closest("[data-note-id]");
    const noteId = Number(item?.dataset.noteId || 0);
    if (!noteId) return;
    button.disabled = true;
    try {
      if (button.dataset.action === "delete-note") {
        if (!confirm("このAIメモを削除しますか？")) return;
        await NovelUI.api(endpoint(noteId), { method: "DELETE" });
        NovelUI.toast("AIメモを削除しました。");
      } else {
        await NovelUI.api(endpoint(noteId), { method: "PATCH", body: payloadFromItem(item) });
        NovelUI.toast("AIメモを更新しました。");
      }
      await loadNotes();
    } catch (error) {
      NovelUI.toast(error.message || "AIメモの更新に失敗しました。", "danger");
    } finally {
      button.disabled = false;
    }
  });

  list.addEventListener("change", async (event) => {
    const field = event.target.closest('[data-field="enabled"], [data-field="pinned"]');
    if (!field || !canManageProject) return;
    const item = field.closest("[data-note-id]");
    const noteId = Number(item?.dataset.noteId || 0);
    if (!noteId) return;
    try {
      await NovelUI.api(endpoint(noteId), { method: "PATCH", body: payloadFromItem(item) });
      await loadNotes();
    } catch (error) {
      NovelUI.toast(error.message || "AIメモの更新に失敗しました。", "danger");
    }
  });

  loadNotes().catch((error) => {
    renderEmpty("AIメモの読み込みに失敗しました。");
    NovelUI.toast(error.message || "AIメモの読み込みに失敗しました。", "danger");
  });
})();
