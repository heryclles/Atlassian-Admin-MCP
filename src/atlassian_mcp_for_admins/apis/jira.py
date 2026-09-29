"""Jira Cloud platform REST API v3 (/rest/api/3)."""
from typing import Any, Iterable, Iterator, List, Optional, Union

from ..nucleo.http import JSON, ClienteHttp, ErroAtlassian


def _sem_vazios(**kw) -> dict:
    """Parametros e corpos so com o que foi informado (0 e False ficam)."""
    return {k: v for k, v in kw.items() if v is not None and v != "" and v != []}


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

    # ------------------------------------------------------ tipos de issue
    def tipos_issue(self, projeto_id: Optional[str] = None) -> List[JSON]:
        if projeto_id:
            return self.http.get("/rest/api/3/issuetype/project", params={"projectId": projeto_id})
        return self.http.get("/rest/api/3/issuetype")

    # --------------------------------------------------------------- telas
    def telas_pagina(self, filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                     escopos: Optional[List[str]] = None, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/screens", params=_sem_vazios(
            startAt=inicio, maxResults=limite, queryString=filtro, id=ids, scope=escopos))

    def tela(self, tela_id: str) -> JSON:
        valores = self.telas_pagina(ids=[tela_id], limite=1).get("values") or []
        if not valores:
            raise LookupError(f"Tela {tela_id} nao encontrada")
        return valores[0]

    def criar_tela(self, nome: str, descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/screens", json=_sem_vazios(name=nome, description=descricao))

    def salvar_tela(self, tela_id: str, nome: Optional[str] = None, descricao: Optional[str] = None) -> JSON:
        return self.http.put(f"/rest/api/3/screens/{tela_id}", json=_sem_vazios(name=nome, description=descricao))

    def excluir_tela(self, tela_id: str) -> None:
        self.http.delete(f"/rest/api/3/screens/{tela_id}")

    def campos_disponiveis_tela(self, tela_id: str) -> List[JSON]:
        return self.http.get(f"/rest/api/3/screens/{tela_id}/availableFields")

    def telas_do_campo(self, campo_id: str, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get(f"/rest/api/3/field/{campo_id}/screens",
                             params={"startAt": inicio, "maxResults": limite, "expand": "tab"})

    # ---------------------------------------------------------------- abas
    def abas(self, tela_id: str, projeto: Optional[str] = None) -> List[JSON]:
        return self.http.get(f"/rest/api/3/screens/{tela_id}/tabs", params=_sem_vazios(projectKey=projeto))

    def criar_aba(self, tela_id: str, nome: str) -> JSON:
        return self.http.post(f"/rest/api/3/screens/{tela_id}/tabs", json={"name": nome})

    def salvar_aba(self, tela_id: str, aba_id: str, nome: str) -> JSON:
        return self.http.put(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}", json={"name": nome})

    def excluir_aba(self, tela_id: str, aba_id: str) -> None:
        self.http.delete(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}")

    def mover_aba(self, tela_id: str, aba_id: str, posicao: int) -> None:
        self.http.post(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}/move/{posicao}")

    # ------------------------------------------------------ campos da aba
    def campos_aba(self, tela_id: str, aba_id: str, projeto: Optional[str] = None) -> List[JSON]:
        return self.http.get(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}/fields",
                             params=_sem_vazios(projectKey=projeto))

    def adicionar_campo_aba(self, tela_id: str, aba_id: str, campo_id: str) -> JSON:
        return self.http.post(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}/fields", json={"fieldId": campo_id})

    def remover_campo_aba(self, tela_id: str, aba_id: str, campo_id: str) -> None:
        self.http.delete(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}/fields/{campo_id}")

    def mover_campo_aba(self, tela_id: str, aba_id: str, campo_id: str,
                        depois_de: Optional[str] = None, posicao: Optional[str] = None) -> None:
        self.http.post(f"/rest/api/3/screens/{tela_id}/tabs/{aba_id}/fields/{campo_id}/move",
                       json=_sem_vazios(after=depois_de, position=posicao))

    # ---------------------------------------------------- esquemas de tela
    def esquemas_tela_pagina(self, filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                             expand: Optional[str] = None, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/screenscheme", params=_sem_vazios(
            startAt=inicio, maxResults=limite, queryString=filtro, id=ids, expand=expand))

    def criar_esquema_tela(self, nome: str, telas: dict, descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/screenscheme",
                              json=_sem_vazios(name=nome, description=descricao, screens=telas))

    def salvar_esquema_tela(self, esquema_id: str, nome: Optional[str] = None, descricao: Optional[str] = None,
                            telas: Optional[dict] = None) -> None:
        self.http.put(f"/rest/api/3/screenscheme/{esquema_id}",
                      json=_sem_vazios(name=nome, description=descricao, screens=telas))

    def excluir_esquema_tela(self, esquema_id: str) -> None:
        self.http.delete(f"/rest/api/3/screenscheme/{esquema_id}")

    # ------------------------- esquemas de tela por tipo de issue (itss)
    def esquemas_tipo_tela_pagina(self, filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                                  expand: Optional[str] = None, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/issuetypescreenscheme", params=_sem_vazios(
            startAt=inicio, maxResults=limite, queryString=filtro, id=ids, expand=expand))

    def itens_tipo_tela_pagina(self, esquema_ids: Optional[List[str]] = None,
                               inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/issuetypescreenscheme/mapping", params=_sem_vazios(
            startAt=inicio, maxResults=limite, issueTypeScreenSchemeId=esquema_ids))

    def tipo_tela_projetos_pagina(self, projeto_ids: List[str], inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/issuetypescreenscheme/project",
                             params={"startAt": inicio, "maxResults": limite, "projectId": projeto_ids})

    def projetos_esquema_tipo_tela_pagina(self, esquema_id: str, filtro: Optional[str] = None,
                                          inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get(f"/rest/api/3/issuetypescreenscheme/{esquema_id}/project",
                             params=_sem_vazios(startAt=inicio, maxResults=limite, query=filtro))

    def criar_esquema_tipo_tela(self, nome: str, itens: List[dict], descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/issuetypescreenscheme",
                              json=_sem_vazios(name=nome, description=descricao, issueTypeMappings=itens))

    def salvar_esquema_tipo_tela(self, esquema_id: str, nome: Optional[str] = None,
                                 descricao: Optional[str] = None) -> None:
        self.http.put(f"/rest/api/3/issuetypescreenscheme/{esquema_id}",
                      json=_sem_vazios(name=nome, description=descricao))

    def excluir_esquema_tipo_tela(self, esquema_id: str) -> None:
        self.http.delete(f"/rest/api/3/issuetypescreenscheme/{esquema_id}")

    def adicionar_itens_tipo_tela(self, esquema_id: str, itens: List[dict]) -> None:
        self.http.put(f"/rest/api/3/issuetypescreenscheme/{esquema_id}/mapping", json={"issueTypeMappings": itens})

    def salvar_padrao_tipo_tela(self, esquema_id: str, esquema_tela_id: str) -> None:
        self.http.put(f"/rest/api/3/issuetypescreenscheme/{esquema_id}/mapping/default",
                      json={"screenSchemeId": esquema_tela_id})

    def remover_itens_tipo_tela(self, esquema_id: str, tipo_issue_ids: List[str]) -> None:
        self.http.post(f"/rest/api/3/issuetypescreenscheme/{esquema_id}/mapping/remove",
                       json={"issueTypeIds": tipo_issue_ids})

    def associar_esquema_tipo_tela(self, esquema_id: str, projeto_id: str) -> None:
        self.http.put("/rest/api/3/issuetypescreenscheme/project",
                      json={"issueTypeScreenSchemeId": esquema_id, "projectId": projeto_id})

    # --------------------------------------------------------- prioridades
    def prioridades_pagina(self, ids: Optional[List[str]] = None, projeto_ids: Optional[List[str]] = None,
                           filtro: Optional[str] = None, expand: Optional[str] = None,
                           inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/priority/search", params=_sem_vazios(
            startAt=inicio, maxResults=limite, id=ids, projectId=projeto_ids, priorityName=filtro, expand=expand))

    def criar_prioridade(self, nome: str, cor: str, avatar_id: int, descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/priority", json=_sem_vazios(
            name=nome, statusColor=cor, avatarId=avatar_id, description=descricao))

    def salvar_prioridade(self, prioridade_id: str, nome: Optional[str] = None, cor: Optional[str] = None,
                          avatar_id: Optional[int] = None, descricao: Optional[str] = None) -> None:
        self.http.put(f"/rest/api/3/priority/{prioridade_id}", json=_sem_vazios(
            name=nome, statusColor=cor, avatarId=avatar_id, description=descricao))

    def excluir_prioridade(self, prioridade_id: str) -> Optional[JSON]:
        """Assincrono: a API responde 303 para a tarefa, que o requests segue com GET."""
        return self.http.delete(f"/rest/api/3/priority/{prioridade_id}")

    def mover_prioridades(self, ids: List[str], depois_de: Optional[str] = None,
                          posicao: Optional[str] = None) -> None:
        self.http.put("/rest/api/3/priority/move", json=_sem_vazios(ids=ids, after=depois_de, position=posicao))

    def salvar_padrao_prioridade(self, prioridade_id: Optional[str]) -> None:
        self.http.put("/rest/api/3/priority/default", json={"id": prioridade_id})

    # ------------------------------------------- esquemas de prioridade
    def esquemas_prioridade_pagina(self, filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                                   prioridade_ids: Optional[List[str]] = None, somente_padrao: bool = False,
                                   expand: Optional[str] = None, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/priorityscheme", params=_sem_vazios(
            startAt=inicio, maxResults=limite, schemeName=filtro, schemeId=ids, priorityId=prioridade_ids,
            onlyDefault="true" if somente_padrao else None, expand=expand))

    def prioridades_esquema_pagina(self, esquema_id: str, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get(f"/rest/api/3/priorityscheme/{esquema_id}/priorities",
                             params={"startAt": inicio, "maxResults": limite})

    def projetos_esquema_prioridade_pagina(self, esquema_id: str, filtro: Optional[str] = None,
                                           projeto_ids: Optional[List[str]] = None,
                                           inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get(f"/rest/api/3/priorityscheme/{esquema_id}/projects", params=_sem_vazios(
            startAt=inicio, maxResults=limite, query=filtro, projectId=projeto_ids))

    def prioridades_mapear_pagina(self, esquema_id: str, adicionar_prioridades: Optional[List[str]] = None,
                                  remover_prioridades: Optional[List[str]] = None,
                                  adicionar_projetos: Optional[List[str]] = None,
                                  inicio: int = 0, limite: int = 50) -> JSON:
        """POST sem efeito: so calcula quais prioridades a mudanca exigiria mapear."""
        return self.http.post("/rest/api/3/priorityscheme/mappings", json=_sem_vazios(
            schemeId=int(esquema_id), startAt=inicio, maxResults=limite,
            priorities=_sem_vazios(add=_inteiros(adicionar_prioridades),
                                   remove=_inteiros(remover_prioridades)) or None,
            projects=_sem_vazios(add=_inteiros(adicionar_projetos)) or None))

    def criar_esquema_prioridade(self, nome: str, prioridade_ids: List[str], prioridade_padrao_id: str,
                                 descricao: Optional[str] = None, projeto_ids: Optional[List[str]] = None,
                                 mapeamentos: Optional[dict] = None) -> JSON:
        return self.http.post("/rest/api/3/priorityscheme", json=_sem_vazios(
            name=nome, description=descricao, priorityIds=_inteiros(prioridade_ids),
            defaultPriorityId=int(prioridade_padrao_id), projectIds=_inteiros(projeto_ids),
            mappings=_mapeamentos(mapeamentos)))

    def salvar_esquema_prioridade(self, esquema_id: str, nome: Optional[str] = None,
                                  descricao: Optional[str] = None, prioridade_padrao_id: Optional[str] = None,
                                  adicionar_prioridades: Optional[List[str]] = None,
                                  remover_prioridades: Optional[List[str]] = None,
                                  adicionar_projetos: Optional[List[str]] = None,
                                  remover_projetos: Optional[List[str]] = None,
                                  mapeamentos: Optional[dict] = None) -> JSON:
        def mudanca(adicionar, remover):
            return _sem_vazios(add={"ids": _inteiros(adicionar)} if adicionar else None,
                               remove={"ids": _inteiros(remover)} if remover else None) or None
        return self.http.put(f"/rest/api/3/priorityscheme/{esquema_id}", json=_sem_vazios(
            name=nome, description=descricao,
            defaultPriorityId=int(prioridade_padrao_id) if prioridade_padrao_id else None,
            priorities=mudanca(adicionar_prioridades, remover_prioridades),
            projects=mudanca(adicionar_projetos, remover_projetos),
            mappings=_mapeamentos(mapeamentos)))

    def excluir_esquema_prioridade(self, esquema_id: str) -> None:
        self.http.delete(f"/rest/api/3/priorityscheme/{esquema_id}")

    # ---------------------------------------- configuracoes de campo
    def configs_campo_pagina(self, filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                             somente_padrao: bool = False, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/fieldconfiguration", params=_sem_vazios(
            startAt=inicio, maxResults=limite, query=filtro, id=ids,
            isDefault="true" if somente_padrao else None))

    def criar_config_campo(self, nome: str, descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/fieldconfiguration", json=_sem_vazios(name=nome, description=descricao))

    def salvar_config_campo(self, config_id: str, nome: str, descricao: Optional[str] = None) -> None:
        self.http.put(f"/rest/api/3/fieldconfiguration/{config_id}",
                      json=_sem_vazios(name=nome, description=descricao))

    def excluir_config_campo(self, config_id: str) -> None:
        self.http.delete(f"/rest/api/3/fieldconfiguration/{config_id}")

    def campos_config_pagina(self, config_id: str, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get(f"/rest/api/3/fieldconfiguration/{config_id}/fields",
                             params={"startAt": inicio, "maxResults": limite})

    def campos_config(self, config_id: str) -> Iterator[JSON]:
        return self.http.paginar_start_at(f"/rest/api/3/fieldconfiguration/{config_id}/fields", tamanho=200)

    def salvar_campos_config(self, config_id: str, itens: List[dict]) -> None:
        self.http.put(f"/rest/api/3/fieldconfiguration/{config_id}/fields", json={"fieldConfigurationItems": itens})

    # --------------------------------- esquemas de configuracao de campo
    def esquemas_config_pagina(self, ids: Optional[List[str]] = None, inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/fieldconfigurationscheme",
                             params=_sem_vazios(startAt=inicio, maxResults=limite, id=ids))

    def criar_esquema_config(self, nome: str, descricao: Optional[str] = None) -> JSON:
        return self.http.post("/rest/api/3/fieldconfigurationscheme",
                              json=_sem_vazios(name=nome, description=descricao))

    def salvar_esquema_config(self, esquema_id: str, nome: str, descricao: Optional[str] = None) -> None:
        self.http.put(f"/rest/api/3/fieldconfigurationscheme/{esquema_id}",
                      json=_sem_vazios(name=nome, description=descricao))

    def excluir_esquema_config(self, esquema_id: str) -> None:
        self.http.delete(f"/rest/api/3/fieldconfigurationscheme/{esquema_id}")

    def itens_config_pagina(self, esquema_ids: Optional[List[str]] = None, inicio: int = 0,
                            limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/fieldconfigurationscheme/mapping", params=_sem_vazios(
            startAt=inicio, maxResults=limite, fieldConfigurationSchemeId=esquema_ids))

    def adicionar_itens_config(self, esquema_id: str, itens: List[dict]) -> None:
        self.http.put(f"/rest/api/3/fieldconfigurationscheme/{esquema_id}/mapping", json={"mappings": itens})

    def remover_itens_config(self, esquema_id: str, tipo_issue_ids: List[str]) -> None:
        self.http.post(f"/rest/api/3/fieldconfigurationscheme/{esquema_id}/mapping/delete",
                       json={"issueTypeIds": tipo_issue_ids})

    def config_projetos_pagina(self, projeto_ids: List[str], inicio: int = 0, limite: int = 50) -> JSON:
        return self.http.get("/rest/api/3/fieldconfigurationscheme/project",
                             params={"startAt": inicio, "maxResults": limite, "projectId": projeto_ids})

    def associar_esquema_config(self, esquema_id: Optional[str], projeto_id: str) -> None:
        """esquema_id None associa o esquema padrao do site."""
        self.http.put("/rest/api/3/fieldconfigurationscheme/project",
                      json={"fieldConfigurationSchemeId": esquema_id, "projectId": projeto_id})

    # ----------------------------- esquemas de campos (API nova, em beta)
    def _esquemas_campos(self, metodo: str, caminho: str = "", **kw) -> Any:
        """/rest/api/3/config/fieldschemes. Com a funcionalidade desligada no site, a API
        responde 404 sem corpo; vira LookupError com o motivo provavel."""
        try:
            return self.http.requisitar(metodo, f"/rest/api/3/config/fieldschemes{caminho}", **kw)
        except ErroAtlassian as e:
            if e.status == 404 and not e.corpo:
                raise LookupError(
                    "HTTP 404 sem corpo em /config/fieldschemes: a API de esquemas de campos (beta) "
                    "esta desligada neste site, ou o id informado nao existe.") from e
            raise

    def esquemas_campos_pagina(self, filtro: Optional[str] = None, projeto_ids: Optional[List[str]] = None,
                               inicio: int = 0, limite: int = 50) -> JSON:
        return self._esquemas_campos("GET", params=_sem_vazios(
            startAt=inicio, maxResults=limite, query=filtro, projectId=projeto_ids))

    def esquema_campos(self, esquema_id: str) -> JSON:
        return self._esquemas_campos("GET", f"/{esquema_id}")

    def criar_esquema_campos(self, nome: str, descricao: Optional[str] = None) -> JSON:
        return self._esquemas_campos("POST", json=_sem_vazios(name=nome, description=descricao))

    def copiar_esquema_campos(self, esquema_id: str, nome: str, descricao: Optional[str] = None) -> JSON:
        return self._esquemas_campos("POST", f"/{esquema_id}/clone", json=_sem_vazios(name=nome, description=descricao))

    def salvar_esquema_campos(self, esquema_id: str, nome: Optional[str] = None,
                              descricao: Optional[str] = None) -> JSON:
        return self._esquemas_campos("PUT", f"/{esquema_id}", json=_sem_vazios(name=nome, description=descricao))

    def excluir_esquema_campos(self, esquema_id: str) -> JSON:
        return self._esquemas_campos("DELETE", f"/{esquema_id}")

    def campos_esquema_pagina(self, esquema_id: str, campo_ids: Optional[List[str]] = None,
                              inicio: int = 0, limite: int = 50) -> JSON:
        return self._esquemas_campos("GET", f"/{esquema_id}/fields", params=_sem_vazios(
            startAt=inicio, maxResults=limite, fieldId=campo_ids))

    def projetos_esquema_campos_pagina(self, esquema_id: str, projeto_ids: Optional[List[str]] = None,
                                       inicio: int = 0, limite: int = 50) -> JSON:
        return self._esquemas_campos("GET", f"/{esquema_id}/projects", params=_sem_vazios(
            startAt=inicio, maxResults=limite, projectId=projeto_ids))

    def adicionar_campos_esquema(self, campos: dict) -> Optional[JSON]:
        """{campo: [{"schemeIds": [...], "restrictedToWorkTypes": [...]}]}"""
        return self._esquemas_campos("PUT", "/fields", json=_ids_inteiros(campos))

    def remover_campos_esquema(self, campos: dict) -> Optional[JSON]:
        """{campo: {"schemeIds": [...]}}"""
        return self._esquemas_campos("DELETE", "/fields", json=_ids_inteiros(campos))

    def salvar_parametros_campos(self, campos: dict) -> Optional[JSON]:
        """{campo: [{"schemeIds", "parameters", "workTypeParameters"}]}"""
        return self._esquemas_campos("PUT", "/fields/parameters", json=_ids_inteiros(campos))

    def remover_parametros_campos(self, campos: dict) -> Optional[JSON]:
        """{campo: [{"schemeId", "workTypeIds", "parameters": [nomes]}]}"""
        return self._esquemas_campos("DELETE", "/fields/parameters", json=_ids_inteiros(campos))

    def associar_esquema_campos(self, esquema_id: str, projeto_ids: List[str]) -> Optional[JSON]:
        return self._esquemas_campos("PUT", "/projects",
                                     json={str(esquema_id): {"projectIds": _inteiros(projeto_ids)}})

    # -------------------------------------------------------------- tarefas
    def tarefa(self, tarefa_id: str) -> JSON:
        return self.http.get(f"/rest/api/3/task/{tarefa_id}")


def _inteiros(ids: Optional[Iterable]) -> Optional[List[int]]:
    """Ids de prioridade, projeto e esquema viram inteiros (int64) no corpo."""
    return [int(i) for i in ids] if ids else None


CHAVES_INTEIRAS = {"schemeId", "schemeIds", "workTypeId", "workTypeIds", "restrictedToWorkTypes"}


def _ids_inteiros(dado: Any) -> Any:
    """Corpos da API de esquemas de campos: ids de esquema e de tipo de issue viram inteiros."""
    if isinstance(dado, dict):
        return {k: (int(v) if isinstance(v, str) else [int(i) for i in v] if isinstance(v, list) else v)
                if k in CHAVES_INTEIRAS and v is not None else _ids_inteiros(v) for k, v in dado.items()}
    if isinstance(dado, list):
        return [_ids_inteiros(v) for v in dado]
    return dado


def _mapeamentos(mapeamentos: Optional[dict]) -> Optional[dict]:
    """{"in": {antiga: nova}, "out": {antiga: nova}}: chave texto, valor inteiro."""
    if not mapeamentos:
        return None
    return {lado: {str(k): int(v) for k, v in (pares or {}).items()} for lado, pares in mapeamentos.items()}
