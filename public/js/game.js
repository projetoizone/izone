
const BRAILLE = {
  a: [1],
  b: [1, 2],
  c: [1, 4],
  d: [1, 4, 5],
  e: [1, 5],
  f: [1, 2, 4],
  g: [1, 2, 4, 5],
  h: [1, 2, 5],
  i: [2, 4],
  j: [2, 4, 5],
  k: [1, 3],
  l: [1, 2, 3],
  m: [1, 3, 4],
  n: [1, 3, 4, 5],
  o: [1, 3, 5],
  p: [1, 2, 3, 4],
  q: [1, 2, 3, 4, 5],
  r: [1, 2, 3, 5],
  s: [2, 3, 4],
  t: [2, 3, 4, 5],
  u: [1, 3, 6],
  v: [1, 2, 3, 6],
  w: [2, 4, 5, 6],
  x: [1, 3, 4, 6],
  y: [1, 3, 4, 5, 6],
  z: [1, 3, 5, 6]
};

function createBrailleCell(character) {
  const activeDots = BRAILLE[character];

  if (!activeDots) {
    return null;
  }

  const cell = document.createElement("div");
  cell.className = "braille-cell";
  cell.setAttribute(
    "role",
    "img"
  );

  cell.setAttribute(
    "aria-label",
    `${character}: pontos ${activeDots.join(", ")}`
  );

  for (let dot = 1; dot <= 6; dot++) {
    const point = document.createElement("span");

    point.className = "braille-dot";
    point.classList.toggle(
      "active",
      activeDots.includes(dot)
    );

    point.setAttribute("aria-hidden", "true");
    cell.appendChild(point);
  }

  return cell;
}

function renderBraille(word) {
  const display = document.querySelector("#braille-display");
  display.replaceChildren();

  for (const character of word.toLowerCase()) {
    if (character === " ") {
      const space = document.createElement("span");
      space.className = "word-space";
      space.setAttribute("aria-hidden", "true");
      display.appendChild(space);
      continue;
    }

    const cell = createBrailleCell(character);

    if (cell) {
      display.appendChild(cell);
    } else {
      // Não inventamos uma representação para caracteres
      // ainda não suportados.
      const unsupported = document.createElement("span");
      unsupported.textContent = character;
      unsupported.setAttribute("aria-label",
        `${character}: representação Braille indisponível`);
      display.appendChild(unsupported);
    }
  }
}


const API_BASE = "https://api.dicionario-aberto.net";

async function fetchJSON(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Erro na API: HTTP ${response.status}`);
  }

  return response.json();
}

async function getRandomWord() {
  const data = await fetchJSON(`${API_BASE}/random`);

  // A API documenta a palavra no campo "word".
  if (!data || typeof data.word !== "string") {
    throw new Error("A API não retornou uma palavra válida.");
  }

  return data.word.trim();
}

async function getWordDefinition(word) {
  const entries = await fetchJSON(
    `${API_BASE}/word/${encodeURIComponent(word)}`
  );

  if (!Array.isArray(entries) || entries.length === 0) {
    return "";
  }

  const definitions = [];

  for (const entry of entries) {
    if (typeof entry.xml !== "string") continue;

    const xml = new DOMParser().parseFromString(
      entry.xml,
      "application/xml"
    );

    if (xml.querySelector("parsererror")) continue;

    const senses = [...xml.querySelectorAll("def")]
      .map(node => node.textContent.trim())
      .filter(Boolean);

    definitions.push(...senses);
  }

  return [...new Set(definitions)].join(" ") ||
    "Definição indisponível.";
}

async function getNextChallenge() {
  // Tentamos encontrar uma palavra compatível com
  // a tabela Braille simplificada deste protótipo.
  for (let attempt = 0; attempt < 8; attempt++) {
    const word = await getRandomWord();

    // Por enquanto, aceitamos apenas letras sem acentos.
    // A tabela Braille portuguesa completa virá depois.
    if (!/^[a-z]{3,12}$/i.test(word)) {
      continue;
    }

    const definition = await getWordDefinition(word);

    return {
      word,
      definition,
      example: ""
    };
  }

  throw new Error(
    "Não foi encontrada uma palavra compatível. Tente novamente."
  );
}


function speak(text) {
  if (!("speechSynthesis" in window)) {
    feedback.textContent =
      "A síntese de voz não é suportada neste navegador.";
    return false;
  }

  const synth = window.speechSynthesis;
  const voices = synth.getVoices();

  // Procura primeiro uma voz em português brasileiro.
  const portugueseVoices = voices.filter(
    voice => voice.lang.toLowerCase() === "pt-br"
  );

  // Tenta priorizar vozes que possam ter melhor qualidade.
  const preferredVoice = portugueseVoices.find(
    voice => /natural|neural|online/i.test(voice.name)
  );

  const selectedVoice =
    preferredVoice ||
    portugueseVoices.find(voice => voice.default) ||
    portugueseVoices[0] ||
    voices.find(voice => voice.lang.toLowerCase().startsWith("pt"));

  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "pt-BR";
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }

  synth.speak(utterance);
  return true;
}


class SpellingGame {
  constructor() {
    this.score = 0;
    this.round = 0;
    this.currentWord = null;
    this.answered = false;
    this.usedWords = new Set();
  }

  async startRound() {
    this.currentWord = await getNextChallenge();
    this.answered = false;
    return this.currentWord;
  }

  checkAnswer(answer) {
    if (!this.currentWord || this.answered) {
      return { status: "invalid" };
    }

    const normalized = answer
      .trim()
      .normalize("NFC")
      .toLocaleLowerCase("pt-BR");

    const expected = this.currentWord.word
      .normalize("NFC")
      .toLocaleLowerCase("pt-BR");

    if (normalized === expected) {
      this.score += 10;
      this.answered = true;

      return {
        status: "correct",
        score: this.score,
        word: this.currentWord
      };
    }

    return {
      status: "incorrect",
      word: this.currentWord
    };
  }

  async nextRound() {
    this.round += 1;
    return this.startRound();
  }
}

const game = new SpellingGame();

const answerForm = document.querySelector("#answer-form");
const answerInput = document.querySelector("#answer");
const feedback = document.querySelector("#feedback");
const scoreDisplay = document.querySelector("#score");
const nextButton = document.querySelector("#next-round");
const learning = document.querySelector("#learning");

const hearButton = document.querySelector("#hear-word");
const definitionDisplay = document.querySelector("#definition");
const exampleDisplay = document.querySelector("#example");


const voiceSelect = document.querySelector("#voice-select");
const testVoiceButton = document.querySelector("#test-voice");

function populateVoices() {
  const voices = speechSynthesis.getVoices()
    .filter(voice => voice.lang.toLowerCase() === "pt-br");

  voiceSelect.replaceChildren();

  voices.forEach(voice => {
    const option = document.createElement("option");
    option.value = voice.voiceURI;
    option.textContent = voice.name;
    voiceSelect.appendChild(option);
  });
}

populateVoices();
speechSynthesis.addEventListener("voiceschanged", populateVoices);

function speak(text) {
  if (!("speechSynthesis" in window)) return false;

  const voice = speechSynthesis.getVoices()
    .find(v => v.voiceURI === voiceSelect.value);

  speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "pt-BR";
  utterance.rate = 0.95;
  utterance.pitch = 1;

  if (voice) utterance.voice = voice;

  speechSynthesis.speak(utterance);
  return true;
}

testVoiceButton.addEventListener("click", () => {
  speak("Olá! Esta é a voz que será utilizada no jogo de soletração.");
});


function showWord(challenge) {
  answerInput.value = "";
  renderBraille("");

  feedback.textContent =
    "Ouça a palavra e digite sua resposta.";

  nextButton.hidden = true;
  learning.hidden = true;
  answerInput.disabled = false;

  speak(challenge.word);
}

async function loadRound() {
  answerInput.disabled = true;
  hearButton.disabled = true;
  nextButton.hidden = true;
  learning.hidden = true;

  feedback.textContent = "Carregando palavra do dicionário...";

  try {
    const challenge = game.currentWord
      ? await game.nextRound()
      : await game.startRound();

    showWord(challenge);
    answerInput.disabled = false;
    answerInput.focus();
  } catch (error) {
    console.error(error);

    feedback.textContent =
      "Não foi possível carregar uma palavra. Tente novamente.";

    nextButton.textContent = "Tentar novamente";
    nextButton.hidden = false;
  } finally {
    hearButton.disabled = false;
  }
}

// O Braille acompanha a resposta digitada.
answerInput.addEventListener("input", () => {
  renderBraille(answerInput.value);
});

hearButton.addEventListener("click", () => {
  if (game.currentWord) {
    speak(game.currentWord.word);
  }
});

answerForm.addEventListener("submit", event => {
  event.preventDefault();

  const result = game.checkAnswer(answerInput.value);

  if (result.status === "invalid") {
    feedback.textContent =
      "Esta rodada já foi concluída ou ainda não começou.";
    return;
  }

  if (result.status === "correct") {
    feedback.textContent = "Correto! Muito bem.";
    scoreDisplay.textContent = `Pontuação: ${result.score}`;

    definitionDisplay.textContent =
      `Definição: ${result.word.definition}`;

    exampleDisplay.textContent = result.word.example
      ? `Exemplo: ${result.word.example}`
      : "";

    learning.hidden = false;
    nextButton.textContent = "Próxima palavra";
    nextButton.hidden = false;
    answerInput.disabled = true;

    speak("Correto! Muito bem.");
  } else {
    feedback.textContent =
      "Ainda não está correto. Tente novamente.";

    speak("Resposta incorreta. Tente novamente.");
  }
});

nextButton.addEventListener("click", loadRound);

// Inicia a primeira rodada.
loadRound();
