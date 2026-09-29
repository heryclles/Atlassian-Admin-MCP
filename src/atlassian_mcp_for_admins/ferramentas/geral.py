"""Conexao e chamadas genericas para qualquer endpoint sem ferramenta propria."""
from typing import Any, Optional

from ..apis import obter
from ._comum import escrita, leitura, limpar

METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}


@leitura
def atlassian_conexao() -> dict:
    """Mostra o site configurado, o usuario autenticado e o cloudId."""
    at = obter()
    eu = at.jira.eu()
    return {"site": at.http.url, "usuario": eu.get("displayName"), "email": eu.get("emailAddress"),
            "account_id": eu.get("accountId"), "cloud_id": at.http.cloud_id()}


@leitura
def atlassian_get(caminho: str, params: Optional[dict] = None) -> Any:
    """GET em qualquer endpoint Atlassian que nao tenha ferramenta propria.

    caminho: relativo ao site ("/rest/api/3/...", "/rest/servicedeskapi/...") ou URL
    completa em https://api.atlassian.com/... ; "{cloudId}" e substituido.
    params: query string. Nao pagina sozinho: passe startAt/start/nextPageToken.
    """
    return limpar(obter().http.get(caminho, params=params))


@escrita
def atlassian_requisicao(metodo: str, caminho: str, corpo: Optional[Any] = None,
                         params: Optional[dict] = None) -> Any:
    """POST, PUT, PATCH ou DELETE em qualquer endpoint Atlassian sem ferramenta propria.

    Mesmas regras de caminho do atlassian_get. corpo: JSON enviado como esta.
    """
    metodo = metodo.upper()
    if metodo not in METODOS_ESCRITA:
        raise ValueError(f"metodo deve ser um de {sorted(METODOS_ESCRITA)}; para GET use atlassian_get")
    return limpar(obter().http.requisitar(metodo, caminho, json=corpo, params=params))


FERRAMENTAS = [atlassian_conexao, atlassian_get, atlassian_requisicao]
