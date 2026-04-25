window.NovelUI = (() => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function normalizeResponse(payload) {
    if (payload && typeof payload === "object" && "data" in payload) {
      return payload.data;
    }
    return payload;
  }

  async function api(url, options = {}) {
    const config = {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      credentials: "same-origin",
      cache: options.cache || "no-store",
    };
    if (options.body !== undefined) {
      config.body = JSON.stringify(options.body);
    }
    const response = await fetch(url, config);
    const payload = await response.json().catch(() => ({}));
    const data = normalizeResponse(payload);
    if (!response.ok) {
      const message = data?.message || payload?.message || `HTTP ${response.status}`;
      if (response.status === 401 && !options.allowUnauthorized) {
        const loginUrl = "/login";
        if (window.location.pathname !== loginUrl) {
          window.location.href = loginUrl;
        }
      }
      throw new Error(message);
    }
    return data;
  }

  function toast(message, tone = "success") {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const wrapper = document.createElement("div");
    wrapper.className = "toast align-items-center text-bg-" + tone + " border-0";
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
    const toastInstance = new bootstrap.Toast(wrapper, { delay: 2800 });
    wrapper.addEventListener("hidden.bs.toast", () => wrapper.remove());
    toastInstance.show();
  }

  function fillForm(form, data) {
    if (!form || !data) return;
    Object.entries(data).forEach(([key, value]) => {
      const field = form.querySelector(`[name="${key}"]`);
      if (!field) return;
      if (field.type === "checkbox") {
        field.checked = Boolean(value);
      } else if (typeof value === "object" && value !== null) {
        field.value = JSON.stringify(value, null, 2);
      } else {
        field.value = value ?? "";
      }
    });
  }

  async function logout() {
    try {
      await api("/api/v1/auth/logout", { method: "POST", allowUnauthorized: true });
    } finally {
      window.location.href = "/login";
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action='logout']");
    if (!button) {
      return;
    }
    event.preventDefault();
    logout();
  });

  return { api, toast, fillForm, escape: escapeHtml, logout };
})();
