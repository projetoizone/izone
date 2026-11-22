from .enums import Contrast, FontSize, Theme


class InvalidPreference(ValueError):
    pass


def clean_preferences(data):
    """Validate the theme, contrast and font_size present in data.

    Returns a dict with only the fields that were sent, ready to be set on
    UserPreferences. Raises InvalidPreference with a message for the user.
    """
    cleaned = {}

    if theme := data.get("theme"):
        if theme not in Theme.values:
            *others, last = (f"'{value}'" for value in Theme.values)
            raise InvalidPreference(
                f"Opção de tema inválida. Temas disponíveis: {', '.join(others)} e {last}."
            )
        cleaned["theme"] = theme

    if contrast := data.get("contrast"):
        if contrast not in Contrast.values:
            raise InvalidPreference(
                "Opção de contraste inválida. Contrastes disponíveis: 'normal' e 'high'."
            )
        cleaned["contrast"] = contrast

    if font_size := data.get("font_size"):
        try:
            font_size = float(font_size)
        except (ValueError, TypeError):
            raise InvalidPreference("Tamanho de fonte inválido.")

        if font_size not in FontSize.values:
            raise InvalidPreference("Tamanho de fonte não permitido.")
        cleaned["font_size"] = font_size

    return cleaned


def update_preferences(preferences, cleaned):
    for field, value in cleaned.items():
        setattr(preferences, field, value)

    if cleaned:
        preferences.save(update_fields=list(cleaned))
