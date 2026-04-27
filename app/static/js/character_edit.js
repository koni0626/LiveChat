(function () {
  const root = document.querySelector("[data-character-editor]");
  if (!root) return;

  const projectId = Number(root.dataset.projectId || document.body.dataset.projectId);
  const initialCharacterId = root.dataset.characterId ? Number(root.dataset.characterId) : null;
  let currentCharacterId = initialCharacterId;

  const form = document.getElementById("characterForm");
  const deleteButton = document.getElementById("characterDeleteButton");
  const generateForm = document.getElementById("baseAssetGenerateForm");
  const generateButton = document.getElementById("generateBaseImageButton");
  const baseAssetUploadForm = document.getElementById("baseAssetUploadForm");
  const baseAssetPreview = document.getElementById("baseAssetPreview");
  const baseAssetDropzone = document.getElementById("baseAssetDropzone");
  const baseAssetFileInput = baseAssetUploadForm.querySelector('[name="file"]');
  const markdownGrid = document.getElementById("characterMarkdownGrid");
  const modalElement = document.getElementById("markdownEditorModal");
  document.body.appendChild(modalElement);
  const modalTitle = document.getElementById("markdownEditorTitle");
  const modalTextarea = document.getElementById("markdownEditorTextarea");
  const modalPreview = document.getElementById("markdownEditorPreview");
  const modalApplyButton = document.getElementById("markdownEditorApply");

  const markdownFields = [
    { name: "appearance_summary", label: "外見要約", hint: "見た目、服装、雰囲気、画像生成で守りたい特徴", placeholder: "## 全体印象\n- \n\n## 髪・顔\n- \n\n## 衣装\n- " },
    { name: "art_style", label: "画風", hint: "ライブチャット画像、場面転換画像、メール画像で優先する絵柄・塗り・色味", placeholder: "- サイバー都市のネオン感\n- 高品質な日本アニメ調\n- 線は繊細、塗りは透明感強め\n- 文字・字幕・吹き出しなし" },
    { name: "personality", label: "性格", hint: "価値観、癖、反応、怒り方・喜び方", placeholder: "- 基本性格\n- 嬉しい時\n- 嫌な時" },
    { name: "likes_text", label: "好きなもの", hint: "贈り物判定、会話評価、話題作りに使う好み・物品・モチーフ・行動", placeholder: "- ぬいぐるみ\n- 甘いもの\n- 夜景\n- 丁寧に褒められる\n- 共通の趣味を見つける" },
    { name: "dislikes_text", label: "嫌いなもの", hint: "評価を下げやすい話題や態度", placeholder: "- 命令口調\n- 雑に扱われること" },
    { name: "hobbies_text", label: "趣味", hint: "会話のフックになる趣味や習慣", placeholder: "- 読書\n- 散歩" },
    { name: "taboos_text", label: "地雷・苦手なもの", hint: "避けたい話題、苦手な接し方", placeholder: "- 初対面で踏み込みすぎる\n- 過去を詮索される" },
    { name: "romance_favorite_approach_text", label: "恋愛: 好きな距離の詰め方", hint: "好感度が上がりやすい近づき方", placeholder: "- 自然に隣へ来る\n- 小さな変化に気づく" },
    { name: "romance_avoid_approach_text", label: "恋愛: 苦手な距離の詰め方", hint: "引いてしまう接し方", placeholder: "- 急に馴れ馴れしい\n- 支配的な言い方" },
    { name: "romance_attraction_points_text", label: "恋愛: 刺さるポイント", hint: "惹かれる言葉、態度、シチュエーション", placeholder: "- 知的な会話\n- 余裕のある優しさ" },
    { name: "romance_boundaries_text", label: "恋愛: 境界線", hint: "越えてはいけないライン", placeholder: "- 本心を無理に聞き出さない\n- 大切なものを笑わない" },
    { name: "memorable_events_text", label: "印象イベント", hint: "記憶しておきたい出来事", placeholder: "- 初めて贈り物をもらった\n- 価値観が近いと感じた" },
    { name: "memory_notes", label: "会話メモ", hint: "会話から覚えておきたい補足情報", placeholder: "## 覚えておくこと\n- " },
    { name: "speech_style", label: "話し方", hint: "一人称、語尾、テンポ、口癖、会話の癖", placeholder: "- 一人称:\n- 語尾:\n- 口癖:" },
    { name: "speech_sample", label: "セリフサンプル", hint: "実際に言いそうなセリフ", placeholder: "- 「こんにちは。今日は何のお話をする？」\n- 「それ、少し気になるね。」" },
    { name: "ng_rules", label: "NGルール", hint: "絶対に言わせないこと、崩してはいけない設定", placeholder: "- 案内役と言わない\n- 口調を変えない" },
  ];

  const markdownEditor = MarkdownEditor.create({
    form,
    grid: markdownGrid,
    fields: markdownFields,
    modalElement,
    modalTitle,
    modalTextarea,
    modalPreview,
    modalApplyButton,
    previewLength: 120,
  });

  function characterPayload() {
    const body = Object.fromEntries(new FormData(form).entries());
    body.base_asset_id = body.base_asset_id ? Number(body.base_asset_id) : null;
    return body;
  }

  function renderBaseAsset(asset) {
    if (!asset?.media_url) {
      baseAssetPreview.innerHTML = `
        <div class="base-asset-empty">
          <div class="base-asset-empty-icon"><i class="bi bi-image"></i></div>
          <div>
            <div class="base-asset-empty-title">基準画像はまだ登録されていません</div>
            <div class="base-asset-empty-text">画像をアップロードするか、基本情報から全身像を生成してください。</div>
          </div>
        </div>
      `;
      return;
    }
    baseAssetPreview.innerHTML = `
      <div class="vstack gap-2">
        <img src="${asset.media_url}" alt="${NovelUI.escape(asset.file_name || "base asset")}" class="img-fluid rounded-4 border">
        <div class="small text-secondary">${NovelUI.escape(asset.file_name || "")}</div>
      </div>
    `;
  }

  async function saveCharacter({ silent = false } = {}) {
    const body = characterPayload();
    let character;
    if (currentCharacterId) {
      character = await NovelUI.api(`/api/v1/characters/${currentCharacterId}`, { method: "PATCH", body });
    } else {
      character = await NovelUI.api(`/api/v1/projects/${projectId}/characters`, { method: "POST", body });
      currentCharacterId = character.id;
    }
    NovelUI.fillForm(form, character);
    renderBaseAsset(character.base_asset);
    markdownEditor.renderCards();
    if (!silent) NovelUI.toast("キャラクターを保存しました。");
    return character;
  }

  function setDropzoneActive(active) {
    baseAssetDropzone.classList.toggle("is-dragover", active);
  }

  function ensureImageFile(file) {
    if (!file) {
      NovelUI.toast("アップロードする画像を選択してください。", "warning");
      return false;
    }
    if (!file.type.startsWith("image/")) {
      NovelUI.toast("画像ファイルのみアップロードできます。", "warning");
      return false;
    }
    return true;
  }

  async function uploadBaseAsset(file) {
    if (!ensureImageFile(file)) return;
    const uploadPayload = new FormData();
    uploadPayload.append("file", file);
    uploadPayload.append("project_id", String(projectId));
    uploadPayload.append("asset_type", "reference_image");
    try {
      const response = await fetch("/api/v1/assets/upload", { method: "POST", body: uploadPayload, credentials: "same-origin" });
      const payload = await response.json().catch(() => ({}));
      const asset = payload?.data;
      if (!response.ok || !asset) throw new Error(payload?.message || `HTTP ${response.status}`);
      form.querySelector('[name="base_asset_id"]').value = asset.id;
      renderBaseAsset(asset);
      if (currentCharacterId) {
        const character = await NovelUI.api(`/api/v1/characters/${currentCharacterId}`, { method: "PATCH", body: { base_asset_id: asset.id } });
        renderBaseAsset(character.base_asset);
      }
      baseAssetFileInput.value = "";
      NovelUI.toast("基準画像をアップロードしました。");
    } catch (error) {
      NovelUI.toast(error.message || "基準画像のアップロードに失敗しました。", "danger");
    } finally {
      setDropzoneActive(false);
    }
  }

  function setGenerating(active) {
    generateButton.disabled = active;
    generateButton.innerHTML = active
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>全身像を生成中...'
      : '<i class="bi bi-stars"></i><span>全身像を生成</span>';
  }

  async function generateBaseImage() {
    setGenerating(true);
    try {
      const character = await saveCharacter({ silent: true });
      const body = Object.fromEntries(new FormData(generateForm).entries());
      const generated = await NovelUI.api(`/api/v1/characters/${character.id}/base-image/generate`, { method: "POST", body });
      NovelUI.fillForm(form, generated);
      renderBaseAsset(generated.base_asset);
      markdownEditor.renderCards();
      NovelUI.toast("基本情報から全身像を生成し、基準画像に設定しました。");
      if (!initialCharacterId) {
        history.replaceState(null, "", `/projects/${projectId}/characters/${generated.id}/edit`);
      }
    } catch (error) {
      NovelUI.toast(error.message || "全身像の生成に失敗しました。", "danger");
    } finally {
      setGenerating(false);
    }
  }

  async function deleteCharacter() {
    if (!currentCharacterId || !deleteButton) return;
    const name = form.querySelector('[name="name"]')?.value || "このキャラクター";
    if (!confirm(`${name}を削除しますか？削除後は一覧に表示されません。`)) {
      return;
    }

    deleteButton.disabled = true;
    try {
      await NovelUI.api(`/api/v1/characters/${currentCharacterId}`, { method: "DELETE" });
      NovelUI.toast("キャラクターを削除しました。");
      location.href = `/projects/${projectId}/characters`;
    } catch (error) {
      deleteButton.disabled = false;
      NovelUI.toast(error.message || "キャラクターの削除に失敗しました。", "danger");
    }
  }

  async function loadCharacter() {
    if (deleteButton) {
      deleteButton.hidden = !currentCharacterId;
    }
    markdownEditor.renderCards();
    if (!currentCharacterId) {
      renderBaseAsset(null);
      return;
    }
    const character = await NovelUI.api(`/api/v1/characters/${currentCharacterId}`);
    NovelUI.fillForm(form, character);
    renderBaseAsset(character.base_asset);
    markdownEditor.renderCards();
  }

  function bindDropzone() {
    baseAssetDropzone.addEventListener("click", (event) => {
      if (event.target !== baseAssetFileInput) baseAssetFileInput.click();
    });
    baseAssetDropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        baseAssetFileInput.click();
      }
    });
    ["dragenter", "dragover"].forEach((eventName) => {
      baseAssetDropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        setDropzoneActive(true);
      });
    });
    ["dragleave", "dragend"].forEach((eventName) => {
      baseAssetDropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!baseAssetDropzone.contains(event.relatedTarget)) setDropzoneActive(false);
      });
    });
    baseAssetDropzone.addEventListener("drop", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const [file] = event.dataTransfer?.files || [];
      await uploadBaseAsset(file);
    });
  }

  function bindEvents() {
    deleteButton?.addEventListener("click", deleteCharacter);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const character = await saveCharacter();
        if (!initialCharacterId) {
          location.href = `/projects/${projectId}/characters/${character.id}/edit`;
        }
      } catch (error) {
        NovelUI.toast(error.message || "保存に失敗しました。", "danger");
      }
    });

    generateForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await generateBaseImage();
    });

    baseAssetUploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await uploadBaseAsset(baseAssetFileInput.files[0]);
    });

    document.getElementById("characterAiAssist").addEventListener("click", () => {
      const button = document.getElementById("characterAiAssist");
      button.disabled = true;
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>AI仮入力中...';
      NovelUI.api(`/api/v1/projects/${projectId}/characters/draft`, {
        method: "POST",
        body: { current_character: characterPayload() },
      }).then((payload) => {
        if (!payload?.draft) {
          throw new Error("AI仮入力の応答が不正です。");
        }
        NovelUI.fillForm(form, payload.draft);
        markdownEditor.renderCards();
        NovelUI.toast("世界観をもとにキャラクターを仮入力しました。");
      }).catch((error) => {
        NovelUI.toast(error.message || "キャラクターのAI仮入力に失敗しました。", "danger");
      }).finally(() => {
        button.disabled = false;
        button.innerHTML = "AI補完";
      });
    });

    bindDropzone();
  }

  bindEvents();
  loadCharacter().catch((error) => {
    NovelUI.toast(error.message || "読み込みに失敗しました。", "danger");
  });
})();
