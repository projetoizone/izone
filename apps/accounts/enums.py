from django.db import models
from django.utils.translation import gettext_lazy as _


class Theme(models.TextChoices):
    LIGHT = "light", _("Light Mode")
    DARK = "dark", _("Dark Mode")


class Contrast(models.TextChoices):
    NORMAL = "normal", _("Normal Contrast")
    HIGH = "high", _("High Contrast")


class FontSize(float, models.Choices):
    FS100 = 1.0, _("Font Size 100%")
    FS110 = 1.1, _("Font Size 110%")
    FS120 = 1.2, _("Font Size 120%")
    FS130 = 1.3, _("Font Size 130%")
    FS140 = 1.4, _("Font Size 140%")
    FS150 = 1.5, _("Font Size 150%")
    FS160 = 1.6, _("Font Size 160%")
    FS170 = 1.7, _("Font Size 170%")
    FS180 = 1.8, _("Font Size 180%")
    FS190 = 1.9, _("Font Size 190%")
    FS200 = 2.0, _("Font Size 200%")
    FS400 = 4.0, _("Font Size 400%")
