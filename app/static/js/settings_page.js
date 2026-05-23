(() => {
  const form = document.getElementById("settingsForm");
  const providerSelect = document.getElementById("imageAiProviderSelect");
  const modelInput = document.getElementById("imageAiModelInput");
  const textModelOptions = document.getElementById("textAiModelOptions");
  const cinemaNovelProviderSelect = document.getElementById("cinemaNovelImageProviderSelect");
  const cinemaNovelModelInput = document.getElementById("cinemaNovelImageModelInput");
  let providerDefaultModels = { openai: "gpt-image-2", grok: "grok-imagine-image-quality" };

  function applyProviderModelDefault(previousProvider) {
    const provider = providerSelect?.value || "openai";
    const previousDefault = providerDefaultModels[previousProvider];
    const currentValue = (modelInput?.value || "").trim();
    const incompatible =
      (provider === "grok" && /^(gpt-|dall-e)/i.test(currentValue)) ||
      (provider === "openai" && /^grok-/i.test(currentValue));
    if (modelInput && (!currentValue || currentValue === previousDefault || incompatible)) {
      modelInput.value = providerDefaultModels[provider] || currentValue;
    }
  }

  function applyCinemaNovelProviderModelDefault(previousProvider) {
    const provider = cinemaNovelProviderSelect?.value || "openai";
    const previousDefault = providerDefaultModels[previousProvider];
    const currentValue = (cinemaNovelModelInput?.value || "").trim();
    const incompatible =
      (provider === "grok" && /^(gpt-|dall-e)/i.test(currentValue)) ||
      (provider === "openai" && /^grok-/i.test(currentValue));
    if (cinemaNovelModelInput && (!currentValue || currentValue === previousDefault || incompatible)) {
      cinemaNovelModelInput.value = providerDefaultModels[provider] || currentValue;
    }
  }

  async function loadSettings() {
    const settings = await NovelUI.api("/api/v1/settings");
    providerDefaultModels = settings?.available_options?.provider_default_models || providerDefaultModels;
    if (textModelOptions && Array.isArray(settings?.available_options?.text_models)) {
      textModelOptions.innerHTML = settings.available_options.text_models
        .map((model) => `<option value="${NovelUI.escape(model)}"></option>`)
        .join("");
    }
    NovelUI.fillForm(form, settings);
    if (providerSelect) providerSelect.dataset.previousProvider = providerSelect.value || "openai";
    if (cinemaNovelProviderSelect) cinemaNovelProviderSelect.dataset.previousProvider = cinemaNovelProviderSelect.value || "openai";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    body.prefer_portrait_on_mobile = "1";
    try {
      const settings = await NovelUI.api("/api/v1/settings", {
        method: "PUT",
        body,
      });
      NovelUI.fillForm(form, settings);
      NovelUI.toast("ユーザー設定を保存しました。");
    } catch (error) {
      NovelUI.toast(error.message || "設定の保存に失敗しました。", "danger");
    }
  });

  document.getElementById("settingsResetButton").addEventListener("click", async () => {
    try {
      const settings = await NovelUI.api("/api/v1/settings/reset", {
        method: "POST",
        body: {},
      });
      NovelUI.fillForm(form, settings);
      NovelUI.toast("設定を初期値に戻しました。", "warning");
    } catch (error) {
      NovelUI.toast(error.message || "設定の初期化に失敗しました。", "danger");
    }
  });

  providerSelect?.addEventListener("change", (event) => {
    applyProviderModelDefault(event.target.dataset.previousProvider || "openai");
    event.target.dataset.previousProvider = event.target.value;
  });

  cinemaNovelProviderSelect?.addEventListener("change", (event) => {
    applyCinemaNovelProviderModelDefault(event.target.dataset.previousProvider || "openai");
    event.target.dataset.previousProvider = event.target.value;
  });

  loadSettings().catch((error) => {
    NovelUI.toast(error.message || "設定の読み込みに失敗しました。", "danger");
  });
})();
