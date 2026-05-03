(() => {
  const form = document.getElementById("adminUserCreateForm");
  const listHost = document.getElementById("adminUserList");
  const reloadButton = document.getElementById("adminUsersReloadButton");

  function roleLabel(role) {
    return {
      superuser: "スーパーユーザー",
      project_user: "プロジェクトユーザー",
      user: "ユーザー",
    }[role] || role || "user";
  }

  function renderUsers(users) {
    const list = Array.isArray(users) ? users : [];
    if (!list.length) {
      listHost.innerHTML = '<div class="empty-panel">ユーザーはまだ登録されていません。</div>';
      return;
    }
    listHost.innerHTML = list.map((user) => `
      <article class="list-row admin-user-row" data-user-id="${user.id}">
        <div class="admin-user-main">
          <div class="list-title">${NovelUI.escape(user.display_name || "No Name")}</div>
          <div class="list-subtitle">${NovelUI.escape(user.email || "")}</div>
        </div>
        <div class="admin-user-controls">
          <select class="form-select form-select-sm" data-role-select>
            ${["superuser", "project_user", "user"].map((role) => `
              <option value="${role}" ${role === user.role ? "selected" : ""}>${roleLabel(role)}</option>
            `).join("")}
          </select>
          <select class="form-select form-select-sm" data-status-select>
            ${["active", "suspended", "deleted"].map((status) => `
              <option value="${status}" ${status === user.status ? "selected" : ""}>${NovelUI.escape(status)}</option>
            `).join("")}
          </select>
          <button class="btn btn-sm btn-outline-light" type="button" data-save-user>保存</button>
        </div>
      </article>
    `).join("");
  }

  async function loadUsers() {
    const users = await NovelUI.api("/api/v1/admin/users");
    renderUsers(users);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      await NovelUI.api("/api/v1/admin/users", { method: "POST", body });
      form.reset();
      form.role.value = "project_user";
      await loadUsers();
      NovelUI.toast("ユーザーを作成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ユーザー作成に失敗しました。", "danger");
    }
  });

  listHost.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-save-user]");
    if (!button) return;
    const row = button.closest("[data-user-id]");
    if (!row) return;
    const body = {
      role: row.querySelector("[data-role-select]").value,
      status: row.querySelector("[data-status-select]").value,
    };
    try {
      await NovelUI.api(`/api/v1/admin/users/${row.dataset.userId}`, { method: "PATCH", body });
      await loadUsers();
      NovelUI.toast("ユーザーを更新しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ユーザー更新に失敗しました。", "danger");
    }
  });

  reloadButton.addEventListener("click", () => {
    loadUsers().catch((error) => NovelUI.toast(error.message || "ユーザー一覧の読み込みに失敗しました。", "danger"));
  });

  loadUsers().catch((error) => NovelUI.toast(error.message || "ユーザー一覧の読み込みに失敗しました。", "danger"));
})();
