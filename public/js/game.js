
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
      unsupported.setAttribute("role", "img");
      unsupported.setAttribute("aria-label",
        `${character}: representação Braille indisponível`);
      display.appendChild(unsupported);
    }
  }
}


// a palavra vem do servidor, que consulta o Dicionário Aberto (apps/spelling/dicionario_aberto.py)
const CHALLENGE_URL = document.querySelector("#answer-form").dataset.challengeUrl;

const LOAD_ERROR = "Não foi possível carregar uma palavra. Tente novamente.";

// a mensagem do erro é escrita para ser mostrada na página
async function getNextChallenge() {
  let response;
  try {
    response = await fetch(CHALLENGE_URL);
  } catch {
    throw new Error(LOAD_ERROR); // sem conexão com o servidor
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok || typeof data.word !== "string") {
    throw new Error(data.error || LOAD_ERROR);
  }

  return data;
}

// fala com a voz da barra de acessibilidade (accessibility.js): mesma velocidade e idioma
// da leitura do site, sem cortar o "Ouvir página"
// devolve a fala, ou null quando o navegador não tem voz
function speak(text) {
  return (window.izone && window.izone.speak && window.izone.speak(text)) || null;
}

// fala a palavra da rodada mostrando na tela que ela está tocando: quem está com o som
// baixo ou desligado vê que o clique funcionou. O aviso é só visual (aria-hidden), para
// o leitor de tela não falar por cima da palavra; os erros vão para o #feedback, que é lido
function speakWord(word) {
  const utterance = speak(word);
  if (!utterance) {
    feedback.textContent = NO_SPEECH;
    return false;
  }

  // só apaga o aviso se nenhuma fala mais nova o tiver mostrado de novo
  currentUtterance = utterance;
  hearStatus.textContent = "Tocando a palavra…";
  const done = () => {
    if (currentUtterance === utterance) hearStatus.textContent = "";
  };

  utterance.addEventListener("end", done);
  utterance.addEventListener("error", event => {
    done();
    // "interrupted" e "canceled": outra fala tomou o lugar desta, não é um erro
    if (event.error === "interrupted" || event.error === "canceled") return;
    // o Chrome não deixa falar antes de a pessoa interagir com a página
    feedback.textContent = event.error === "not-allowed"
      ? "Selecione “Ouvir palavra novamente” para ouvir a palavra."
      : "Não foi possível tocar a palavra. Verifique o volume e tente de novo.";
  });
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
const hearStatus = document.querySelector("#hear-status");
let currentUtterance = null;
const definitionDisplay = document.querySelector("#definition");
const exampleDisplay = document.querySelector("#example");


// sem voz no navegador não dá para ouvir a palavra; o botão fica desativado, como o "Ouvir página"
const canSpeak = "speechSynthesis" in window;
const NO_SPEECH = "A leitura em voz alta não é suportada neste navegador, então não é possível ouvir a palavra.";

if (!canSpeak) hearButton.title = "Leitura em voz alta não é suportada neste navegador";


function showWord(challenge) {
  answerInput.value = "";
  renderBraille("");

  nextButton.hidden = true;
  learning.hidden = true;
  answerInput.disabled = false;

  feedback.textContent = "Ouça a palavra e digite sua resposta.";
  speakWord(challenge.word);
}

// Move o foco só quando ele se perdeu (o elemento focado sumiu ou foi
// desativado), para não tirar o usuário do lugar em que ele está na página.
function focusIfLost(element) {
  const active = document.activeElement;
  const lost = !active || active === document.body
    || active.disabled || !!active.closest("[hidden]");

  if (lost) element.focus();
}

// startedByUser: a rodada foi pedida pelo botão "Próxima palavra" ou
// "Tentar novamente". Na primeira rodada, ao abrir a página, o foco não muda.
async function loadRound(startedByUser = false) {
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
    if (startedByUser) focusIfLost(answerInput);
  } catch (error) {
    console.error(error);

    feedback.textContent = error.message;

    nextButton.textContent = "Tentar novamente";
    nextButton.hidden = false;
    if (startedByUser) focusIfLost(nextButton);
  } finally {
    hearButton.disabled = !canSpeak;
  }
}

// O Braille acompanha a resposta digitada.
answerInput.addEventListener("input", () => {
  renderBraille(answerInput.value);
});

hearButton.addEventListener("click", () => {
  if (game.currentWord) {
    speakWord(game.currentWord.word);
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
    // a resposta foi desativada com o foco nela; o próximo passo é a próxima palavra
    focusIfLost(nextButton);

    speak("Correto! Muito bem.");
  } else {
    feedback.textContent =
      "Ainda não está correto. Tente novamente.";

    speak("Resposta incorreta. Tente novamente.");
  }
});

nextButton.addEventListener("click", () => loadRound(true));

// Inicia a primeira rodada.
loadRound();
