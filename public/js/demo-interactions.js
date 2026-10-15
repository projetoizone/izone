// Mostra uma mensagem nos formularios e botoes enquanto nao tem back-end

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  toast.textContent = message;
  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add("toast-visible"));

  setTimeout(() => {
    toast.classList.remove("toast-visible");
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

document.addEventListener("submit", (e) => {
  const form = e.target.closest("form[data-demo-message]");
  if (!form) return;
  e.preventDefault();
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  showToast(form.getAttribute("data-demo-message"));
});

document.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-demo-message]");
  if (!btn) return;
  showToast(btn.getAttribute("data-demo-message"));
});
