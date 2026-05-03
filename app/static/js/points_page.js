(() => {
  const form = document.getElementById("pointsPurchaseForm");
  const amountInput = document.getElementById("pointsPurchaseAmount");
  if (!form || !amountInput) return;

  document.querySelectorAll("[data-points-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      amountInput.value = button.dataset.pointsPreset || "3000";
      amountInput.focus();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("button[type='submit']");
    const amount = Number(amountInput.value);
    if (!Number.isFinite(amount) || amount <= 0) {
      NovelUI.toast("追加するポイントを入力してください。", "warning");
      return;
    }

    submitButton.disabled = true;
    try {
      const roundedAmount = Math.trunc(amount);
      const result = await NovelUI.api("/api/v1/auth/points/test-purchase", {
        method: "POST",
        body: { amount: roundedAmount },
      });
      NovelUI.toast(`${roundedAmount.toLocaleString("ja-JP")} ptを追加しました。`);
      if (result?.points?.balance !== undefined) NovelUI.setPointsBalance(result.points.balance);
    } catch (error) {
      NovelUI.toast(error.message || "ポイント購入に失敗しました。", "danger");
    } finally {
      submitButton.disabled = false;
    }
  });
})();
