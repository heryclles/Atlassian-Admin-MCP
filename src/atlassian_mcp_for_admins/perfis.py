"""Perfis de site: varios sites Atlassian salvos, um deles ativo.

Os dados de cada perfil (nome, URL, e-mail) ficam em ~/.config/atlassian-admin/sites.json,
com permissao 600. O API token fica no cofre do sistema (Keychain no macOS, Credential
Manager no Windows, Secret Service no Linux) pela biblioteca keyring, nunca no arquivo.
O servidor le o perfil ativo a cada chamada, entao trocar de perfil vale na hora.
"""
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

PASTA = Path.home() / ".config" / "atlassian-admin"
ARQUIVO = PASTA / "sites.json"
SERVICO = "atlassian-admin"


def _cofre():
    """Modulo keyring, importado so quando precisa (os testes trocam por um falso)."""
    try:
        import keyring
    except ImportError as erro:  # pragma: no cover - dependencia do projeto
        raise RuntimeError("A biblioteca keyring nao esta instalada no ambiente do plugin.") from erro
    return keyring


def _vazio() -> dict:
    return {"ativo": None, "sites": {}}


def carregar() -> dict:
    if not ARQUIVO.is_file():
        return _vazio()
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except ValueError as erro:
        raise RuntimeError(f"{ARQUIVO} esta corrompido: {erro}") from erro
    dados.setdefault("ativo", None)
    dados.setdefault("sites", {})
    return dados


def _gravar(dados: dict) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(dir=PASTA, prefix=".sites-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        os.chmod(temporario, 0o600)
        os.replace(temporario, ARQUIVO)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise


def normalizar_url(url: str) -> str:
    """So esquema e host: https://empresa.atlassian.net (sem caminho nem barra final)."""
    partes = urlparse((url or "").strip())
    if partes.scheme != "https" or not partes.hostname:
        raise ValueError("A URL do site deve comecar com https:// (ex.: https://empresa.atlassian.net)")
    return f"https://{partes.netloc.lower()}"


def _slug(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-") or "site"


def _validar(nome: str, url: str, email: str) -> tuple:
    nome, email = (nome or "").strip(), (email or "").strip()
    if not nome:
        raise ValueError("Informe um nome para o perfil")
    if "@" not in email:
        raise ValueError("Informe o e-mail da conta dona do API token")
    return nome, normalizar_url(url), email


def token(perfil_id: str) -> Optional[str]:
    return _cofre().get_password(SERVICO, perfil_id)


def salvar_site(nome: str, url: str, email: str, novo_token: Optional[str] = None,
                perfil_id: Optional[str] = None) -> str:
    """Cria (sem perfil_id) ou altera um perfil. Token vazio na alteracao mantem o atual."""
    nome, url, email = _validar(nome, url, email)
    dados = carregar()
    if perfil_id is None:
        base = _slug(nome)
        perfil_id, n = base, 2
        while perfil_id in dados["sites"]:
            perfil_id, n = f"{base}-{n}", n + 1
        if not (novo_token or "").strip():
            raise ValueError("Informe o API token do perfil novo")
    elif perfil_id not in dados["sites"]:
        raise LookupError(f"Perfil {perfil_id} nao existe")
    if (novo_token or "").strip():
        _cofre().set_password(SERVICO, perfil_id, novo_token.strip())
    dados["sites"][perfil_id] = {"nome": nome, "url": url, "email": email}
    if not dados["ativo"]:
        dados["ativo"] = perfil_id
    _gravar(dados)
    return perfil_id


def ativar(perfil_id: str) -> None:
    dados = carregar()
    if perfil_id not in dados["sites"]:
        raise LookupError(f"Perfil {perfil_id} nao existe")
    dados["ativo"] = perfil_id
    _gravar(dados)


def remover(perfil_id: str) -> None:
    dados = carregar()
    if dados["sites"].pop(perfil_id, None) is None:
        raise LookupError(f"Perfil {perfil_id} nao existe")
    if dados["ativo"] == perfil_id:
        dados["ativo"] = next(iter(dados["sites"]), None)
    _gravar(dados)
    try:
        _cofre().delete_password(SERVICO, perfil_id)
    except Exception:  # token ja ausente no cofre: nada a apagar
        pass


def ativo() -> Optional[dict]:
    """Perfil ativo com o token: {id, nome, url, email, token}, ou None."""
    dados = carregar()
    perfil_id = dados.get("ativo")
    perfil = dados["sites"].get(perfil_id) if perfil_id else None
    if not perfil:
        return None
    return {"id": perfil_id, **perfil, "token": token(perfil_id) or ""}
