
(() => {
  const projectId = Number(1);
  const canManageProject = true;
  const editToggleButton = document.getElementById("projectEditToggleButton");
  const quickEditButton = document.getElementById("projectQuickEditButton");
  const editCancelButton = document.getElementById("projectEditCancelButton");
  const editForm = document.getElementById("projectEditForm");
  const titleInput = document.getElementById("projectTitleInput");
  const summaryInput = document.getElementById("projectSummaryInput");
  const projectStatusSelect = document.getElementById("projectStatusSelect");
  const signboardPreview = document.getElementById("worldSignboardPreview");
  const signboardUploadForm = document.getElementById("worldSignboardUploadForm");
  const signboardDropzone = document.getElementById("worldSignboardDropzone");
  const signboardFileInput = signboardUploadForm?.querySelector('[name="file"]');
  const signboardGenerateButton = document.getElementById("worldSignboardGenerateButton");
  const params = new URLSearchParams(window.location.search);

  function setEditVisible(visible) {
    if (!canManageProject || !editForm || !editToggleButton) return;
    editForm.hidden = !visible;
    editToggleButton.textContent = visible ? "編集中" : "ワールド情報を編集";
    if (visible) {
      titleInput?.focus();
      titleInput?.select();
    }
  }

  function normalizeProjectStatus(status) {
    return status === "published" || status === "active" ? "published" : "draft";
  }

  function statusLabel(status) {
    return normalizeProjectStatus(status) === "published" ? "公開" : "下書き";
  }

  function renderMetaChips(project) {
    const chips = [`ステータス: ${statusLabel(project?.status)}`];
    document.getElementById("projectMetaChips").innerHTML = chips
      .map((item) => `<span class="soft-code">${NovelUI.escape(item)}</span>`)
      .join("");
  }

  function renderSignboard(project) {
    if (!signboardPreview) return;
    const asset = project?.thumbnail_asset;
    if (asset?.media_url) {
      signboardPreview.innerHTML = `
        <img src="${asset.media_url}" alt="${NovelUI.escape(project?.title || "ワールド看板")}" class="world-signboard-image">
        <div class="small text-secondary mt-2">${NovelUI.escape(asset.file_name || "看板画像")}</div>
      `;
      return;
    }
    signboardPreview.innerHTML = `
      <div class="empty-panel mb-0">
        看板画像はまだ登録されていません。アップロードするか、世界観設定から生成してください。
      </div>
    `;
  }

  async function loadOverview() {
    const [project, characters, sessions] = await Promise.all([
      NovelUI.api(`/api/v1/projects/${projectId}`),
      NovelUI.api(`/api/v1/projects/${projectId}/characters`),
      NovelUI.api(`/api/v1/chat/sessions?project_id=${projectId}`),
    ]);

    const characterList = Array.isArray(characters) ? characters : [];
    const sessionList = Array.isArray(sessions) ? sessions : [];

    document.getElementById("projectHomeTitle").textContent = project?.title || "Untitled";
    document.getElementById("projectHomeSummary").textContent =
      project?.summary || "キャラクターとライブチャットを楽しむためのワールドホームです。";
    renderMetaChips(project);
    renderSignboard(project);

    if (canManageProject) {
      titleInput.value = project?.title || "";
      summaryInput.value = project?.summary || "";
      projectStatusSelect.value = normalizeProjectStatus(project?.status);
    }

    document.getElementById("projectStatsRow").innerHTML = [
      ["キャラクター", characterList.length],
      ["ライブチャット", sessionList.length],
      ["ステータス", statusLabel(project?.status)],
    ].map(([label, value]) => `
      <article class="metric-card"><div class="metric-label">${NovelUI.escape(label)}</div><div class="metric-value">${NovelUI.escape(String(value))}</div></article>
    `).join("");

    const recentList = sessionList
      .slice()
      .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))
      .slice(0, 5);

    document.getElementById("recentLiveChatList").innerHTML = recentList.length ? recentList.map((item) => `
      <a class="list-row" href="/projects/${projectId}/live-chat/${item.id}">
        <div>
          <div class="list-title">${NovelUI.escape(item.title || "ライブチャットセッション")}</div>
          <div class="list-subtitle">${NovelUI.escape(item.last_message_text || "まだ会話メッセージがありません。")}</div>
        </div>
        <span class="soft-code">${NovelUI.escape(String(item.message_count || 0))} messages</span>
      </a>
      `).join("") : `<div class="empty-panel">まだライブチャットセッションがありません。</div>`;
  }

  editToggleButton?.addEventListener("click", () => {
    setEditVisible(editForm.hidden);
  });

  quickEditButton?.addEventListener("click", () => {
    setEditVisible(true);
  });

  editCancelButton?.addEventListener("click", () => {
    setEditVisible(false);
  });

  editForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = {
      title: titleInput.value.trim(),
      summary: summaryInput.value.trim(),
      status: projectStatusSelect.value,
    };

    if (!body.title) {
      NovelUI.toast("作品名を入力してください。", "warning");
      titleInput.focus();
      return;
    }

    try {
      await NovelUI.api(`/api/v1/projects/${projectId}`, { method: "PATCH", body });
      setEditVisible(false);
      params.delete("edit");
      const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
      window.history.replaceState({}, "", nextUrl);
      await loadOverview();
      NovelUI.toast("ワールド情報を更新しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ワールド情報の更新に失敗しました。", "danger");
    }
  });

  function setSignboardDropzoneActive(active) {
    signboardDropzone?.classList.toggle("is-dragover", active);
  }

  function ensureImageFile(file) {
    if (!file) {
      NovelUI.toast("アップロードする看板画像を選択してください。", "warning");
      return false;
    }
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("画像ファイルのみアップロードできます。", "warning");
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
      NovelUI.toast("ワールド看板画像を更新しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ワールド看板画像のアップロードに失敗しました。", "danger");
    } finally {
      setSignboardDropzoneActive(false);
    }
  }

  function setGeneratingSignboard(active) {
    if (!signboardGenerateButton) return;
    signboardGenerateButton.disabled = active;
    signboardGenerateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>看板を生成中...'
      : '<i class="bi bi-stars"></i><span>世界観から看板を生成</span>';
  }

  async function generateSignboard() {
    setGeneratingSignboard(true);
    try {
      const project = await NovelUI.api(`/api/v1/projects/${projectId}/signboard/generate`, {
        method: "POST",
        body: { size: "1536x1024" },
      });
      renderSignboard(project);
      NovelUI.toast("世界観からワールド看板画像を生成しました。");
    } catch (error) {
      NovelUI.toast(error.message || "ワールド看板画像の生成に失敗しました。", "danger");
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

  loadOverview().then(() => {
    if (canManageProject && params.get("edit") === "1") {
      setEditVisible(true);
    }
  }).catch((error) => {
    NovelUI.toast(error.message || "ワールドホームの読み込みに失敗しました。", "danger");
  });
})();
