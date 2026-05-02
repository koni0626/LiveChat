(function () {
  const root = document.querySelector("[data-character-editor]");
  if (!root) return;

  const characterId = root.dataset.characterId ? Number(root.dataset.characterId) : null;
  const canManageProject = root.dataset.canManageProject !== "false";
  const form = document.getElementById("characterMemoryNoteForm");
  const list = document.getElementById("characterMemoryNoteList");
  const summaryPanel = document.getElementById("characterMemorySummary");
  const summarizeButton = document.getElementById("characterMemorySummarizeButton");
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

  function summaryEndpoint(action) {
    const base = `/api/v1/characters/${characterId}/memory-summary`;
    return action ? `${base}/${action}` : base;
  }

  function renderSummary(summary) {
    if (!summaryPanel) return;
    if (!characterId) {
      summaryPanel.innerHTML = '<div class="character-memory-summary-empty">キャラクター保存後にAIメモ要約を作成できます。</div>';
      if (summarizeButton) summarizeButton.disabled = true;
      return;
    }
    if (summarizeButton) summarizeButton.disabled = !canManageProject;
    const data = summary?.summary_json || {};
    const promptText = summary?.prompt_text || data.prompt_text || "";
    const updatedAt = formatDate(summary?.updated_at);
    const noteCount = Number(summary?.source_note_count || 0);
    if (!promptText && !noteCount) {
      summaryPanel.innerHTML = `
        <div class="character-memory-summary-empty">
          まだ要約はありません。会話でAIメモが増えると自動更新されます。すぐ作る場合は「要約を更新」を押してください。
        </div>
      `;
      return;
    }
    const groups = [
      ["性格の変化", data.stable_traits],
      ["癖", data.habits],
      ["好み", data.preferences],
      ["関係性フック", data.relationship_hooks],
      ["境界線", data.boundaries],
      ["未回収フック", data.open_threads],
    ].filter(([, items]) => Array.isArray(items) && items.length);
    summaryPanel.innerHTML = `
      <article class="character-memory-summary-card">
        <div class="character-memory-summary-meta">
          <span>${noteCount ? `${noteCount}件のAIメモから要約` : "AIメモ要約"}</span>
          <span>更新 ${NovelUI.escape(updatedAt)}</span>
        </div>
        ${data.overview ? `<p class="character-memory-summary-overview">${NovelUI.escape(data.overview)}</p>` : ""}
        <div class="character-memory-summary-prompt">${NovelUI.escape(promptText)}</div>
        ${groups.length ? `
          <div class="character-memory-summary-groups">
            ${groups.map(([label, items]) => `
              <div>
                <strong>${NovelUI.escape(label)}</strong>
                <ul>${items.map((item) => `<li>${NovelUI.escape(item)}</li>`).join("")}</ul>
              </div>
            `).join("")}
          </div>
        ` : ""}
      </article>
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

  async function loadSummary() {
    if (!characterId) {
      renderSummary(null);
      return;
    }
    const summary = await NovelUI.api(summaryEndpoint());
    renderSummary(summary);
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
      await loadSummary();
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
      await loadSummary();
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
      await loadSummary();
    } catch (error) {
      NovelUI.toast(error.message || "AIメモの更新に失敗しました。", "danger");
    }
  });

  summarizeButton?.addEventListener("click", async () => {
    if (!characterId || !canManageProject) return;
    const original = summarizeButton.innerHTML;
    summarizeButton.disabled = true;
    summarizeButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>要約中...';
    try {
      const summary = await NovelUI.api(summaryEndpoint("summarize"), { method: "POST", body: {} });
      renderSummary(summary);
      NovelUI.toast("AIメモ要約を更新しました。");
    } catch (error) {
      NovelUI.toast(error.message || "AIメモ要約に失敗しました。", "danger");
    } finally {
      summarizeButton.disabled = !canManageProject;
      summarizeButton.innerHTML = original;
    }
  });

  loadSummary().catch((error) => {
    renderSummary(null);
    NovelUI.toast(error.message || "AIメモ要約の読み込みに失敗しました。", "danger");
  });
  loadNotes().catch((error) => {
    renderEmpty("AIメモの読み込みに失敗しました。");
    NovelUI.toast(error.message || "AIメモの読み込みに失敗しました。", "danger");
  });
})();
