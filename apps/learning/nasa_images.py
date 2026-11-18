"""
Consulta o acervo de imagens da NASA (NASA Image and Video Library), em https://images-api.nasa.gov.

A API e publica e nao precisa de chave. Cada resposta fica uma hora em cache, para que
voltar aos resultados ou abrir de novo uma imagem nao repita a consulta.
"""

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from http.client import HTTPException
from math import ceil
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils.html import strip_tags

API_URL = "https://images-api.nasa.gov/search"
DETAILS_URL = "https://images.nasa.gov/details/{}"
PAGE_SIZE = 12
MAX_RESULTS = 10_000  # a API nao mostra resultados alem do 10.000o de uma pesquisa
MAX_PAGE = MAX_RESULTS // PAGE_SIZE
SHOWN_WIDTH = (
    1280  # a maior versao da imagem que a pagina carrega; a original fica num link
)
TIMEOUT = 10  # segundos
CACHE_SECONDS = 60 * 60

UNAVAILABLE = "Não foi possível consultar o acervo da NASA agora. Tente de novo em alguns minutos."
REFUSED = "O acervo da NASA não aceitou essa pesquisa. Tente outras palavras ou outro período."

# o acervo indica o centro da NASA so pela sigla
CENTERS = {
    "AFRC": "Armstrong Flight Research Center",
    "ARC": "Ames Research Center",
    "GRC": "Glenn Research Center",
    "GSFC": "Goddard Space Flight Center",
    "HQ": "sede da NASA",
    "JPL": "Jet Propulsion Laboratory",
    "JSC": "Johnson Space Center",
    "KSC": "Kennedy Space Center",
    "LARC": "Langley Research Center",
    "MSFC": "Marshall Space Flight Center",
    "SSC": "Stennis Space Center",
}


class NasaImagesError(Exception):
    """A consulta falhou. A mensagem e escrita para ser mostrada na pagina."""


@dataclass(frozen=True)
class Rendition:
    url: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class NasaImage:
    nasa_id: str
    title: str
    description: tuple[str, ...]  # paragrafos, ja sem HTML
    created: date | None
    credit: str
    center: str
    keywords: tuple[str, ...]
    thumbnail: str | None
    renditions: tuple[
        Rendition, ...
    ]  # versoes da imagem, da mais estreita para a mais larga
    original: str | None

    @property
    def details_url(self):
        return DETAILS_URL.format(quote(self.nasa_id))

    @property
    def shown(self):
        """A versao mostrada na pagina: a maior que nao passa de SHOWN_WIDTH."""
        fitting = [r for r in self.renditions if r.width and r.width <= SHOWN_WIDTH]
        if fitting:
            return fitting[-1]
        if self.renditions:
            return self.renditions[0]
        url = self.thumbnail or self.original
        return Rendition(url) if url else None

    @property
    def srcset(self):
        """Versoes com largura conhecida, para o navegador escolher a que serve a tela."""
        return ", ".join(
            f"{r.url} {r.width}w"
            for r in self.renditions
            if r.width and r.width <= SHOWN_WIDTH
        )


@dataclass(frozen=True)
class SearchPage:
    images: tuple[NasaImage, ...]
    total: int
    page: int

    @property
    def pages(self):
        return max(1, ceil(min(self.total, MAX_RESULTS) / PAGE_SIZE))


def search(query, *, year_start=None, year_end=None, page=1):
    params = {"q": query, "media_type": "image", "page": page, "page_size": PAGE_SIZE}
    if year_start:
        params["year_start"] = year_start
    if year_end:
        params["year_end"] = year_end
    collection = _get(params)
    try:
        total = int(collection.get("metadata", {}).get("total_hits", 0))
    except (TypeError, ValueError):
        total = 0
    images = tuple(filter(None, map(_image, collection.get("items") or [])))
    return SearchPage(images, total, page)


def get_image(nasa_id):
    """A imagem com esse codigo, ou None se o acervo nao tem uma imagem com ele."""
    for image in filter(
        None, map(_image, _get({"nasa_id": nasa_id}).get("items") or [])
    ):
        if image.nasa_id == nasa_id:
            return image
    return None


def _get(params):
    url = f"{API_URL}?{urlencode(params)}"
    key = "nasa-images:" + hashlib.sha256(url.encode()).hexdigest()
    collection = cache.get(key)
    if collection is None:
        collection = _fetch(url)
        cache.set(key, collection, CACHE_SECONDS)
    return collection


def _fetch(url):
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "iZone"}
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            data = json.load(response)
    except HTTPError as error:
        # 400: a API recusou a pesquisa (por exemplo, uma pagina alem do limite de resultados)
        raise NasaImagesError(REFUSED if error.code == 400 else UNAVAILABLE) from error
    except (
        OSError,
        HTTPException,
        ValueError,
    ) as error:  # rede, tempo esgotado ou JSON invalido
        raise NasaImagesError(UNAVAILABLE) from error
    collection = data.get("collection") if isinstance(data, dict) else None
    if not isinstance(collection, dict):
        raise NasaImagesError(UNAVAILABLE)
    return collection


def _image(item):
    try:
        data = item["data"][0]
    except (KeyError, IndexError, TypeError):
        return None
    nasa_id, title = _text(data.get("nasa_id")), _text(data.get("title"))
    if data.get("media_type") != "image" or not nasa_id or not title:
        return None

    links = [
        link
        for link in item.get("links") or []
        if isinstance(link, dict)
        and link.get("render") == "image"
        and _is_web(link.get("href"))
    ]
    renditions = sorted(
        (
            Rendition(
                link["href"], _number(link.get("width")), _number(link.get("height"))
            )
            for link in links
            if link.get("rel") == "alternate"
        ),
        key=lambda r: r.width or 0,
    )
    return NasaImage(
        nasa_id=nasa_id,
        title=title,
        description=_paragraphs(data.get("description")),
        created=_date(data.get("date_created")),
        credit=_text(data.get("secondary_creator") or data.get("photographer"))
        or "NASA",
        center=_center(_text(data.get("center"))),
        keywords=_keywords(data.get("keywords")),
        thumbnail=next(
            (link["href"] for link in links if link.get("rel") == "preview"), None
        ),
        renditions=tuple(renditions),
        original=next(
            (link["href"] for link in links if link.get("rel") == "canonical"), None
        ),
    )


def _text(value):
    """As descricoes trazem tags (<a>, <b>) e entidades (&quot;); a pagina mostra so o texto."""
    if not isinstance(value, str):
        return ""
    return " ".join(html.unescape(strip_tags(value)).split())


def _paragraphs(value):
    if not isinstance(value, str):
        return ()
    return tuple(
        filter(None, map(_text, re.split(r"\n\s*\n|<br\s*/?>\s*<br\s*/?>", value)))
    )


def _center(code):
    name = CENTERS.get(code.upper())
    return f"{name} ({code})" if name else code


def _keywords(value):
    keywords, seen = [], set()
    for keyword in value if isinstance(value, list) else []:
        keyword = _text(keyword)
        if keyword and keyword.casefold() not in seen:
            seen.add(keyword.casefold())
            keywords.append(keyword)
    return tuple(keywords[:10])


def _date(value):
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def _number(value):
    return value if isinstance(value, int) and value > 0 else None


def _is_web(url):
    # os enderecos vao para src e href; so http e https, nunca javascript: ou data:
    return isinstance(url, str) and urlsplit(url).scheme in ("http", "https")
