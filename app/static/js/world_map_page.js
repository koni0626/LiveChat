(() => {
  const root = document.querySelector("[data-world-map-page]");
  if (!root) return;

  const projectId = Number(root.dataset.worldMapPage);
  const canManage = root.dataset.canManage === "true";
  const mapFrame = document.getElementById("worldMapImageFrame");
  const mapImageList = document.getElementById("worldMapImageList");
  const mapUploadInput = document.getElementById("worldMapUploadInput");
  const mapGenerateButton = document.getElementById("worldMapGenerateButton");
  const locationList = document.getElementById("worldLocationList");
  const locationForm = document.getElementById("worldLocationForm");
  const locationResetButton = document.getElementById("worldLocationResetButton");
  const locationAiAssistButton = document.getElementById("worldLocationAiAssistButton");
  const locationAiAssistLabel = document.getElementById("worldLocationAiAssistLabel");
  const locationAiAssistSpinner = document.getElementById("worldLocationAiAssistSpinner");
  const locationSubmitLabel = document.getElementById("worldLocationSubmitLabel");
  const locationSubmitSpinner = document.getElementById("worldLocationSubmitSpinner");
  const locationSubmitButton = locationForm?.querySelector('button[type="submit"]');
  const ownerSelect = locationForm?.querySelector('[name="owner_character_id"]');
  const searchInput = document.getElementById("worldLocationSearchInput");
  const regionFilter = document.getElementById("worldLocationRegionFilter");
  const typeFilter = document.getElementById("worldLocationTypeFilter");
  const tagFilter = document.getElementById("worldLocationTagFilter");
  const candidatesButton = document.getElementById("worldLocationCandidatesButton");
  const candidateList = document.getElementById("worldLocationCandidateList");
  const locationImageModalElement = document.getElementById("worldLocationImageModal");
  const locationImageModalTitle = document.getElementById("worldLocationImageModalTitle");
  const locationImageModalImage = document.getElementById("worldLocationImageModalImage");
  if (locationImageModalElement) {
    document.body.appendChild(locationImageModalElement);
  }
  const locationImageModal = locationImageModalElement && window.bootstrap
    ? new bootstrap.Modal(locationImageModalElement)
    : null;

  let locations = [];
  let mapImages = [];
  let locationSaveBusy = false;
  let locationAiAssistBusy = false;

  function ensureImageFile(file) {
    if (!file) {
      NovelUI.toast("画像ファイルを選択してください。", "warning");
      return false;
    }
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("画像ファイルのみアップロードできます。", "warning");
      return false;
    }
    return true;
  }

  function renderMap(activeMap, images) {
    mapImages = images || [];
    const mediaUrl = activeMap?.asset?.media_url;
    if (mediaUrl) {
      mapFrame.innerHTML = `<img class="world-map-image" src="${NovelUI.escape(mediaUrl)}" alt="${NovelUI.escape(activeMap.title || "ワールドマップ")}">`;
    } else {
      mapFrame.innerHTML = `
        <div class="world-map-empty">
          <i class="bi bi-map"></i>
          <span>俯瞰図はまだありません</span>
        </div>
      `;
    }

    if (!mapImageList) return;
    if (!mapImages.length) {
      mapImageList.innerHTML = "";
      return;
    }
    mapImageList.innerHTML = mapImages.map((image) => {
      const src = image?.asset?.media_url || "";
      return `
        <span class="world-map-thumb-wrap">
          <button class="world-map-thumb ${image.is_active ? "active" : ""}" type="button" data-map-image-id="${image.id}" title="${NovelUI.escape(image.title || "ワールドマップ")}">
            ${src ? `<img src="${NovelUI.escape(src)}" alt="">` : '<i class="bi bi-image"></i>'}
          </button>
          ${canManage ? `<button class="world-map-thumb-delete" type="button" data-delete-map-image="${image.id}" aria-label="俯瞰図を削除"><i class="bi bi-x"></i></button>` : ""}
        </span>
      `;
    }).join("");
  }

  function renderLocations(items) {
    locations = items || [];
    updateFilters(locations);
    if (!locations.length) {
      locationList.innerHTML = '<div class="empty-panel">施設はまだ登録されていません。</div>';
      return;
    }
    locationList.innerHTML = locations.map((location) => {
      const src = location?.image_asset?.media_url;
      const owner = location.owner_character_name ? `所有者: ${location.owner_character_name}` : "所有者なし";
      const descriptionId = `world-location-description-${location.id}`;
      const description = location.description || "説明はまだありません。";
      return `
        <article class="project-card entity-card-stable world-location-card" data-location-id="${location.id}">
          ${src ? `
            <button class="world-location-image" type="button" data-open-location-image="${location.id}" aria-label="${NovelUI.escape(location.name)}の画像を拡大表示">
              <img src="${NovelUI.escape(src)}" alt="${NovelUI.escape(location.name)}">
            </button>
          ` : `
            <div class="world-location-image">
              <i class="bi bi-building"></i>
            </div>
          `}
            <div>
              <div class="eyebrow">${NovelUI.escape(location.location_type || "施設")}</div>
              <h4>${NovelUI.escape(location.name)}</h4>
              <button class="btn btn-outline-light btn-sm world-location-description-toggle" type="button" data-toggle-location-description="${location.id}" aria-controls="${descriptionId}" aria-expanded="false">
                <i class="bi bi-card-text"></i><span>説明</span>
              </button>
              <p class="world-location-description" id="${descriptionId}" hidden>${NovelUI.escape(description)}</p>
            </div>
          <div class="world-location-meta">
            ${location.region ? `<span>${NovelUI.escape(location.region)}</span>` : ""}
            <span>${NovelUI.escape(owner)}</span>
            ${(location.tags || []).map((tag) => `<span>${NovelUI.escape(tag)}</span>`).join("")}
            ${location.source_note ? `<span>${NovelUI.escape(location.source_note)}</span>` : ""}
          </div>
          ${canManage ? `
            <div class="world-location-actions">
              <label class="btn btn-outline-light btn-sm mb-0">
                <i class="bi bi-image"></i>
                <span>画像</span>
                <input class="d-none" type="file" data-location-image-input="${location.id}" accept="image/png,image/jpeg,image/webp">
              </label>
              <button class="btn btn-sunrise btn-sm" type="button" data-generate-location-image="${location.id}">
                <i class="bi bi-stars"></i><span>生成</span>
              </button>
              <button class="btn btn-outline-light btn-sm" type="button" data-edit-location="${location.id}">
                <i class="bi bi-pencil"></i><span>編集</span>
              </button>
              <button class="btn btn-outline-light btn-sm" type="button" data-related-location="${location.id}">
                <i class="bi bi-link-45deg"></i><span>履歴</span>
              </button>
              <button class="btn btn-outline-danger btn-sm" type="button" data-delete-location="${location.id}">
                <i class="bi bi-trash"></i><span>削除</span>
              </button>
            </div>
          ` : ""}
        </article>
      `;
    }).join("");
  }

  function updateFilters(items) {
    const preserve = (select) => select?.value || "";
    const currentRegion = preserve(regionFilter);
    const currentType = preserve(typeFilter);
    const regions = [...new Set((items || []).map((item) => item.region).filter(Boolean))].sort();
    const types = [...new Set((items || []).map((item) => item.location_type).filter(Boolean))].sort();
    if (regionFilter) {
      regionFilter.innerHTML = '<option value="">全地域</option>' + regions.map((value) => `<option value="${NovelUI.escape(value)}">${NovelUI.escape(value)}</option>`).join("");
      regionFilter.value = currentRegion;
    }
    if (typeFilter) {
      typeFilter.innerHTML = '<option value="">全種別</option>' + types.map((value) => `<option value="${NovelUI.escape(value)}">${NovelUI.escape(value)}</option>`).join("");
      typeFilter.value = currentType;
    }
  }

  function filteredLocations() {
    const search = (searchInput?.value || "").trim().toLowerCase();
    const region = regionFilter?.value || "";
    const type = typeFilter?.value || "";
    const tag = (tagFilter?.value || "").trim();
    return locations.filter((item) => {
      if (region && item.region !== region) return false;
      if (type && item.location_type !== type) return false;
      if (tag && !(item.tags || []).includes(tag)) return false;
      if (search) {
        const haystack = [item.name, item.region, item.location_type, item.description, ...(item.tags || [])].join(" ").toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
  }

  function applyLocationFilters() {
    const source = locations;
    locations = filteredLocations();
    const rendered = locations;
    locations = source;
    renderLocations(rendered);
    locations = source;
  }

  async function loadCharacters() {
    if (!ownerSelect) return;
    const characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    ownerSelect.innerHTML = '<option value="">なし</option>' + (characters || []).map((character) => {
      return `<option value="${character.id}">${NovelUI.escape(character.name || `#${character.id}`)}</option>`;
    }).join("");
  }

  async function loadWorldMap() {
    const overview = await NovelUI.api(`/api/v1/projects/${projectId}/world-map`);
    renderMap(overview.active_map_image, overview.map_images);
    renderLocations(overview.locations);
  }

  function formPayload() {
    const data = new FormData(locationForm);
    const payload = {};
    for (const [key, value] of data.entries()) {
      payload[key] = value;
    }
    return payload;
  }

  function resetForm() {
    if (!locationForm) return;
    locationForm.reset();
    locationForm.querySelector('[name="location_id"]').value = "";
    if (locationSubmitLabel) locationSubmitLabel.textContent = "施設を追加";
  }

  function setLocationSaveBusy(active) {
    locationSaveBusy = active;
    const locationId = locationForm?.querySelector('[name="location_id"]')?.value;
    if (locationSubmitButton) locationSubmitButton.disabled = active;
    if (locationResetButton) locationResetButton.disabled = active;
    if (locationSubmitSpinner) locationSubmitSpinner.classList.toggle("d-none", !active);
    if (locationSubmitLabel) {
      locationSubmitLabel.textContent = active
        ? "保存中..."
        : (locationId ? "施設を更新" : "施設を追加");
    }
  }

  function setLocationAiAssistBusy(active) {
    locationAiAssistBusy = active;
    if (locationAiAssistButton) locationAiAssistButton.disabled = active;
    if (locationAiAssistSpinner) locationAiAssistSpinner.classList.toggle("d-none", !active);
    if (locationAiAssistLabel) locationAiAssistLabel.textContent = active ? "AI補完中..." : "AI補完";
  }

  function applyLocationDraft(draft) {
    if (!locationForm || !draft) return;
    ["name", "region", "location_type", "owner_character_id", "tags_text", "description", "sort_order", "source_note"].forEach((key) => {
      const field = locationForm.querySelector(`[name="${key}"]`);
      if (!field || draft[key] === undefined || draft[key] === null) return;
      field.value = Array.isArray(draft[key]) ? draft[key].join("\n") : draft[key];
    });
  }

  async function assistLocation() {
    if (locationAiAssistBusy || !locationForm) return;
    setLocationAiAssistBusy(true);
    try {
      const payload = formPayload();
      const locationId = payload.location_id;
      delete payload.location_id;
      const response = await NovelUI.api(`/api/v1/projects/${projectId}/locations/draft`, {
        method: "POST",
        body: { current_location: payload },
      });
      if (!response?.draft) throw new Error("AI補完の応答が不正です。");
      applyLocationDraft(response.draft);
      if (locationId) locationForm.querySelector('[name="location_id"]').value = locationId;
      NovelUI.toast("施設情報をAI補完しました。");
    } finally {
      setLocationAiAssistBusy(false);
    }
  }

  async function saveLocation(event) {
    event.preventDefault();
    if (locationSaveBusy) return;
    const payload = formPayload();
    const locationId = payload.location_id;
    delete payload.location_id;
    const url = locationId ? `/api/v1/locations/${locationId}` : `/api/v1/projects/${projectId}/locations`;
    const method = locationId ? "PATCH" : "POST";
    setLocationSaveBusy(true);
    try {
      await NovelUI.api(url, { method, body: payload });
      NovelUI.toast(locationId ? "施設を更新しました。" : "施設を追加しました。");
      resetForm();
      await loadWorldMap();
    } finally {
      setLocationSaveBusy(false);
    }
  }

  function editLocation(locationId) {
    const location = locations.find((item) => Number(item.id) === Number(locationId));
    if (!location || !locationForm) return;
    locationForm.querySelector('[name="location_id"]').value = location.id;
    locationForm.querySelector('[name="name"]').value = location.name || "";
    locationForm.querySelector('[name="region"]').value = location.region || "";
    locationForm.querySelector('[name="location_type"]').value = location.location_type || "";
    locationForm.querySelector('[name="owner_character_id"]').value = location.owner_character_id || "";
    locationForm.querySelector('[name="tags_text"]').value = location.tags_text || "";
    locationForm.querySelector('[name="description"]').value = location.description || "";
    locationForm.querySelector('[name="sort_order"]').value = location.sort_order || 0;
    locationForm.querySelector('[name="source_note"]').value = location.source_note || "";
    if (locationSubmitLabel) locationSubmitLabel.textContent = "施設を更新";
    locationForm.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function deleteLocation(locationId) {
    if (!window.confirm("この施設を削除しますか？")) return;
    await NovelUI.api(`/api/v1/locations/${locationId}`, { method: "DELETE" });
    NovelUI.toast("施設を削除しました。");
    await loadWorldMap();
  }

  function openLocationImage(locationId) {
    const location = locations.find((item) => Number(item.id) === Number(locationId));
    const src = location?.image_asset?.media_url;
    if (!src || !locationImageModal || !locationImageModalImage) return;
    locationImageModalImage.src = src;
    locationImageModalImage.alt = location.name || "施設画像";
    if (locationImageModalTitle) locationImageModalTitle.textContent = location.name || "施設画像";
    locationImageModal.show();
  }

  async function uploadMapImage(file) {
    if (!ensureImageFile(file)) return;
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`/api/v1/projects/${projectId}/world-map/upload`, { method: "POST", body, credentials: "same-origin" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.data?.message || payload?.message || `HTTP ${response.status}`);
    NovelUI.toast("ワールドマップ画像をアップロードしました。");
    if (mapUploadInput) mapUploadInput.value = "";
    await loadWorldMap();
  }

  async function generateMapImage() {
    const originalHtml = mapGenerateButton?.innerHTML;
    if (mapGenerateButton) {
      mapGenerateButton.disabled = true;
      mapGenerateButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>生成中';
    }
    try {
      await NovelUI.api(`/api/v1/projects/${projectId}/world-map/generate`, { method: "POST", body: {} });
      NovelUI.toast("ワールドマップ俯瞰図を生成しました。");
      await loadWorldMap();
    } finally {
      if (mapGenerateButton) {
        mapGenerateButton.disabled = false;
        mapGenerateButton.innerHTML = originalHtml;
      }
    }
  }

  async function uploadLocationImage(locationId, file) {
    if (!ensureImageFile(file)) return;
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`/api/v1/locations/${locationId}/image/upload`, { method: "POST", body, credentials: "same-origin" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.data?.message || payload?.message || `HTTP ${response.status}`);
    NovelUI.toast("施設画像を更新しました。");
    await loadWorldMap();
  }

  async function generateLocationImage(locationId, button) {
    const originalHtml = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>生成中';
    }
    try {
      await NovelUI.api(`/api/v1/locations/${locationId}/image/generate`, { method: "POST", body: {} });
      NovelUI.toast("施設イメージを生成しました。");
      await loadWorldMap();
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }
  }

  async function loadCandidates() {
    if (!candidateList) return;
    candidateList.classList.remove("d-none");
    candidateList.innerHTML = '<div class="empty-panel">候補を抽出しています...</div>';
    const candidates = await NovelUI.api(`/api/v1/projects/${projectId}/locations/candidates`);
    if (!candidates.length) {
      candidateList.innerHTML = '<div class="empty-panel">新しい施設候補は見つかりませんでした。</div>';
      return;
    }
    candidateList.innerHTML = candidates.map((candidate, index) => `
      <article class="list-row world-location-candidate-row">
          <div>
            <strong>${NovelUI.escape(candidate.name)}</strong>
            <div class="small text-secondary">${NovelUI.escape(candidate.location_type || "施設")} / ${NovelUI.escape(candidate.source_note || "")}</div>
            <div class="small world-location-candidate-label">概要</div>
            <div class="small">${NovelUI.escape(candidate.description || "")}</div>
          </div>
        <button class="btn btn-sunrise btn-sm" type="button" data-add-candidate="${index}">
          <i class="bi bi-plus-lg"></i><span>追加</span>
        </button>
      </article>
    `).join("");
    candidateList.dataset.candidates = JSON.stringify(candidates);
  }

  async function addCandidate(index) {
    const candidates = JSON.parse(candidateList?.dataset.candidates || "[]");
    const candidate = candidates[Number(index)];
    if (!candidate) return;
    await NovelUI.api(`/api/v1/projects/${projectId}/locations`, {
      method: "POST",
      body: {
          name: candidate.name,
          location_type: candidate.location_type,
          description: candidate.description,
          source_note: candidate.source_note,
        },
    });
    NovelUI.toast("施設候補を追加しました。");
    await loadWorldMap();
    await loadCandidates();
  }

  async function showRelatedSources(locationId) {
    const related = await NovelUI.api(`/api/v1/locations/${locationId}/related-sources`);
    const count = (related.feed_posts || []).length + (related.chat_messages || []).length + (related.story_messages || []).length;
    const lines = [
      ...(related.feed_posts || []).map((item) => `Feed #${item.id}: ${item.body}`),
      ...(related.chat_messages || []).map((item) => `チャット #${item.session_id}: ${item.speaker_name || ""} ${item.message_text}`),
      ...(related.story_messages || []).map((item) => `セッション #${item.session_id}: ${item.speaker_name || ""} ${item.message_text}`),
    ];
    window.alert(count ? lines.join("\n\n") : "関連履歴はまだ見つかりません。");
  }

  async function selectMapImage(imageId) {
    await NovelUI.api(`/api/v1/projects/${projectId}/world-map/images/${imageId}/select`, { method: "POST" });
    await loadWorldMap();
  }

  async function deleteMapImage(imageId) {
    if (!window.confirm("この俯瞰図を削除しますか？")) return;
    await NovelUI.api(`/api/v1/projects/${projectId}/world-map/images/${imageId}`, { method: "DELETE" });
    NovelUI.toast("俯瞰図を削除しました。");
    await loadWorldMap();
  }

  locationForm?.addEventListener("submit", (event) => {
    saveLocation(event).catch((error) => NovelUI.toast(error.message || "施設の保存に失敗しました。", "danger"));
  });
  locationAiAssistButton?.addEventListener("click", () => {
    assistLocation().catch((error) => NovelUI.toast(error.message || "施設情報のAI補完に失敗しました。", "danger"));
  });
  locationResetButton?.addEventListener("click", resetForm);
  mapUploadInput?.addEventListener("change", () => {
    uploadMapImage(mapUploadInput.files?.[0]).catch((error) => NovelUI.toast(error.message || "アップロードに失敗しました。", "danger"));
  });
  mapGenerateButton?.addEventListener("click", () => {
    generateMapImage().catch((error) => NovelUI.toast(error.message || "俯瞰図の生成に失敗しました。", "danger"));
  });
  [searchInput, regionFilter, typeFilter, tagFilter].forEach((element) => {
    element?.addEventListener("input", applyLocationFilters);
    element?.addEventListener("change", applyLocationFilters);
  });
  candidatesButton?.addEventListener("click", () => {
    loadCandidates().catch((error) => NovelUI.toast(error.message || "候補抽出に失敗しました。", "danger"));
  });
  candidateList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-candidate]");
    if (!button) return;
    addCandidate(button.dataset.addCandidate).catch((error) => NovelUI.toast(error.message || "候補の追加に失敗しました。", "danger"));
  });
  mapImageList?.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-map-image]");
    if (deleteButton && canManage) {
      deleteMapImage(deleteButton.dataset.deleteMapImage).catch((error) => NovelUI.toast(error.message || "俯瞰図の削除に失敗しました。", "danger"));
      return;
    }
    const button = event.target.closest("[data-map-image-id]");
    if (!button || !canManage) return;
    selectMapImage(button.dataset.mapImageId).catch((error) => NovelUI.toast(error.message || "ワールドマップ画像の選択に失敗しました。", "danger"));
  });
  locationList?.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-edit-location]");
    const deleteButton = event.target.closest("[data-delete-location]");
    const generateButton = event.target.closest("[data-generate-location-image]");
    const relatedButton = event.target.closest("[data-related-location]");
    const imageButton = event.target.closest("[data-open-location-image]");
    const descriptionButton = event.target.closest("[data-toggle-location-description]");
    if (imageButton) openLocationImage(imageButton.dataset.openLocationImage);
    if (descriptionButton) {
      const panel = document.getElementById(`world-location-description-${descriptionButton.dataset.toggleLocationDescription}`);
      const willOpen = panel?.hidden;
      if (panel) panel.hidden = !willOpen;
      descriptionButton.setAttribute("aria-expanded", String(Boolean(willOpen)));
      descriptionButton.classList.toggle("active", Boolean(willOpen));
    }
    if (editButton) editLocation(editButton.dataset.editLocation);
    if (deleteButton) deleteLocation(deleteButton.dataset.deleteLocation).catch((error) => NovelUI.toast(error.message || "施設の削除に失敗しました。", "danger"));
    if (relatedButton) showRelatedSources(relatedButton.dataset.relatedLocation).catch((error) => NovelUI.toast(error.message || "関連履歴の取得に失敗しました。", "danger"));
    if (generateButton) {
      generateLocationImage(generateButton.dataset.generateLocationImage, generateButton).catch((error) => {
        NovelUI.toast(error.message || "施設イメージの生成に失敗しました。", "danger");
      });
    }
  });
  locationList?.addEventListener("change", (event) => {
    const input = event.target.closest("[data-location-image-input]");
    if (!input) return;
    uploadLocationImage(input.dataset.locationImageInput, input.files?.[0]).catch((error) => NovelUI.toast(error.message || "施設画像のアップロードに失敗しました。", "danger"));
  });

  Promise.all([loadCharacters(), loadWorldMap()]).catch((error) => {
    NovelUI.toast(error.message || "ワールドマップの読み込みに失敗しました。", "danger");
  });
})();
