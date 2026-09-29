"""Credenciais do site Atlassian.

Ordem de leitura (vale o primeiro valor preenchido):
  1. Variaveis de ambiente JIRA_URL, JIRA_EMAIL e JIRA_TOKEN. Instalado como plugin,
     o Claude Code as preenche com o userConfig do plugin (token no Keychain).
  2. Arquivo .env na raiz do repositorio, para desenvolvimento e testes locais (e
     clone carregado direto como plugin, ex. em ~/.claude/skills/).
  3. Arquivo do usuario ~/.config/atlassian-admin/.env: o metodo padrao, igual no CLI
     e na aba Code do Claude Desktop. Fica fora do repositorio e da copia instalada e
     sobrevive a atualizacoes.
"""
import os
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_REPOSITORIO = RAIZ / ".env"
ARQUIVO_USUARIO = Path.home() / ".config" / "atlassian-admin" / ".env"


def _carregar(arquivo: Path) -> dict:
    return dotenv_values(arquivo) if arquivo.is_file() else {}


def ler(nome: str, arquivos: list[dict]) -> str:
    valor = (os.getenv(nome) or "").strip()
    # userConfig nao preenchido chega vazio (default "") ou como "${user_config.x}" sem expandir
    if valor.startswith("${"):
        valor = ""
    for conteudo in arquivos:
        if valor:
            break
        valor = (conteudo.get(nome) or "").strip()
    return valor


_ARQUIVOS = [_carregar(ARQUIVO_REPOSITORIO), _carregar(ARQUIVO_USUARIO)]
URL = ler("JIRA_URL", _ARQUIVOS).rstrip("/")
EMAIL = ler("JIRA_EMAIL", _ARQUIVOS)
TOKEN = ler("JIRA_TOKEN", _ARQUIVOS)


def validar() -> None:
    faltando = [n for n, v in (("JIRA_URL", URL), ("JIRA_EMAIL", EMAIL), ("JIRA_TOKEN", TOKEN)) if not v]
    if faltando:
        raise RuntimeError(
            "Credenciais ausentes: " + ", ".join(faltando)
            + f". Crie o arquivo {ARQUIVO_USUARIO} com as linhas JIRA_URL=, JIRA_EMAIL= e"
            " JIRA_TOKEN= preenchidas (secao Credenciais do README) e abra uma sessao nova.")
    if not URL.startswith("https://"):
        raise RuntimeError("JIRA_URL deve comecar com https:// (ex.: https://empresa.atlassian.net)")
