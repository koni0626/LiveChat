(() => {
  const page = document.querySelector("[data-dashboard-page]");
  if (!page) return;

  const showProjectCreateHint = page.dataset.showQuickStart === "true";

  function statusLabel(status) {
    return status === "published" || status === "active" ? "Published" : "Draft";
  }

  function renderWorldImage(project) {
    const mediaUrl = project.thumbnail_asset?.media_url;
    if (mediaUrl) {
      return `<img class="world-card-image" src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(project.title || "World image")}">`;
    }
    return '<div class="world-card-placeholder"><i class="bi bi-image"></i><span>No image</span></div>';
  }

  async function loadDashboard() {
    const projects = await NovelUI.api("/api/v1/projects");
    const list = Array.isArray(projects) ? projects : [];
    document.getElementById("dashboardProjectCount").textContent = String(list.length);

    const host = document.getElementById("recentProjects");
    if (!list.length) {
      host.innerHTML = showProjectCreateHint
        ? '<div class="empty-panel">No worlds yet. Create a new world to begin.</div>'
        : '<div class="empty-panel">No available worlds yet.</div>';
      return;
    }

    host.innerHTML = list.slice(0, 6).map((project) => `
      <a class="project-card" href="/projects/${project.id}/home">
        ${renderWorldImage(project)}
        <div class="project-card-top">
          <span class="soft-code">${NovelUI.escape(statusLabel(project.status))}</span>
        </div>
        <h4>${NovelUI.escape(project.title || "Untitled")}</h4>
        <p>${NovelUI.escape(project.summary || "No description yet.")}</p>
      </a>
    `).join("");
  }

  loadDashboard().catch((error) => {
    NovelUI.toast(error.message || "Dashboard loading failed.", "danger");
  });
})();
