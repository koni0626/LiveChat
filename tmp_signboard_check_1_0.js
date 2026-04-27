
(() => {
  const canManageWorlds = false;
  const form = document.getElementById("projectSearchForm");
  const host = document.getElementById("projectList");
  const countLabel = document.getElementById("projectCountLabel");

  function statusLabel(status) {
    return status === "published" || status === "active" ? "公開" : "下書き";
  }

  function renderWorldImage(project) {
    const mediaUrl = project.thumbnail_asset?.media_url;
    if (mediaUrl) {
      return `<img class="world-card-image" src="${mediaUrl}" alt="${NovelUI.escape(project.title || "ワールド看板")}">`;
    }
    return `<div class="world-card-placeholder"><i class="bi bi-image"></i><span>看板画像なし</span></div>`;
  }

  async function loadProjects() {
    const params = new URLSearchParams();
    const formData = new FormData(form);
    for (const [key, value] of formData.entries()) {
      if (value) {
        params.set(key, value);
      }
    }

    const suffix = params.toString() ? `?${params.toString()}` : "";
    const data = await NovelUI.api(`/api/v1/projects${suffix}`);
    const list = Array.isArray(data) ? data : [];
    countLabel.textContent = `${list.length} items`;

    if (!list.length) {
      host.innerHTML = `<div class="empty-panel">条件に合うワールドがありません。</div>`;
      return;
    }

    host.innerHTML = list.map((project) => `
      <article class="project-card">
        ${renderWorldImage(project)}
        <div class="project-card-top">
          <span class="soft-code">${NovelUI.escape(statusLabel(project.status))}</span>
        </div>
        <h4>${NovelUI.escape(project.title || "Untitled")}</h4>
        <p>${NovelUI.escape(project.summary || "説明はまだありません。")}</p>
        <div class="d-flex justify-content-between align-items-center mt-3">
          <a class="btn btn-sm btn-dark" href="/projects/${project.id}/home">開く</a>
          ${canManageWorlds ? `<button class="btn btn-sm btn-outline-danger" data-project-delete="${project.id}">削除</button>` : ""}
        </div>
      </article>
    `).join("");
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadProjects().catch((error) => {
      NovelUI.toast(error.message || "ワールド一覧の読み込みに失敗しました。", "danger");
    });
  });

  host.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-project-delete]");
    if (!button) {
      return;
    }
    if (!window.confirm("このワールドを削除しますか？")) {
      return;
    }
    try {
      await NovelUI.api(`/api/v1/projects/${button.dataset.projectDelete}`, { method: "DELETE" });
      NovelUI.toast("ワールドを削除しました。");
      await loadProjects();
    } catch (error) {
      NovelUI.toast(error.message || "削除に失敗しました。", "danger");
    }
  });

  loadProjects().catch((error) => {
    NovelUI.toast(error.message || "ワールド一覧の読み込みに失敗しました。", "danger");
  });
})();
