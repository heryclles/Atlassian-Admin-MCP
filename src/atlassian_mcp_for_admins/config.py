"""Credenciais do site Atlassian, lidas de novo a cada chamada (trocar de site vale na hora).

Ordem (vale a primeira fonte completa: URL, e-mail e token):
  1. Variaveis de ambiente JIRA_URL, JIRA_EMAIL e JIRA_TOKEN, completadas pelo .env na
     raiz do repositorio. Instalado como plugin, o Claude Code preenche o ambiente com
     o userConfig do plugin (/plugin configure); o .env do repositorio e para
     desenvolvimento e testes.
  2. Perfil ativo da tela de sites (perfis.py): ~/.config/atlassian-admin/sites.json e
     o token no cofre do sistema. O METODO PADRAO, para quem troca de site.
  3. Arquivo do usuario ~/.config/atlassian-admin/.env, o metodo anterior aos perfis.
     Continua valendo para quem nao tem perfil.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

from . import perfis

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_REPOSITORIO = RAIZ / ".env"
ARQUIVO_USUARIO = Path.home() / ".config" / "atlassian-admin" / ".env"
NOMES = ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN")


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


def _fonte(arquivos: list[dict]) -> dict:
    url, email, token = (ler(n, arquivos) for n in NOMES)
    return {"url": url.rstrip("/"), "email": email, "token": token}


def _completa(c: dict) -> bool:
    return all(c[k] for k in ("url", "email", "token"))


def credenciais(com_repositorio: bool = True) -> dict:
    """{url, email, token, origem} da primeira fonte completa; incompleta se nenhuma for.

    com_repositorio=False ignora o .env do repositorio: e a visao do plugin instalado, que a
    tela de sites mostra mesmo quando aberta de dentro do repositorio.
    """
    repositorio = _carregar(ARQUIVO_REPOSITORIO) if com_repositorio else {}
    usuario = _carregar(ARQUIVO_USUARIO)
    ambiente = _fonte([repositorio])
    if _completa(ambiente):
        origem = "ambiente (userConfig do plugin)" if all(ler(n, []) for n in NOMES) else f"{ARQUIVO_REPOSITORIO}"
        return {**ambiente, "origem": origem}
    perfil = perfis.ativo()
    if perfil and perfil["token"]:
        return {"url": perfil["url"], "email": perfil["email"], "token": perfil["token"],
                "origem": f"perfil {perfil['nome']}"}
    legado = _fonte([repositorio, usuario])
    return {**legado, "origem": str(ARQUIVO_USUARIO) if _completa(legado) else None}


def validar(c: Optional[dict] = None) -> dict:
    c = c or credenciais()
    faltando = [n for n, k in zip(NOMES, ("url", "email", "token")) if not c[k]]
    if faltando:
        raise RuntimeError(
            "Credenciais ausentes: " + ", ".join(faltando) + ". Abra a tela de sites do plugin "
            "(/atlassian-admin:sites) e cadastre o site, ou crie o arquivo "
            f"{ARQUIVO_USUARIO} com JIRA_URL=, JIRA_EMAIL= e JIRA_TOKEN= (secao Credenciais do README).")
    if not c["url"].startswith("https://"):
        raise RuntimeError("JIRA_URL deve comecar com https:// (ex.: https://empresa.atlassian.net)")
    return c
