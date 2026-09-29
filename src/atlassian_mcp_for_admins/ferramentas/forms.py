"""Jira Forms: templates de formulario por projeto e formularios anexados a issues.

`projeto`: chave ou id do projeto. Ids de formulario sao UUIDs.
"""
from typing import List, Optional

from ..apis import obter
from ..apis.forms import design_vazio, publicacao
from ._comum import escrita, leitura, limpar, usa_skill

SKILL = "forms-design"

PARTES_DESIGN = ["settings", "questions", "sections", "conditions", "layout"]
PARTES_PADRAO = ["settings", "questions", "sections", "conditions"]


def _recortar(template: Optional[dict], partes: Optional[List[str]]) -> Optional[dict]:
    if not template:
        return template
    escolhidas = partes or PARTES_PADRAO
    design = template.get("design") or {}
    return {**{k: v for k, v in template.items() if k != "design"},
            "design": {k: design[k] for k in escolhidas if k in design}}


@leitura
def forms_listar(projeto: str) -> dict:
    """Templates de formulario do projeto (id, nome, request types onde aparecem)."""
    itens = obter().forms.templates(projeto)
    return {"total": len(itens), "formularios": itens}


@leitura
@usa_skill(SKILL)
def forms_obter(projeto: str, form_id: str, partes: Optional[List[str]] = None) -> dict:
    """Um template de formulario com o design e a publicacao.

    partes: quais partes do design trazer, entre settings, questions, sections,
    conditions e layout. Padrao: todas menos layout, que e o documento visual e
    costuma ser muito grande.
    """
    return _recortar(obter().forms.template(projeto, form_id), partes)


@leitura
@usa_skill(SKILL)
def forms_obter_do_request_type(projeto: str, request_type_id: str, partes: Optional[List[str]] = None) -> dict:
    """O template que o portal exibe em um request type (null se nenhum). partes: como em forms_obter."""
    at = obter()
    sd = at.jsm.service_desk(projeto)["id"]
    return {"request_type_id": request_type_id,
            "formulario": _recortar(at.forms.do_request_type(sd, request_type_id), partes)}


@escrita
@usa_skill(SKILL)
def forms_criar(projeto: str, nome: str, portal_request_type_ids: Optional[List[int]] = None,
                design: Optional[dict] = None, publish: Optional[dict] = None) -> dict:
    """Cria um template de formulario no projeto.

    Sem `design`, cria o formulario vazio (sem perguntas). portal_request_type_ids:
    request types em que ele aparece no portal. `publish`, se enviado, substitui o
    bloco de publicacao inteiro (formato da Forms API).
    """
    corpo = {"design": design or design_vazio(nome),
             "publish": publish or publicacao(portal_request_type_ids)}
    return limpar(obter().forms.criar_template(projeto, corpo))


@escrita
@usa_skill(SKILL)
def forms_salvar(projeto: str, form_id: str, design: dict, publish: Optional[dict] = None) -> dict:
    """Substitui o design (e opcionalmente a publicacao) de um template existente.

    E substituicao completa: leia antes com forms_obter(partes com layout) e envie
    o design inteiro, nao so a parte alterada.
    """
    corpo = {"design": design}
    if publish is not None:
        corpo["publish"] = publish
    return limpar(obter().forms.salvar_template(projeto, form_id, corpo))


@escrita
def forms_excluir(projeto: str, form_id: str) -> dict:
    """Exclui um template de formulario. Nao ha como desfazer."""
    obter().forms.excluir_template(projeto, form_id)
    return {"excluido": form_id}


@leitura
def forms_listar_da_issue(chave: str) -> dict:
    """Formularios anexados a uma issue (id, nome, status de envio)."""
    itens = obter().forms.da_issue(chave)
    return {"total": len(itens), "formularios": itens}


@leitura
def forms_obter_respostas(chave: str, form_id: str) -> dict:
    """Respostas de um formulario anexado a uma issue."""
    return limpar(obter().forms.respostas(chave, form_id))


FERRAMENTAS = [forms_listar, forms_obter, forms_obter_do_request_type, forms_criar, forms_salvar,
               forms_excluir, forms_listar_da_issue, forms_obter_respostas]
