window.NovelUI = (() => {
  const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
  const nativeFetch = window.fetch.bind(window);

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || "";
  }

  function shouldAttachCsrf(resource, init = {}) {
    const method = String(init.method || "GET").toUpperCase();
    if (!UNSAFE_METHODS.has(method)) return false;
    const url = typeof resource === "string" ? resource : resource?.url;
    if (!url) return true;
    try {
      const parsed = new URL(url, window.location.href);
      return parsed.origin === window.location.origin;
    } catch (_error) {
      return true;
    }
  }

  window.fetch = (resource, init = {}) => {
    const config = { ...init };
    if (shouldAttachCsrf(resource, config)) {
      const headers = new Headers(config.headers || {});
      const token = csrfToken();
      if (token && !headers.has("X-CSRFToken")) headers.set("X-CSRFToken", token);
      config.headers = headers;
    }
    return nativeFetch(resource, config);
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function normalizeResponse(payload) {
    if (payload && typeof payload === "object" && "data" in payload) return payload.data;
    return payload;
  }

  async function api(url, options = {}) {
    const config = {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      credentials: "same-origin",
      cache: options.cache || "no-store",
    };
    if (options.body !== undefined) config.body = JSON.stringify(options.body);
    const response = await fetch(url, config);
    const payload = await response.json().catch(() => ({}));
    const data = normalizeResponse(payload);
    if (!response.ok) {
      const message = data?.message || payload?.message || `HTTP ${response.status}`;
      if (response.status === 401 && !options.allowUnauthorized && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      throw new Error(message);
    }
    return data;
  }

  function toast(message, tone = "success", options = {}) {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const wrapper = document.createElement("div");
    wrapper.className = `toast align-items-center text-bg-${tone} border-0`;
    wrapper.setAttribute("role", "status");
    wrapper.setAttribute("aria-live", "polite");
    wrapper.setAttribute("aria-atomic", "true");
    wrapper.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${escapeHtml(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;
    stack.appendChild(wrapper);
    const delay = Number(options.delay || options.duration || 5600);
    const instance = new bootstrap.Toast(wrapper, { delay: Number.isFinite(delay) ? delay : 5600 });
    wrapper.addEventListener("hidden.bs.toast", () => wrapper.remove());
    instance.show();
  }

  function fillForm(form, data) {
    if (!form || !data) return;
    Object.entries(data).forEach(([key, value]) => {
      const field = form.querySelector(`[name="${key}"]`);
      if (!field) return;
      if (field.type === "checkbox") field.checked = Boolean(value);
      else if (typeof value === "object" && value !== null) field.value = JSON.stringify(value, null, 2);
      else field.value = value ?? "";
    });
  }

  function truncateText(value, maxLength = 120) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}...` : text;
  }

  function formatDateTime(value, locale = "ja-JP") {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString(locale, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function statusLabel(value) {
    if (value === "published" || value === "active") return "公開";
    if (value === "archived") return "アーカイブ";
    return "下書き";
  }

  function renderHistoryRows(items, options = {}) {
    const actionLabel = options.actionLabel || "開く";
    return (Array.isArray(items) ? items : []).map((item) => {
      const href = typeof options.href === "function" ? options.href(item) : "#";
      const title = typeof options.title === "function" ? options.title(item) : (item?.title || "");
      const meta = typeof options.meta === "function" ? options.meta(item) : "";
      return `
        <a class="list-row text-decoration-none" href="${escapeHtml(href)}">
          <div>
            <strong>${escapeHtml(title || "項目")}</strong>
            ${meta ? `<div class="small text-secondary">${escapeHtml(meta)}</div>` : ""}
          </div>
          <span class="soft-code">${escapeHtml(actionLabel)}</span>
        </a>
      `;
    }).join("");
  }

  async function toggleLazyList(options = {}) {
    const container = typeof options.container === "string" ? document.querySelector(options.container) : options.container;
    if (!container) return { opened: false, loaded: false };
    const button = typeof options.button === "string" ? document.querySelector(options.button) : options.button;
    const openLabel = options.openLabel || "履歴を閉じる";
    const closedLabel = options.closedLabel || "履歴";
    if (container.dataset.loaded === "true") {
      const nextOpen = container.classList.contains("is-hidden");
      container.classList.toggle("is-hidden", !nextOpen);
      if (button) button.textContent = nextOpen ? openLabel : closedLabel;
      return { opened: nextOpen, loaded: true };
    }
    container.classList.remove("is-hidden");
    container.innerHTML = options.loadingHtml || '<div class="empty-panel">読み込み中...</div>';
    const items = await options.load();
    container.dataset.loaded = "true";
    if (button) button.textContent = openLabel;
    const list = Array.isArray(items) ? items : [];
    container.innerHTML = list.length ? options.render(list) : (options.emptyHtml || '<div class="empty-panel">履歴はまだありません。</div>');
    return { opened: true, loaded: false, items: list };
  }

  async function logout() {
    try {
      await api("/api/v1/auth/logout", { method: "POST", allowUnauthorized: true });
    } finally {
      window.location.href = "/login";
    }
  }

  async function editPlayerName() {
    const modalEl = document.getElementById("profileModal");
    const input = document.getElementById("profilePlayerNameInput");
    const saveButton = document.getElementById("profilePlayerNameSaveButton");
    if (!modalEl || !input || !saveButton) return;
    const me = await api("/api/v1/auth/me", { allowUnauthorized: true }).catch(() => null);
    if (!me?.user) return;
    input.value = me.user.player_name || me.user.display_name || "";
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    const submit = async () => {
      const trimmed = String(input.value || "").trim();
      if (!trimmed) {
        toast("プレイヤー名を入力してください。", "warning");
        input.focus();
        return;
      }
      saveButton.disabled = true;
      try {
        await api("/api/v1/auth/me/player-name", { method: "PATCH", body: { player_name: trimmed } });
        modal.hide();
        toast("プロフィールを更新しました。");
        window.location.reload();
      } catch (error) {
        toast(error.message || "更新に失敗しました。", "danger");
      } finally {
        saveButton.disabled = false;
      }
    };

    saveButton.onclick = submit;
    input.onkeydown = (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        submit();
      }
    };

    modal.show();
    setTimeout(() => input.focus(), 120);
  }

  async function refreshLetterBadge() {
    const badge = document.getElementById("letterNavBadge");
    if (!badge) return;
    try {
      const payload = await api("/api/v1/letters/unread-count", { allowUnauthorized: true });
      const count = Number(payload?.unread_count || 0);
      badge.textContent = count > 99 ? "99+" : String(count);
      badge.classList.toggle("d-none", count <= 0);
    } catch (_error) {
      badge.classList.add("d-none");
    }
  }

  document.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-action='edit-player-name']");
    if (editButton) {
      event.preventDefault();
      editPlayerName().catch((error) => toast(error.message || "更新に失敗しました。", "danger"));
      return;
    }
    const button = event.target.closest("[data-action='logout']");
    if (!button) return;
    event.preventDefault();
    logout();
  });

  refreshLetterBadge();
  window.setInterval(refreshLetterBadge, 60000);

  return {
    api,
    toast,
    fillForm,
    escape: escapeHtml,
    logout,
    refreshLetterBadge,
    truncateText,
    formatDateTime,
    statusLabel,
    renderHistoryRows,
    toggleLazyList,
  };
})();
