(function () {
  async function loadContext(sessionId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}`);
  }

  async function loadSettings() {
    return NovelUI.api("/api/v1/settings");
  }

  async function generateSessionImage(sessionId, body) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/images/generate`, {
      method: "POST",
      body,
    });
  }

  async function selectCostume(sessionId, imageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/costumes/${imageId}/select`, {
      method: "POST",
      body: {},
    });
  }

  async function loadClosetOutfits(sessionId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/closet-outfits`);
  }

  async function selectClosetOutfit(sessionId, outfitId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/closet-outfits/${outfitId}/select`, {
      method: "POST",
      body: {},
    });
  }

  async function deleteCostume(sessionId, imageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/costumes/${imageId}`, {
      method: "DELETE",
    });
  }

  async function executeSceneChoice(sessionId, choiceId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/choices/${encodeURIComponent(choiceId)}/execute`, {
      method: "POST",
      body,
    });
  }

  async function moveToLocation(sessionId, locationId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/locations/${locationId}/move`, {
      method: "POST",
      body,
    });
  }

  async function selectLocationService(sessionId, serviceId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/location-services/${serviceId}/select`, {
      method: "POST",
      body,
    });
  }

  async function generatePhotoModeShoot(sessionId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/photo-mode/shoot`, {
      method: "POST",
      body,
    });
  }

  async function claimAffinityReward(sessionId, characterId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/affinity-rewards/${characterId}/claim`, {
      method: "POST",
      body: {},
    });
  }

  async function debugAffinityClear(sessionId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/debug/affinity-clear`, {
      method: "POST",
      body,
    });
  }

  async function postMessage(sessionId, body) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body,
    });
  }

  async function generateProxyPlayerMessage(sessionId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/proxy-player-message`, {
      method: "POST",
      body,
    });
  }

  async function postIdleMessage(sessionId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/idle-message`, {
      method: "POST",
      body: {},
    });
  }

  async function analyzePlayerReaction(sessionId, formData) {
    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/player-reaction`, {
      method: "POST",
      credentials: "same-origin",
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.data?.message || payload?.message || `HTTP ${response.status}`);
    }
    return payload?.data ?? payload;
  }

  async function generateShortStory(sessionId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/short-story`, {
      method: "POST",
      body,
    });
  }

  async function saveShortStory(sessionId, story) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/short-stories/save`, {
      method: "POST",
      body: { story },
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

  async function loadInventory(projectId) {
    return NovelUI.api(`/api/v1/projects/${projectId}/inventory`);
  }

  async function generateInventoryItem(projectId, body = {}) {
    return NovelUI.api(`/api/v1/projects/${projectId}/inventory/generate`, {
      method: "POST",
      body,
    });
  }

  async function giveInventoryItem(sessionId, itemId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/inventory/${itemId}/give`, {
      method: "POST",
      body,
    });
  }

  async function revealCharacterIntel(sessionId, body = {}) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/intel/reveal`, {
      method: "POST",
      body,
    });
  }

  async function selectImage(sessionId, imageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/images/${imageId}/select`, {
      method: "POST",
      body: {},
    });
  }

  async function setReferenceImage(sessionId, imageId, isReference) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/images/${imageId}/reference`, {
      method: "POST",
      body: { is_reference: isReference !== false },
    });
  }

  async function deleteMessage(sessionId, messageId) {
    return NovelUI.api(`/api/v1/chat/sessions/${sessionId}/messages/${messageId}`, {
      method: "DELETE",
    });
  }

  window.LiveChatApi = {
    loadSettings,
    loadContext,
    generateSessionImage,
    postMessage,
    analyzePlayerReaction,
    generateShortStory,
    saveShortStory,
    generateProxyPlayerMessage,
    postIdleMessage,
    extractState,
    uploadImage,
    uploadGift,
    loadInventory,
    generateInventoryItem,
    giveInventoryItem,
    revealCharacterIntel,
    selectImage,
    selectCostume,
    loadClosetOutfits,
    selectClosetOutfit,
    deleteCostume,
    executeSceneChoice,
    moveToLocation,
    selectLocationService,
    generatePhotoModeShoot,
    claimAffinityReward,
    debugAffinityClear,
    setReferenceImage,
    deleteMessage,
  };
})();
