(() => {
  const page = document.querySelector("[data-project-list-page]");
  if (!page) return;

  const canManageWorlds = page.dataset.canManageWorlds === "true";
  const form = document.getElementById("projectSearchForm");
  const viewport = document.getElementById("worldCarouselViewport");
  const host = document.getElementById("projectList");
  const countLabel = document.getElementById("projectCountLabel");
  const prevButton = document.getElementById("worldCarouselPrev");
  const nextButton = document.getElementById("worldCarouselNext");
  if (!form || !viewport || !host || !countLabel || !prevButton || !nextButton) return;

  function statusLabel(status) {
    return status === "published" || status === "active" ? "Published" : "Draft";
  }

  function renderWorldImage(project) {
    const title = NovelUI.escape(project.title || "World");
    const mediaUrl = project.thumbnail_asset?.media_url;
    if (mediaUrl) {
      return `
        <a class="world-card-image-link" href="/projects/${project.id}/home" aria-label="${title}">
          <img class="world-card-image" src="${NovelUI.escape(mediaUrl)}" alt="${title}">
        </a>
      `;
    }
    return `
      <a class="world-card-image-link" href="/projects/${project.id}/home" aria-label="${title}">
        <div class="world-card-placeholder"><i class="bi bi-image"></i><span>No image</span></div>
      </a>
    `;
  }

  function updateCarouselButtons() {
    const hasOverflow = viewport.scrollWidth > viewport.clientWidth + 4;
    prevButton.disabled = !hasOverflow || viewport.scrollLeft <= 4;
    nextButton.disabled = !hasOverflow || viewport.scrollLeft + viewport.clientWidth >= viewport.scrollWidth - 4;
  }

  function scrollCarousel(direction) {
    const firstCard = host.querySelector(".project-card");
    const cardWidth = firstCard ? firstCard.getBoundingClientRect().width : viewport.clientWidth * 0.8;
    viewport.scrollBy({ left: direction * (cardWidth + 24), behavior: "smooth" });
  }

  async function loadProjects() {
    const params = new URLSearchParams();
    const formData = new FormData(form);
    for (const [key, value] of formData.entries()) {
      if (value) params.set(key, value);
    }

    const suffix = params.toString() ? `?${params.toString()}` : "";
    const data = await NovelUI.api(`/api/v1/projects${suffix}`);
    const list = Array.isArray(data) ? data : [];
    countLabel.textContent = `${list.length} items`;
    viewport.scrollTo({ left: 0 });

    if (!list.length) {
      host.innerHTML = '<div class="empty-panel world-carousel-empty">No matching worlds.</div>';
      updateCarouselButtons();
      return;
    }

    host.innerHTML = list.map((project) => `
      <article class="project-card world-carousel-card">
        ${renderWorldImage(project)}
        <div class="project-card-top">
          <span class="soft-code">${NovelUI.escape(statusLabel(project.status))}</span>
        </div>
        <h4>${NovelUI.escape(project.title || "Untitled")}</h4>
        <p>${NovelUI.escape(project.summary || "No description yet.")}</p>
        <div class="d-flex justify-content-end align-items-center gap-2 mt-3">
          ${canManageWorlds ? `<button class="btn btn-sm btn-outline-danger" data-project-delete="${project.id}">Delete</button>` : ""}
        </div>
      </article>
    `).join("");
    requestAnimationFrame(updateCarouselButtons);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadProjects().catch((error) => {
      NovelUI.toast(error.message || "World list loading failed.", "danger");
    });
  });

  host.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-project-delete]");
    if (!button) return;
    if (!window.confirm("Delete this world?")) return;
    try {
      await NovelUI.api(`/api/v1/projects/${button.dataset.projectDelete}`, { method: "DELETE" });
      NovelUI.toast("World deleted.");
      await loadProjects();
    } catch (error) {
      NovelUI.toast(error.message || "Delete failed.", "danger");
    }
  });

  prevButton.addEventListener("click", () => scrollCarousel(-1));
  nextButton.addEventListener("click", () => scrollCarousel(1));
  viewport.addEventListener("scroll", () => requestAnimationFrame(updateCarouselButtons));
  window.addEventListener("resize", () => requestAnimationFrame(updateCarouselButtons));

  loadProjects().catch((error) => {
    NovelUI.toast(error.message || "World list loading failed.", "danger");
  });
})();
