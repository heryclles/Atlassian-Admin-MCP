"""As ferramentas do servidor: conexao e tres chamadas genericas, divididas por risco.

atlassian_ler (leitura), atlassian_escrever (POST/PUT/PATCH) e atlassian_excluir
(DELETE) falam com qualquer endpoint das APIs Atlassian. O conhecimento de cada
endpoint (caminho, payload, paginacao, armadilhas) fica nas skills do plugin; aqui
so ha mecanica: paginacao, filtro por igualdade, recorte e trava de tamanho.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from ..nucleo.http import ERROS_PREVISTOS, cliente
from ._comum import escrita, leitura, limpar, usa_skill

log = logging.getLogger(__name__)

SKILL = "atlassian-chamadas"

# POST que so consulta: entram em atlassian_ler. Lista fechada; incluir um caminho
# aqui exige que o endpoint nao altere nada no site.
CONSULTAS_POST = {
    "/rest/api/3/search/jql",
    "/rest/api/3/search/approximate-count",
    "/rest/api/3/priorityscheme/mappings",
    "/rest/api/3/issue/bulkfetch",
    "/rest/api/3/jql/parse",
    "/rest/api/3/workflows",
}
METODOS_ESCRITA = {"POST", "PUT", "PATCH"}
MAXIMO_CAMINHOS = 20
MAXIMO_ITENS = 500
# Acima disso o Claude Code tira o resultado do chat e grava em arquivo.
TETO_CARACTERES = 50_000
MINIMO_INTENCAO = 10


def _conferir_intencao(intencao: str, metodo: str, caminho: Any) -> None:
    if len((intencao or "").strip()) < MINIMO_INTENCAO:
        raise ValueError("intencao e obrigatoria: diga em portugues, numa frase, o que esta chamada faz "
                         "(ex.: \"Listar as abas da tela 10000\").")
    log.info("%s %s | %s", metodo, caminho, intencao.strip())


def _projetar(dado: Any, arvore: dict) -> Any:
    if not arvore:
        return dado
    if isinstance(dado, list):
        return [_projetar(i, arvore) for i in dado]
    if isinstance(dado, dict):
        return {k: _projetar(dado[k], sub) for k, sub in arvore.items() if k in dado}
    return dado


def _arvore(caminhos: List[str]) -> dict:
    arvore: dict = {}
    for caminho in caminhos:
        no = arvore
        for parte in caminho.split("."):
            no = no.setdefault(parte, {})
    return arvore


def _conferir_tamanho(resultado: Any) -> Any:
    tamanho = len(json.dumps(resultado, ensure_ascii=False, default=str))
    if tamanho > TETO_CARACTERES:
        raise ValueError(
            f"Resposta com {tamanho} caracteres, acima do teto de {TETO_CARACTERES}. Peca menos: "
            "limite (segue a paginacao da API; em lista entregue inteira, fatia com inicio), filtro por "
            "igualdade, manter so os campos necessarios, ou os parametros de pagina e de campos do proprio "
            "endpoint (fields, expand, maxResults).")
    return resultado


def _ler_um(caminho: str, params: Optional[dict], corpo: Optional[Any], limite: Optional[int],
            inicio: int, filtro: Optional[Dict[str, list]], manter: Optional[List[str]]) -> Any:
    metodo = "GET"
    if corpo is not None:
        if urlparse(caminho).path.rstrip("/") not in CONSULTAS_POST:
            raise ValueError(f"atlassian_ler so envia corpo (POST) para consultas: {sorted(CONSULTAS_POST)}. "
                             "Para criar ou alterar, use atlassian_escrever.")
        metodo = "POST"
    http = cliente()
    meta: dict = {}
    if limite is None and not inicio and not filtro:
        dados = http.requisitar(metodo, caminho, params=params, json=corpo)
    else:
        if limite is not None and not 1 <= int(limite) <= MAXIMO_ITENS:
            raise ValueError(f"limite vai de 1 a {MAXIMO_ITENS}")
        dados, meta = http.paginar(metodo, caminho, params=params, corpo=corpo,
                                   limite=int(limite) if limite else None, inicio=int(inicio or 0),
                                   filtro=filtro, maximo_itens=MAXIMO_ITENS)
    dados = limpar(dados)
    if manter:
        dados = _projetar(dados, _arvore(manter))
    if not meta:
        return dados
    return {"itens": dados, **meta} if isinstance(dados, list) else {**dados, **meta}


@leitura
@usa_skill(SKILL)
def atlassian_ler(intencao: str, caminho: Union[str, List[str]], params: Optional[Dict[str, Any]] = None,
                  corpo: Optional[Any] = None, limite: Optional[int] = None, inicio: int = 0,
                  filtro: Optional[Dict[str, List[Any]]] = None, manter: Optional[List[str]] = None) -> Any:
    """Le qualquer endpoint das APIs Atlassian Cloud (Jira, JSM, Forms...). Nao altera nada.

    intencao: obrigatoria. Uma frase em portugues dizendo o que a chamada faz; e o que
    o usuario le no transcript (ex.: "Listar as abas da tela 10000").
    caminho: relativo ao site ("/rest/api/3/...", "/rest/servicedeskapi/...") ou URL em
    https://api.atlassian.com/... ("{cloudId}" e substituido). Uma lista de caminhos
    (ate 20) faz um GET por caminho e devolve {caminho: resposta}; o erro de um caminho
    vira {"erro": ...} so nele.
    params: query string. corpo: so para POST de consulta (busca e contagem JQL,
    issues em lote, validar JQL, workflows em lote, mapeamento de prioridades);
    qualquer outro POST e escrita.
    Sem limite, inicio e filtro, devolve a resposta como a API entregou (uma pagina).
    limite: ate 500 itens da lista principal, seguindo a paginacao da API (token,
    startAt, start/limit ou token aninhado). A resposta traz `continuar` com os params
    ou o corpo para pedir o resto; null quando acabou.
    inicio: fatia de lista que a API entrega inteira (sem paginacao); devolve total e
    proximo_inicio.
    filtro: {"chave": [valores]}, igualdade exata (chave com ponto para aninhado);
    percorre as paginas e devolve so os itens que casaram e sem_correspondencia.
    manter: caminhos com ponto que ficam na resposta (ex. ["values.id", "values.name"],
    ["design.questions"]); listas no caminho valem para cada item.
    Resposta acima de 50 mil caracteres e recusada com a orientacao de pedir menos.
    """
    _conferir_intencao(intencao, "POST" if corpo is not None else "GET", caminho)
    if isinstance(caminho, list):
        if not caminho or len(caminho) > MAXIMO_CAMINHOS:
            raise ValueError(f"caminho em lista aceita de 1 a {MAXIMO_CAMINHOS} itens")
        if corpo is not None:
            raise ValueError("caminho em lista faz so GET; corpo vale para um caminho")
        resultado = {}
        for c in caminho:
            try:
                resultado[c] = _ler_um(c, params, None, limite, inicio, filtro, manter)
            except ERROS_PREVISTOS as erro:
                resultado[c] = {"erro": str(erro)}
        return _conferir_tamanho(resultado)
    return _conferir_tamanho(_ler_um(caminho, params, corpo, limite, inicio, filtro, manter))


@escrita
@usa_skill(SKILL)
def atlassian_escrever(intencao: str, metodo: str, caminho: str, corpo: Optional[Any] = None,
                       params: Optional[Dict[str, Any]] = None) -> dict:
    """Cria ou altera dados no site: POST, PUT ou PATCH em qualquer endpoint Atlassian.

    intencao: obrigatoria. Uma frase em portugues dizendo o que muda no site; e o que
    o usuario le no pedido de confirmacao (ex.: "Criar a aba Detalhes na tela 10000").
    metodo: POST, PUT ou PATCH. Para excluir use atlassian_excluir; para ler,
    atlassian_ler. caminho: mesmas regras de atlassian_ler. corpo: JSON enviado como esta.
    Devolve {"http": status, "resposta": corpo}: 201 criou, 204 sem corpo, 207 lote
    com resultado por item (confira cada um), 303 ja seguido ate a tarefa assincrona.
    """
    metodo = (metodo or "").upper()
    if metodo not in METODOS_ESCRITA:
        outra = "atlassian_excluir" if metodo == "DELETE" else "atlassian_ler"
        raise ValueError(f"metodo deve ser um de {sorted(METODOS_ESCRITA)}; para {metodo or 'ler'} use {outra}")
    _conferir_intencao(intencao, metodo, caminho)
    status, resposta = cliente().requisitar(metodo, caminho, com_status=True, json=corpo, params=params)
    return {"http": status, "resposta": limpar(resposta)}


@escrita
@usa_skill(SKILL)
def atlassian_excluir(intencao: str, caminho: str, corpo: Optional[Any] = None,
                      params: Optional[Dict[str, Any]] = None) -> dict:
    """Exclui no site: DELETE em qualquer endpoint Atlassian.

    intencao: obrigatoria. Uma frase em portugues dizendo o que sera excluido; e o que
    o usuario le no pedido de confirmacao (ex.: "Excluir a aba vazia 10200 da tela 10000").
    caminho: mesmas regras de atlassian_ler. corpo: alguns DELETE em lote recebem JSON
    (ex. /rest/api/3/config/fieldschemes/fields).
    Devolve {"http": status, "resposta": corpo}; exclusao assincrona traz a tarefa.
    """
    _conferir_intencao(intencao, "DELETE", caminho)
    status, resposta = cliente().requisitar("DELETE", caminho, com_status=True, json=corpo, params=params)
    return {"http": status, "resposta": limpar(resposta)}


@leitura
def atlassian_conexao() -> dict:
    """Mostra o site configurado, o usuario autenticado e o cloudId."""
    http = cliente()
    eu = http.get("/rest/api/3/myself")
    return {"site": http.url, "usuario": eu.get("displayName"), "email": eu.get("emailAddress"),
            "account_id": eu.get("accountId"), "cloud_id": http.cloud_id()}


FERRAMENTAS = [atlassian_conexao, atlassian_ler, atlassian_escrever, atlassian_excluir]
