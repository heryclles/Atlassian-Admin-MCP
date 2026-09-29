"""Uma classe por API Atlassian, sem dependencia do MCP.

    from atlassian_mcp_for_admins.apis import obter
    at = obter()
    at.jira.buscar_jql("project = SUP", maximo=10)
"""
from typing import Optional

from .. import config
from ..nucleo.http import ClienteHttp, ErroAtlassian
from .forms import Forms
from .jira import Jira
from .jsm import Jsm

__all__ = ["Atlassian", "ErroAtlassian", "obter"]


class Atlassian:
    def __init__(self, http: ClienteHttp):
        self.http = http
        self.jira = Jira(http)
        self.jsm = Jsm(http)
        self.forms = Forms(http)


_instancia: Optional[Atlassian] = None


def obter() -> Atlassian:
    global _instancia
    if _instancia is None:
        config.validar()
        _instancia = Atlassian(ClienteHttp(config.URL, config.EMAIL, config.TOKEN))
    return _instancia
