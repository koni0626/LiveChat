(function () {
  async function loadSessionCharacterOptions(projectId) {
    const data = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    return Array.isArray(data) ? data : [];
  }

  async function loadContext(sessionId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}`);
  }

  async function generateSessionImage(sessionId, body) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/images/generate`, {
      method: "POST",
      body,
    });
  }

  async function updateSession(sessionId, body) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}`, {
      method: "PATCH",
      body,
    });
  }

  async function postMessage(sessionId, body) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body,
    });
  }

  async function extractState(sessionId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/state/extract`, {
      method: "POST",
      body: {},
    });
  }

  async function uploadImage(sessionId, formData) {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/images/upload`, {
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

  async function uploadGift(sessionId, formData) {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/gifts/upload`, {
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

  async function selectImage(sessionId, imageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/images/${imageId}/select`, {
      method: "POST",
      body: {},
    });
  }

  async function deleteMessage(sessionId, messageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/messages/${messageId}`, {
      method: "DELETE",
    });
  }

  window.LiveChatApi = {
    loadSessionCharacterOptions,
    loadContext,
    generateSessionImage,
    updateSession,
    postMessage,
    extractState,
    uploadImage,
    uploadGift,
    selectImage,
    deleteMessage,
  };
})();
