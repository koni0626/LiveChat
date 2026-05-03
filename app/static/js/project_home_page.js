(() => {
  const page = document.querySelector("[data-project-home]");
  if (!page) return;

  const projectId = Number(page.dataset.projectHome);
  const signboardPreview = document.getElementById("worldSignboardPreview");
  const signboardUploadForm = document.getElementById("worldSignboardUploadForm");
  const signboardDropzone = document.getElementById("worldSignboardDropzone");
  const signboardFileInput = signboardUploadForm?.querySelector('[name="file"]');
  const signboardGenerateButton = document.getElementById("worldSignboardGenerateButton");
  if (!projectId || !signboardPreview) return;

  function renderSignboard(project) {
    const asset = project?.thumbnail_asset;
    if (asset?.media_url) {
      signboardPreview.innerHTML = `
        <img src="${NovelUI.escape(asset.media_url)}" alt="${NovelUI.escape(project?.title || "World signboard")}" class="world-home-signboard-image">
      `;
      return;
    }
    signboardPreview.innerHTML = `
      <div class="world-home-signboard-empty">
        <i class="bi bi-image"></i>
        <span>No image</span>
      </div>
    `;
  }

  async function loadOverview() {
    const project = await NovelUI.api(`/api/v1/projects/${projectId}`);
    document.getElementById("projectHomeTitle").textContent = project?.title || "Untitled";
    document.getElementById("projectHomeSummary").textContent = project?.summary || "No description yet.";
    renderSignboard(project);
  }

  function setSignboardDropzoneActive(active) {
    signboardDropzone?.classList.toggle("is-dragover", active);
  }

  function ensureImageFile(file) {
    if (!file) {
      NovelUI.toast("Choose a signboard image.", "warning");
      return false;
    }
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("Only image files can be uploaded.", "warning");
      return false;
    }
    return true;
  }

  async function uploadSignboard(file) {
    if (!ensureImageFile(file)) return;
    const uploadPayload = new FormData();
    uploadPayload.append("file", file);
    uploadPayload.append("project_id", String(projectId));
    uploadPayload.append("asset_type", "world_signboard");
    try {
      const response = await fetch("/api/v1/assets/upload", { method: "POST", body: uploadPayload, credentials: "same-origin" });
      const payload = await response.json().catch(() => ({}));
      const asset = payload?.data;
      if (!response.ok || !asset) throw new Error(payload?.message || `HTTP ${response.status}`);
      const project = await NovelUI.api(`/api/v1/projects/${projectId}`, {
        method: "PATCH",
        body: { thumbnail_asset_id: asset.id },
      });
      renderSignboard(project);
      if (signboardFileInput) signboardFileInput.value = "";
      NovelUI.toast("World signboard updated.");
    } catch (error) {
      NovelUI.toast(error.message || "Signboard upload failed.", "danger");
    } finally {
      setSignboardDropzoneActive(false);
    }
  }

  function setGeneratingSignboard(active) {
    if (!signboardGenerateButton) return;
    signboardGenerateButton.disabled = active;
    signboardGenerateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Generating...'
      : '<i class="bi bi-stars"></i><span>Generate signboard</span>';
  }

  async function generateSignboard() {
    setGeneratingSignboard(true);
    try {
      const project = await NovelUI.api(`/api/v1/projects/${projectId}/signboard/generate`, {
        method: "POST",
        body: { size: "1536x1024" },
      });
      renderSignboard(project);
      NovelUI.toast("World signboard generated.");
    } catch (error) {
      NovelUI.toast(error.message || "Signboard generation failed.", "danger");
    } finally {
      setGeneratingSignboard(false);
    }
  }

  signboardGenerateButton?.addEventListener("click", generateSignboard);
  signboardUploadForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await uploadSignboard(signboardFileInput?.files?.[0]);
  });
  signboardDropzone?.addEventListener("click", (event) => {
    if (event.target !== signboardFileInput) signboardFileInput?.click();
  });
  signboardDropzone?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      signboardFileInput?.click();
    }
  });
  signboardFileInput?.addEventListener("change", async () => {
    await uploadSignboard(signboardFileInput.files?.[0]);
  });
  ["dragenter", "dragover"].forEach((eventName) => {
    signboardDropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      setSignboardDropzoneActive(true);
    });
  });
  ["dragleave", "dragend"].forEach((eventName) => {
    signboardDropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!signboardDropzone.contains(event.relatedTarget)) setSignboardDropzoneActive(false);
    });
  });
  signboardDropzone?.addEventListener("drop", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await uploadSignboard(event.dataTransfer?.files?.[0]);
  });

  loadOverview().catch((error) => {
    NovelUI.toast(error.message || "World home loading failed.", "danger");
  });
})();
