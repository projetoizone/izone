"""
Consulta o Dicionário Aberto (https://api.dicionario-aberto.net), de onde vêm as palavras do jogo.

A API é pública e não precisa de chave. O jogo pede uma palavra ao servidor, e o servidor
consulta a API, como o dicionário de inglês faz, em vez de o navegador chamar a API direto.
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

API_URL = "https://api.dicionario-aberto.net"
TIMEOUT = 10  # segundos
ATTEMPTS = 8
# a tabela Braille do jogo ainda só tem as letras sem acento
PLAYABLE = re.compile(r"[a-z]{3,12}", re.IGNORECASE)

UNAVAILABLE = "Não foi possível carregar uma palavra. Tente novamente."
NO_WORD = "Não foi encontrada uma palavra compatível. Tente novamente."
NO_DEFINITION = "Definição indisponível."


class DicionarioError(Exception):
    """A consulta falhou. A mensagem é escrita para ser mostrada na página."""


def _get(path):
    try:
        response = requests.get(f"{API_URL}/{path}", timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        raise DicionarioError(UNAVAILABLE) from error


def random_word():
    data = _get("random")
    word = data.get("word") if isinstance(data, dict) else None
    if not isinstance(word, str):
        raise DicionarioError(UNAVAILABLE)
    return word.strip()


def definition(word):
    """As definições da palavra num só texto, sem repetir as que aparecem em mais de um verbete."""
    entries = _get(f"word/{quote(word, safe='')}")
    senses = []
    for entry in entries if isinstance(entries, list) else []:
        try:
            root = ET.fromstring(entry.get("xml", ""))
        except (ET.ParseError, AttributeError, TypeError):
            continue
        for node in root.iter("def"):
            # o dicionário marca os exemplos em itálico com _sublinhados_
            text = " ".join("".join(node.itertext()).replace("_", "").split())
            if text and text not in senses:
                senses.append(text)
    return " ".join(senses) or NO_DEFINITION


def challenge():
    """Uma palavra que o jogo consegue mostrar em Braille, com a sua definição."""
    for _ in range(ATTEMPTS):
        word = random_word()
        if PLAYABLE.fullmatch(word):
            return {"word": word, "definition": definition(word), "example": ""}
    raise DicionarioError(NO_WORD)
