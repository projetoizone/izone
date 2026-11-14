
(() => {
    const form = document.getElementById("dictionaryForm");
    const input = document.getElementById("word");
    const submitButton = document.getElementById("dictionarySubmit");
    const status = document.getElementById("dictionaryStatus");
    const result = document.getElementById("dictionaryResult");

    const displayWord = document.getElementById("displayWord");
    const phoneticsSection = document.getElementById("phoneticsSection");
    const displayPhonetics = document.getElementById("displayPhonetics");
    const displayMeanings = document.getElementById("displayMeanings");
    const dictionarySources = document.getElementById("dictionarySources");
    const displaySources = document.getElementById("displaySources");
    const displayLicense = document.getElementById("displayLicense");

    const definitionUrl = form.dataset.definitionUrl;

    // Cria um elemento HTML com texto e classes.
    function createElement(tag, className, text = "") {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        element.textContent = text;

        return element;
    }

    // Atualiza mensagens acessíveis para leitores de tela.
    function announce(message, isError = false) {
        status.setAttribute("role", isError ? "alert" : "status");
        status.setAttribute("aria-live", isError ? "assertive" : "polite");
        status.textContent = message;

        status.classList.toggle("dictionary-error", isError);
    }

    // Cria uma lista de termos, como sinônimos e antônimos.
    function renderWordList(container, title, words) {
        if (!Array.isArray(words) || words.length === 0) {
            return;
        }

        const label = createElement(
            "p",
            "dictionary-word-list-label",
            `${title}:`
        );

        const list = createElement("ul", "dictionary-word-list");

        words.forEach(word => {
            if (typeof word !== "string" || !word.trim()) {
                return;
            }

            list.appendChild(
                createElement("li", "dictionary-term", word)
            );
        });

        if (list.childElementCount > 0) {
            container.appendChild(label);
            container.appendChild(list);
        }
    }

    // Aceita apenas URLs HTTPS para links externos e áudios.
    function getSafeUrl(value) {
        if (typeof value !== "string" || !value.trim()) {
            return null;
        }

        try {
            const url = new URL(value);

            return url.protocol === "https:" ? url.href : null;
        } catch {
            return null;
        }
    }

    // Apresenta as pronúncias fonéticas e seus respectivos áudios.
    function renderPhonetics(phonetics) {
        displayPhonetics.replaceChildren();

        const validPhonetics = Array.isArray(phonetics)
            ? phonetics.filter(item =>
                item &&
                (item.text || item.audio)
            )
            : [];

        phoneticsSection.hidden = validPhonetics.length === 0;

        validPhonetics.forEach((phonetic, index) => {
            const item = createElement("li", "phonetic-card");

            if (phonetic.text) {
                item.appendChild(
                    createElement("p", "phonetic-text", phonetic.text)
                );
            }

            if (phonetic.audio) {
                const audioUrl = getSafeUrl(phonetic.audio);

                if (audioUrl) {
                    const audio = createElement("audio", "phonetic-audio");

                    audio.controls = true;
                    audio.preload = "none";
                    audio.src = audioUrl;
                    audio.setAttribute(
                        "aria-label",
                        `Áudio da pronúncia ${index + 1}`
                    );

                    item.appendChild(audio);
                }
            }

            displayPhonetics.appendChild(item);
        });
    }

    // Apresenta os significados agrupados por classe gramatical.
    function renderMeanings(meanings) {
        displayMeanings.replaceChildren();

        if (!Array.isArray(meanings) || meanings.length === 0) {
            const item = createElement(
                "li",
                "dictionary-empty",
                "Nenhuma definição disponível."
            );

            displayMeanings.appendChild(item);
            return;
        }

        meanings.forEach(meaning => {
            const meaningItem = createElement("li", "meaning-item");
            const meaningArticle = createElement("article", "meaning-card");

            const partOfSpeech = createElement(
                "h4",
                "meaning-part-of-speech",
                meaning.part_of_speech || "Classe gramatical não informada"
            );

            meaningArticle.appendChild(partOfSpeech);

            renderWordList(
                meaningArticle,
                "Sinônimos",
                meaning.synonyms
            );

            renderWordList(
                meaningArticle,
                "Antônimos",
                meaning.antonyms
            );

            const definitions = Array.isArray(meaning.definitions)
                ? meaning.definitions
                : [];

            const definitionList = createElement(
                "ol",
                "definition-list"
            );

            definitions.forEach(definition => {
                const definitionItem = createElement(
                    "li",
                    "definition-card"
                );

                definitionItem.appendChild(
                    createElement(
                        "p",
                        "definition-text",
                        definition.definition || "Definição indisponível."
                    )
                );

                if (definition.example) {
                    const example = createElement(
                        "blockquote",
                        "definition-example",
                        definition.example
                    );

                    definitionItem.appendChild(example);
                }

                renderWordList(
                    definitionItem,
                    "Sinônimos",
                    definition.synonyms
                );

                renderWordList(
                    definitionItem,
                    "Antônimos",
                    definition.antonyms
                );

                definitionList.appendChild(definitionItem);
            });

            if (definitionList.childElementCount > 0) {
                meaningArticle.appendChild(definitionList);
            }

            meaningItem.appendChild(meaningArticle);
            displayMeanings.appendChild(meaningItem);
        });
    }

    // Apresenta as fontes e informações de licença.
    function renderSources(data) {
        displaySources.replaceChildren();
        displayLicense.replaceChildren();

        let hasSources = false;

        if (Array.isArray(data.source_urls)) {
            data.source_urls.forEach(source => {
                const safeUrl = getSafeUrl(source);

                if (!safeUrl) {
                    return;
                }

                const link = createElement(
                    "a",
                    "source-link",
                    new URL(safeUrl).hostname
                );

                link.href = safeUrl;
                link.target = "_blank";
                link.rel = "noopener noreferrer";

                const item = createElement("li", "source-item");
                item.appendChild(link);

                displaySources.appendChild(item);
                hasSources = true;
            });
        }

        if (data.license) {
            const licenseName = data.license.name || "Não informada";

            displayLicense.appendChild(
                document.createTextNode(`Licença: ${licenseName}`)
            );

            const licenseUrl = getSafeUrl(data.license.url);

            if (licenseUrl) {
                const link = createElement(
                    "a",
                    "license-link",
                    "Consultar licença"
                );

                link.href = licenseUrl;
                link.target = "_blank";
                link.rel = "noopener noreferrer";

                displayLicense.appendChild(
                    document.createTextNode(" ")
                );

                displayLicense.appendChild(link);
            }

            hasSources = true;
        }

        dictionarySources.hidden = !hasSources;
    }

    // Atualiza a interface com os dados recebidos do Django.
    function renderDictionary(data) {
        displayWord.textContent = data.word || input.value;

        renderPhonetics(data.phonetics);
        renderMeanings(data.meanings);
        renderSources(data);

        result.hidden = false;
    }

    // Consulta o endpoint do Django.
    form.addEventListener("submit", async event => {
        event.preventDefault();

        const word = input.value.trim();

        if (!word) {
            input.focus();
            return;
        }

        submitButton.disabled = true;
        form.setAttribute("aria-busy", "true");
        result.hidden = true;

        announce("Consultando o dicionário...");

        try {
            const url = new URL(definitionUrl, window.location.origin);
            url.searchParams.set("word", word);

            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Não foi possível encontrar a palavra."
                );
            }

            renderDictionary(data);

            announce(
                `Pesquisa concluída. Resultados para ${data.word || word} disponíveis.`
            );
        } catch (error) {
            announce(
                error.message ||
                "Não foi possível comunicar com o servidor.",
                true
            );
        } finally {
            submitButton.disabled = false;
            form.removeAttribute("aria-busy");
        }
    });
})();
