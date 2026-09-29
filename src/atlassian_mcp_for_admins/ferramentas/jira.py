"""Jira: issues, projetos, campos, status, workflows, telas e esquemas de tela.

Telas e esquemas so existem em projetos company-managed (classicos) e exigem admin do Jira.
"""
from typing import List, Literal, Optional

from ..apis import obter
from ._comum import escrita, faixa, leitura, limpar, usa_skill

SKILL_TELAS = "jira-telas"


def _fatia(itens: list, inicio: int, limite: int, chave: str = "itens") -> dict:
    """Recorte de uma lista que a API entrega inteira (sem paginacao), para caber na saida do MCP."""
    inicio = max(0, inicio)
    parte = itens[inicio:inicio + limite]
    return {"total": len(itens), "inicio": inicio, "retornados": len(parte),
            "proximo_inicio": inicio + len(parte) if inicio + len(parte) < len(itens) else None,
            chave: parte}


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


@leitura
def jira_listar_tipos_issue(projeto_id: Optional[str] = None) -> dict:
    """Tipos de issue do site (id, nome, subtask, hierarchyLevel). projeto_id: so os do projeto (id numerico)."""
    itens = limpar(obter().jira.tipos_issue(projeto_id))
    return {"total": len(itens), "tipos_issue": itens}


# ---------------------------------------------------------------- telas
@leitura
def jira_listar_telas(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                      escopos: Optional[List[Literal["GLOBAL", "TEMPLATE", "PROJECT"]]] = None,
                      inicio: int = 0, limite: int = 50) -> dict:
    """Telas do site, paginadas. filtro: trecho do nome. Se isLast for false, chame de novo
    com inicio = inicio + limite."""
    return limpar(obter().jira.telas_pagina(filtro=filtro, ids=ids, escopos=escopos,
                                            inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
def jira_obter_tela(tela_id: str, projeto: Optional[str] = None, limite_campos: int = 100) -> dict:
    """Uma tela inteira: dados da tela, abas na ordem e os campos de cada aba na ordem.

    Junta tres endpoints (tela, abas, campos da aba). Cada aba traz total_campos e ate
    limite_campos campos; se total_campos for maior, o resto sai em jira_listar_campos_aba.
    A API pode repetir o mesmo campo em sequencia na aba: vem como ela entrega.
    projeto: chave do projeto, so necessaria para quem e admin do projeto e nao do Jira.
    """
    j = obter().jira
    tela = j.tela(tela_id)
    limite = faixa(limite_campos, 1, 500)
    abas = []
    for aba in j.abas(tela_id, projeto):
        campos = j.campos_aba(tela_id, aba["id"], projeto)
        abas.append({**aba, "total_campos": len(campos), "fields": campos[:limite]})
    return limpar({**tela, "tabs": abas})


@escrita
def jira_criar_tela(nome: str, descricao: Optional[str] = None) -> dict:
    """Cria uma tela (nome unico, ate 255 caracteres). A API cria junto uma aba padrao vazia."""
    return limpar(obter().jira.criar_tela(nome, descricao))


@escrita
def jira_salvar_tela(tela_id: str, nome: Optional[str] = None, descricao: Optional[str] = None) -> dict:
    """Renomeia uma tela ou troca a descricao. Abas e campos tem ferramentas proprias."""
    if nome is None and descricao is None:
        raise ValueError("Informe nome ou descricao.")
    return limpar(obter().jira.salvar_tela(tela_id, nome, descricao))


@escrita
def jira_excluir_tela(tela_id: str) -> dict:
    """Exclui uma tela. A API recusa se ela estiver em um esquema de tela ou em uma
    transicao de workflow (inclusive rascunho). Nao ha como desfazer."""
    obter().jira.excluir_tela(tela_id)
    return {"excluida": tela_id}


@leitura
def jira_listar_campos_disponiveis(tela_id: str, filtro: Optional[str] = None, inicio: int = 0,
                                   limite: int = 200) -> dict:
    """Campos que ainda podem ser adicionados a uma tela (os que nao estao em nenhuma aba dela).

    filtro: trecho do nome ou do id, sem diferenciar maiusculas. A API devolve a lista
    inteira; a ferramenta entrega em partes: se proximo_inicio vier, chame de novo com ele.
    """
    itens = limpar(obter().jira.campos_disponiveis_tela(tela_id))
    if filtro:
        f = filtro.lower()
        itens = [c for c in itens if f in (c.get("name") or "").lower() or f in (c.get("id") or "").lower()]
    return _fatia(itens, inicio, faixa(limite, 1, 1000), "campos")


@leitura
def jira_usos_campo(campo_id: str, inicio: int = 0, limite: int = 50) -> dict:
    """Telas em que um campo customizado aparece, com a aba (tab) de cada uma, paginadas.

    campo_id: "customfield_..."; campo do sistema (summary, duedate...) da 404 nesta API.
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.telas_do_campo(campo_id, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


# ----------------------------------------------------------------- abas
@leitura
def jira_listar_abas(tela_id: str, projeto: Optional[str] = None) -> dict:
    """Abas de uma tela, na ordem de exibicao. projeto: chave, para admin do projeto."""
    itens = limpar(obter().jira.abas(tela_id, projeto))
    return {"total": len(itens), "abas": itens}


@escrita
def jira_criar_aba(tela_id: str, nome: str) -> dict:
    """Cria uma aba no fim da tela (nome unico na tela, ate 255 caracteres)."""
    return limpar(obter().jira.criar_aba(tela_id, nome))


@escrita
def jira_salvar_aba(tela_id: str, aba_id: str, nome: str) -> dict:
    """Renomeia uma aba (a API so edita o nome)."""
    return limpar(obter().jira.salvar_aba(tela_id, aba_id, nome))


@escrita
def jira_excluir_aba(tela_id: str, aba_id: str) -> dict:
    """Exclui uma aba e tira da tela os campos que estavam nela. Nao ha como desfazer."""
    obter().jira.excluir_aba(tela_id, aba_id)
    return {"excluida": aba_id}


@escrita
def jira_mover_aba(tela_id: str, aba_id: str, posicao: int) -> dict:
    """Move uma aba para a posicao indicada, contada a partir de 0 (0 = primeira)."""
    obter().jira.mover_aba(tela_id, aba_id, max(0, posicao))
    return {"aba_id": aba_id, "posicao": max(0, posicao)}


# ------------------------------------------------------- campos da aba
@leitura
def jira_listar_campos_aba(tela_id: str, aba_id: str, projeto: Optional[str] = None, inicio: int = 0,
                           limite: int = 500) -> dict:
    """Campos de uma aba, na ordem de exibicao. projeto: chave, para admin do projeto.

    A API devolve a lista inteira (pode repetir o mesmo campo em sequencia); a ferramenta
    entrega em partes: se proximo_inicio vier, chame de novo com ele.
    """
    return _fatia(limpar(obter().jira.campos_aba(tela_id, aba_id, projeto)), inicio, faixa(limite, 1, 2000),
                  "campos")


@escrita
def jira_adicionar_campo_aba(tela_id: str, aba_id: str, campo_id: str) -> dict:
    """Coloca um campo existente no fim de uma aba. campo_id: ex. "duedate", "customfield_10000".

    Um campo so pode estar uma vez na tela: veja jira_listar_campos_disponiveis.
    """
    return limpar(obter().jira.adicionar_campo_aba(tela_id, aba_id, campo_id))


@escrita
def jira_remover_campo_aba(tela_id: str, aba_id: str, campo_id: str) -> dict:
    """Tira um campo da aba. O campo continua existindo no Jira e nas outras telas."""
    obter().jira.remover_campo_aba(tela_id, aba_id, campo_id)
    return {"removido": campo_id, "aba_id": aba_id}


@escrita
@usa_skill(SKILL_TELAS)
def jira_mover_campo_aba(tela_id: str, aba_id: str, campo_id: str, depois_de: Optional[str] = None,
                         posicao: Optional[Literal["First", "Last", "Earlier", "Later"]] = None) -> dict:
    """Muda a ordem de um campo dentro da aba.

    Informe depois_de (id do campo apos o qual ele fica) ou posicao: First, Last,
    Earlier (sobe uma) ou Later (desce uma). Se vierem os dois, a API ignora posicao.
    Para levar o campo a outra aba: remover desta e adicionar na outra.
    """
    if not depois_de and not posicao:
        raise ValueError("Informe depois_de ou posicao.")
    obter().jira.mover_campo_aba(tela_id, aba_id, campo_id, depois_de, posicao)
    return {"campo_id": campo_id, "depois_de": depois_de, "posicao": None if depois_de else posicao}


# ---------------------------------------------------- esquemas de tela
@leitura
@usa_skill(SKILL_TELAS)
def jira_listar_esquemas_tela(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                              incluir_usos: bool = False, inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de tela, paginados, com a tela de cada operacao (default, create, edit, view).

    filtro: trecho do nome. incluir_usos: traz os esquemas de tela por tipo de issue
    que usam cada esquema. Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.esquemas_tela_pagina(
        filtro=filtro, ids=ids, expand="issueTypeScreenSchemes" if incluir_usos else None,
        inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@escrita
@usa_skill(SKILL_TELAS)
def jira_criar_esquema_tela(nome: str, telas: dict, descricao: Optional[str] = None) -> dict:
    """Cria um esquema de tela. telas: {"default": id, "create": id, "edit": id, "view": id},
    com default obrigatorio. Devolve o id do esquema."""
    return limpar(obter().jira.criar_esquema_tela(nome, telas, descricao))


@escrita
@usa_skill(SKILL_TELAS)
def jira_salvar_esquema_tela(esquema_id: str, nome: Optional[str] = None, descricao: Optional[str] = None,
                             telas: Optional[dict] = None) -> dict:
    """Altera nome, descricao ou telas de um esquema de tela.

    telas: so as operacoes que mudam; null em create, edit ou view tira a tela da
    operacao (passa a valer a default). default nao pode ser null.
    """
    if nome is None and descricao is None and telas is None:
        raise ValueError("Informe nome, descricao ou telas.")
    obter().jira.salvar_esquema_tela(esquema_id, nome, descricao, telas)
    return {"salvo": esquema_id}


@escrita
def jira_excluir_esquema_tela(esquema_id: str) -> dict:
    """Exclui um esquema de tela. A API recusa se ele estiver em um esquema de tela por
    tipo de issue. As telas nao sao excluidas. Nao ha como desfazer."""
    obter().jira.excluir_esquema_tela(esquema_id)
    return {"excluido": esquema_id}


# ------------------------------------- esquemas de tela por tipo de issue
@leitura
@usa_skill(SKILL_TELAS)
def jira_listar_esquemas_tipo_tela(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                                   incluir_projetos: bool = False, inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de tela por tipo de issue (o que o projeto usa), paginados.

    filtro: trecho do nome. incluir_projetos: traz os projetos de cada esquema.
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.esquemas_tipo_tela_pagina(
        filtro=filtro, ids=ids, expand="projects" if incluir_projetos else None,
        inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_TELAS)
def jira_listar_itens_tipo_tela(esquema_ids: Optional[List[str]] = None, inicio: int = 0,
                                limite: int = 50) -> dict:
    """Itens dos esquemas de tela por tipo de issue: qual esquema de tela vale para cada
    tipo de issue (issueTypeId "default" = tipos sem item proprio), paginados.

    esquema_ids: so desses esquemas (sem ele, de todos). Se isLast for false, chame de
    novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.itens_tipo_tela_pagina(esquema_ids, inicio=max(0, inicio),
                                                      limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_TELAS)
def jira_listar_tipo_tela_projetos(projeto_ids: List[str], inicio: int = 0, limite: int = 50) -> dict:
    """Esquema de tela por tipo de issue de cada projeto. projeto_ids: ids numericos
    (jira_obter_projeto da o id pela chave). Projeto team-managed nao aparece."""
    return limpar(obter().jira.tipo_tela_projetos_pagina(projeto_ids, inicio=max(0, inicio),
                                                         limite=faixa(limite, 1, 100)))


@leitura
def jira_usos_esquema_tipo_tela(esquema_id: str, filtro: Optional[str] = None, inicio: int = 0,
                                limite: int = 50) -> dict:
    """Projetos que usam um esquema de tela por tipo de issue, paginados.

    filtro: trecho do nome ou da chave do projeto. Se isLast for false, chame de novo
    com inicio = inicio + limite.
    """
    return limpar(obter().jira.projetos_esquema_tipo_tela_pagina(
        esquema_id, filtro=filtro, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@escrita
@usa_skill(SKILL_TELAS)
def jira_criar_esquema_tipo_tela(nome: str, itens: List[dict], descricao: Optional[str] = None) -> dict:
    """Cria um esquema de tela por tipo de issue.

    itens: [{"issueTypeId": "default", "screenSchemeId": "10000"}, {"issueTypeId": "10001",
    "screenSchemeId": "10002"}]; o item "default" e obrigatorio. Devolve o id do esquema.
    """
    return limpar(obter().jira.criar_esquema_tipo_tela(nome, itens, descricao))


@escrita
def jira_salvar_esquema_tipo_tela(esquema_id: str, nome: Optional[str] = None,
                                  descricao: Optional[str] = None) -> dict:
    """Renomeia ou troca a descricao de um esquema de tela por tipo de issue. Os itens tem
    ferramentas proprias (adicionar, remover, padrao)."""
    if nome is None and descricao is None:
        raise ValueError("Informe nome ou descricao.")
    obter().jira.salvar_esquema_tipo_tela(esquema_id, nome, descricao)
    return {"salvo": esquema_id}


@escrita
def jira_excluir_esquema_tipo_tela(esquema_id: str) -> dict:
    """Exclui um esquema de tela por tipo de issue. A API recusa se algum projeto o usar.
    Os esquemas de tela nao sao excluidos. Nao ha como desfazer."""
    obter().jira.excluir_esquema_tipo_tela(esquema_id)
    return {"excluido": esquema_id}


@escrita
@usa_skill(SKILL_TELAS)
def jira_adicionar_itens_tipo_tela(esquema_id: str, itens: List[dict]) -> dict:
    """Liga tipos de issue a esquemas de tela dentro de um esquema de tela por tipo de issue.

    itens: [{"issueTypeId": "10001", "screenSchemeId": "10002"}]. Nao aceita "default":
    para ele, jira_salvar_padrao_tipo_tela.
    """
    obter().jira.adicionar_itens_tipo_tela(esquema_id, itens)
    return {"esquema_id": esquema_id, "adicionados": itens}


@escrita
@usa_skill(SKILL_TELAS)
def jira_salvar_padrao_tipo_tela(esquema_id: str, esquema_tela_id: str) -> dict:
    """Troca o esquema de tela padrao (item "default"), que vale para os tipos de issue sem
    item proprio."""
    obter().jira.salvar_padrao_tipo_tela(esquema_id, esquema_tela_id)
    return {"esquema_id": esquema_id, "padrao": esquema_tela_id}


@escrita
@usa_skill(SKILL_TELAS)
def jira_remover_itens_tipo_tela(esquema_id: str, tipo_issue_ids: List[str]) -> dict:
    """Tira os itens dos tipos de issue indicados; eles passam a usar o esquema de tela padrao."""
    obter().jira.remover_itens_tipo_tela(esquema_id, tipo_issue_ids)
    return {"esquema_id": esquema_id, "removidos": tipo_issue_ids}


@escrita
@usa_skill(SKILL_TELAS)
def jira_associar_esquema_tipo_tela(esquema_id: str, projeto_id: str) -> dict:
    """Troca o esquema de tela por tipo de issue de um projeto company-managed.

    projeto_id: id numerico do projeto. Muda as telas de todas as issues do projeto.
    """
    obter().jira.associar_esquema_tipo_tela(esquema_id, projeto_id)
    return {"projeto_id": projeto_id, "esquema_id": esquema_id}


FERRAMENTAS = [jira_buscar_issues, jira_contar_issues, jira_obter_issue, jira_listar_comentarios,
               jira_listar_projetos, jira_obter_projeto, jira_listar_campos,
               jira_listar_status, jira_usos_status, jira_listar_workflows, jira_usos_workflow,
               jira_listar_tipos_issue,
               jira_listar_telas, jira_obter_tela, jira_criar_tela, jira_salvar_tela, jira_excluir_tela,
               jira_listar_campos_disponiveis, jira_usos_campo,
               jira_listar_abas, jira_criar_aba, jira_salvar_aba, jira_excluir_aba, jira_mover_aba,
               jira_listar_campos_aba, jira_adicionar_campo_aba, jira_remover_campo_aba, jira_mover_campo_aba,
               jira_listar_esquemas_tela, jira_criar_esquema_tela, jira_salvar_esquema_tela,
               jira_excluir_esquema_tela,
               jira_listar_esquemas_tipo_tela, jira_listar_itens_tipo_tela, jira_listar_tipo_tela_projetos,
               jira_usos_esquema_tipo_tela, jira_criar_esquema_tipo_tela, jira_salvar_esquema_tipo_tela,
               jira_excluir_esquema_tipo_tela, jira_adicionar_itens_tipo_tela, jira_salvar_padrao_tipo_tela,
               jira_remover_itens_tipo_tela, jira_associar_esquema_tipo_tela]
