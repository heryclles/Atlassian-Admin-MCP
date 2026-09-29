"""Jira Cloud platform REST API v3 (/rest/api/3)."""
from typing import Iterable, Iterator, List, Optional, Union

from ..nucleo.http import JSON, ClienteHttp


class Jira:
    def __init__(self, http: ClienteHttp):
        self.http = http

    # --------------------------------------------------------------- conta
    def eu(self) -> JSON:
        return self.http.get("/rest/api/3/myself")

    def usuario(self, account_id: str) -> JSON:
        return self.http.get("/rest/api/3/user", params={"accountId": account_id})

    # -------------------------------------------------------------- issues
    def buscar_jql(self, jql: str, campos: Union[str, Iterable[str]] = ("summary", "status", "created"),
                   expand: Optional[Iterable[str]] = None, tamanho: int = 100,
                   maximo: Optional[int] = None) -> Iterator[JSON]:
        """POST /rest/api/3/search/jql, paginado por nextPageToken. campos="*all" traz todos."""
        corpo: JSON = {"jql": jql, "maxResults": tamanho,
                       "fields": ["*all"] if campos == "*all" else list(campos)}
        if expand:
            corpo["expand"] = ",".join(expand)
        contagem = 0
        while True:
            pagina = self.http.post("/rest/api/3/search/jql", json=corpo)
            for issue in pagina.get("issues", []):
                yield issue
                contagem += 1
                if maximo and contagem >= maximo:
                    return
            token = pagina.get("nextPageToken")
            if not token or pagina.get("isLast"):
                return
            corpo["nextPageToken"] = token

    def buscar_pagina(self, jql: str, campos: Union[str, Iterable[str]] = ("summary", "status"),
                      limite: int = 50, token: Optional[str] = None,
                      expand: Optional[Iterable[str]] = None) -> JSON:
        """Uma "pagina" de ate `limite` issues e o token para continuar. Os pedidos a API
        usam maxResults exato para o token devolvido apontar para a issue seguinte."""
        corpo: JSON = {"jql": jql, "fields": ["*all"] if campos == "*all" else list(campos)}
        if expand:
            corpo["expand"] = ",".join(expand)
        issues: list = []
        while len(issues) < limite:
            corpo["maxResults"] = min(100, limite - len(issues))
            if token:
                corpo["nextPageToken"] = token
            pagina = self.http.post("/rest/api/3/search/jql", json=corpo)
            issues += pagina.get("issues", [])
            token = None if pagina.get("isLast") else pagina.get("nextPageToken")
            if not token or not pagina.get("issues"):
                break
        return {"issues": issues, "proximo_token": token}

    def contar_jql(self, jql: str) -> int:
        return self.http.post("/rest/api/3/search/approximate-count", json={"jql": jql})["count"]

    def issue(self, chave: str, campos: Optional[Iterable[str]] = None,
              expand: Optional[Iterable[str]] = None) -> JSON:
        params: dict = {}
        if campos:
            params["fields"] = ",".join(campos)
        if expand:
            params["expand"] = ",".join(expand)
        return self.http.get(f"/rest/api/3/issue/{chave}", params=params)

    def comentarios(self, chave: str, maximo: Optional[int] = None) -> Iterator[JSON]:
        return self.http.paginar_start_at(f"/rest/api/3/issue/{chave}/comment", chave="comments",
                                          params={"orderBy": "-created"}, maximo=maximo)

    def changelog(self, chave: str) -> Iterator[JSON]:
        return self.http.paginar_start_at(f"/rest/api/3/issue/{chave}/changelog")

    # ------------------------------------------------- campos e projetos
    def campos(self) -> List[JSON]:
        return self.http.get("/rest/api/3/field")

    def projetos(self, filtro: Optional[str] = None, tipo: Optional[str] = None,
                 incluir_arquivados: bool = False) -> Iterator[JSON]:
        params: dict = {"expand": "lead"}
        if filtro:
            params["query"] = filtro
        if tipo:
            params["typeKey"] = tipo
        if incluir_arquivados:
            params["status"] = "live,archived"
        return self.http.paginar_start_at("/rest/api/3/project/search", params=params)

    def projeto(self, chave: str) -> JSON:
        return self.http.get(f"/rest/api/3/project/{chave}")

    def grupos_por_id(self, ids: List[str]) -> dict:
        nomes: dict = {}
        for i in range(0, len(ids), 50):
            r = self.http.get("/rest/api/3/group/bulk", params={"groupId": ids[i:i + 50], "maxResults": 50})
            nomes.update({g["groupId"]: g["name"] for g in r.get("values", [])})
        return nomes

    # ----------------------------------------------- status e workflows
    def buscar_status(self, texto: Optional[str] = None, projeto_id: Optional[str] = None) -> Iterator[JSON]:
        """GET /rest/api/3/statuses/search (exige admin do Jira)."""
        params: dict = {}
        if texto:
            params["searchString"] = texto
        if projeto_id:
            params["projectId"] = projeto_id
        return self.http.paginar_start_at("/rest/api/3/statuses/search", params=params, tamanho=200)

    def status_workflows(self, status_id: str) -> List[str]:
        return [w["id"] for w in self.http.paginar_token_aninhado(
            f"/rest/api/3/statuses/{status_id}/workflowUsages", "workflows")]

    def status_projetos(self, status_id: str) -> List[str]:
        return [p["id"] for p in self.http.paginar_token_aninhado(
            f"/rest/api/3/statuses/{status_id}/projectUsages", "projects")]

    def workflows_pagina(self, filtro: Optional[str] = None, inicio: int = 0, limite: int = 50,
                         expand: str = "statuses") -> JSON:
        params: dict = {"startAt": inicio, "maxResults": limite, "expand": expand}
        if filtro:
            params["queryString"] = filtro
        return self.http.get("/rest/api/3/workflow/search", params=params)

    def workflows(self, expand: str = "statuses") -> Iterator[JSON]:
        """GET /rest/api/3/workflow/search. id do workflow = item["id"]["entityId"]."""
        return self.http.paginar_start_at("/rest/api/3/workflow/search", params={"expand": expand}, tamanho=50)

    def workflow_projetos(self, workflow_id: str) -> List[str]:
        return [p["id"] for p in self.http.paginar_token_aninhado(
            f"/rest/api/3/workflow/{workflow_id}/projectUsages", "projects")]

    def workflow_esquemas(self, workflow_id: str) -> List[str]:
        return [e["id"] for e in self.http.paginar_token_aninhado(
            f"/rest/api/3/workflow/{workflow_id}/workflowSchemes", "workflowSchemes")]
