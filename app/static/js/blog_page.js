(() => {
  const root = document.querySelector("[data-blog-page]");
  if (!root) return;

  const canCreate = root.dataset.canCreate === "true";
  const filterForm = document.getElementById("blogFilterForm");
  const projectFilter = document.getElementById("blogProjectFilter");
  const characterFilter = document.getElementById("blogCharacterFilter");
  const stream = document.getElementById("blogStream");
  const pagination = document.getElementById("blogPagination");
  const reloadButton = document.getElementById("blogReloadButton");
  const composerForm = document.getElementById("blogComposerForm");
  const composerProject = document.getElementById("blogComposerProject");
  const composerCharacter = document.getElementById("blogComposerCharacter");
  const editModalEl = document.getElementById("blogEditModal");
  const editForm = document.getElementById("blogEditForm");
  const editPostId = document.getElementById("blogEditPostId");
  const editCharacter = document.getElementById("blogEditCharacter");
  const editStatus = document.getElementById("blogEditStatus");
  const editTheme = document.getElementById("blogEditTheme");
  const editInstruction = document.getElementById("blogEditInstruction");
  const editBody = document.getElementById("blogEditBody");
  const xScheduleModalEl = document.getElementById("blogXScheduleModal");
  const xScheduleTarget = document.getElementById("blogXScheduleTarget");
  const xCalendar = document.getElementById("blogXCalendar");
  const xCalendarTitle = document.getElementById("blogXCalendarTitle");
  const xCalendarPrev = document.getElementById("blogXCalendarPrev");
  const xCalendarNext = document.getElementById("blogXCalendarNext");

  if (editModalEl && editModalEl.parentElement !== document.body) document.body.appendChild(editModalEl);
  if (xScheduleModalEl && xScheduleModalEl.parentElement !== document.body) document.body.appendChild(xScheduleModalEl);
  const editModal = editModalEl ? new bootstrap.Modal(editModalEl) : null;
  const xScheduleModal = xScheduleModalEl ? new bootstrap.Modal(xScheduleModalEl) : null;

  let projects = [];
  let blogPosts = new Map();
  let scheduleTargetPost = null;
  let scheduleWeekStart = startOfDay(new Date());
  let xSchedules = [];
  const pageSize = 10;
  let currentPage = 1;
  let currentPagination = { page: 1, per_page: pageSize, total: 0, total_pages: 1, has_prev: false, has_next: false };

  function escapeText(value) {
    return NovelUI.escape(value || "");
  }

  function formatDate(value) {
    if (!value) return "";
    try {
      return new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
    } catch (_) {
      return value;
    }
  }

  function startOfDay(date) {
    const next = new Date(date);
    next.setHours(0, 0, 0, 0);
    return next;
  }

  function addDays(date, days) {
    const next = new Date(date);
    next.setDate(next.getDate() + days);
    return next;
  }

  function toLocalIsoHour(date) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:00:00`;
  }

  function scheduleKey(value) {
    return value ? toLocalIsoHour(new Date(value)) : "";
  }

  function avatar(post) {
    const character = post.character || {};
    const image = character.thumbnail_asset?.media_url || character.base_asset?.media_url;
    if (image) return `<img src="${escapeText(image)}" alt="${escapeText(character.name)}">`;
    return `<span>${escapeText((character.name || "?").slice(0, 1))}</span>`;
  }

  function thumbnail(post) {
    if (!post.thumbnail_asset?.media_url) return "";
    return `
      <button class="feed-post-image-button" type="button" data-blog-image-url="${escapeText(post.thumbnail_asset.media_url)}" data-blog-image-alt="${escapeText(post.theme || "Blog thumbnail")}">
        <img class="feed-post-image" src="${escapeText(post.thumbnail_asset.media_url)}" alt="Blog thumbnail">
      </button>
    `;
  }

  function bodyToHtml(body) {
    return String(body || "")
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean)
      .map((paragraph) => `<p>${escapeText(paragraph).replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function managementActions(post) {
    if (!post.can_manage) return "";
    const scheduled = post.x_schedule?.scheduled_for
      ? `<span class="feed-x-scheduled-badge"><i class="bi bi-clock-history"></i>${escapeText(formatDate(post.x_schedule.scheduled_for))}</span>`
      : "";
    return `
      <div class="feed-post-manage">
        ${scheduled}
        <button class="btn btn-sm btn-outline-light blog-post-edit" type="button" data-post-id="${post.id}">
          <i class="bi bi-pencil-square"></i><span>編集</span>
        </button>
        <button class="btn btn-sm btn-outline-light blog-thumbnail-generate" type="button" data-post-id="${post.id}">
          <i class="bi bi-image"></i><span>サムネ生成</span>
        </button>
        <button class="btn btn-sm btn-outline-info blog-x-schedule" type="button" data-post-id="${post.id}">
          <i class="bi bi-calendar-plus"></i><span>予約投稿</span>
        </button>
        <button class="btn btn-sm btn-outline-warning blog-x-publish" type="button" data-post-id="${post.id}">
          <i class="bi bi-send"></i><span>Xに投稿</span>
        </button>
        <button class="btn btn-sm btn-outline-danger blog-post-delete" type="button" data-post-id="${post.id}">
          <i class="bi bi-trash"></i><span>削除</span>
        </button>
      </div>
    `;
  }

  function renderPost(post) {
    blogPosts.set(String(post.id), post);
    const characterName = post.character?.name || "Unknown";
    const worldTitle = post.project?.title || "World";
    const statusBadge = post.status !== "published" ? `<span class="feed-status-badge">${escapeText(post.status)}</span>` : "";
    return `
      <article class="feed-post-card blog-post-card" data-post-id="${post.id}">
        <div class="feed-post-main">
          <div class="feed-post-head">
            <div class="feed-post-author">
              <div class="feed-post-avatar">${avatar(post)}</div>
              <div>
                <div class="feed-post-name">${escapeText(post.theme || "Blog")}</div>
                <a class="feed-post-world" href="/projects/${post.project_id}/live-chat">${escapeText(worldTitle)}</a>
                <div class="blog-character-name">${escapeText(characterName)} の口調</div>
              </div>
            </div>
            <div class="feed-post-date">${statusBadge}${escapeText(formatDate(post.published_at || post.created_at))}</div>
          </div>
          <div class="feed-post-body">${bodyToHtml(post.body || "")}</div>
          ${thumbnail(post)}
          <div class="feed-post-footer">
            <span class="blog-x-length">${String(post.body || "").length} chars</span>
            ${managementActions(post)}
          </div>
        </div>
      </article>
    `;
  }

  function renderEmpty() {
    stream.innerHTML = `
      <div class="empty-panel">
        <div class="empty-panel-icon"><i class="bi bi-journal-text"></i></div>
        <div>
          <h3>まだブログ記事がありません</h3>
          <p>ワールド、キャラクター、テーマ、指示を指定して最初の記事を生成してください。</p>
        </div>
      </div>
    `;
  }

  function renderPagination(info = currentPagination) {
    currentPagination = {
      page: Number(info.page || 1),
      per_page: Number(info.per_page || pageSize),
      total: Number(info.total || 0),
      total_pages: Math.max(1, Number(info.total_pages || 1)),
      has_prev: Boolean(info.has_prev),
      has_next: Boolean(info.has_next),
    };
    if (!pagination) return;
    if (currentPagination.total <= currentPagination.per_page) {
      pagination.innerHTML = "";
      pagination.classList.add("d-none");
      return;
    }
    pagination.classList.remove("d-none");
    const page = currentPagination.page;
    const totalPages = currentPagination.total_pages;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    const pageButtons = [];
    for (let pageNumber = start; pageNumber <= end; pageNumber += 1) {
      pageButtons.push(`<button class="feed-page-number ${pageNumber === page ? "is-active" : ""}" type="button" data-blog-page-number="${pageNumber}">${pageNumber}</button>`);
    }
    pagination.innerHTML = `
      <div class="feed-pagination-summary">${(page - 1) * currentPagination.per_page + 1}-${Math.min(currentPagination.total, page * currentPagination.per_page)} / ${currentPagination.total}</div>
      <div class="feed-pagination-controls">
        <button class="feed-page-button" type="button" data-blog-page-step="-1" ${currentPagination.has_prev ? "" : "disabled"}><i class="bi bi-chevron-left"></i></button>
        ${pageButtons.join("")}
        <button class="feed-page-button" type="button" data-blog-page-step="1" ${currentPagination.has_next ? "" : "disabled"}><i class="bi bi-chevron-right"></i></button>
      </div>
    `;
  }

  async function loadProjects() {
    projects = await NovelUI.api("/api/v1/projects");
    const options = projects.map((project) => `<option value="${project.id}">${escapeText(project.title)}</option>`).join("");
    projectFilter.insertAdjacentHTML("beforeend", options);
    if (composerProject) composerProject.innerHTML = options;
    const firstProjectId = composerProject?.value || projectFilter.value || projects[0]?.id;
    if (firstProjectId) await loadCharactersForProject(firstProjectId, { target: composerCharacter });
  }

  async function loadCharactersForProject(projectId, { target }) {
    if (!target) return [];
    target.innerHTML = '<option value="">読み込み中...</option>';
    if (!projectId) {
      target.innerHTML = '<option value="">すべて</option>';
      return [];
    }
    const characters = await NovelUI.api(`/api/v1/projects/${projectId}/characters`);
    const prefix = target === characterFilter ? '<option value="">すべて</option>' : "";
    target.innerHTML = prefix + characters.map((character) => `<option value="${character.id}">${escapeText(character.name)}</option>`).join("");
    return characters;
  }

  async function loadBlog(page = currentPage) {
    currentPage = Math.max(1, Number(page || 1));
    const params = new URLSearchParams(new FormData(filterForm));
    [...params.keys()].forEach((key) => {
      if (!params.get(key)) params.delete(key);
    });
    params.set("include_pagination", "1");
    params.set("page", String(currentPage));
    params.set("per_page", String(pageSize));
    const payload = await NovelUI.api(`/api/v1/blog/posts?${params.toString()}`);
    const posts = payload.items || [];
    renderPagination(payload.pagination);
    blogPosts.clear();
    if (!posts.length) {
      renderEmpty();
      return;
    }
    stream.innerHTML = posts.map(renderPost).join("");
  }

  async function generateBlog(event) {
    event.preventDefault();
    const submitButton = composerForm.querySelector('button[type="submit"]');
    const originalHtml = submitButton.innerHTML;
    const body = Object.fromEntries(new FormData(composerForm).entries());
    const projectId = Number(body.project_id);
    body.character_id = Number(body.character_id);
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span>生成中...</span>';
    try {
      await NovelUI.api(`/api/v1/projects/${projectId}/blog/generate`, { method: "POST", body });
      NovelUI.toast("ブログ記事を生成しました。");
      composerForm.reset();
      if (projects[0]) {
        composerProject.value = String(projectId || projects[0].id);
        await loadCharactersForProject(composerProject.value, { target: composerCharacter });
      }
      await loadBlog(1);
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = originalHtml;
    }
  }

  async function generateThumbnail(button) {
    const postId = Number(button.dataset.postId);
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span>生成中...</span>';
    try {
      await NovelUI.api(`/api/v1/blog/posts/${postId}/thumbnail/generate`, { method: "POST", body: {} });
      NovelUI.toast("サムネイルを生成しました。");
      await loadBlog();
    } finally {
      button.disabled = false;
      button.innerHTML = originalHtml;
    }
  }

  async function openEditPost(button) {
    const post = blogPosts.get(String(button.dataset.postId));
    if (!post || !editModal) return;
    editPostId.value = post.id;
    editTheme.value = post.theme || "";
    editInstruction.value = post.instruction || "";
    editBody.value = post.body || "";
    editStatus.value = post.status || "draft";
    await loadCharactersForProject(post.project_id, { target: editCharacter });
    editCharacter.value = String(post.character_id);
    editModal.show();
  }

  async function saveEditedPost(event) {
    event.preventDefault();
    const postId = Number(editPostId.value);
    const submitButton = editForm.querySelector('button[type="submit"]');
    const originalHtml = submitButton.innerHTML;
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span>保存中...</span>';
    try {
      await NovelUI.api(`/api/v1/blog/posts/${postId}`, {
        method: "PATCH",
        body: {
          character_id: Number(editCharacter.value),
          status: editStatus.value,
          theme: editTheme.value,
          instruction: editInstruction.value,
          body: editBody.value,
        },
      });
      editModal.hide();
      NovelUI.toast("ブログ記事を更新しました。");
      await loadBlog();
    } finally {
      submitButton.disabled = false;
      submitButton.innerHTML = originalHtml;
    }
  }

  async function deletePost(button) {
    const postId = Number(button.dataset.postId);
    if (!confirm("このブログ記事を削除しますか？")) return;
    await NovelUI.api(`/api/v1/blog/posts/${postId}`, { method: "DELETE" });
    NovelUI.toast("ブログ記事を削除しました。");
    await loadBlog();
  }

  function renderXCalendar() {
    if (!xCalendar || !scheduleTargetPost) return;
    xCalendarTitle.textContent = `${new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric" }).format(scheduleWeekStart)} - ${new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric" }).format(addDays(scheduleWeekStart, 6))}`;
    const days = Array.from({ length: 7 }, (_, index) => addDays(scheduleWeekStart, index));
    const bySlot = new Map(xSchedules.map((item) => [scheduleKey(item.scheduled_for), item]));
    xScheduleTarget.innerHTML = `
      <div class="feed-x-target-card">
        ${scheduleTargetPost.thumbnail_asset?.media_url ? `<img src="${escapeText(scheduleTargetPost.thumbnail_asset.media_url)}" alt="">` : '<div class="feed-x-target-noimage"><i class="bi bi-journal-text"></i></div>'}
        <div>
          <strong>${escapeText(scheduleTargetPost.theme)}</strong>
          <p>${escapeText((scheduleTargetPost.body || "").slice(0, 140))}</p>
        </div>
      </div>
    `;
    const header = days.map((day) => `<div class="feed-x-calendar-day">${escapeText(new Intl.DateTimeFormat("ja-JP", { weekday: "short", day: "numeric" }).format(day))}</div>`).join("");
    const cells = [];
    for (let hour = 0; hour < 24; hour += 1) {
      cells.push(`<div class="feed-x-calendar-hour">${String(hour).padStart(2, "0")}:00</div>`);
      days.forEach((day) => {
        const slotDate = new Date(day);
        slotDate.setHours(hour, 0, 0, 0);
        const key = toLocalIsoHour(slotDate);
        const item = bySlot.get(key);
        const disabled = slotDate <= new Date();
        const isTarget = item?.blog_post_id === scheduleTargetPost.id;
        const thumb = item?.thumbnail_url || item?.post?.thumbnail_asset?.media_url || "";
        cells.push(`
          <button class="feed-x-calendar-slot ${item ? "has-schedule" : ""} ${isTarget ? "is-target" : ""}" type="button"
            data-scheduled-for="${key}" data-schedule-id="${item?.id || ""}" data-post-id="${item?.blog_post_id || ""}" ${disabled && !item ? "disabled" : ""}>
            ${thumb ? `<img src="${escapeText(thumb)}" alt="">` : ""}
            ${item ? `<span>${escapeText(item.post?.theme || "予約済み")}</span>` : ""}
          </button>
        `);
      });
    }
    xCalendar.innerHTML = `<div></div>${header}${cells.join("")}`;
  }

  async function loadXSchedules() {
    const params = new URLSearchParams({
      start: toLocalIsoHour(scheduleWeekStart),
      end: toLocalIsoHour(addDays(scheduleWeekStart, 7)),
    });
    const projectId = scheduleTargetPost?.project_id || projectFilter.value || "";
    if (projectId) params.set("project_id", String(projectId));
    xSchedules = await NovelUI.api(`/api/v1/blog/x-schedules?${params.toString()}`);
    renderXCalendar();
  }

  async function openXSchedule(button) {
    const post = blogPosts.get(String(button.dataset.postId));
    if (!post || !xScheduleModal) return;
    scheduleTargetPost = post;
    scheduleWeekStart = startOfDay(new Date());
    xScheduleModal.show();
    await loadXSchedules();
  }

  async function scheduleXAt(scheduledFor) {
    if (!scheduleTargetPost) return;
    await NovelUI.api(`/api/v1/blog/posts/${scheduleTargetPost.id}/x-schedule`, {
      method: "POST",
      body: { scheduled_for: scheduledFor },
    });
    NovelUI.toast("X予約投稿を設定しました。");
    await loadXSchedules();
    await loadBlog();
  }

  async function cancelXSchedule(scheduleId, postId) {
    if (!confirm("予約投稿を解除しますか？")) return;
    const suffix = scheduleId ? `?schedule_id=${encodeURIComponent(scheduleId)}` : "";
    await NovelUI.api(`/api/v1/blog/posts/${postId}/x-schedule${suffix}`, { method: "DELETE" });
    NovelUI.toast("X予約投稿を解除しました。");
    await loadXSchedules();
    await loadBlog();
  }

  async function publishXNow(button) {
    const postId = Number(button.dataset.postId || 0);
    if (!postId) return;
    if (!confirm("このブログ記事を今すぐXに投稿しますか？")) return;
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span>投稿中...</span>';
    try {
      const result = await NovelUI.api(`/api/v1/blog/posts/${postId}/x-publish`, { method: "POST", body: {} });
      const xPostId = result?.x_schedule?.x_post_id;
      NovelUI.toast(xPostId ? `Xに投稿しました: ${xPostId}` : "Xに投稿しました。");
      await loadBlog();
    } finally {
      button.disabled = false;
      button.innerHTML = originalHtml;
    }
  }

  function openImageLightbox(url, alt = "Blog thumbnail") {
    if (!url) return;
    let overlay = document.querySelector(".feed-image-lightbox");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "feed-image-lightbox";
      overlay.innerHTML = `
        <button class="feed-image-lightbox-close" type="button" aria-label="閉じる"><i class="bi bi-x-lg"></i></button>
        <img class="feed-image-lightbox-image" alt="">
      `;
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay || event.target.closest(".feed-image-lightbox-close")) overlay.classList.remove("is-open");
      });
      document.body.appendChild(overlay);
    }
    const image = overlay.querySelector(".feed-image-lightbox-image");
    image.src = url;
    image.alt = alt;
    overlay.classList.add("is-open");
  }

  projectFilter.addEventListener("change", async () => {
    await loadCharactersForProject(projectFilter.value, { target: characterFilter });
    await loadBlog(1);
  });
  characterFilter.addEventListener("change", () => loadBlog(1).catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger")));
  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadBlog(1).catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
  });
  filterForm.addEventListener("input", (event) => {
    if (event.target.id === "blogSearchInput") {
      clearTimeout(filterForm._timer);
      filterForm._timer = setTimeout(() => loadBlog(1).catch(() => {}), 350);
    }
  });
  reloadButton.addEventListener("click", () => loadBlog().catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger")));
  composerForm?.addEventListener("submit", (event) => {
    generateBlog(event).catch((error) => NovelUI.toast(error.message || "ブログ生成に失敗しました。", "danger"));
  });
  composerProject?.addEventListener("change", () => {
    loadCharactersForProject(composerProject.value, { target: composerCharacter }).catch((error) => NovelUI.toast(error.message || "キャラクター取得に失敗しました。", "danger"));
  });
  editForm?.addEventListener("submit", (event) => {
    saveEditedPost(event).catch((error) => NovelUI.toast(error.message || "保存に失敗しました。", "danger"));
  });
  stream.addEventListener("click", (event) => {
    const thumbnailButton = event.target.closest(".blog-thumbnail-generate");
    if (thumbnailButton) {
      generateThumbnail(thumbnailButton).catch((error) => NovelUI.toast(error.message || "サムネイル生成に失敗しました。", "danger"));
      return;
    }
    const editButton = event.target.closest(".blog-post-edit");
    if (editButton) {
      openEditPost(editButton).catch((error) => NovelUI.toast(error.message || "編集画面を開けませんでした。", "danger"));
      return;
    }
    const deleteButton = event.target.closest(".blog-post-delete");
    if (deleteButton) {
      deletePost(deleteButton).catch((error) => NovelUI.toast(error.message || "削除に失敗しました。", "danger"));
      return;
    }
    const scheduleButton = event.target.closest(".blog-x-schedule");
    if (scheduleButton) {
      openXSchedule(scheduleButton).catch((error) => NovelUI.toast(error.message || "予約カレンダーを開けませんでした。", "danger"));
      return;
    }
    const publishButton = event.target.closest(".blog-x-publish");
    if (publishButton) {
      publishXNow(publishButton).catch((error) => NovelUI.toast(error.message || "X投稿に失敗しました。", "danger"));
      return;
    }
    const imageButton = event.target.closest("[data-blog-image-url]");
    if (imageButton) {
      openImageLightbox(imageButton.dataset.blogImageUrl, imageButton.dataset.blogImageAlt);
    }
  });
  pagination?.addEventListener("click", (event) => {
    const stepButton = event.target.closest("[data-blog-page-step]");
    const numberButton = event.target.closest("[data-blog-page-number]");
    let nextPage = currentPage;
    if (stepButton) nextPage += Number(stepButton.dataset.blogPageStep || 0);
    else if (numberButton) nextPage = Number(numberButton.dataset.blogPageNumber || currentPage);
    else return;
    nextPage = Math.max(1, Math.min(currentPagination.total_pages || 1, nextPage));
    if (nextPage === currentPage) return;
    loadBlog(nextPage)
      .then(() => window.scrollTo({ top: root.offsetTop || 0, behavior: "smooth" }))
      .catch((error) => NovelUI.toast(error.message || "読み込みに失敗しました。", "danger"));
  });
  xCalendar?.addEventListener("click", (event) => {
    const slot = event.target.closest(".feed-x-calendar-slot");
    if (!slot || slot.disabled) return;
    if (slot.dataset.scheduleId && slot.dataset.postId) {
      cancelXSchedule(slot.dataset.scheduleId, slot.dataset.postId).catch((error) => NovelUI.toast(error.message || "予約解除に失敗しました。", "danger"));
      return;
    }
    scheduleXAt(slot.dataset.scheduledFor).catch((error) => NovelUI.toast(error.message || "予約設定に失敗しました。", "danger"));
  });
  xCalendarPrev?.addEventListener("click", () => {
    scheduleWeekStart = addDays(scheduleWeekStart, -7);
    loadXSchedules().catch((error) => NovelUI.toast(error.message || "予約カレンダーを読み込めませんでした。", "danger"));
  });
  xCalendarNext?.addEventListener("click", () => {
    scheduleWeekStart = addDays(scheduleWeekStart, 7);
    loadXSchedules().catch((error) => NovelUI.toast(error.message || "予約カレンダーを読み込めませんでした。", "danger"));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.querySelector(".feed-image-lightbox")?.classList.remove("is-open");
  });

  loadProjects()
    .then(() => loadBlog())
    .catch((error) => NovelUI.toast(error.message || "ブログの初期化に失敗しました。", "danger"));
})();
