(function () {
  function escapeHtml(value) {
    return window.NovelUI?.escape ? window.NovelUI.escape(value ?? "") : String(value ?? "");
  }

  function defaultMessages(messages) {
    return {
      loading: "衣装を読み込み中です。",
      emptyCharacter: "キャラクターを選択すると衣装が表示されます。",
      emptyOutfits: "このキャラクターの衣装はまだありません。",
      selected: "選択中",
      outfitFallbackName: "衣装",
      loadError: "衣装一覧の読み込みに失敗しました。",
      refreshError: "衣装一覧の更新に失敗しました。",
      ...(messages || {}),
    };
  }

  class OutfitPicker {
    constructor(options) {
      this.characterSelect = options.characterSelect;
      this.input = options.input;
      this.picker = options.picker;
      this.messages = defaultMessages(options.messages);
      this.api = options.api || window.NovelUI?.api;
      this.toast = options.toast || window.NovelUI?.toast;
      this.onChange = options.onChange || null;
      this._bind();
    }

    get value() {
      return this.input?.value || "";
    }

    set value(nextValue) {
      if (this.input) {
        this.input.value = nextValue ? String(nextValue) : "";
      }
    }

    clear() {
      this.value = "";
    }

    async load(selectedOutfitId = "") {
      if (!this.characterSelect || !this.input || !this.picker || !this.api) return;
      const characterId = Number(this.characterSelect.value || 0);
      const selectedValue = String(selectedOutfitId || this.value || "");
      this.picker.innerHTML = `<div class="empty-panel">${escapeHtml(this.messages.loading)}</div>`;
      if (!characterId) {
        this.picker.innerHTML = `<div class="empty-panel">${escapeHtml(this.messages.emptyCharacter)}</div>`;
        this.clear();
        return;
      }
      const outfits = await this.api(`/api/v1/characters/${characterId}/outfits`);
      const rows = Array.isArray(outfits) ? outfits : [];
      if (selectedValue && rows.some((item) => String(item.id) === selectedValue)) {
        this.value = selectedValue;
      } else {
        const defaultOutfit = rows.find((item) => item.is_default) || rows[0];
        this.value = defaultOutfit ? String(defaultOutfit.id) : "";
      }
      this.picker.innerHTML = rows.length
        ? rows.map((item) => this._renderCard(item)).join("")
        : `<div class="empty-panel">${escapeHtml(this.messages.emptyOutfits)}</div>`;
      this._emitChange();
    }

    _bind() {
      this.characterSelect?.addEventListener("change", () => {
        this.clear();
        this.load("").catch((error) => this._showError(error, this.messages.loadError));
      });
      this.picker?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-outfit-id]");
        if (!button) return;
        this.value = button.dataset.outfitId || "";
        this.load(this.value).catch((error) => this._showError(error, this.messages.refreshError));
      });
    }

    _renderCard(item) {
      const mediaUrl = item.thumbnail_asset?.media_url || item.asset?.media_url || "";
      const isSelected = String(item.id) === String(this.value);
      const label = item.is_default ? "Default" : (item.source_type === "character_base" ? "base" : (item.usage_scene || "outfit"));
      return `
        <button class="room-outfit-card ${isSelected ? "selected" : ""}" type="button" data-outfit-id="${escapeHtml(item.id)}">
          <span class="room-outfit-thumb">
            ${mediaUrl ? `<img src="${escapeHtml(mediaUrl)}" alt="">` : '<i class="bi bi-image"></i>'}
            ${isSelected ? `<span class="room-outfit-selected">${escapeHtml(this.messages.selected)}</span>` : ""}
          </span>
          <span class="room-outfit-name">${escapeHtml(item.name || this.messages.outfitFallbackName)}</span>
          <span class="room-outfit-meta">${escapeHtml(label)}</span>
        </button>
      `;
    }

    _emitChange() {
      if (typeof this.onChange === "function") {
        this.onChange(this.value);
      }
    }

    _showError(error, fallback) {
      const message = error?.message || fallback;
      if (typeof this.toast === "function") {
        this.toast(message, "danger");
      }
    }
  }

  window.OutfitPicker = {
    create(options) {
      return new OutfitPicker(options || {});
    },
  };
})();
