// Barra de acessibilidade: fonte, contraste, tema e leitura em voz alta

const root = document.documentElement;
const STEPS = [1, 1.1, 1.2, 1.3]; // 100% ate 130%
const announcer = document.getElementById("a11y-announcer");

function announce(msg) {
  if (!announcer) return;
  announcer.textContent = "";
  setTimeout(() => { announcer.textContent = msg; }, 50);
}

function getStepIndex() {
  const saved = parseInt(localStorage.getItem("izone-fs-step"), 10);
  return isNaN(saved) ? 0 : Math.min(Math.max(saved, 0), STEPS.length - 1);
}

function applyFontStep(index) {
  root.style.setProperty("--fs-step", STEPS[index]);
  localStorage.setItem("izone-fs-step", String(index));
}

function applyTheme(theme) {
  if (theme === "light") {
    root.setAttribute("data-theme", "light");
  } else {
    root.removeAttribute("data-theme");
  }
  localStorage.setItem("izone-theme", theme || "dark");
  const themeBtn = document.querySelector('[data-action="toggle-theme"]');
  if (themeBtn) themeBtn.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
}

function applyContrast(high) {
  if (high) {
    root.setAttribute("data-contrast", "high");
  } else {
    root.removeAttribute("data-contrast");
  }
  localStorage.setItem("izone-contrast", high ? "high" : "normal");
  const contrastBtn = document.querySelector('[data-action="toggle-contrast"]');
  if (contrastBtn) contrastBtn.setAttribute("aria-pressed", high ? "true" : "false");
}

// carrega as preferencias salvas
applyFontStep(getStepIndex());
applyTheme(localStorage.getItem("izone-theme"));
applyContrast(localStorage.getItem("izone-contrast") === "high");

document.addEventListener("DOMContentLoaded", () => {
  const incBtn = document.querySelector('[data-action="font-increase"]');
  const decBtn = document.querySelector('[data-action="font-decrease"]');
  const contrastBtn = document.querySelector('[data-action="toggle-contrast"]');
  const themeBtn = document.querySelector('[data-action="toggle-theme"]');
  const ttsBtn = document.querySelector('[data-action="toggle-tts"]');

  if (incBtn) {
    incBtn.addEventListener("click", () => {
      const i = Math.min(getStepIndex() + 1, STEPS.length - 1);
      applyFontStep(i);
      announce("Tamanho da fonte: " + Math.round(STEPS[i] * 100) + "%");
    });
  }
  if (decBtn) {
    decBtn.addEventListener("click", () => {
      const i = Math.max(getStepIndex() - 1, 0);
      applyFontStep(i);
      announce("Tamanho da fonte: " + Math.round(STEPS[i] * 100) + "%");
    });
  }
  if (contrastBtn) {
    contrastBtn.setAttribute("aria-pressed", root.getAttribute("data-contrast") === "high" ? "true" : "false");
    contrastBtn.addEventListener("click", () => {
      const high = root.getAttribute("data-contrast") !== "high";
      applyContrast(high);
      announce(high ? "Alto contraste ativado" : "Alto contraste desativado");
    });
  }
  if (themeBtn) {
    themeBtn.setAttribute("aria-pressed", root.getAttribute("data-theme") === "light" ? "true" : "false");
    themeBtn.addEventListener("click", () => {
      const light = root.getAttribute("data-theme") !== "light";
      applyTheme(light ? "light" : "dark");
      announce(light ? "Tema claro ativado" : "Tema escuro ativado");
    });
  }

  // ler a pagina em voz alta
  if (ttsBtn && "speechSynthesis" in window) {
    let reading = false;
    ttsBtn.addEventListener("click", () => {
      if (reading) {
        speechSynthesis.cancel();
        reading = false;
        ttsBtn.setAttribute("aria-pressed", "false");
        announce("Leitura em voz alta interrompida");
        return;
      }
      const mainEl = document.querySelector("main");
      const text = mainEl ? mainEl.innerText : document.body.innerText;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "pt-BR";
      utterance.onend = () => {
        reading = false;
        ttsBtn.setAttribute("aria-pressed", "false");
      };
      speechSynthesis.cancel();
      speechSynthesis.speak(utterance);
      reading = true;
      ttsBtn.setAttribute("aria-pressed", "true");
      announce("Lendo o conteúdo da página em voz alta");
    });
  } else if (ttsBtn) {
    ttsBtn.disabled = true;
    ttsBtn.title = "Leitura em voz alta não é suportada neste navegador";
  }
});
