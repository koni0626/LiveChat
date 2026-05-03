(() => {
  const projectId = Number(document.querySelector("[data-project-id]")?.dataset.projectId || 0);
  const grid = document.getElementById("studioImageGrid");
  const pagination = document.getElementById("studioPagination");
  const sourceSelect = document.getElementById("studioSourceSelect");
  const searchInput = document.getElementById("studioSearchInput");
  let searchTimer = null;
  let currentPage = 1;
  const perPage = 24;

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
    const images = Array.isArray(payload) ? payload : payload.items || [];
    const page = payload.pagination || { page: 1, total_pages: 1, total: images.length, has_prev: false, has_next: false };
    if (!images.length) {
      grid.innerHTML = '<div class="empty-panel">条件に合う画像がありません。</div>';
      renderPagination(page);
      return;
    }
    grid.innerHTML = images.map((image) => `
      <a class="studio-image-card" href="/projects/${projectId}/studio/images/${image.asset_id}?${currentParams(page.page).toString()}">
        <img src="${NovelUI.escape(image.media_url)}" alt="${NovelUI.escape(image.file_name || "generated image")}">
        <span>${NovelUI.escape(image.source_label || image.source)}</span>
      </a>
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

  loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
})();
