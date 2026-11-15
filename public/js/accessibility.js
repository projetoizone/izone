// Barra de acessibilidade: fonte, contraste, tema e leitura em voz alta

const root = document.documentElement;
const STEPS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]; // 100% ate 200%
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

  saveUserPreferences({ font_size: STEPS[index] });
}

// aplica um tema de cores com o nivel de contraste ("normal" ou "high")
function applyTheme(theme, contrast) {
  root.setAttribute("data-theme", theme);
  if (contrast === "high") {
    root.setAttribute("data-contrast", "high");
  } else {
    root.removeAttribute("data-contrast");
  }
  localStorage.setItem("izone-theme", theme);
  localStorage.setItem("izone-contrast", contrast);
  showTheme();

  saveUserPreferences({ theme: theme, contrast: contrast });
}

// mostra o tema atual na lista de temas ou, nas copias estaticas das paginas em
// prototype/views (GitHub Pages), nos botoes C e ◐, que elas ainda usam
function showTheme() {
  const select = document.querySelector('[data-action="theme"]');
  if (select) select.value = currentThemeOption(select).value;
  const contrastBtn = document.querySelector('[data-action="toggle-contrast"]');
  if (contrastBtn) contrastBtn.setAttribute("aria-pressed", root.getAttribute("data-contrast") === "high" ? "true" : "false");
  const themeBtn = document.querySelector('[data-action="toggle-theme"]');
  if (themeBtn) themeBtn.setAttribute("aria-pressed", root.getAttribute("data-theme") === "light" ? "true" : "false");
}

// a opcao que corresponde ao tema da pagina; "Amarelo no preto" e "Sepia" nao tem variante de contraste
function currentThemeOption(select) {
  const theme = root.getAttribute("data-theme") || "dark";
  const contrast = root.getAttribute("data-contrast") === "high" ? "high" : "normal";
  const options = [...select.options];
  return options.find((o) => o.dataset.setTheme === theme && o.dataset.setContrast === contrast)
    || options.find((o) => o.dataset.setTheme === theme)
    || options[0];
}

function saveUserPreferences(preferences) {
  // as paginas estaticas de prototype/views nao tem window.user
  if (!window.user || !window.user.is_authenticated) return;
  
  fetch("/accounts/update-preferences", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": window.csrftoken
    },
    body: JSON.stringify(preferences)
  });
}

// carrega as preferencias salvas
// applyFontStep(getStepIndex());

document.addEventListener("DOMContentLoaded", () => {
  const incBtn = document.querySelector('[data-action="font-increase"]');
  const decBtn = document.querySelector('[data-action="font-decrease"]');
  const themeSelect = document.querySelector('[data-action="theme"]');
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
  // cada opcao da lista combina um tema e o contraste. O leitor de tela ja fala a opcao
  // escolhida, entao a troca nao e anunciada de novo
  if (themeSelect) {
    themeSelect.addEventListener("change", () => {
      const option = themeSelect.selectedOptions[0];
      applyTheme(option.dataset.setTheme, option.dataset.setContrast);
    });
  }
  // botoes C e ◐ das paginas estaticas; so os temas claro e escuro tem versao de alto contraste
  if (contrastBtn) {
    contrastBtn.addEventListener("click", () => {
      const high = root.getAttribute("data-contrast") !== "high";
      applyTheme(root.getAttribute("data-theme") === "light" ? "light" : "dark", high ? "high" : "normal");
      announce(high ? "Alto contraste ativado" : "Alto contraste desativado");
    });
  }
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const light = root.getAttribute("data-theme") !== "light";
      applyTheme(light ? "light" : "dark", root.getAttribute("data-contrast") === "high" ? "high" : "normal");
      announce(light ? "Tema claro ativado" : "Tema escuro ativado");
    });
  }
  showTheme();

  // ao criar uma conta, envia as preferencias atuais para que a conta ja comece com elas
  document.querySelectorAll("form[data-send-preferences]").forEach((form) => {
    form.addEventListener("submit", () => {
      const current = {
        theme: root.getAttribute("data-theme") || "dark",
        contrast: root.getAttribute("data-contrast") === "high" ? "high" : "normal",
        font_size: String(STEPS[getStepIndex()]),
      };
      for (const [name, value] of Object.entries(current)) {
        let input = form.querySelector(`input[type="hidden"][name="${name}"]`);
        if (!input) {
          input = document.createElement("input");
          input.type = "hidden";
          input.name = name;
          form.append(input);
        }
        input.value = value;
      }
    });
  });

  // ler a pagina (ou o trecho selecionado) em voz alta, com pausar, continuar e parar
  if (ttsBtn && "speechSynthesis" in window) {
    const mainEl = document.querySelector("main");
    let selectedText = "";
    let selectedRange = null;
    let state = "idle"; // idle | playing | paused
    let reading = { text: "", where: [] };
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

    // velocidade da leitura, de 0,5x a 2x; fica salva neste navegador
    const RATES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
    const formatRate = (value) => String(value).replace(".", ",") + "x";
    const savedRate = parseFloat(localStorage.getItem("izone-tts-rate"));
    let rate = RATES.includes(savedRate) ? savedRate : 1;

    const speedLabel = document.createElement("label");
    speedLabel.className = "a11y-field";
    const speedText = document.createElement("span");
    speedText.textContent = "Velocidade";
    const speedSelect = document.createElement("select");
    speedSelect.dataset.action = "tts-rate";
    speedSelect.setAttribute("aria-label", "Velocidade da leitura"); // contem o texto visivel (WCAG 2.5.3)
    for (const value of RATES) {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = value === 1 ? "1x (normal)" : formatRate(value);
      speedSelect.append(option);
    }
    speedLabel.append(speedText, speedSelect);
    stopBtn.after(speedLabel);

    // o perfil tem um controle deslizante para a mesma velocidade
    const profileSlider = document.getElementById("pref-velocidade");
    const profileOutput = document.getElementById("pref-velocidade-valor");

    const showRate = () => {
      speedSelect.value = String(rate);
      if (profileSlider) {
        profileSlider.value = String(rate);
        profileSlider.setAttribute("aria-valuetext", formatRate(rate));
      }
      if (profileOutput) profileOutput.textContent = formatRate(rate);
    };
    showRate();

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

    // texto a ler, com o lugar de cada caractere na pagina, para destacar o que esta sendo
    // falado. Segue o innerText: so o que aparece, espacos juntados e uma quebra de linha
    // entre blocos. Icones decorativos (aria-hidden) ficam de fora, como no leitor de tela;
    // o texto .sr-only e lido junto com a frase em que esta
    const SKIP = "script, style, noscript, template, select, textarea, [aria-hidden='true']";
    const readableText = (range) => {
      let text = "";
      const where = []; // where[i] = [no de texto, posicao] do caractere i; null numa quebra de linha
      const styles = new Map();
      const style = (el) => {
        if (!styles.has(el)) styles.set(el, getComputedStyle(el));
        return styles.get(el);
      };
      const isBlock = (el) => {
        const display = style(el).display;
        return !(display.startsWith("inline") || display === "contents" || el.classList.contains("sr-only"));
      };
      const blockOf = (node) => {
        let el = node.parentElement;
        while (el && el !== document.body && !isBlock(el)) el = el.parentElement;
        return el;
      };
      const newLine = () => {
        if (text.endsWith(" ")) {
          text = text.slice(0, -1);
          where.pop();
        }
        if (text && !text.endsWith("\n")) {
          text += "\n";
          where.push(null);
        }
      };

      let scope = range.commonAncestorContainer;
      if (scope.nodeType !== Node.ELEMENT_NODE) scope = scope.parentNode;
      const walker = document.createTreeWalker(scope, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
        acceptNode: (node) => {
          if (!range.intersectsNode(node)) return NodeFilter.FILTER_REJECT;
          if (node.nodeType === Node.TEXT_NODE || node.nodeName === "BR") return NodeFilter.FILTER_ACCEPT;
          return node.matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
        },
      });
      let lastBlock = null;
      for (let node; (node = walker.nextNode());) {
        if (node.nodeName === "BR") {
          newLine();
          continue;
        }
        const box = document.createRange();
        box.selectNodeContents(node);
        if (!box.getClientRects().length || style(node.parentElement).visibility !== "visible") continue;
        const block = blockOf(node);
        if (block !== lastBlock) {
          newLine();
          lastBlock = block;
        }
        const from = node === range.startContainer ? range.startOffset : 0;
        const to = node === range.endContainer ? range.endOffset : node.length;
        for (let i = from; i < to; i++) {
          if (/\s/.test(node.data[i])) {
            if (!text || /\s$/.test(text)) continue;
            text += " ";
          } else {
            text += node.data[i];
          }
          where.push([node, i]);
        }
      }
      return { text, where };
    };

    // o texto e falado frase a frase: speechSynthesis.pause()/resume() nao funcionam de forma
    // consistente entre navegadores, entao pausar cancela a fala e continuar repete a frase atual.
    // Cada parte guarda onde comeca e termina no texto, para ser destacada na pagina
    const MAX_CHUNK = 200;
    const toChunks = (text) => {
      const parts = [];
      let last = 0;
      for (const separator of text.matchAll(/\n+|(?<=[.!?…])\s+/g)) {
        parts.push([last, separator.index]);
        last = separator.index + separator[0].length;
      }
      parts.push([last, text.length]);

      const chunks = [];
      for (let [start, end] of parts) {
        if (text[end - 1] === " ") end--;
        while (end - start > MAX_CHUNK) {
          let cut = text.lastIndexOf(" ", start + MAX_CHUNK);
          if (cut <= start) cut = start + MAX_CHUNK;
          chunks.push({ start, end: cut });
          start = text[cut] === " " ? cut + 1 : cut;
        }
        if (end > start) chunks.push({ start, end });
      }
      return chunks;
    };

    // a frase sendo lida fica destacada e a palavra falada, sublinhada (CSS Custom Highlight API).
    // Sem suporte no navegador, a leitura continua sem o destaque
    const canHighlight = "highlights" in CSS && typeof Highlight === "function";
    const highlight = (name, range) => {
      if (!canHighlight) return;
      if (range) CSS.highlights.set(name, new Highlight(range));
      else CSS.highlights.delete(name);
    };
    const rangeOf = (start, end) => {
      const first = reading.where[start];
      const last = reading.where[end - 1];
      if (end <= start || !first || !last) return null;
      try {
        const range = document.createRange();
        range.setStart(first[0], first[1]);
        range.setEnd(last[0], last[1] + 1);
        return range;
      } catch {
        return null; // o texto da pagina mudou desde o inicio da leitura
      }
    };
    // rola a pagina quando a frase lida esta fora da tela
    const reveal = (range) => {
      const box = range.getBoundingClientRect();
      if ((!box.width && !box.height) || (box.top >= 0 && box.bottom <= window.innerHeight)) return;
      const top = box.height > window.innerHeight / 2 ? box.top - 16 : box.top - window.innerHeight / 3;
      window.scrollBy({ top });
    };

    const halt = () => {
      run++;
      speechSynthesis.cancel();
    };

    const stop = (message) => {
      halt();
      state = "idle";
      chunks = [];
      index = 0;
      highlight("tts-sentence", null);
      highlight("tts-word", null);
      render();
      announce(message);
    };

    const speakCurrent = () => {
      if (index >= chunks.length) {
        stop("Leitura concluída");
        return;
      }
      const myRun = run;
      const { start: from, end: to } = chunks[index];
      const sentence = rangeOf(from, to);
      highlight("tts-sentence", sentence);
      highlight("tts-word", null);
      if (sentence) reveal(sentence);

      current = new SpeechSynthesisUtterance(reading.text.slice(from, to));
      current.lang = "pt-BR";
      current.rate = rate;
      // nem toda voz informa as palavras; sem isso, fica so o destaque da frase
      current.onboundary = (event) => {
        if (myRun !== run || event.name !== "word") return;
        const at = from + event.charIndex;
        let length = event.charLength;
        if (!length) {
          const space = reading.text.slice(at, to).search(/\s/);
          length = space < 0 ? to - at : space;
        }
        highlight("tts-word", rangeOf(at, Math.min(at + length, to)));
      };
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
      const fromSelection = !!selectedText;
      let range = selectedRange;
      if (!fromSelection) {
        range = document.createRange();
        range.selectNodeContents(mainEl || document.body);
      }
      reading = readableText(range);
      chunks = toChunks(reading.text);
      index = 0;
      state = "playing";
      // a selecao do navegador seria pintada por cima do destaque da leitura
      if (fromSelection) window.getSelection().removeAllRanges();
      render();
      announce(fromSelection ? "Lendo o trecho selecionado" : "Lendo o conteúdo da página em voz alta");
      speakCurrent();
    };

    const pause = () => {
      halt();
      state = "paused";
      highlight("tts-word", null); // a frase continua destacada, mostrando onde a leitura parou
      render();
      announce("Leitura pausada");
    };

    const resume = () => {
      state = "playing";
      render();
      announce("Leitura retomada");
      speakCurrent();
    };

    // uma fala nao muda de velocidade no meio, entao a frase atual recomeca na nova velocidade
    const setRate = (value) => {
      const next = parseFloat(value);
      if (RATES.includes(next) && next !== rate) {
        rate = next;
        localStorage.setItem("izone-tts-rate", String(rate));
        if (state === "playing") {
          halt();
          speakCurrent();
        }
      }
      showRate();
    };

    const isFormField = (el) => !!el && (el.matches("input, textarea, select") || el.isContentEditable);

    // lembra o ultimo trecho selecionado no conteudo principal. Ao ir com o teclado
    // ate o botao, o foco passa pelo campo de busca, que desfaz a selecao; por isso
    // ela so e esquecida quando o usuario de fato a desfaz fora de um campo
    document.addEventListener("selectionchange", () => {
      const sel = window.getSelection();
      if (mainEl && sel && !sel.isCollapsed && sel.rangeCount > 0 && sel.getRangeAt(0).intersectsNode(mainEl)) {
        selectedText = sel.toString().trim();
        selectedRange = sel.getRangeAt(0).cloneRange();
      } else if (!isFormField(document.activeElement)) {
        selectedText = "";
        selectedRange = null;
      }
      render();
    });

    ttsBtn.addEventListener("click", () => {
      if (state === "playing") pause();
      else if (state === "paused") resume();
      else start();
    });
    stopBtn.addEventListener("click", () => stop("Leitura interrompida"));
    speedSelect.addEventListener("change", () => setRate(speedSelect.value));
    if (profileSlider) profileSlider.addEventListener("input", () => setRate(profileSlider.value));
  } else if (ttsBtn) {
    ttsBtn.disabled = true;
    ttsBtn.title = "Leitura em voz alta não é suportada neste navegador";
    const profileSlider = document.getElementById("pref-velocidade");
    if (profileSlider) profileSlider.disabled = true;
  }
});
