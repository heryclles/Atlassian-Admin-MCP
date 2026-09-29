"""Jira Service Management: service desks e request types.

Parametro `projeto`: chave do projeto (ex. SUP), id do projeto ou id do service desk.
"""
from typing import Optional

from ..apis import obter
from ._comum import escrita, leitura, limpar


def _sd_id(projeto: str) -> str:
    return obter().jsm.service_desk(projeto)["id"]


@leitura
def jsm_listar_service_desks() -> dict:
    """Todos os service desks visiveis (id, chave e nome do projeto)."""
    itens = limpar(list(obter().jsm.service_desks()))
    return {"total": len(itens), "service_desks": itens}


@leitura
def jsm_listar_request_types(projeto: str) -> dict:
    """Request types de um service desk."""
    sd = _sd_id(projeto)
    itens = limpar(list(obter().jsm.request_types(sd)))
    return {"service_desk_id": sd, "total": len(itens), "request_types": itens}


@leitura
def jsm_obter_request_type(projeto: str, request_type_id: str) -> dict:
    """Um request type pelo id."""
    return limpar(obter().jsm.request_type(_sd_id(projeto), request_type_id))


@leitura
def jsm_listar_campos_request_type(projeto: str, request_type_id: str) -> dict:
    """Campos do Jira exibidos no request type (fora do Forms), com obrigatoriedade e valores validos."""
    return limpar(obter().jsm.request_type_campos(_sd_id(projeto), request_type_id))


@leitura
def jsm_listar_grupos_request_type(projeto: str) -> dict:
    """Grupos do portal (abas que organizam os request types)."""
    itens = limpar(list(obter().jsm.grupos_request_type(_sd_id(projeto))))
    return {"total": len(itens), "grupos": itens}


@escrita
def jsm_criar_request_type(projeto: str, nome: str, issue_type_id: str,
                           descricao: str = "", ajuda: str = "") -> dict:
    """Cria um request type (API experimental).

    issue_type_id precisa existir no esquema de tipos de issue do projeto.
    A API nao define grupo do portal, campos nem icone: isso e feito na tela.
    """
    return limpar(obter().jsm.criar_request_type(_sd_id(projeto), nome, issue_type_id, descricao, ajuda))


@escrita
def jsm_excluir_request_type(projeto: str, request_type_id: str) -> dict:
    """Exclui um request type (API experimental). Nao ha como desfazer."""
    obter().jsm.excluir_request_type(_sd_id(projeto), request_type_id)
    return {"excluido": request_type_id}


FERRAMENTAS = [jsm_listar_service_desks, jsm_listar_request_types, jsm_obter_request_type,
               jsm_listar_campos_request_type, jsm_listar_grupos_request_type,
               jsm_criar_request_type, jsm_excluir_request_type]
