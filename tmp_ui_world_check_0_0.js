
(() => {
  const showProjectCreateHint = false;

  function statusLabel(status) {
    return status === "published" || status === "active" ? "公開" : "下書き";
  }

  async function loadDashboard() {
    const projects = await NovelUI.api("/api/v1/projects");
    const list = Array.isArray(projects) ? projects : [];
    document.getElementById("dashboardProjectCount").textContent = String(list.length);

    const host = document.getElementById("recentProjects");
    if (!list.length) {
      host.innerHTML = showProjectCreateHint
        ? `<div class="empty-panel">まだワールドがありません。新規作成から始めてください。</div>`
        : `<div class="empty-panel">利用できるワールドがまだありません。</div>`;
      return;
    }

    host.innerHTML = list.slice(0, 6).map((project) => `
      <a class="project-card" href="/projects/${project.id}/home">
        <div class="project-card-top">
          <span class="soft-code">${NovelUI.escape(statusLabel(project.status))}</span>
        </div>
        <h4>${NovelUI.escape(project.title || "Untitled")}</h4>
        <p>${NovelUI.escape(project.summary || "説明はまだありません。")}</p>
      </a>
    `).join("");
  }

  loadDashboard().catch((error) => {
    NovelUI.toast(error.message || "ダッシュボードの読み込みに失敗しました。", "danger");
  });
})();
