(() => {
  const projectId = Number(document.querySelector("[data-project-id]")?.dataset.projectId || 0);
  const worldForm = document.getElementById("worldForm");
  const markdownGrid = document.getElementById("worldMarkdownGrid");
  const draftButton = document.getElementById("worldAiDraft");
  const modalElement = document.getElementById("markdownEditorModal");
  document.body.appendChild(modalElement);
  const modalTitle = document.getElementById("markdownEditorTitle");
  const modalTextarea = document.getElementById("markdownEditorTextarea");
  const modalPreview = document.getElementById("markdownEditorPreview");
  const modalApplyButton = document.getElementById("markdownEditorApply");

  const markdownFields = [
    { name: "time_period", label: "時代背景", hint: "いつの時代か、何が起きているか", placeholder: "## 時代\n- \n\n## 現在起きていること\n- " },
    { name: "place_description", label: "場所説明", hint: "主要エリア、街並み、生活空間、危険な場所", placeholder: "## 主要エリア\n- \n\n## 街並み\n- \n\n## 危険な場所\n- " },
    { name: "technology_level", label: "技術水準", hint: "AI、交通、医療、通信など", placeholder: "- AI:\n- 交通:\n- 医療:\n- 通信:" },
    { name: "social_structure", label: "社会構造", hint: "階層、権力、市民生活、経済など", placeholder: "- 階層:\n- 権力:\n- 市民生活:\n- 経済:" },
    { name: "important_facilities", label: "重要施設 / ルール", hint: "重要施設と、この世界で守られるルール", placeholder: "## 重要施設\n- 施設名: 役割\n\n## ルール\n- " },
    { name: "forbidden_settings", label: "禁止設定", hint: "出してはいけない設定、矛盾させたくない設定", placeholder: "- 出してはいけない設定\n- 矛盾させたくない設定\n- キャラクターに言わせたくないこと" },
  ];

  const markdownEditor = MarkdownEditor.create({
    form: worldForm,
    grid: markdownGrid,
    fields: markdownFields,
    modalElement,
    modalTitle,
    modalTextarea,
    modalPreview,
    modalApplyButton,
    previewLength: 140,
  });

  function formPayload() {
    return Object.fromEntries(new FormData(worldForm).entries());
  }

  function setDrafting(active) {
    draftButton.disabled = active;
    draftButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>AI仮入力中...'
      : "AIで仮入力";
  }

  async function generateDraft() {
    setDrafting(true);
    try {
      const payload = await NovelUI.api(`/api/v1/projects/${projectId}/world/draft`, {
        method: "POST",
        body: { ui_fields: formPayload() },
      });
      if (!payload?.draft) throw new Error("AI仮入力の応答が不正です。");
      NovelUI.fillForm(worldForm, payload.draft);
      markdownEditor.renderCards();
      NovelUI.toast("世界観をAIで仮入力しました。内容を確認して保存してください。");
    } catch (error) {
      NovelUI.toast(error.message || "世界観のAI仮入力に失敗しました。", "danger");
    } finally {
      setDrafting(false);
    }
  }

  async function loadWorldContext() {
    const payload = await NovelUI.api(`/api/v1/projects/${projectId}/world-context`);
    if (payload.world?.ui_fields) {
      NovelUI.fillForm(worldForm, payload.world.ui_fields);
    }
    markdownEditor.renderCards();
  }

  draftButton.addEventListener("click", generateDraft);

  worldForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await NovelUI.api(`/api/v1/projects/${projectId}/world`, { method: "PUT", body: formPayload() });
      NovelUI.toast("世界観を保存しました。");
      await loadWorldContext();
    } catch (error) {
      NovelUI.toast(error.message || "保存に失敗しました。", "danger");
    }
  });

  markdownEditor.renderCards();
  loadWorldContext().catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
})();
