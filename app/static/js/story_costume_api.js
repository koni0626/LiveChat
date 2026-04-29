(function () {
  async function loadContext(sessionId) {
    return NovelUI.api(`/api/v1/story-sessions/${sessionId}`);
  }

  async function loadSettings() {
    return NovelUI.api("/api/v1/settings");
  }

  async function generateCostume(sessionId, body) {
    return NovelUI.api(`/api/v1/story-sessions/${sessionId}/costumes/generate`, {
      method: "POST",
      body,
    });
  }

  async function uploadCostume(sessionId, formData) {
    const response = await fetch(`/api/v1/story-sessions/${sessionId}/costumes/upload`, {
      method: "POST",
      credentials: "same-origin",
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.data?.message || payload?.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  async function selectCostume(sessionId, imageId) {
    return NovelUI.api(`/api/v1/story-sessions/${sessionId}/costumes/${imageId}/select`, {
      method: "POST",
      body: {},
    });
  }

  async function deleteCostume(sessionId, imageId) {
    return NovelUI.api(`/api/v1/story-sessions/${sessionId}/costumes/${imageId}`, {
      method: "DELETE",
    });
  }

  window.StoryCostumeApi = {
    loadContext,
    loadSettings,
    generateCostume,
    uploadCostume,
    selectCostume,
    deleteCostume,
  };
})();
