(() => {
  const projectId = document.body.dataset.projectId;
  const generatedSaveForm = document.getElementById("closetGeneratedSaveForm");
  const newOutfitButton = document.getElementById("closetNewOutfitButton");
  const detailCreateFields = document.getElementById("closetDetailCreateFields");
  const detailCharacterSelect = document.getElementById("closetDetailCharacterSelect");
  const detailPromptInput = document.getElementById("closetDetailPromptInput");
  const filterCharacter = document.getElementById("closetFilterCharacter");
  const grid = document.getElementById("closetGrid");
  const countLabel = document.getElementById("closetCount");
  const loading = document.getElementById("closetLoading");
  const generateImageButton = document.getElementById("closetGenerateImageButton");
  const generateImageSpinner = document.getElementById("closetGenerateImageSpinner");
  const generateImageButtonText = document.getElementById("closetGenerateImageButtonText");
  const generatedSaveButton = document.getElementById("closetGeneratedSaveButton");
  const generatedSaveButtonText = document.getElementById("closetGeneratedSaveButtonText");
  const detailModalElement = document.getElementById("closetDetailModal");
  const detailModal = new bootstrap.Modal(detailModalElement);
  const detailModalTitle = document.getElementById("closetDetailModalTitle");
  const detailPreviewImage = document.getElementById("closetDetailPreviewImage");
  const detailPreviewEmpty = document.getElementById("closetDetailPreviewEmpty");
  const refreshButton = document.getElementById("closetRefreshButton");
  const uploadDrop = document.getElementById("closetUploadDrop");
  const uploadInput = document.getElementById("closetUploadInput");
  const uploadLabel = document.getElementById("closetUploadLabel");

  document.body.appendChild(detailModalElement);

  let state = { characters: [], outfits: [] };
  let generatedDraft = null;
  let isGeneratingImage = false;
  let uploadedPreviewUrl = "";

  function resolveGeneratedImageUrl(payload) {
    if (!payload || typeof payload !== "object") return "";
    return String(
      payload.image_url
      || payload.media_url
      || payload.url
      || payload.asset?.media_url
      || payload.asset?.url
      || ""
    ).trim();
  }

  async function fetchAssetMediaUrl(assetId) {
    const id = Number(assetId || 0);
    if (!id) return "";
    try {
      const asset = await NovelUI.api(`/api/v1/assets/${id}`);
      return String(asset?.media_url || "").trim();
    } catch (_error) {
      return "";
    }
  }

  function normalizeApiResponse(payload) {
    if (payload && typeof payload === "object" && "data" in payload) return payload.data;
    return payload;
  }

  async function submitMultipart(url, method, formData) {
    const response = await fetch(url, {
      method,
      body: formData,
      credentials: "same-origin",
      cache: "no-store",
    });
    const payload = await response.json().catch(() => ({}));
    const data = normalizeApiResponse(payload);
    if (!response.ok) {
      throw new Error(data?.message || payload?.message || `HTTP ${response.status}`);
    }
    return data;
  }

  function getUploadFile() {
    return uploadInput?.files?.[0] || generatedDraft?.upload_file || null;
  }

  function canSaveDraft() {
    return Boolean(generatedDraft?.outfit_id || generatedDraft?.asset_id || getUploadFile());
  }

  function updateSaveButtonState(active = false) {
    generatedSaveButton.disabled = Boolean(active || isGeneratingImage || !canSaveDraft());
  }

  function clearUploadSelection() {
    if (uploadedPreviewUrl) {
      URL.revokeObjectURL(uploadedPreviewUrl);
      uploadedPreviewUrl = "";
    }
    if (uploadInput) uploadInput.value = "";
    if (uploadLabel) uploadLabel.textContent = "画像を選択 / ドロップ";
    if (generatedDraft) delete generatedDraft.upload_file;
  }

  function setGeneratedPreview(draft) {
    const previewUrl = String(draft?.image_url || "").trim();
    detailPreviewImage.src = previewUrl;
    detailPreviewImage.alt = draft?.name || "衣装画像";
    detailPreviewImage.classList.toggle("d-none", !previewUrl);
    detailPreviewEmpty.classList.toggle("d-none", Boolean(previewUrl));
  }

  function setUploadFile(file) {
    if (!file) return;
    if (!/^image\/(png|jpeg|webp)$/.test(file.type || "")) {
      NovelUI.toast("PNG / JPEG / WebP の画像を選択してください。", "danger");
      return;
    }
    clearUploadSelection();
    uploadedPreviewUrl = URL.createObjectURL(file);
    generatedDraft = {
      ...(generatedDraft || {}),
      upload_file: file,
      asset_id: null,
      image_url: uploadedPreviewUrl,
    };
    if (uploadLabel) uploadLabel.textContent = file.name || "アップロード画像を選択中";
    setGeneratedPreview(generatedDraft);
    updateSaveButtonState(false);
  }

  function setLoading(active) {
    loading.classList.toggle("d-none", !active);
    newOutfitButton.disabled = active;
    generateImageButton.disabled = active || isGeneratingImage;
    updateSaveButtonState(active);
    refreshButton.disabled = active;
  }

  function setImageGenerating(active) {
    isGeneratingImage = active;
    detailPreviewImage.parentElement.classList.toggle("is-generating", active);
    generateImageSpinner.classList.toggle("d-none", !active);
    generateImageButton.disabled = active;
    updateSaveButtonState(active);
    generateImageButtonText.textContent = active
      ? "画像を生成中..."
      : (generatedDraft?.asset_id ? "画像を再生成" : "画像を生成");
  }

  function renderCharacterSelects() {
    const currentFilterCharacter = filterCharacter.value || "";
    const currentDetailCharacter = detailCharacterSelect.value || "";
    const options = state.characters
      .map((character) => `<option value="${character.id}">${NovelUI.escape(character.name || "Character")}</option>`)
      .join("");
    detailCharacterSelect.innerHTML = options || '<option value="">キャラクターがありません</option>';
    filterCharacter.innerHTML = '<option value="">すべてのキャラクター</option>' + options;
    if ([...filterCharacter.options].some((option) => option.value === currentFilterCharacter)) {
      filterCharacter.value = currentFilterCharacter;
    }
    if ([...detailCharacterSelect.options].some((option) => option.value === currentDetailCharacter)) {
      detailCharacterSelect.value = currentDetailCharacter;
    }
  }

  function openDetailFormForDraft(draft) {
    clearUploadSelection();
    generatedDraft = draft;
    const isEdit = Boolean(draft.outfit_id);
    detailModalTitle.textContent = isEdit ? "衣装情報を編集" : "新規衣装を追加";
    detailCreateFields.classList.toggle("d-none", isEdit);
    generateImageButton.classList.remove("d-none");
    generateImageButtonText.textContent = draft.asset_id ? "画像を再生成" : "画像を生成";
    setGeneratedPreview(draft);
    generatedSaveButtonText.textContent = isEdit ? "変更を保存" : "この画像を衣装として保存";
    detailCharacterSelect.value = draft.character_id || detailCharacterSelect.value || "";
    detailPromptInput.value = draft.prompt_text || draft.prompt_notes || "";
    document.getElementById("closetGeneratedNameInput").value = draft.name || "";
    document.getElementById("closetGeneratedDescriptionInput").value = draft.description || "";
    document.getElementById("closetGeneratedUsageSelect").value = draft.usage_scene || "";
    document.getElementById("closetGeneratedSeasonSelect").value = draft.season || "";
    document.getElementById("closetGeneratedTagsInput").value = Array.isArray(draft.tags) ? draft.tags.join(", ") : "";
    updateSaveButtonState(false);
    detailModal.show();
  }

  function openNewOutfitModal() {
    openDetailFormForDraft({
      character_id: Number(detailCharacterSelect.value || state.characters[0]?.id || 0),
      prompt_text: "",
      name: "",
      description: "",
      usage_scene: "",
      season: "",
      tags: [],
      image_url: "",
      asset_id: null,
    });
  }

  function renderOutfits() {
    const selectedCharacterId = Number(filterCharacter.value || 0);
    const outfits = state.outfits.filter((outfit) => !selectedCharacterId || Number(outfit.character_id) === selectedCharacterId);
    countLabel.textContent = `${outfits.length} outfits`;
    if (!outfits.length) {
      grid.innerHTML = `
        <div class="empty-panel closet-empty">
          <i class="bi bi-person-bounding-box"></i>
          <div>
            <strong>衣装はまだありません。</strong>
            <p>キャラクターの衣装画像を生成またはアップロードして登録してください。</p>
          </div>
        </div>
      `;
      return;
    }
    grid.innerHTML = outfits.map((outfit) => {
      const imageUrl = outfit.thumbnail_asset?.media_url || outfit.asset?.media_url || "";
      const character = state.characters.find((item) => Number(item.id) === Number(outfit.character_id));
      const tags = Array.isArray(outfit.tags) ? outfit.tags : [];
      return `
        <article class="closet-card" data-outfit-id="${outfit.id}">
          <button class="closet-card-image closet-card-image-button" type="button" data-action="detail" aria-label="衣装詳細を編集">
            ${imageUrl ? `<img src="${NovelUI.escape(imageUrl)}" alt="">` : `<i class="bi bi-image"></i>`}
          </button>
          <div class="closet-card-body">
            <div class="closet-card-meta">
              <span>${NovelUI.escape(character?.name || "Character")}</span>
              <span>${NovelUI.escape(outfit.usage_scene || "outfit")}</span>
            </div>
            <h4>${NovelUI.escape(outfit.name || "衣装")}</h4>
            <details class="closet-description">
              <summary>説明を表示</summary>
              <p>${NovelUI.escape(outfit.description || "説明はありません。")}</p>
            </details>
            <div class="closet-tags">
              ${tags.map((tag) => `<span>${NovelUI.escape(tag)}</span>`).join("")}
            </div>
            <div class="closet-actions">
              <button class="btn btn-outline-light btn-sm" type="button" data-action="detail">
                <i class="bi bi-pencil-square"></i>
                編集
              </button>
              <button class="btn btn-outline-light btn-sm" type="button" data-action="delete">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </article>
      `;
    }).join("");
  }

  async function loadCloset() {
    setLoading(true);
    try {
      state = await NovelUI.api(`/api/v1/projects/${projectId}/outfits`);
      state.characters = Array.isArray(state.characters) ? state.characters : [];
      state.outfits = Array.isArray(state.outfits) ? state.outfits : [];
      renderCharacterSelects();
      renderOutfits();
    } finally {
      setLoading(false);
    }
  }

  generateImageButton.addEventListener("click", async () => {
    const characterId = Number(detailCharacterSelect.value || generatedDraft?.character_id || 0);
    const promptText = String(detailPromptInput.value || "").trim() || "おまかせの衣装";
    if (!characterId) {
      NovelUI.toast("キャラクターを選択してください。", "danger");
      return;
    }
    setLoading(true);
    setImageGenerating(true);
    try {
      const generated = await NovelUI.api(`/api/v1/projects/${projectId}/characters/${characterId}/outfits/generate`, {
        method: "POST",
        body: {
          prompt_text: promptText,
          reference_outfit_id: generatedDraft?.outfit_id || undefined,
          edit_existing: Boolean(generatedDraft?.outfit_id),
        },
      });
      clearUploadSelection();
      const resolvedUrl = resolveGeneratedImageUrl(generated) || await fetchAssetMediaUrl(generated?.asset_id);
      generatedDraft = {
        ...(generatedDraft || {}),
        character_id: characterId,
        asset_id: generated.asset_id,
        asset: generated.asset,
        image_url: resolvedUrl,
        prompt_text: promptText,
      };
      setGeneratedPreview(generatedDraft);
      generateImageButtonText.textContent = "画像を再生成";
      updateSaveButtonState(false);
      NovelUI.toast("画像を生成しました。気に入らなければプロンプトを変えて再生成できます。");
    } catch (error) {
      NovelUI.toast(error.message || "画像生成に失敗しました。", "danger");
    } finally {
      setImageGenerating(false);
      setLoading(false);
    }
  });

  detailPreviewImage.addEventListener("error", () => {
    detailPreviewImage.classList.add("d-none");
    detailPreviewEmpty.classList.remove("d-none");
  });

  uploadDrop?.addEventListener("click", () => uploadInput?.click());
  uploadDrop?.addEventListener("dragover", (event) => {
    event.preventDefault();
    uploadDrop.classList.add("is-dragover");
  });
  uploadDrop?.addEventListener("dragleave", () => {
    uploadDrop.classList.remove("is-dragover");
  });
  uploadDrop?.addEventListener("drop", (event) => {
    event.preventDefault();
    uploadDrop.classList.remove("is-dragover");
    setUploadFile(event.dataTransfer?.files?.[0]);
  });
  uploadInput?.addEventListener("change", () => {
    setUploadFile(uploadInput.files?.[0]);
  });

  generatedSaveForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!generatedDraft?.character_id && !detailCharacterSelect.value) return;
    const formData = new FormData(generatedSaveForm);
    const body = Object.fromEntries(formData.entries());
    const uploadFile = getUploadFile();
    const shouldUseMultipart = Boolean(uploadFile);
    const isEdit = Boolean(generatedDraft.outfit_id);
    if (uploadFile && uploadInput?.files?.[0] !== uploadFile) {
      formData.set("file", uploadFile, uploadFile.name || "outfit.png");
    }
    setLoading(true);
    try {
      if (isEdit) {
        body.name = String(body.name || "").trim() || generatedDraft.name || "衣装";
        body.prompt_notes = generatedDraft.prompt_text || generatedDraft.prompt_notes || "";
        if (generatedDraft.asset_id) {
          body.asset_id = generatedDraft.asset_id;
          body.thumbnail_asset_id = generatedDraft.asset_id;
        }
        if (shouldUseMultipart) {
          formData.set("name", body.name);
          formData.set("prompt_notes", body.prompt_notes);
          await submitMultipart(`/api/v1/outfits/${generatedDraft.outfit_id}`, "PATCH", formData);
        } else {
          await NovelUI.api(`/api/v1/outfits/${generatedDraft.outfit_id}`, {
            method: "PATCH",
            body,
          });
        }
      } else {
        const characterId = Number(detailCharacterSelect.value || generatedDraft.character_id || 0);
        const promptText = String(detailPromptInput.value || "").trim() || "おまかせの衣装";
        if (!characterId) throw new Error("キャラクターを選択してください。");
        if (!generatedDraft.asset_id && !uploadFile) throw new Error("画像を生成またはアップロードしてください。");
        body.name = String(body.name || "").trim() || promptText.slice(0, 80) || "衣装";
        body.prompt_notes = generatedDraft.prompt_text || promptText;
        if (shouldUseMultipart) {
          formData.set("name", body.name);
          formData.set("prompt_notes", body.prompt_notes);
          await submitMultipart(`/api/v1/projects/${projectId}/characters/${characterId}/outfits`, "POST", formData);
        } else {
          body.asset_id = generatedDraft.asset_id;
          body.thumbnail_asset_id = generatedDraft.asset_id;
          await NovelUI.api(`/api/v1/projects/${projectId}/characters/${characterId}/outfits`, {
            method: "POST",
            body,
          });
        }
      }
      clearUploadSelection();
      generatedDraft = null;
      generatedSaveForm.reset();
      detailModal.hide();
      await loadCloset();
      NovelUI.toast(isEdit ? "衣装情報を更新しました。" : "衣装を保存しました。");
    } catch (error) {
      NovelUI.toast(error.message || "衣装を保存できませんでした。", "danger");
    } finally {
      setLoading(false);
    }
  });

  newOutfitButton.addEventListener("click", openNewOutfitModal);
  filterCharacter.addEventListener("change", renderOutfits);
  refreshButton.addEventListener("click", () => loadCloset().catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger")));

  grid.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    const card = event.target.closest("[data-outfit-id]");
    if (!button || !card) return;
    const outfitId = card.dataset.outfitId;
    try {
      if (button.dataset.action === "detail") {
        const outfit = state.outfits.find((item) => Number(item.id) === Number(outfitId));
        if (!outfit) return;
        const imageUrl = outfit.thumbnail_asset?.media_url || outfit.asset?.media_url || "";
        openDetailFormForDraft({
          outfit_id: outfit.id,
          asset_id: outfit.asset?.id || outfit.thumbnail_asset?.id,
          character_id: outfit.character_id,
          name: outfit.name || "",
          description: outfit.description || "",
          usage_scene: outfit.usage_scene || "",
          season: outfit.season || "",
          tags: outfit.tags || [],
          prompt_notes: outfit.prompt_notes || "",
          prompt_text: outfit.prompt_notes || "",
          image_url: imageUrl,
        });
      } else if (button.dataset.action === "delete") {
        if (!window.confirm("この衣装を削除しますか？")) return;
        const previousFilterCharacter = filterCharacter.value || "";
        const previousScrollY = window.scrollY;
        await NovelUI.api(`/api/v1/outfits/${outfitId}`, { method: "DELETE" });
        if (previousFilterCharacter) filterCharacter.value = previousFilterCharacter;
        NovelUI.toast("衣装を削除しました。");
        await loadCloset();
        if (previousFilterCharacter && [...filterCharacter.options].some((option) => option.value === previousFilterCharacter)) {
          filterCharacter.value = previousFilterCharacter;
          renderOutfits();
        }
        window.scrollTo({ top: previousScrollY, left: 0, behavior: "instant" });
        return;
      }
      await loadCloset();
    } catch (error) {
      NovelUI.toast(error.message || "操作に失敗しました。", "danger");
    }
  });

  loadCloset().catch((error) => NovelUI.toast(error.message || "クローゼットを読み込めませんでした。", "danger"));
})();
