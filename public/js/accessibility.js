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

  // ler a pagina (ou o trecho selecionado) em voz alta, com pausar, continuar e parar
  if (ttsBtn && "speechSynthesis" in window) {
    const mainEl = document.querySelector("main");
    let selectedText = "";
    let state = "idle"; // idle | playing | paused
    let chunks = [];
    let index = 0;
    let run = 0; // muda a cada cancelamento, para ignorar eventos de falas canceladas
    let current = null; // manter a referencia evita que o Chrome descarte a fala antes do "end"

    const stopBtn = document.createElement("button");
    stopBtn.type = "button";
    stopBtn.className = "a11y-btn";
    stopBtn.dataset.action = "stop-tts";
    stopBtn.hidden = true;
    ttsBtn.removeAttribute("aria-pressed"); // o rotulo muda com o estado, entao nao e um botao de alternancia
    ttsBtn.after(stopBtn);

    // o nome acessivel e o proprio texto visivel (WCAG 2.5.3); o icone fica oculto do leitor de tela
    const setLabel = (btn, icon, text, ariaLabel) => {
      const key = icon + text + (ariaLabel || "");
      if (btn.dataset.label === key) return;
      btn.dataset.label = key;
      const iconEl = document.createElement("span");
      iconEl.setAttribute("aria-hidden", "true");
      iconEl.textContent = icon;
      btn.replaceChildren(iconEl, " " + text);
      if (ariaLabel) btn.setAttribute("aria-label", ariaLabel);
      else btn.removeAttribute("aria-label");
    };

    const render = () => {
      if (state === "playing") setLabel(ttsBtn, "⏸", "Pausar leitura");
      else if (state === "paused") setLabel(ttsBtn, "▶", "Continuar leitura");
      else if (selectedText) setLabel(ttsBtn, "🔊", "Ouvir trecho", "Ouvir trecho selecionado");
      else setLabel(ttsBtn, "🔊", "Ouvir página");
      ttsBtn.classList.toggle("is-active", state !== "idle");
      // o botao parar some quando a leitura termina; o foco volta para o botao principal
      if (state === "idle" && document.activeElement === stopBtn) ttsBtn.focus();
      stopBtn.hidden = state === "idle";
    };

    setLabel(stopBtn, "⏹", "Parar leitura");
    render();

    // o texto e falado frase a frase: speechSynthesis.pause()/resume() nao funcionam de forma
    // consistente entre navegadores, entao pausar cancela a fala e continuar repete a frase atual
    const MAX_CHUNK = 200;
    const toChunks = (text) => text
      .split(/\n+/)
      .flatMap((line) => line.split(/(?<=[.!?…])\s+/))
      .flatMap((part) => {
        const out = [];
        let rest = part.trim();
        while (rest.length > MAX_CHUNK) {
          let cut = rest.lastIndexOf(" ", MAX_CHUNK);
          if (cut <= 0) cut = MAX_CHUNK;
          out.push(rest.slice(0, cut));
          rest = rest.slice(cut).trim();
        }
        if (rest) out.push(rest);
        return out;
      });

    const halt = () => {
      run++;
      speechSynthesis.cancel();
    };

    const stop = (message) => {
      halt();
      state = "idle";
      chunks = [];
      index = 0;
      render();
      announce(message);
    };

    const speakCurrent = () => {
      if (index >= chunks.length) {
        stop("Leitura concluída");
        return;
      }
      const myRun = run;
      current = new SpeechSynthesisUtterance(chunks[index]);
      current.lang = "pt-BR";
      current.onend = () => {
        if (myRun !== run) return;
        index++;
        speakCurrent();
      };
      current.onerror = () => {
        if (myRun !== run) return;
        stop("Não foi possível continuar a leitura");
      };
      speechSynthesis.speak(current);
    };

    const start = () => {
      halt();
      chunks = toChunks(selectedText || (mainEl ? mainEl.innerText : document.body.innerText));
      index = 0;
      state = "playing";
      render();
      announce(selectedText ? "Lendo o trecho selecionado" : "Lendo o conteúdo da página em voz alta");
      speakCurrent();
    };

    const pause = () => {
      halt();
      state = "paused";
      render();
      announce("Leitura pausada");
    };

    const resume = () => {
      state = "playing";
      render();
      announce("Leitura retomada");
      speakCurrent();
    };

    const isFormField = (el) => !!el && (el.matches("input, textarea, select") || el.isContentEditable);

    // lembra o ultimo trecho selecionado no conteudo principal. Ao ir com o teclado
    // ate o botao, o foco passa pelo campo de busca, que desfaz a selecao; por isso
    // ela so e esquecida quando o usuario de fato a desfaz fora de um campo
    document.addEventListener("selectionchange", () => {
      const sel = window.getSelection();
      if (mainEl && sel && !sel.isCollapsed && sel.rangeCount > 0 && sel.getRangeAt(0).intersectsNode(mainEl)) {
        selectedText = sel.toString().trim();
      } else if (!isFormField(document.activeElement)) {
        selectedText = "";
      }
      render();
    });

    ttsBtn.addEventListener("click", () => {
      if (state === "playing") pause();
      else if (state === "paused") resume();
      else start();
    });
    stopBtn.addEventListener("click", () => stop("Leitura interrompida"));
  } else if (ttsBtn) {
    ttsBtn.disabled = true;
    ttsBtn.title = "Leitura em voz alta não é suportada neste navegador";
  }
});
