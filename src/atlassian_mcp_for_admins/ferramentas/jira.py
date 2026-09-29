"""Jira: issues, projetos, campos, status, workflows, telas, esquemas de tela, prioridades,
esquemas de prioridade, configuracoes de campo e esquemas de configuracao de campo
(API antiga), esquemas de campos (API nova, em beta) e esquemas de notificacao.

Telas e esquemas so existem em projetos company-managed (classicos) e exigem admin do Jira.
"""
from typing import List, Literal, Optional

from ..apis import obter
from ._comum import escrita, faixa, leitura, limpar, usa_skill

SKILL_TELAS = "jira-telas"
SKILL_PRIORIDADES = "jira-prioridades"
SKILL_CONFIG = "jira-config-campos"
SKILL_CAMPOS = "jira-esquemas-campos"
SKILL_NOTIF = "jira-notificacoes"


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


# ----------------------------------------------------------- prioridades
@leitura
def jira_listar_prioridades(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                            projeto_ids: Optional[List[str]] = None, incluir_esquemas: bool = False,
                            inicio: int = 0, limite: int = 50) -> dict:
    """Prioridades do site na ordem global (a primeira e a mais alta), paginadas.

    filtro: trecho do nome, sem diferenciar maiusculas. projeto_ids: so as disponiveis
    nesses projetos (ids numericos). incluir_esquemas: traz os esquemas de prioridade de
    cada uma (ate 15). avatarId e o icone, reaproveitavel em jira_criar_prioridade.
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.prioridades_pagina(
        ids=ids, projeto_ids=projeto_ids, filtro=filtro, expand="schemes" if incluir_esquemas else None,
        inicio=max(0, inicio), limite=faixa(limite, 1, 200)))


@escrita
@usa_skill(SKILL_PRIORIDADES)
def jira_criar_prioridade(nome: str, cor: str, avatar_id: int, descricao: Optional[str] = None) -> dict:
    """Cria uma prioridade no fim da ordem global. Ela nao entra em nenhum esquema sozinha.

    nome: unico, ate 60 caracteres. cor: hexadecimal de 3 ou 6 digitos ("#ff0000").
    avatar_id: icone, ex. o avatarId de uma prioridade existente. Devolve o id.
    """
    return limpar(obter().jira.criar_prioridade(nome, cor, avatar_id, descricao))


@escrita
def jira_salvar_prioridade(prioridade_id: str, nome: Optional[str] = None, cor: Optional[str] = None,
                           avatar_id: Optional[int] = None, descricao: Optional[str] = None) -> dict:
    """Altera nome, cor (hexadecimal), icone (avatar_id) ou descricao de uma prioridade.

    A prioridade e global: a mudanca aparece em todos os esquemas e issues que a usam.
    """
    if nome is None and cor is None and avatar_id is None and descricao is None:
        raise ValueError("Informe nome, cor, avatar_id ou descricao.")
    obter().jira.salvar_prioridade(prioridade_id, nome, cor, avatar_id, descricao)
    return {"salva": prioridade_id}


@escrita
@usa_skill(SKILL_PRIORIDADES)
def jira_excluir_prioridade(prioridade_id: str) -> dict:
    """Exclui uma prioridade do site. Assincrono: devolve a tarefa, que se acompanha em
    jira_obter_tarefa. A API recusa (409) se ja houver exclusao em andamento. Nao ha
    como desfazer."""
    tarefa = obter().jira.excluir_prioridade(prioridade_id)
    return {"excluida": prioridade_id, "tarefa": limpar(tarefa)}


@escrita
def jira_mover_prioridades(ids: List[str], depois_de: Optional[str] = None,
                           posicao: Optional[Literal["First", "Last"]] = None) -> dict:
    """Muda a ordem global das prioridades (a ordem de exibicao e de ordenacao por prioridade).

    ids: prioridades a mover, na ordem em que devem ficar. Informe depois_de (id da
    prioridade apos a qual elas ficam, fora de ids) ou posicao (First ou Last).
    """
    if not depois_de and not posicao:
        raise ValueError("Informe depois_de ou posicao.")
    obter().jira.mover_prioridades(ids, depois_de, posicao)
    return {"movidas": ids, "depois_de": depois_de, "posicao": None if depois_de else posicao}


@escrita
def jira_salvar_padrao_prioridade(prioridade_id: Optional[str] = None) -> dict:
    """Troca a prioridade padrao global do site; sem prioridade_id, apaga a configuracao.

    O padrao que vale num projeto e o defaultPriorityId do esquema de prioridade dele
    (jira_salvar_esquema_prioridade). A Atlassian marcou o isDefault global como obsoleto.
    """
    obter().jira.salvar_padrao_prioridade(prioridade_id)
    return {"padrao": prioridade_id}


# --------------------------------------------- esquemas de prioridade
@leitura
@usa_skill(SKILL_PRIORIDADES)
def jira_listar_esquemas_prioridade(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                                    prioridade_ids: Optional[List[str]] = None, somente_padrao: bool = False,
                                    incluir_prioridades: bool = False, incluir_projetos: bool = False,
                                    inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de prioridade, paginados, com defaultPriorityId (padrao do esquema).

    filtro: trecho do nome. prioridade_ids: so esquemas que tem essas prioridades.
    somente_padrao: so o esquema padrao do site (isDefault true), o dos projetos sem
    esquema proprio; o nome nao indica qual e.
    incluir_prioridades / incluir_projetos: traz a primeira pagina de cada lista (com
    total); o resto sai em jira_listar_prioridades_esquema e jira_usos_esquema_prioridade.
    Com incluir_*, use limite pequeno (ex. 10): cada esquema pode trazer 50 projetos.
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    expand = ",".join(n for n, sim in (("priorities", incluir_prioridades), ("projects", incluir_projetos)) if sim)
    return limpar(obter().jira.esquemas_prioridade_pagina(
        filtro=filtro, ids=ids, prioridade_ids=prioridade_ids, somente_padrao=somente_padrao,
        expand=expand or None, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
def jira_listar_prioridades_esquema(esquema_id: str, inicio: int = 0, limite: int = 100) -> dict:
    """Prioridades de um esquema de prioridade, na ordem global (sequence), paginadas.

    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.prioridades_esquema_pagina(esquema_id, inicio=max(0, inicio),
                                                          limite=faixa(limite, 1, 200)))


@leitura
def jira_usos_esquema_prioridade(esquema_id: str, filtro: Optional[str] = None,
                                 projeto_ids: Optional[List[str]] = None, inicio: int = 0,
                                 limite: int = 50) -> dict:
    """Projetos que usam um esquema de prioridade, paginados.

    filtro: trecho do nome do projeto. projeto_ids: confere se esses projetos (ids
    numericos) estao no esquema. Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.projetos_esquema_prioridade_pagina(
        esquema_id, filtro=filtro, projeto_ids=projeto_ids, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_PRIORIDADES)
def jira_listar_prioridades_mapear(esquema_id: str, adicionar_prioridades: Optional[List[str]] = None,
                                   remover_prioridades: Optional[List[str]] = None,
                                   adicionar_projetos: Optional[List[str]] = None,
                                   inicio: int = 0, limite: int = 50) -> dict:
    """Prioridades que uma mudanca no esquema exigiria mapear (chaves do mapeamento "in").

    Nao altera nada: a API so calcula. Informe as mesmas listas que irao para
    jira_salvar_esquema_prioridade. Nao cobre remocao de projetos (mapeamento "out").
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.prioridades_mapear_pagina(
        esquema_id, adicionar_prioridades, remover_prioridades, adicionar_projetos,
        inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@escrita
@usa_skill(SKILL_PRIORIDADES)
def jira_criar_esquema_prioridade(nome: str, prioridade_ids: List[str], prioridade_padrao_id: str,
                                  descricao: Optional[str] = None, projeto_ids: Optional[List[str]] = None,
                                  mapeamentos: Optional[dict] = None) -> dict:
    """Cria um esquema de prioridade e, se vierem projeto_ids, ja o associa a eles.

    prioridade_padrao_id deve estar em prioridade_ids. Projetos cujas issues usam
    prioridades fora do esquema exigem mapeamentos {"in": {"<antiga>": <nova>}}.
    Devolve o id e, se houver migracao de issues, a tarefa (jira_obter_tarefa).
    """
    return limpar(obter().jira.criar_esquema_prioridade(nome, prioridade_ids, prioridade_padrao_id, descricao,
                                                        projeto_ids, mapeamentos))


@escrita
@usa_skill(SKILL_PRIORIDADES)
def jira_salvar_esquema_prioridade(esquema_id: str, nome: Optional[str] = None, descricao: Optional[str] = None,
                                   prioridade_padrao_id: Optional[str] = None,
                                   adicionar_prioridades: Optional[List[str]] = None,
                                   remover_prioridades: Optional[List[str]] = None,
                                   adicionar_projetos: Optional[List[str]] = None,
                                   remover_projetos: Optional[List[str]] = None,
                                   mapeamentos: Optional[dict] = None) -> dict:
    """Altera um esquema de prioridade: nome, descricao, padrao, prioridades e projetos.

    Adicionar um projeto o tira do esquema anterior; remover o devolve ao esquema
    padrao do site. Remover prioridades ou adicionar projetos exige mapeamentos "in";
    remover projetos exige "out". Devolve o esquema e a tarefa de migracao de issues
    (jira_obter_tarefa).
    """
    if all(v is None or v == [] for v in (nome, descricao, prioridade_padrao_id, adicionar_prioridades,
                                          remover_prioridades, adicionar_projetos, remover_projetos)):
        raise ValueError("Informe ao menos uma alteracao.")
    return limpar(obter().jira.salvar_esquema_prioridade(
        esquema_id, nome, descricao, prioridade_padrao_id, adicionar_prioridades, remover_prioridades,
        adicionar_projetos, remover_projetos, mapeamentos))


@escrita
def jira_excluir_esquema_prioridade(esquema_id: str) -> dict:
    """Exclui um esquema de prioridade. A API recusa se algum projeto o usar: tire os
    projetos antes (jira_salvar_esquema_prioridade). As prioridades nao sao excluidas."""
    obter().jira.excluir_esquema_prioridade(esquema_id)
    return {"excluido": esquema_id}


# ------------------------------------------------ configuracoes de campo
@leitura
@usa_skill(SKILL_CONFIG)
def jira_listar_configs_campo(filtro: Optional[str] = None, ids: Optional[List[str]] = None,
                              somente_padrao: bool = False, inicio: int = 0, limite: int = 50) -> dict:
    """Configuracoes de campo (obrigatorio, oculto, descricao e renderizador de cada campo),
    paginadas. So projetos company-managed.

    filtro: trecho do nome ou da descricao. somente_padrao: so a configuracao padrao do
    site (isDefault). Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.configs_campo_pagina(filtro=filtro, ids=ids, somente_padrao=somente_padrao,
                                                    inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_CONFIG)
def jira_listar_campos_config(config_id: str, campo_ids: Optional[List[str]] = None, inicio: int = 0,
                              limite: int = 100) -> dict:
    """Itens de uma configuracao de campo: id do campo, isHidden, isRequired, description e
    renderer. A configuracao traz todos os campos do site (mais de mil em sites grandes).

    campo_ids: so esses campos (ex. ["description", "customfield_10000"]); a ferramenta
    percorre todas as paginas e devolve so eles. Sem campo_ids, uma pagina: se isLast for
    false, chame de novo com inicio = inicio + limite.
    """
    j = obter().jira
    if campo_ids:
        procurados = set(campo_ids)
        itens = [i for i in j.campos_config(config_id) if i.get("id") in procurados]
        return {"config_id": config_id, "campo_ids": campo_ids,
                "nao_encontrados": sorted(procurados - {i["id"] for i in itens}), "values": limpar(itens)}
    return limpar(j.campos_config_pagina(config_id, inicio=max(0, inicio), limite=faixa(limite, 1, 200)))


@escrita
def jira_criar_config_campo(nome: str, descricao: Optional[str] = None) -> dict:
    """Cria uma configuracao de campo com as propriedades da padrao, mas com todos os campos
    opcionais. Nao entra em esquema sozinha: jira_adicionar_itens_config. Devolve o id."""
    return limpar(obter().jira.criar_config_campo(nome, descricao))


@escrita
def jira_salvar_config_campo(config_id: str, nome: str, descricao: Optional[str] = None) -> dict:
    """Renomeia uma configuracao de campo. A API sobrescreve nome E descricao: para manter a
    descricao, repita a atual. Os campos tem ferramenta propria (jira_salvar_campos_config)."""
    obter().jira.salvar_config_campo(config_id, nome, descricao)
    return {"salva": config_id}


@escrita
def jira_excluir_config_campo(config_id: str) -> dict:
    """Exclui uma configuracao de campo. Exclua so a que nao esta em nenhum esquema de
    configuracao de campo (jira_listar_itens_config). Nao ha como desfazer."""
    obter().jira.excluir_config_campo(config_id)
    return {"excluida": config_id}


@escrita
@usa_skill(SKILL_CONFIG)
def jira_salvar_campos_config(config_id: str, itens: List[dict]) -> dict:
    """Muda obrigatorio, oculto, descricao (texto de ajuda) ou renderizador de campos numa
    configuracao de campo. Vale para todo projeto e tipo de issue que usa a configuracao.

    itens: [{"id": "customfield_10000", "isRequired": true}, {"id": "environment",
    "isHidden": true}, {"id": "description", "description": "Passos para reproduzir",
    "renderer": "wiki-renderer"}]. So o que vier no item muda. Ocultar apaga obrigatorio,
    descricao e renderizador do campo; reexibir nao os restaura.
    """
    obter().jira.salvar_campos_config(config_id, itens)
    return {"config_id": config_id, "salvos": [i.get("id") for i in itens]}


# ---------------------------------- esquemas de configuracao de campo
@leitura
@usa_skill(SKILL_CONFIG)
def jira_listar_esquemas_config(ids: Optional[List[str]] = None, inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de configuracao de campo (ligam cada tipo de issue a uma configuracao de
    campo), paginados. A API nao filtra por nome. Se isLast for false, chame de novo com
    inicio = inicio + limite."""
    return limpar(obter().jira.esquemas_config_pagina(ids, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_CONFIG)
def jira_listar_itens_config(esquema_ids: Optional[List[str]] = None, inicio: int = 0, limite: int = 50) -> dict:
    """Itens dos esquemas de configuracao de campo: qual configuracao vale para cada tipo de
    issue (issueTypeId "default" = tipos sem item proprio), paginados.

    esquema_ids: so desses esquemas (ate 50). Se isLast for false, chame de novo com
    inicio = inicio + limite.
    """
    return limpar(obter().jira.itens_config_pagina(esquema_ids, inicio=max(0, inicio),
                                                   limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_CONFIG)
def jira_listar_config_projetos(projeto_ids: List[str], inicio: int = 0, limite: int = 50) -> dict:
    """Esquema de configuracao de campo de cada projeto: grupos {fieldConfigurationScheme,
    projectIds}. Grupo sem fieldConfigurationScheme = projetos no esquema padrao do site.

    projeto_ids: ids numericos (jira_obter_projeto da o id pela chave). Projeto
    team-managed nao aparece.
    """
    return limpar(obter().jira.config_projetos_pagina(projeto_ids, inicio=max(0, inicio),
                                                      limite=faixa(limite, 1, 100)))


@escrita
def jira_criar_esquema_config(nome: str, descricao: Optional[str] = None) -> dict:
    """Cria um esquema de configuracao de campo vazio. Os itens (tipo de issue ->
    configuracao) entram com jira_adicionar_itens_config. Devolve o id."""
    return limpar(obter().jira.criar_esquema_config(nome, descricao))


@escrita
def jira_salvar_esquema_config(esquema_id: str, nome: str, descricao: Optional[str] = None) -> dict:
    """Renomeia um esquema de configuracao de campo. A API sobrescreve nome E descricao:
    para manter a descricao, repita a atual."""
    obter().jira.salvar_esquema_config(esquema_id, nome, descricao)
    return {"salvo": esquema_id}


@escrita
def jira_excluir_esquema_config(esquema_id: str) -> dict:
    """Exclui um esquema de configuracao de campo. Exclua so esquema sem projetos
    (jira_listar_config_projetos). As configuracoes de campo nao sao excluidas. Nao ha
    como desfazer."""
    obter().jira.excluir_esquema_config(esquema_id)
    return {"excluido": esquema_id}


@escrita
@usa_skill(SKILL_CONFIG)
def jira_adicionar_itens_config(esquema_id: str, itens: List[dict]) -> dict:
    """Liga tipos de issue a configuracoes de campo num esquema (cria ou troca o item).

    itens: [{"issueTypeId": "default", "fieldConfigurationId": "10000"}, {"issueTypeId":
    "10001", "fieldConfigurationId": "10002"}]; cada tipo uma vez so por chamada.
    """
    obter().jira.adicionar_itens_config(esquema_id, itens)
    return {"esquema_id": esquema_id, "adicionados": itens}


@escrita
@usa_skill(SKILL_CONFIG)
def jira_remover_itens_config(esquema_id: str, tipo_issue_ids: List[str]) -> dict:
    """Tira os itens dos tipos de issue indicados (ate 100); eles passam a usar a
    configuracao do item "default"."""
    obter().jira.remover_itens_config(esquema_id, tipo_issue_ids)
    return {"esquema_id": esquema_id, "removidos": tipo_issue_ids}


@escrita
@usa_skill(SKILL_CONFIG)
def jira_associar_esquema_config(projeto_id: str, esquema_id: Optional[str] = None) -> dict:
    """Troca o esquema de configuracao de campo de um projeto company-managed.

    projeto_id: id numerico. Sem esquema_id, volta ao esquema padrao do site. Muda
    obrigatorio e oculto de todos os campos do projeto.
    """
    obter().jira.associar_esquema_config(esquema_id, projeto_id)
    return {"projeto_id": projeto_id, "esquema_id": esquema_id}


# ------------------------------------ esquemas de campos (API nova, beta)
def _resultado(r, **padrao) -> dict:
    """Escritas em lote respondem 200/207 com results (sucesso ou erro por item) ou 204 vazio."""
    return limpar(r) if r else {**padrao, "results": None}


@leitura
@usa_skill(SKILL_CAMPOS)
def jira_listar_esquemas_campos(filtro: Optional[str] = None, projeto_ids: Optional[List[str]] = None,
                                inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de campos (API nova, em beta), paginados, com fieldsCount e isDefault.

    filtro: trecho do nome ou da descricao. projeto_ids: so os esquemas desses projetos
    (ids numericos): e assim que se acha o esquema de um projeto.
    Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.esquemas_campos_pagina(filtro=filtro, projeto_ids=projeto_ids,
                                                      inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
def jira_obter_esquema_campos(esquema_id: str) -> dict:
    """Um esquema de campos pelo id: nome, descricao, fieldsCount e isDefault."""
    return limpar(obter().jira.esquema_campos(esquema_id))


@leitura
@usa_skill(SKILL_CAMPOS)
def jira_listar_campos_esquema(esquema_id: str, campo_ids: Optional[List[str]] = None, inicio: int = 0,
                               limite: int = 50) -> dict:
    """Campos de um esquema de campos, paginados: parametros (isRequired, description,
    rendererType), excecoes por tipo de issue (workTypeParameters), restrictedToWorkTypes e
    allowedOperations (o que o campo permite mudar).

    campo_ids: so esses campos (ex. ["customfield_10000", "description"]); campo fora do
    esquema nao aparece. Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.campos_esquema_pagina(esquema_id, campo_ids, inicio=max(0, inicio),
                                                     limite=faixa(limite, 1, 100)))


@leitura
def jira_usos_esquema_campos(esquema_id: str, projeto_ids: Optional[List[str]] = None, inicio: int = 0,
                             limite: int = 50) -> dict:
    """Projetos que usam um esquema de campos, paginados. projeto_ids: confere se esses
    projetos estao nele. Se isLast for false, chame de novo com inicio = inicio + limite."""
    return limpar(obter().jira.projetos_esquema_campos_pagina(esquema_id, projeto_ids, inicio=max(0, inicio),
                                                              limite=faixa(limite, 1, 100)))


@escrita
def jira_criar_esquema_campos(nome: str, descricao: Optional[str] = None) -> dict:
    """Cria um esquema de campos vazio, so com os campos essenciais do sistema. Para partir
    de um existente, use jira_copiar_esquema_campos. Devolve o id."""
    return limpar(obter().jira.criar_esquema_campos(nome, descricao))


@escrita
def jira_copiar_esquema_campos(esquema_id: str, nome: str, descricao: Optional[str] = None) -> dict:
    """Cria um esquema de campos novo copiando campos e parametros de outro. Devolve o id.
    O esquema novo nasce sem projetos."""
    return limpar(obter().jira.copiar_esquema_campos(esquema_id, nome, descricao))


@escrita
def jira_salvar_esquema_campos(esquema_id: str, nome: Optional[str] = None,
                               descricao: Optional[str] = None) -> dict:
    """Renomeia ou troca a descricao de um esquema de campos. Campos e parametros tem
    ferramentas proprias."""
    if nome is None and descricao is None:
        raise ValueError("Informe nome ou descricao.")
    return limpar(obter().jira.salvar_esquema_campos(esquema_id, nome, descricao))


@escrita
def jira_excluir_esquema_campos(esquema_id: str) -> dict:
    """Exclui um esquema de campos. A API recusa o esquema do sistema (400) e esquema em uso
    por projetos (409). Nao ha como desfazer."""
    return limpar(obter().jira.excluir_esquema_campos(esquema_id))


@escrita
@usa_skill(SKILL_CAMPOS)
def jira_adicionar_campos_esquema(campos: dict) -> dict:
    """Coloca campos em esquemas de campos, ou troca os tipos de issue a que ficam restritos.

    campos: {"customfield_10000": [{"schemeIds": [10000], "restrictedToWorkTypes": [10001]}]};
    ate 100 campos e 50 esquemas por item. restrictedToWorkTypes substitui a restricao
    atual; sem ele, o campo vale para todos os tipos. Devolve results por campo e esquema
    (success/error): confira cada um.
    """
    return _resultado(obter().jira.adicionar_campos_esquema(campos), campos=list(campos))


@escrita
@usa_skill(SKILL_CAMPOS)
def jira_remover_campos_esquema(campos: dict) -> dict:
    """Tira campos de esquemas de campos: o campo deixa de existir nos projetos desses
    esquemas (substitui o antigo "oculto"). O campo continua existindo no Jira.

    campos: {"customfield_10000": {"schemeIds": [10000, 10001]}}. Devolve results por item.
    """
    return _resultado(obter().jira.remover_campos_esquema(campos), campos=list(campos))


@escrita
@usa_skill(SKILL_CAMPOS)
def jira_salvar_parametros_campos(campos: dict) -> dict:
    """Muda obrigatoriedade, descricao (texto de ajuda) e renderizador de campos em esquemas
    de campos, no esquema todo e/ou por tipo de issue.

    campos: {"customfield_10000": [{"schemeIds": [10000], "parameters": {"isRequired": true},
    "workTypeParameters": [{"workTypeId": 10001, "isRequired": false}]}]}. Parametro omitido
    ou null fica como esta. O campo precisa ja estar no esquema. Devolve results por item.
    """
    return _resultado(obter().jira.salvar_parametros_campos(campos), campos=list(campos))


@escrita
@usa_skill(SKILL_CAMPOS)
def jira_remover_parametros_campos(campos: dict) -> dict:
    """Apaga excecoes por tipo de issue: o tipo volta a seguir os parametros do esquema.

    campos: {"customfield_10000": [{"schemeId": 10000, "workTypeIds": [10001],
    "parameters": ["isRequired", "description"]}]}; ate 100 remocoes (tipos x parametros)
    por chamada. Devolve results por item.
    """
    return _resultado(obter().jira.remover_parametros_campos(campos), campos=list(campos))


@escrita
@usa_skill(SKILL_CAMPOS)
def jira_associar_esquema_campos(esquema_id: str, projeto_ids: List[str]) -> dict:
    """Troca o esquema de campos dos projetos indicados (ids numericos): eles passam a ter
    os campos e parametros desse esquema. Devolve results por projeto."""
    return _resultado(obter().jira.associar_esquema_campos(esquema_id, projeto_ids), esquema_id=esquema_id)


# --------------------------------------------- esquemas de notificacao
@leitura
@usa_skill(SKILL_NOTIF)
def jira_listar_esquemas_notif(ids: Optional[List[str]] = None, projeto_ids: Optional[List[str]] = None,
                               somente_padrao: bool = False, incluir_notificacoes: bool = False,
                               inicio: int = 0, limite: int = 50) -> dict:
    """Esquemas de notificacao (evento -> quem recebe e-mail), paginados, por nome.

    projeto_ids: so os esquemas desses projetos. somente_padrao: so o esquema padrao do
    site. incluir_notificacoes: traz eventos e destinatarios de cada esquema (use limite
    pequeno, ex. 5). Se isLast for false, chame de novo com inicio = inicio + limite.
    """
    return limpar(obter().jira.esquemas_notif_pagina(
        ids=ids, projeto_ids=projeto_ids, somente_padrao=somente_padrao,
        expand="all" if incluir_notificacoes else None, inicio=max(0, inicio), limite=faixa(limite, 1, 100)))


@leitura
@usa_skill(SKILL_NOTIF)
def jira_obter_esquema_notif(esquema_id: str) -> dict:
    """Um esquema de notificacao inteiro: cada evento com seus destinatarios (notificationType,
    parameter, id da notificacao e o usuario, grupo, papel ou campo expandido)."""
    return limpar(obter().jira.esquema_notif(esquema_id))


@leitura
@usa_skill(SKILL_NOTIF)
def jira_obter_notif_projeto(projeto: str) -> dict:
    """O esquema de notificacao de um projeto (chave ou id), com eventos e destinatarios.
    Aceita admin do projeto, nao so do Jira."""
    return limpar(obter().jira.esquema_notif_projeto(projeto))


@leitura
def jira_listar_notif_projetos(esquema_ids: Optional[List[str]] = None, projeto_ids: Optional[List[str]] = None,
                               inicio: int = 0, limite: int = 50) -> dict:
    """Pares projeto -> esquema de notificacao, paginados por projectId. esquema_ids: projetos
    que usam esses esquemas. So projetos company-managed. Se isLast for false, chame de
    novo com inicio = inicio + limite."""
    return limpar(obter().jira.notif_projetos_pagina(esquema_ids, projeto_ids, inicio=max(0, inicio),
                                                     limite=faixa(limite, 1, 100)))


@leitura
def jira_listar_eventos() -> dict:
    """Eventos de issue do site (id e nome): os do sistema e os personalizados. O id vai em
    event.id das notificacoes."""
    itens = limpar(obter().jira.eventos())
    return {"total": len(itens), "eventos": itens}


@leitura
def jira_listar_papeis(filtro: Optional[str] = None) -> dict:
    """Papeis de projeto do site (id, nome, descricao, escopo). O id e o parameter de
    destinatario ProjectRole. filtro: trecho do nome, sem diferenciar maiusculas."""
    itens = limpar(obter().jira.papeis())
    if filtro:
        f = filtro.lower()
        itens = [p for p in itens if f in (p.get("name") or "").lower()]
    return {"total": len(itens), "papeis": itens}


@escrita
@usa_skill(SKILL_NOTIF)
def jira_criar_esquema_notif(nome: str, descricao: Optional[str] = None,
                             eventos: Optional[List[dict]] = None) -> dict:
    """Cria um esquema de notificacao, ja com os destinatarios de cada evento (ate 1000).

    eventos: [{"event": {"id": "1"}, "notifications": [{"notificationType": "Reporter"},
    {"notificationType": "Group", "parameter": "nome-do-grupo"}]}]. Nasce sem projetos.
    Devolve o id.
    """
    return limpar(obter().jira.criar_esquema_notif(nome, descricao, eventos))


@escrita
def jira_salvar_esquema_notif(esquema_id: str, nome: Optional[str] = None,
                              descricao: Optional[str] = None) -> dict:
    """Renomeia ou troca a descricao de um esquema de notificacao. Destinatarios:
    jira_adicionar_notificacoes e jira_remover_notificacao."""
    if nome is None and descricao is None:
        raise ValueError("Informe nome ou descricao.")
    obter().jira.salvar_esquema_notif(esquema_id, nome, descricao)
    return {"salvo": esquema_id}


@escrita
def jira_excluir_esquema_notif(esquema_id: str) -> dict:
    """Exclui um esquema de notificacao. Exclua so esquema sem projetos
    (jira_listar_notif_projetos). Nao ha como desfazer."""
    obter().jira.excluir_esquema_notif(esquema_id)
    return {"excluido": esquema_id}


@escrita
@usa_skill(SKILL_NOTIF)
def jira_adicionar_notificacoes(esquema_id: str, eventos: List[dict]) -> dict:
    """Acrescenta destinatarios a eventos de um esquema de notificacao (ate 1000). Os que ja
    existem continuam; muda o e-mail de todos os projetos do esquema.

    eventos: [{"event": {"id": "6"}, "notifications": [{"notificationType": "ProjectRole",
    "parameter": "10002"}]}].
    """
    obter().jira.adicionar_notificacoes(esquema_id, eventos)
    return {"esquema_id": esquema_id, "adicionados": eventos}


@escrita
@usa_skill(SKILL_NOTIF)
def jira_remover_notificacao(esquema_id: str, notificacao_id: str) -> dict:
    """Tira um destinatario de um evento, pelo id da notificacao (jira_obter_esquema_notif).
    Nao ha edicao: para trocar, remova e adicione."""
    obter().jira.remover_notificacao(esquema_id, notificacao_id)
    return {"esquema_id": esquema_id, "removida": notificacao_id}


@escrita
@usa_skill(SKILL_NOTIF)
def jira_associar_esquema_notif(projeto: str, esquema_id: str) -> dict:
    """Troca o esquema de notificacao de um projeto company-managed (chave ou id). Vai pelo
    cadastro do projeto, so com notificationScheme; o resto do projeto nao muda."""
    r = obter().jira.associar_esquema_notif(projeto, esquema_id)
    return {"projeto": (r or {}).get("key", projeto), "esquema_id": esquema_id}


# --------------------------------------------------------------- tarefas
@leitura
def jira_obter_tarefa(tarefa_id: str) -> dict:
    """Situacao de uma tarefa assincrona do Jira (exclusao de prioridade, migracao de
    issues de esquema): status ENQUEUED, RUNNING, COMPLETE, FAILED, CANCELLED ou DEAD,
    progress (%) e result. A Atlassian guarda a tarefa por cerca de 14 dias."""
    return limpar(obter().jira.tarefa(tarefa_id))


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
               jira_remover_itens_tipo_tela, jira_associar_esquema_tipo_tela,
               jira_listar_prioridades, jira_criar_prioridade, jira_salvar_prioridade, jira_excluir_prioridade,
               jira_mover_prioridades, jira_salvar_padrao_prioridade,
               jira_listar_esquemas_prioridade, jira_listar_prioridades_esquema, jira_usos_esquema_prioridade,
               jira_listar_prioridades_mapear, jira_criar_esquema_prioridade, jira_salvar_esquema_prioridade,
               jira_excluir_esquema_prioridade, jira_obter_tarefa,
               jira_listar_configs_campo, jira_listar_campos_config, jira_criar_config_campo,
               jira_salvar_config_campo, jira_excluir_config_campo, jira_salvar_campos_config,
               jira_listar_esquemas_config, jira_listar_itens_config, jira_listar_config_projetos,
               jira_criar_esquema_config, jira_salvar_esquema_config, jira_excluir_esquema_config,
               jira_adicionar_itens_config, jira_remover_itens_config, jira_associar_esquema_config,
               jira_listar_esquemas_campos, jira_obter_esquema_campos, jira_listar_campos_esquema,
               jira_usos_esquema_campos, jira_criar_esquema_campos, jira_copiar_esquema_campos,
               jira_salvar_esquema_campos, jira_excluir_esquema_campos, jira_adicionar_campos_esquema,
               jira_remover_campos_esquema, jira_salvar_parametros_campos, jira_remover_parametros_campos,
               jira_associar_esquema_campos,
               jira_listar_esquemas_notif, jira_obter_esquema_notif, jira_obter_notif_projeto,
               jira_listar_notif_projetos, jira_listar_eventos, jira_listar_papeis, jira_criar_esquema_notif,
               jira_salvar_esquema_notif, jira_excluir_esquema_notif, jira_adicionar_notificacoes,
               jira_remover_notificacao, jira_associar_esquema_notif]
