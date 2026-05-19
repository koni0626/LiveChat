(() => {
  const root = document.querySelector("[data-observation-page]");
  if (!root) return;

  const projectId = Number(root.dataset.projectId || 0);
  const canManageProject = root.dataset.canManageProject === "true";
  const sourceSelect = document.getElementById("observationSourceSelect");
  const followCleanupButton = document.getElementById("observationFollowCleanupButton");
  const followCleanupPanel = document.getElementById("observationFollowCleanupPanel");
  const followCleanupSummary = document.getElementById("observationFollowCleanupSummary");
  const followCleanupList = document.getElementById("observationFollowCleanupList");
  const followCleanupReloadButton = document.getElementById("observationFollowCleanupReloadButton");
  const followCleanupSelectAllButton = document.getElementById("observationFollowCleanupSelectAllButton");
  const followCleanupUnfollowButton = document.getElementById("observationFollowCleanupUnfollowButton");
  const hoursInput = document.getElementById("observationHoursInput");
  const maxUsersInput = document.getElementById("observationMaxUsersInput");
  const userSamplePoolInput = document.getElementById("observationUserSamplePoolInput");
  const tweetsPerUserInput = document.getElementById("observationTweetsPerUserInput");
  const sortSelect = document.getElementById("observationSortSelect");
  const replyFilterSelect = document.getElementById("observationReplyFilterSelect");
  const refreshButton = document.getElementById("observationRefreshButton");
  const countLabel = document.getElementById("observationCountLabel");
  const postList = document.getElementById("observationPostList");
  const detailEmpty = document.getElementById("observationDetailEmpty");
  const detailPanel = document.getElementById("observationDetail");
  const detailAuthor = document.getElementById("observationDetailAuthor");
  const detailMeta = document.getElementById("observationDetailMeta");
  const detailText = document.getElementById("observationDetailText");
  const existingReply = document.getElementById("observationExistingReply");
  const detailLink = document.getElementById("observationDetailLink");
  const mediaGrid = document.getElementById("observationMediaGrid");
  const characterSelect = document.getElementById("observationCharacterSelect");
  const commentButton = document.getElementById("observationCommentButton");
  const publishReplyButton = document.getElementById("observationPublishReplyButton");
  const replyButton = document.getElementById("observationReplyButton");
  const commentOutput = document.getElementById("observationCommentOutput");
  const replyResult = document.getElementById("observationReplyResult");
  let posts = [];
  let selectedPost = null;
  let characters = [];
  let followCleanupCandidates = [];

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("ja-JP", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function metrics(post) {
    const parts = [];
    if (post.like_count) parts.push(`♡ ${post.like_count}`);
    if (post.repost_count) parts.push(`RP ${post.repost_count}`);
    if (post.reply_count) parts.push(`返信 ${post.reply_count}`);
    return parts.join(" / ");
  }

  function authorKey(post) {
    return String(post.author_username || post.author_id || post.author_name || "");
  }

  function replySnippet(reply) {
    return NovelUI.truncateText(reply?.reply_text || "", 72);
  }

  function relationshipBadges(post) {
    const badges = [];
    if (post.is_mutual_follow) badges.push('<span class="observation-relation-badge is-mutual">相互</span>');
    else {
      if (post.followed_by_me) badges.push('<span class="observation-relation-badge">フォロー中</span>');
      if (post.follows_me) badges.push('<span class="observation-relation-badge">フォロワー</span>');
    }
    return badges.join("");
  }

  function replySettingsBadge(post) {
    const value = String(post.reply_settings || "").toLowerCase();
    if (!value) return "";
    if (value === "everyone") {
      return '<span class="observation-reply-setting-badge is-open">返信: 全員</span>';
    }
    if (value === "following") {
      const likely = post.follows_me ? " 推定OK" : "";
      return `<span class="observation-reply-setting-badge ${post.follows_me ? "is-likely" : "is-limited"}">返信: 投稿者のフォロー先${likely}</span>`;
    }
    if (value === "mentionedusers" || value === "mentioned_users") {
      return '<span class="observation-reply-setting-badge is-limited">返信: メンションのみ</span>';
    }
    if (value === "verified") {
      return '<span class="observation-reply-setting-badge is-limited">返信: 認証済みのみ</span>';
    }
    return `<span class="observation-reply-setting-badge is-limited">返信: ${NovelUI.escape(post.reply_settings)}</span>`;
  }

  function visiblePosts() {
    const repliedUsers = new Set(posts.filter((post) => post.is_replied).map(authorKey));
    let items = [...posts];
    if (replyFilterSelect.value === "unreplied") {
      items = items.filter((post) => !post.is_replied);
    } else if (replyFilterSelect.value === "unreplied_users") {
      items = items.filter((post) => !repliedUsers.has(authorKey(post)));
    }
    if (sortSelect.value === "user") {
      items.sort((a, b) => {
        const authorCompare = authorKey(a).localeCompare(authorKey(b), "ja");
        if (authorCompare) return authorCompare;
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      });
    } else {
      items.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    }
    return items;
  }

  function params() {
    return new URLSearchParams({
      source: sourceSelect.value || "home_timeline",
      hours: String(Math.max(1, Number(hoursInput.value || 24))),
      max_users: String(Math.max(1, Number(maxUsersInput.value || 50))),
      user_sample_pool: String(Math.max(1, Number(userSamplePoolInput.value || 1000))),
      tweets_per_user: String(Math.max(1, Number(tweetsPerUserInput.value || 1))),
    });
  }

  function syncSourceControls() {
    const isHomeTimeline = (sourceSelect.value || "home_timeline") === "home_timeline";
    userSamplePoolInput.disabled = isHomeTimeline;
    userSamplePoolInput.closest("label")?.classList.toggle("opacity-50", isHomeTimeline);
  }

  async function loadCharacters() {
    characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    characterSelect.innerHTML = characters.map((character) => `
      <option value="${character.id}">${NovelUI.escape(character.name || "Character")}</option>
    `).join("");
    const noah = characters.find((character) => character.name === "ノア" || character.nickname === "ノア");
    if (noah) characterSelect.value = String(noah.id);
  }

  async function loadPosts() {
    refreshButton.disabled = true;
    refreshButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>取得中</span>';
    postList.innerHTML = '<div class="empty-panel">Xの投稿を取得しています。</div>';
    try {
      const payload = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/recent?${params().toString()}`);
      posts = payload.items || [];
      renderPosts();
    } catch (error) {
      postList.innerHTML = `<div class="empty-panel">${NovelUI.escape(error.message || "取得に失敗しました。")}</div>`;
    } finally {
      refreshButton.disabled = false;
      refreshButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i><span>更新</span>';
    }
  }

  function renderFollowCleanupCandidates() {
    if (!followCleanupCandidates.length) {
      followCleanupList.innerHTML = '<div class="empty-panel">解除候補はいません。</div>';
      followCleanupSummary.textContent = "相互フォローではないフォロー中ユーザーは見つかりませんでした。";
      return;
    }
    followCleanupSummary.textContent = `${followCleanupCandidates.length}件の候補があります。解除するユーザーだけチェックしてください。`;
    followCleanupList.innerHTML = followCleanupCandidates.map((user) => `
      <label class="observation-cleanup-user">
        <input class="form-check-input" type="checkbox" value="${NovelUI.escape(user.id)}" data-cleanup-user>
        <span class="observation-cleanup-user-main">
          <span class="observation-cleanup-user-name">
            ${NovelUI.escape(user.name || "")}
            <a href="${NovelUI.escape(user.url)}" target="_blank" rel="noopener">@${NovelUI.escape(user.username || "")}</a>
          </span>
          ${user.description ? `<span class="observation-cleanup-user-description">${NovelUI.escape(user.description)}</span>` : ""}
        </span>
        <span class="observation-cleanup-user-meta">
          フォロワー ${Number(user.followers_count || 0).toLocaleString("ja-JP")}
        </span>
      </label>
    `).join("");
  }

  async function loadFollowCleanupCandidates() {
    followCleanupPanel.classList.remove("d-none");
    followCleanupReloadButton.disabled = true;
    followCleanupReloadButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>取得中</span>';
    followCleanupList.innerHTML = '<div class="empty-panel">相互フォローではないユーザーを確認しています。</div>';
    try {
      const payload = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/follow-cleanup/candidates?max_users=5000`);
      followCleanupCandidates = payload.items || [];
      renderFollowCleanupCandidates();
    } catch (error) {
      followCleanupList.innerHTML = `<div class="empty-panel">${NovelUI.escape(error.message || "候補取得に失敗しました。")}</div>`;
    } finally {
      followCleanupReloadButton.disabled = false;
      followCleanupReloadButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i><span>候補取得</span>';
    }
  }

  function selectedCleanupUserIds() {
    return [...followCleanupList.querySelectorAll("[data-cleanup-user]:checked")].map((input) => input.value);
  }

  function selectAllCleanupCandidates() {
    const checkboxes = [...followCleanupList.querySelectorAll("[data-cleanup-user]")];
    const shouldCheck = checkboxes.some((checkbox) => !checkbox.checked);
    checkboxes.forEach((checkbox) => {
      checkbox.checked = shouldCheck;
    });
    followCleanupSelectAllButton.innerHTML = shouldCheck
      ? '<i class="bi bi-square"></i><span>全解除</span>'
      : '<i class="bi bi-check2-square"></i><span>全選択</span>';
  }

  async function unfollowSelectedUsers() {
    const userIds = selectedCleanupUserIds();
    if (!userIds.length) {
      NovelUI.toast("解除するユーザーにチェックを入れてください。", "warning");
      return;
    }
    if (!window.confirm(`${userIds.length}件のフォローを解除します。よろしいですか？`)) return;
    followCleanupUnfollowButton.disabled = true;
    followCleanupUnfollowButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>解除中</span>';
    try {
      const result = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/follow-cleanup/unfollow`, {
        method: "POST",
        body: { user_ids: userIds },
      });
      const failed = result.failure_count || 0;
      const succeededIds = new Set((result.results || []).filter((item) => item.ok).map((item) => String(item.user_id)));
      followCleanupCandidates = followCleanupCandidates.filter((user) => !succeededIds.has(String(user.id)));
      renderFollowCleanupCandidates();
      NovelUI.toast(`フォロー解除: ${result.success_count || 0}件 / 失敗: ${failed}件`, failed ? "warning" : "success");
    } catch (error) {
      NovelUI.toast(error.message || "フォロー解除に失敗しました。", "danger");
    } finally {
      followCleanupUnfollowButton.disabled = false;
      followCleanupUnfollowButton.innerHTML = '<i class="bi bi-person-dash"></i><span>選択を解除</span>';
    }
  }

  function renderPosts() {
    const items = visiblePosts();
    countLabel.textContent = items.length === posts.length ? `${posts.length}件` : `${items.length} / ${posts.length}件`;
    if (!items.length) {
      postList.innerHTML = '<div class="empty-panel">投稿が見つかりませんでした。</div>';
      return;
    }
    postList.innerHTML = items.map((post) => `
      <article class="observation-post-card ${post.is_replied ? "is-replied" : ""}">
        <div class="observation-post-main">
          <div class="observation-post-author">
            ${NovelUI.escape(post.author_name || "")} <span>@${NovelUI.escape(post.author_username || "")}</span>
            ${relationshipBadges(post)}
            ${replySettingsBadge(post)}
            ${post.is_replied ? '<span class="observation-replied-badge">返信済み</span>' : ""}
          </div>
          <p>${NovelUI.escape(NovelUI.truncateText(post.text || "", 180))}</p>
          ${post.is_replied ? `<div class="observation-reply-snippet">返信: ${NovelUI.escape(replySnippet(post.observation_reply))}</div>` : ""}
          <div class="observation-post-meta">${NovelUI.escape(formatDate(post.created_at))}${metrics(post) ? ` / ${NovelUI.escape(metrics(post))}` : ""}</div>
        </div>
        <div class="observation-post-actions">
          <button class="btn btn-sm btn-outline-dark" type="button" data-detail-id="${post.id}">
            <i class="bi bi-images"></i>
            <span>詳細</span>
          </button>
          <a class="btn btn-sm btn-outline-dark" href="${NovelUI.escape(post.url)}" target="_blank" rel="noopener">
            <i class="bi bi-box-arrow-up-right"></i>
          </a>
        </div>
      </article>
    `).join("");
  }

  async function showDetail(tweetId) {
    commentOutput.value = "";
    replyResult.classList.add("d-none");
    replyResult.innerHTML = "";
    detailEmpty.classList.add("d-none");
    detailPanel.classList.remove("d-none");
    mediaGrid.innerHTML = '<div class="empty-panel">画像を取得しています。</div>';
    const detail = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/posts/${tweetId}`);
    const listPost = posts.find((post) => String(post.id) === String(tweetId)) || {};
    selectedPost = { ...listPost, ...detail };
    detailAuthor.textContent = `${detail.author_name || ""} @${detail.author_username || ""}`;
    detailMeta.textContent = `${formatDate(detail.created_at)}${metrics(detail) ? ` / ${metrics(detail)}` : ""}`;
    const detailBadges = relationshipBadges(selectedPost);
    const settingsBadge = replySettingsBadge(selectedPost);
    if (detailBadges || settingsBadge) {
      detailMeta.innerHTML = `${NovelUI.escape(detailMeta.textContent)} <span class="observation-detail-relations">${detailBadges}${settingsBadge}</span>`;
    }
    detailText.textContent = detail.text || "";
    detailLink.href = detail.url;
    renderExistingReply(detail.observation_reply);
    renderMedia(detail.media || []);
  }

  function renderExistingReply(reply) {
    if (!reply?.reply_text) {
      existingReply.classList.add("d-none");
      existingReply.innerHTML = "";
      return;
    }
    existingReply.classList.remove("d-none");
    existingReply.innerHTML = `
      <div class="observation-existing-reply-head">
        <span>返信済み</span>
        ${reply.reply_url ? `<a href="${NovelUI.escape(reply.reply_url)}" target="_blank" rel="noopener">Xで開く</a>` : ""}
      </div>
      <p>${NovelUI.escape(reply.reply_text)}</p>
      ${reply.created_at ? `<small>${NovelUI.escape(formatDate(reply.created_at))}</small>` : ""}
    `;
  }

  function renderMedia(media) {
    if (!media.length) {
      mediaGrid.innerHTML = '<div class="empty-panel">画像はありません。</div>';
      return;
    }
    mediaGrid.innerHTML = media.map((item) => {
      const src = item.media_url || item.url || "";
      if (!src) return "";
      return `
        <a class="observation-media-card" href="${NovelUI.escape(src)}" target="_blank" rel="noopener">
          <img src="${NovelUI.escape(src)}" alt="${NovelUI.escape(item.alt_text || "X media")}">
        </a>
      `;
    }).join("");
  }

  async function generateComment() {
    if (!selectedPost?.id) {
      NovelUI.toast("先に詳細を開いてください。", "warning");
      return;
    }
    if (!canManageProject) return;
    commentButton.disabled = true;
    commentButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>作成中</span>';
    try {
      const result = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/posts/${selectedPost.id}/comment`, {
        method: "POST",
        body: { character_id: characterSelect.value },
      });
      commentOutput.value = result.comment || "";
      replyResult.classList.add("d-none");
      replyResult.innerHTML = "";
    } catch (error) {
      NovelUI.toast(error.message || "コメント生成に失敗しました。", "danger");
    } finally {
      commentButton.disabled = false;
      commentButton.innerHTML = '<i class="bi bi-chat-heart"></i><span>コメント作成</span>';
    }
  }

  function targetPayload() {
    return {
      author_id: selectedPost.author_id,
      author_name: selectedPost.author_name,
      author_username: selectedPost.author_username,
    };
  }

  function applyReplyResult(result) {
    selectedPost.observation_reply = result.observation_reply || null;
    selectedPost.is_replied = Boolean(selectedPost.observation_reply);
    posts = posts.map((post) => (
      String(post.id) === String(selectedPost.id)
        ? { ...post, observation_reply: selectedPost.observation_reply, is_replied: selectedPost.is_replied }
        : post
    ));
    renderPosts();
    renderExistingReply(selectedPost.observation_reply);
  }

  async function submitReply({ manual }) {
    if (!selectedPost?.id) {
      NovelUI.toast("先に詳細を開いてください。", "warning");
      return;
    }
    if (!canManageProject) return;
    const text = commentOutput.value.trim();
    if (!text) {
      NovelUI.toast("返信文を入力してください。", "warning");
      return;
    }
    const message = manual
      ? "この内容を手動返信済みとして記録します。よろしいですか？"
      : "この内容をX API経由で返信します。よろしいですか？";
    if (!window.confirm(message)) return;

    const button = manual ? replyButton : publishReplyButton;
    button.disabled = true;
    button.innerHTML = manual
      ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>記録中</span>'
      : '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>返信中</span>';
    try {
      const endpoint = manual ? "mark-replied" : "reply";
      const result = await NovelUI.api(`/api/v1/projects/${projectId}/observations/x/posts/${selectedPost.id}/${endpoint}`, {
        method: "POST",
        body: {
          text,
          character_id: characterSelect.value,
          target: targetPayload(),
        },
      });
      applyReplyResult(result);
      replyResult.classList.remove("d-none");
      replyResult.innerHTML = `
        <span>${manual ? "返信済みとして記録しました。" : "X API経由で返信しました。"}</span>
        ${result.url ? `<a href="${NovelUI.escape(result.url)}" target="_blank" rel="noopener">Xで開く</a>` : ""}
      `;
      NovelUI.toast(manual ? "返信済みとして記録しました。" : "X API経由で返信しました。", "success");
    } catch (error) {
      const fallback = manual
        ? "返信済み記録に失敗しました。"
        : "API返信に失敗しました。手動で返信した場合は「返信済みにする」で記録できます。";
      NovelUI.toast(error.message || fallback, "danger");
    } finally {
      button.disabled = false;
      button.innerHTML = manual
        ? '<i class="bi bi-check2-circle"></i><span>返信済みにする</span>'
        : '<i class="bi bi-send"></i><span>APIで返信</span>';
    }
  }

  async function publishReply() {
    await submitReply({ manual: false });
  }

  async function markReplyDone() {
    await submitReply({ manual: true });
  }

  refreshButton.addEventListener("click", loadPosts);
  sourceSelect.addEventListener("change", () => {
    syncSourceControls();
    loadPosts();
  });
  followCleanupButton.addEventListener("click", () => {
    if (followCleanupPanel.classList.contains("d-none") || !followCleanupCandidates.length) {
      loadFollowCleanupCandidates();
    } else {
      followCleanupPanel.classList.toggle("d-none");
    }
  });
  followCleanupReloadButton.addEventListener("click", loadFollowCleanupCandidates);
  followCleanupSelectAllButton.addEventListener("click", selectAllCleanupCandidates);
  followCleanupUnfollowButton.addEventListener("click", unfollowSelectedUsers);
  sortSelect.addEventListener("change", renderPosts);
  replyFilterSelect.addEventListener("change", renderPosts);
  postList.addEventListener("click", (event) => {
    const detailButton = event.target.closest("[data-detail-id]");
    if (!detailButton) return;
    showDetail(detailButton.dataset.detailId).catch((error) => NovelUI.toast(error.message || "詳細取得に失敗しました。", "danger"));
  });
  commentButton.addEventListener("click", generateComment);
  publishReplyButton.addEventListener("click", publishReply);
  replyButton.addEventListener("click", markReplyDone);

  syncSourceControls();
  loadCharacters().catch((error) => NovelUI.toast(error.message || "キャラクター取得に失敗しました。", "danger"));
  loadPosts();
})();
