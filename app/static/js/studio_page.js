(() => {
  const shell = document.querySelector("[data-project-id]");
  const projectId = Number(shell?.dataset.projectId || 0);
  const canManageProject = shell?.dataset.canManageProject === "true";
  const grid = document.getElementById("studioImageGrid");
  const pagination = document.getElementById("studioPagination");
  const sourceSelect = document.getElementById("studioSourceSelect");
  const searchInput = document.getElementById("studioSearchInput");
  let images = [];
  let searchTimer = null;
  let currentPage = 1;
  const perPage = 24;

  function openLightbox(image) {
    if (!image?.media_url) return;
    let overlay = document.querySelector(".studio-lightbox-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "studio-lightbox-overlay";
      overlay.innerHTML = `
        <button class="studio-lightbox-close" type="button" aria-label="閉じる"><i class="bi bi-x-lg"></i></button>
        <img class="studio-lightbox-image" alt="">
      `;
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay || event.target.closest(".studio-lightbox-close")) {
          overlay.classList.remove("is-open");
        }
      });
      document.body.appendChild(overlay);
    }
    const imageNode = overlay.querySelector(".studio-lightbox-image");
    imageNode.src = image.media_url;
    imageNode.alt = image.file_name || "studio image";
    overlay.classList.add("is-open");
  }

  function currentParams(page) {
    return new URLSearchParams({
      page: String(page || currentPage),
      per_page: String(perPage),
      source: sourceSelect.value,
      q: searchInput.value.trim(),
    });
  }

  async function loadImages() {
    const params = currentParams(currentPage);
    const payload = await NovelUI.api(`/api/v1/projects/${projectId}/studio/images?${params.toString()}`);
    images = Array.isArray(payload) ? payload : payload.items || [];
    const page = payload.pagination || { page: 1, total_pages: 1, total: images.length, has_prev: false, has_next: false };
    if (!images.length) {
      grid.innerHTML = '<div class="empty-panel">条件に合う画像がありません。</div>';
      renderPagination(page);
      return;
    }
    grid.innerHTML = images.map((image) => canManageProject ? `
      <a class="studio-image-card" href="/projects/${projectId}/studio/images/${image.asset_id}?${currentParams(page.page).toString()}">
        <img src="${NovelUI.escape(image.media_url)}" alt="${NovelUI.escape(image.file_name || "generated image")}">
        <span>${NovelUI.escape(image.source_label || image.source)}</span>
      </a>
    ` : `
      <button class="studio-image-card" type="button" data-lightbox-asset-id="${image.asset_id}">
        <img src="${NovelUI.escape(image.media_url)}" alt="${NovelUI.escape(image.file_name || "generated image")}">
        <span>${NovelUI.escape(image.source_label || image.source)}</span>
      </button>
    `).join("");
    renderPagination(page);
  }

  function renderPagination(page) {
    if (!pagination) return;
    if (!page.total || page.total_pages <= 1) {
      pagination.innerHTML = "";
      return;
    }
    pagination.innerHTML = `
      <button class="btn btn-sm btn-outline-dark" type="button" data-page="${page.page - 1}" ${page.has_prev ? "" : "disabled"}>前へ</button>
      <span>${page.page} / ${page.total_pages} ページ（${page.total}件）</span>
      <button class="btn btn-sm btn-outline-dark" type="button" data-page="${page.page + 1}" ${page.has_next ? "" : "disabled"}>次へ</button>
    `;
  }

  document.getElementById("studioReloadButton").addEventListener("click", () => {
    loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
  });

  function resetAndLoad() {
    currentPage = 1;
    loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
  }

  sourceSelect.addEventListener("change", resetAndLoad);
  searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(resetAndLoad, 250);
  });

  pagination?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-page]");
    if (!button || button.disabled) return;
    currentPage = Number(button.dataset.page || 1);
    loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
  });

  grid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-lightbox-asset-id]");
    if (!button) return;
    const image = images.find((item) => Number(item.asset_id) === Number(button.dataset.lightboxAssetId));
    openLightbox(image);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      document.querySelector(".studio-lightbox-overlay")?.classList.remove("is-open");
    }
  });

  loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
})();
