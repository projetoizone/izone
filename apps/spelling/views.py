from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from . import dicionario_aberto


class GameView(TemplateView):
    template_name = "spelling/index.html"


@require_GET
def challenge(request):
    """Sorteia a palavra da próxima rodada do jogo."""
    try:
        return JsonResponse(dicionario_aberto.challenge())
    except dicionario_aberto.DicionarioError as error:
        return JsonResponse({"error": str(error)}, status=502)
