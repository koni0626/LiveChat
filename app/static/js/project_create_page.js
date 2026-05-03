(() => {
  const form = document.getElementById("projectCreateForm");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      const project = await NovelUI.api("/api/v1/projects", { method: "POST", body });
      location.href = `/projects/${project.id}/home?edit=1`;
    } catch (error) {
      NovelUI.toast(error.message || "World creation failed.", "danger");
    }
  });
})();
