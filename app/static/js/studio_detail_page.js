(() => {
  const shell = document.querySelector("[data-project-id][data-asset-id]");
  const projectId = Number(shell?.dataset.projectId || 0);
  const canManageProject = shell?.dataset.canManageProject === "true";
  let selectedAssetId = Number(shell?.dataset.assetId || 0);
  let images = [];
  let selected = null;
  const initialPage = Number(new URLSearchParams(window.location.search).get("page") || 1);
  let currentPage = Number.isFinite(initialPage) && initialPage > 0 ? initialPage : 1;
  const perPage = 24;
  const selectedPanel = document.getElementById("studioSelectedPanel");
  const grid = document.getElementById("studioImageGrid");
  const pagination = document.getElementById("studioPagination");
  const sourceSelect = document.getElementById("studioSourceSelect");
  const searchInput = document.getElementById("studioSearchInput");
  const generateButton = document.getElementById("studioGenerateButton");
  let searchTimer = null;

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

  sourceSelect.value = new URLSearchParams(window.location.search).get("source") || "all";
  searchInput.value = new URLSearchParams(window.location.search).get("q") || "";

  function normalizePrompt(image) {
    return image?.prompt_text || image?.metadata?.revised_prompt || image?.metadata?.prompt || "プロンプトは保存されていません。";
  }

  function selectImage(image, replaceUrl = true) {
    selected = image || null;
    if (selected) {
      selectedAssetId = Number(selected.asset_id);
      if (replaceUrl) {
        history.replaceState(null, "", `/projects/${projectId}/studio/images/${selectedAssetId}?${currentParams(currentPage).toString()}`);
      }
    }
    renderSelected();
    renderGrid();
  }

  function currentParams(page) {
    return new URLSearchParams({
      page: String(page || currentPage),
      per_page: String(perPage),
      source: sourceSelect.value,
      q: searchInput.value.trim(),
    });
  }

  function renderSelected() {
    if (!selected) {
      selectedPanel.innerHTML = '<div class="empty-panel">画像が見つかりません。</div>';
      return;
    }
    selectedPanel.innerHTML = `
      <button class="studio-detail-image-button" type="button" data-open-selected-image>
        <img class="studio-detail-image" src="${NovelUI.escape(selected.media_url)}" alt="${NovelUI.escape(selected.file_name || "selected image")}">
      </button>
      <div class="studio-selected-meta">
        <span>${NovelUI.escape(selected.source_label || selected.source)}</span>
        <span>${NovelUI.escape(selected.size || "")}</span>
        <span>${NovelUI.escape(selected.quality || "")}</span>
      </div>
    `;
  }

  function renderGrid() {
    if (!images.length) {
      grid.innerHTML = '<div class="empty-panel">まだ表示できる画像がありません。</div>';
      return;
    }
    grid.innerHTML = images.map((image) => `
      <button class="studio-image-card ${Number(image.asset_id) === selectedAssetId ? "is-selected" : ""}" type="button" data-asset-id="${image.asset_id}">
        <img src="${NovelUI.escape(image.media_url)}" alt="${NovelUI.escape(image.file_name || "generated image")}">
        <span>${NovelUI.escape(image.source_label || image.source)}</span>
      </button>
    `).join("");
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

  async function loadImages() {
    const params = currentParams(currentPage);
    const payload = await NovelUI.api(`/api/v1/projects/${projectId}/studio/images?${params.toString()}`);
    images = Array.isArray(payload) ? payload : payload.items || [];
    renderPagination(payload.pagination || { page: 1, total_pages: 1, total: images.length, has_prev: false, has_next: false });
    const pageSelected = images.find((image) => Number(image.asset_id) === selectedAssetId);
    if (pageSelected) {
      selectImage(pageSelected, false);
    } else {
      renderGrid();
    }
  }

  async function loadSelectedImage() {
    selected = await NovelUI.api(`/api/v1/projects/${projectId}/studio/images/${selectedAssetId}`);
    renderSelected();
  }

  document.getElementById("studioImageGrid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-asset-id]");
    if (!button) return;
    const image = images.find((item) => Number(item.asset_id) === Number(button.dataset.assetId));
    if (!canManageProject) {
      openLightbox(image);
      return;
    }
    selectImage(image);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  selectedPanel?.addEventListener("click", (event) => {
    if (!event.target.closest("[data-open-selected-image]")) return;
    openLightbox(selected);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      document.querySelector(".studio-lightbox-overlay")?.classList.remove("is-open");
    }
  });

  const studioForm = document.getElementById("studioForm");
  studioForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canManageProject) {
      NovelUI.toast("この画面では画像編集できません。", "warning");
      return;
    }
    if (!selected) {
      NovelUI.toast("基準画像を選択してください。", "warning");
      return;
    }
    const instruction = document.getElementById("studioInstructionInput").value.trim();
    if (!instruction) {
      NovelUI.toast("変更指示を入力してください。", "warning");
      return;
    }
    generateButton.disabled = true;
    generateButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>生成中...';
    try {
      const generated = await NovelUI.api(`/api/v1/projects/${projectId}/studio/generate`, {
        method: "POST",
        body: {
          source_asset_id: selected.asset_id,
          instruction,
          quality: document.getElementById("studioQualitySelect").value,
          size: document.getElementById("studioSizeSelect").value,
        },
      });
      currentPage = 1;
      images = [generated, ...images.filter((image) => Number(image.asset_id) !== Number(generated.asset_id))];
      document.getElementById("studioInstructionInput").value = "";
      selectImage(generated);
      NovelUI.toast("画像を生成し、ギャラリーに追加しました。");
    } catch (error) {
      NovelUI.toast(error.message || "画像生成に失敗しました。", "danger");
    } finally {
      generateButton.disabled = false;
      generateButton.innerHTML = "画像を変更";
    }
  });

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

  loadSelectedImage()
    .catch((error) => NovelUI.toast(error.message || "選択画像を読み込めませんでした。", "danger"))
    .finally(() => {
      loadImages().catch((error) => NovelUI.toast(error.message || "画像を読み込めませんでした。", "danger"));
    });
})();
