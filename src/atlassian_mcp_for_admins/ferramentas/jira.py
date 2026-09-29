"""Jira: issues, projetos, campos, status e workflows."""
from typing import List, Optional

from ..apis import obter
from ._comum import faixa, leitura, limpar


@leitura
def jira_buscar_issues(jql: str, campos: Optional[List[str]] = None, limite: int = 50,
                       proximo_token: Optional[str] = None, expand: Optional[List[str]] = None) -> dict:
    """Busca issues por JQL e devolve os campos pedidos como a API entrega.

    campos: ids dos campos (padrao ["summary", "status"]); ["*all"] traz todos.
    limite: 1 a 500 issues por chamada. Se a resposta trouxer proximo_token, chame de
    novo com ele para a pagina seguinte.
    expand: ex. ["changelog"], ["renderedFields"].
    """
    lista = campos or ["summary", "status"]
    pagina = obter().jira.buscar_pagina(jql, campos="*all" if lista == ["*all"] else lista,
                                        limite=faixa(limite, 1, 500), token=proximo_token, expand=expand)
    issues = [{"key": i["key"], "id": i["id"], "fields": limpar(i.get("fields", {})),
               **({"changelog": limpar(i["changelog"])} if "changelog" in i else {})} for i in pagina["issues"]]
    return {"retornados": len(issues), "proximo_token": pagina["proximo_token"], "issues": issues}


@leitura
def jira_contar_issues(jql: str) -> dict:
    """Contagem aproximada de issues de uma JQL."""
    return {"total_aproximado": obter().jira.contar_jql(jql)}


@leitura
def jira_obter_issue(chave: str, campos: Optional[List[str]] = None, expand: Optional[List[str]] = None) -> dict:
    """Uma issue pela chave ou id. campos: ids (padrao: todos os navegaveis). expand: ex. ["changelog"]."""
    return limpar(obter().jira.issue(chave, campos=campos, expand=expand))


@leitura
def jira_listar_comentarios(chave: str, limite: int = 50) -> dict:
    """Comentarios de uma issue, do mais recente para o mais antigo (corpo em ADF)."""
    itens = list(obter().jira.comentarios(chave, maximo=faixa(limite, 1, 500)))
    return {"retornados": len(itens), "comentarios": limpar(itens)}


@leitura
def jira_listar_projetos(filtro: Optional[str] = None, tipo: Optional[str] = None,
                         incluir_arquivados: bool = False, limite: int = 300) -> dict:
    """Projetos visiveis. filtro: trecho da chave ou do nome. tipo: service_desk, software, business."""
    itens = list(obter().jira.projetos(filtro=filtro, tipo=tipo, incluir_arquivados=incluir_arquivados))
    return {"total": len(itens), "projetos": limpar(itens[:faixa(limite, 1, 1000)])}


@leitura
def jira_obter_projeto(chave: str) -> dict:
    """Um projeto pela chave ou id, com tipos de issue, componentes e versoes."""
    return limpar(obter().jira.projeto(chave))


@leitura
def jira_listar_campos(filtro: Optional[str] = None) -> dict:
    """Campos do Jira (id, nome, schema). filtro: trecho do nome ou do id, sem diferenciar maiusculas."""
    itens = obter().jira.campos()
    if filtro:
        f = filtro.lower()
        itens = [c for c in itens if f in c.get("name", "").lower() or f in c.get("id", "").lower()]
    campos = [{"id": c["id"], "nome": c.get("name"), "custom": c.get("custom"), "schema": c.get("schema")} for c in itens]
    return {"total": len(campos), "campos": campos}


@leitura
def jira_listar_status(texto: Optional[str] = None, projeto_id: Optional[str] = None, limite: int = 500) -> dict:
    """Status do Jira (exige admin). texto: trecho do nome. projeto_id: status de um projeto team-managed."""
    itens = list(obter().jira.buscar_status(texto=texto, projeto_id=projeto_id))
    return {"total": len(itens), "status": limpar(itens[:faixa(limite, 1, 2000)])}


@leitura
def jira_usos_status(status_id: str) -> dict:
    """Ids dos workflows e dos projetos que usam um status."""
    j = obter().jira
    return {"status_id": status_id, "workflow_ids": j.status_workflows(status_id),
            "projeto_ids": j.status_projetos(status_id)}


@leitura
def jira_listar_workflows(filtro: Optional[str] = None, inicio: int = 0, limite: int = 50,
                          incluir_status: bool = True) -> dict:
    """Workflows do site, paginados. filtro: trecho do nome. Id do workflow = id.entityId.

    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    r = obter().jira.workflows_pagina(filtro=filtro, inicio=max(0, inicio), limite=faixa(limite, 1, 200),
                                      expand="statuses" if incluir_status else "")
    return limpar(r)


@leitura
def jira_usos_workflow(workflow_id: str) -> dict:
    """Ids dos projetos e dos esquemas de workflow que usam um workflow (entityId)."""
    j = obter().jira
    return {"workflow_id": workflow_id, "projeto_ids": j.workflow_projetos(workflow_id),
            "esquema_ids": j.workflow_esquemas(workflow_id)}


FERRAMENTAS = [jira_buscar_issues, jira_contar_issues, jira_obter_issue, jira_listar_comentarios,
               jira_listar_projetos, jira_obter_projeto, jira_listar_campos,
               jira_listar_status, jira_usos_status, jira_listar_workflows, jira_usos_workflow]
