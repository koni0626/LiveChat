(() => {
  document.querySelectorAll("[data-auth-form]").forEach((form) => {
    const errorBox = document.getElementById(form.dataset.errorTarget || "");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorBox?.classList.add("d-none");

      const formData = new FormData(form);
      try {
        const result = await NovelUI.api(form.dataset.authEndpoint, {
          method: "POST",
          body: Object.fromEntries(formData.entries()),
        });
        location.href = result?.user?.role === "user"
          ? form.dataset.userRedirect
          : form.dataset.adminRedirect;
      } catch (error) {
        if (!errorBox) return;
        errorBox.textContent = error.message || form.dataset.defaultError || "処理に失敗しました。";
        errorBox.classList.remove("d-none");
      }
    });
  });
})();
