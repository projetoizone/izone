# izone

## Testes

```sh
uv run coverage run manage.py test   # roda os testes medindo a cobertura
uv run coverage report               # resumo no terminal
uv run coverage html                 # relatório completo em htmlcov/index.html
```

O CI (`.github/workflows/ci.yml`) roda esses comandos em cada pull request e em cada push na `main`. O resumo da cobertura aparece na página de cada execução, e o relatório completo fica disponível para download como `coverage-html`.
