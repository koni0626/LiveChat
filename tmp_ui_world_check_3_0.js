
(() => {
  const projectId = Number(1);
  const canManageProject = false;
  const editToggleButton = document.getElementById("projectEditToggleButton");
  const quickEditButton = document.getElementById("projectQuickEditButton");
  const editCancelButton = document.getElementById("projectEditCancelButton");
  const editForm = document.getElementById("projectEditForm");
  const titleInput = document.getElementById("projectTitleInput");
  const summaryInput = document.getElementById("projectSummaryInput");
  const projectStatusSelect = document.getElementById("projectStatusSelect");
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

  loadOverview().then(() => {
    if (canManageProject && params.get("edit") === "1") {
      setEditVisible(true);
    }
  }).catch((error) => {
    NovelUI.toast(error.message || "ワールドホームの読み込みに失敗しました。", "danger");
  });
})();
