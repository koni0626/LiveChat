(function () {
  function escapeHtml(value) {
    return window.NovelUI.escape(value ?? "");
  }

  function renderInlineMarkdown(text) {
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function markdownToHtml(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let inList = false;

    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }

    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (!trimmed) {
        closeList();
        continue;
      }
      if (trimmed.startsWith("## ")) {
        closeList();
        html.push(`<h5>${renderInlineMarkdown(trimmed.slice(3))}</h5>`);
      } else if (trimmed.startsWith("# ")) {
        closeList();
        html.push(`<h4>${renderInlineMarkdown(trimmed.slice(2))}</h4>`);
      } else if (trimmed.startsWith("> ")) {
        closeList();
        html.push(`<blockquote>${renderInlineMarkdown(trimmed.slice(2))}</blockquote>`);
      } else if (trimmed.startsWith("- ")) {
        if (!inList) {
          html.push("<ul>");
          inList = true;
        }
        html.push(`<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`);
      } else {
        closeList();
        html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
      }
    }
    closeList();
    return html.join("") || '<p class="text-muted mb-0">まだ入力されていません。</p>';
  }

  function createMarkdownEditor(options) {
    const {
      form,
      grid,
      fields,
      modalElement,
      modalTitle,
      modalTextarea,
      modalPreview,
      modalApplyButton,
      previewLength = 120,
    } = options;
    const modal = new bootstrap.Modal(modalElement);
    let editingFieldName = "";

    function fieldInput(name) {
      return form.querySelector(`[name="${name}"]`);
    }

    function plainPreview(value) {
      const text = String(value || "").replace(/[#>*`_-]/g, "").replace(/\s+/g, " ").trim();
      return text ? text.slice(0, previewLength) + (text.length > previewLength ? "..." : "") : "まだ入力されていません。";
    }

    function renderCards() {
      grid.innerHTML = fields.map((field) => {
        const value = fieldInput(field.name)?.value || "";
        return `
          <article class="markdown-summary-card" data-markdown-card="${field.name}">
            <div class="markdown-summary-head">
              <div>
                <h4>${escapeHtml(field.label)}</h4>
                <p>${escapeHtml(field.hint)}</p>
              </div>
              <button class="btn btn-sm btn-outline-light" type="button" data-edit-markdown="${field.name}">
                <i class="bi bi-pencil-square"></i>
                <span>編集</span>
              </button>
            </div>
            <div class="markdown-summary-body">${escapeHtml(plainPreview(value))}</div>
          </article>
        `;
      }).join("");
    }

    function open(fieldName) {
      const field = fields.find((item) => item.name === fieldName);
      const input = fieldInput(fieldName);
      if (!field || !input) return;
      editingFieldName = fieldName;
      modalTitle.textContent = field.label;
      modalTextarea.placeholder = field.placeholder;
      modalTextarea.value = input.value || "";
      modalPreview.innerHTML = markdownToHtml(modalTextarea.value);
      modal.show();
      setTimeout(() => modalTextarea.focus(), 180);
    }

    function apply() {
      const input = fieldInput(editingFieldName);
      if (!input) return;
      input.value = modalTextarea.value;
      renderCards();
      modal.hide();
    }

    grid.addEventListener("click", (event) => {
      const button = event.target.closest("[data-edit-markdown]");
      if (button) open(button.dataset.editMarkdown);
    });
    modalTextarea.addEventListener("input", () => {
      modalPreview.innerHTML = markdownToHtml(modalTextarea.value);
    });
    modalApplyButton.addEventListener("click", apply);

    return {
      fieldInput,
      markdownToHtml,
      open,
      apply,
      renderCards,
    };
  }

  window.MarkdownEditor = {
    create: createMarkdownEditor,
    markdownToHtml,
  };
})();
