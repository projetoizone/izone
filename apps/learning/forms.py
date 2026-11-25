from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

FIRST_YEAR = 1920  # as imagens mais antigas do acervo da NASA sao dos anos 1920


class YearInput(forms.TextInput):
    # campo de texto com teclado numerico: o type="number" muda o valor com a roda do mouse
    # e as setas, e alguns leitores de tela o anunciam mal
    def __init__(self):
        super().__init__(
            attrs={"inputmode": "numeric", "autocomplete": "off", "size": 6}
        )


class SpaceImageSearchForm(forms.Form):
    q = forms.CharField(
        label="Assunto, em inglês",
        max_length=100,
        help_text="A NASA descreve as imagens em inglês. Por exemplo: nebula, galaxy, Saturn.",
        widget=forms.TextInput(attrs={"type": "search"}),
        error_messages={"required": "Digite um assunto para pesquisar."},
    )
    ano_inicio = forms.IntegerField(label="De", required=False, widget=YearInput())
    ano_fim = forms.IntegerField(label="Até", required=False, widget=YearInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        this_year = timezone.localdate().year
        message = f"Digite um ano entre {FIRST_YEAR} e {this_year}."
        for name in ("ano_inicio", "ano_fim"):
            field = self.fields[name]
            field.error_messages["invalid"] = message
            field.validators += [
                MinValueValidator(FIRST_YEAR, message),
                MaxValueValidator(this_year, message),
            ]

    def clean(self):
        cleaned_data = super().clean()
        start, end = cleaned_data.get("ano_inicio"), cleaned_data.get("ano_fim")
        if start and end and start > end:
            self.add_error("ano_fim", "O ano final não pode ser antes do inicial.")
        return cleaned_data


class WikipediaSearchForm(forms.Form):
    q = forms.CharField(
        label="Assunto",
        max_length=300,  # a pesquisa da Wikipedia recusa textos mais longos
        help_text="Uma ou mais palavras. Por exemplo: fotossíntese, Machado de Assis, Revolução Francesa.",
        widget=forms.TextInput(attrs={"type": "search"}),
        error_messages={
            "required": "Digite um assunto para pesquisar.",
            "max_length": "Use no máximo 300 caracteres.",
        },
    )
