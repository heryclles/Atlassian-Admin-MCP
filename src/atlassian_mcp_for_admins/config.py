"""Credenciais do site Atlassian.

Ordem de leitura:
  1. Variaveis de ambiente JIRA_URL, JIRA_EMAIL e JIRA_TOKEN. Instalado como plugin,
     o Claude Code as preenche com o userConfig do plugin (token no Keychain).
  2. Arquivo .env na raiz do repositorio, para desenvolvimento e testes locais.
"""
import os
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[2]
_ARQUIVO_ENV = dotenv_values(RAIZ / ".env") if (RAIZ / ".env").exists() else {}


def _ler(nome: str) -> str:
    valor = (os.getenv(nome) or "").strip()
    # userConfig nao preenchido pode chegar como o texto "${user_config.x}" sem expandir
    if not valor or valor.startswith("${"):
        valor = (_ARQUIVO_ENV.get(nome) or "").strip()
    return valor


URL = _ler("JIRA_URL").rstrip("/")
EMAIL = _ler("JIRA_EMAIL")
TOKEN = _ler("JIRA_TOKEN")


def comando_configurar() -> str:
    """O /plugin configure exato desta instalacao. O Claude Code passa ao servidor o
    CLAUDE_PLUGIN_ROOT, que tem a forma .../plugins/cache/<marketplace>/<plugin>/<versao>."""
    partes = Path(os.getenv("CLAUDE_PLUGIN_ROOT") or "").parts
    if "cache" in partes and len(partes) > partes.index("cache") + 2:
        i = partes.index("cache")
        return f"/plugin configure {partes[i + 2]}@{partes[i + 1]}"
    return "/plugin configure atlassian-admin@<marketplace>"


def validar() -> None:
    faltando = [n for n, v in (("JIRA_URL", URL), ("JIRA_EMAIL", EMAIL), ("JIRA_TOKEN", TOKEN)) if not v]
    if faltando:
        raise RuntimeError(
            "Credenciais ausentes: " + ", ".join(faltando)
            + f". Preencha as credenciais do plugin com {comando_configurar()} no Claude Code"
            " e reconecte o servidor (/mcp). Em desenvolvimento, use o .env na raiz do repositorio.")
    if not URL.startswith("https://"):
        raise RuntimeError("JIRA_URL deve comecar com https:// (ex.: https://empresa.atlassian.net)")
