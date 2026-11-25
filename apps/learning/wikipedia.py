"""
Consulta a Wikipédia em português, pela API do MediaWiki em https://pt.wikipedia.org/w/api.php.

A API e publica e nao precisa de chave, mas a Wikimedia pede que cada cliente se identifique
no User-Agent. Cada resposta fica uma hora em cache, para que voltar aos resultados ou abrir
de novo um artigo nao repita a consulta.
"""

import hashlib
import html
import json
import re
from dataclasses import dataclass
from http.client import HTTPException
from math import ceil
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils.html import strip_tags

API_URL = "https://pt.wikipedia.org/w/api.php"
INDEX_URL = "https://pt.wikipedia.org/w/index.php"
USER_AGENT = "iZone/0.1 (https://github.com/projetoizone/izone)"
PAGE_SIZE = 10
MAX_RESULTS = 10_000  # a pesquisa nao mostra resultados alem do 10.000o
MAX_PAGE = MAX_RESULTS // PAGE_SIZE
THUMB_WIDTH = 160  # as miniaturas dos resultados
IMAGE_WIDTH = 800  # a imagem principal do artigo
TIMEOUT = 10  # segundos
CACHE_SECONDS = 60 * 60

UNAVAILABLE = (
    "Não foi possível consultar a Wikipédia agora. Tente de novo em alguns minutos."
)


class WikipediaError(Exception):
    """A consulta falhou. A mensagem e escrita para ser mostrada na pagina."""


def slug(title):
    """O titulo como aparece nos enderecos: a Wikipedia troca os espacos por _."""
    return title.replace(" ", "_")


@dataclass(frozen=True)
class SearchResult:
    title: str
    description: str
    thumbnail: str | None

    @property
    def slug(self):
        return slug(self.title)


@dataclass(frozen=True)
class SearchPage:
    results: tuple[SearchResult, ...]
    total: int
    page: int
    suggestion: str  # outra grafia que a Wikipedia sugere, ou ""

    @property
    def pages(self):
        return max(1, ceil(min(self.total, MAX_RESULTS) / PAGE_SIZE))


def search(query, *, page=1):
    data = _get(
        {
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 0,  # so artigos
            "gsrlimit": PAGE_SIZE,
            "gsroffset": (page - 1) * PAGE_SIZE,
            "gsrinfo": "totalhits|suggestion",
            "prop": "description|pageimages",
            "piprop": "thumbnail",
            "pithumbsize": THUMB_WIDTH,
            "pilimit": PAGE_SIZE,
        }
    )
    info = data.get("searchinfo") or {}
    try:
        total = int(info.get("totalhits", 0))
    except (TypeError, ValueError):
        total = 0
    suggestion = _text(info.get("suggestion"))
    if suggestion.casefold() == query.casefold():
        suggestion = ""
    # a API lista as paginas em qualquer ordem, com a posicao na pesquisa em "index"
    pages = sorted(
        (p for p in data.get("pages") or [] if isinstance(p, dict)),
        key=lambda p: p.get("index") if isinstance(p.get("index"), int) else 0,
    )
    results = tuple(filter(None, map(_result, pages)))
    return SearchPage(results, total, page, suggestion)


@dataclass(frozen=True)
class Section:
    level: int  # o nivel do titulo na pagina: 2 para h2, 3 para h3...
    title: str
    paragraphs: tuple[str, ...]
    anchor: str


@dataclass(frozen=True)
class Image:
    url: str
    width: int | None
    height: int | None
    alt: str
    alt_lang: str  # o idioma do texto alternativo, quando nao e portugues
    author: str
    license: str
    license_url: str | None
    page_url: str | None  # a pagina da imagem no Wikimedia Commons

    @property
    def public_domain(self):
        return self.license.casefold() == "public domain"


@dataclass(frozen=True)
class Article:
    title: str
    description: str
    intro: tuple[str, ...]  # os paragrafos antes da primeira secao
    sections: tuple[Section, ...]
    url: str | None
    image: Image | None = None
    disambiguation: bool = False  # uma pagina que lista artigos com nomes parecidos

    @property
    def slug(self):
        return slug(self.title)

    @property
    def history_url(self):
        """O historico de edicoes, que lista os autores do texto."""
        return f"{INDEX_URL}?{urlencode({'title': self.slug, 'action': 'history'})}"

    @property
    def contents(self):
        """As secoes de primeiro nivel, para a lista de secoes do artigo."""
        return tuple(s for s in self.sections if s.level == 2)


def get_article(title):
    """O artigo com esse titulo ou redirecionado por ele, ou None se nao existe."""
    pages = _get(
        {
            "titles": title,
            "redirects": 1,
            "prop": "extracts|description|pageimages|info|pageprops",
            # o texto puro, com os titulos das secoes marcados com = como no codigo da wiki
            "explaintext": 1,
            "exsectionformat": "wiki",
            "piprop": "name",
            "inprop": "url",
            "ppprop": "disambiguation",
        }
    ).get("pages")
    page = pages[0] if isinstance(pages, list) and pages else {}
    if not isinstance(page, dict) or page.get("missing") or page.get("invalid"):
        return None
    if page.get("ns") != 0 or not _text(page.get("title")):
        return None

    title = _text(page["title"])
    intro, sections = _sections(page.get("extract"))
    image = None
    if isinstance(page.get("pageimage"), str):
        try:
            image = _image(page["pageimage"], title)
        except WikipediaError:
            pass  # sem a imagem, o artigo ainda pode ser lido
    url = page.get("fullurl")
    return Article(
        title=title,
        description=_text(page.get("description")),
        intro=intro,
        sections=sections,
        url=url if _is_web(url) else None,
        image=image,
        disambiguation="disambiguation" in (page.get("pageprops") or {}),
    )


HEADING = re.compile(r"(={2,6})\s*(.+?)\s*\1")


def _sections(extract):
    """Separa o texto puro em paragrafos e secoes, sem as secoes vazias."""
    intro, found = [], []
    paragraphs = intro
    for line in extract.splitlines() if isinstance(extract, str) else []:
        line = " ".join(line.split())
        heading = HEADING.fullmatch(line)
        if heading:
            paragraphs = []
            found.append((len(heading[1]), heading[2], paragraphs))
        elif line:
            paragraphs.append(line)

    # sem as referencias e notas, que o texto puro deixa vazias; uma secao que so
    # tem subsecoes fica
    kept = []
    for level, title, paragraphs in reversed(found):
        if paragraphs or (kept and kept[-1][0] > level):
            kept.append((level, title, paragraphs))
    kept.reverse()

    # os niveis nunca pulam, para quem navega pelos titulos com o leitor de tela
    sections, previous = [], 1
    for number, (level, title, paragraphs) in enumerate(kept, start=1):
        level = min(level, previous + 1)
        sections.append(Section(level, title, tuple(paragraphs), f"secao-{number}"))
        previous = level
    return tuple(intro), tuple(sections)


def _image(name, article_title):
    pages = _get(
        {
            "titles": f"File:{name}",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": IMAGE_WIDTH,
            "iiextmetadatafilter": "ImageDescription|Artist|LicenseShortName|LicenseUrl",
            "iiextmetadatamultilang": 1,  # a descricao em cada idioma, para escolher
        }
    ).get("pages")
    try:
        info = pages[0]["imageinfo"][0]
    except (KeyError, IndexError, TypeError):
        return None
    if not _is_web(info.get("thumburl")):
        return None

    metadata = info.get("extmetadata") or {}

    def value(name):
        field = metadata.get(name)
        return field.get("value") if isinstance(field, dict) else None

    alt, alt_lang = _description(value("ImageDescription"))
    license_url = value("LicenseUrl")
    page_url = info.get("descriptionurl")
    return Image(
        url=info["thumburl"],
        width=_number(info.get("thumbwidth")),
        height=_number(info.get("thumbheight")),
        alt=alt or f"Imagem do artigo {article_title}",
        alt_lang=alt_lang,
        author=_text(value("Artist")),
        license=_text(value("LicenseShortName")),
        license_url=license_url if _is_web(license_url) else None,
        page_url=page_url if _is_web(page_url) else None,
    )


def _description(value):
    """A descricao da imagem e o idioma dela: em portugues se houver, senao em ingles."""
    if isinstance(value, str):  # sem idioma indicado
        return _text(value), ""
    if not isinstance(value, dict):
        return "", ""
    texts = {
        lang: _text(text)
        for lang, text in value.items()
        if lang != "_type" and _text(text)
    }
    for lang in ("pt", "pt-br", "en", *texts):
        if lang in texts:
            return texts[lang], "" if lang.startswith("pt") else lang
    return "", ""


def _result(page):
    title = _text(page.get("title"))
    if page.get("ns") != 0 or not title:
        return None
    thumbnail = (page.get("thumbnail") or {}).get("source")
    return SearchResult(
        title=title,
        description=_text(page.get("description")),
        thumbnail=thumbnail if _is_web(thumbnail) else None,
    )


def _get(params):
    params = {"action": "query", "format": "json", "formatversion": 2, **params}
    url = f"{API_URL}?{urlencode(params)}"
    key = "wikipedia:" + hashlib.sha256(url.encode()).hexdigest()
    query = cache.get(key)
    if query is None:
        query = _fetch(url)
        cache.set(key, query, CACHE_SECONDS)
    return query


def _fetch(url):
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            data = json.load(response)
    except (OSError, HTTPException, ValueError) as error:
        # rede, tempo esgotado, erro HTTP (HTTPError e um OSError) ou JSON invalido
        raise WikipediaError(UNAVAILABLE) from error
    # os erros da API vem com status 200 e uma chave "error" no lugar de "query"
    query = data.get("query") if isinstance(data, dict) else None
    if not isinstance(query, dict):
        raise WikipediaError(UNAVAILABLE)
    return query


def _text(value):
    if not isinstance(value, str):
        return ""
    return " ".join(html.unescape(strip_tags(value)).split())


def _number(value):
    return value if isinstance(value, int) and value > 0 else None


def _is_web(url):
    # os enderecos vao para src e href; so http e https, nunca javascript: ou data:
    return isinstance(url, str) and urlsplit(url).scheme in ("http", "https")
