"""Cliente HTTP base das APIs Atlassian Cloud.

Resolve autenticacao (email + API token), retry em 429/5xx, a trava de host e a
paginacao. A paginacao nao depende do endpoint: `paginar` descobre o estilo pela
primeira resposta e segue os seguintes:
  - token ........... nextPageToken no topo (busca JQL, APIs novas)
  - startAt ......... startAt / maxResults (+ total / isLast), maior parte da /rest/api/3
  - start/limit ..... start / limit (+ isLastPage), /rest/servicedeskapi
  - token aninhado .. {chave: {values, nextPageToken}}, usos de status e workflow
  - lista inteira ... a API entrega tudo de uma vez; a fatia e local
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)
JSON = Dict[str, Any]
HOST_GATEWAY = "api.atlassian.com"

# 404 sem corpo nesses prefixos tem causa conhecida; vira LookupError explicando.
DICAS_404_SEM_CORPO = {
    "/rest/api/3/config/fieldschemes": (
        "HTTP 404 sem corpo em /config/fieldschemes: a API de esquemas de campos (beta) "
        "esta desligada neste site, ou o id informado nao existe."),
}

# Chaves de lista preferidas quando a resposta tem mais de uma lista no topo.
CHAVES_LISTA = ("values", "issues", "comments", "results", "fields", "workflows", "statuses")
# Chaves de controle de paginacao, tiradas da resposta montada com varias paginas.
CHAVES_PAGINACAO = {"nextPageToken", "startAt", "maxResults", "isLast", "start", "limit",
                    "isLastPage", "size"}
TAMANHO_PAGINA = 100


class ErroAtlassian(Exception):
    def __init__(self, status: int, url: str, corpo: Any):
        self.status, self.url, self.corpo = status, url, corpo
        self.mensagem = self._extrair_mensagem(corpo)
        super().__init__(f"HTTP {status} em {url}: {self.mensagem}")

    @staticmethod
    def _extrair_mensagem(corpo: Any) -> str:
        if isinstance(corpo, dict):
            partes = list(corpo.get("errorMessages") or [])
            erros = corpo.get("errors") or {}
            if isinstance(erros, dict):
                partes += [f"{k}: {v}" for k, v in erros.items()]
            else:  # Forms API: [{"status", "code", "title", "detail", "context"}]
                partes += [": ".join(str(e[c]) for c in ("title", "detail") if e.get(c)) if isinstance(e, dict)
                           else str(e) for e in erros]
            for chave in ("errorMessage", "message", "detail"):
                if corpo.get(chave):
                    partes.append(str(corpo[chave]))
            if partes:
                return "; ".join(partes)
        return str(corpo)[:500]

    @classmethod
    def de_resposta(cls, r: requests.Response) -> "ErroAtlassian":
        try:
            corpo = r.json()
        except ValueError:
            corpo = r.text[:500]
        return cls(r.status_code, r.url, corpo)


# Falhas previstas: o texto chega ao Claude para ele corrigir o pedido (JQL invalida,
# credencial ausente, host recusado...). Qualquer outra excecao o SDK esconde e so
# informa "Error executing tool".
ERROS_PREVISTOS = (ErroAtlassian, requests.RequestException, ValueError, LookupError, RuntimeError)


class ClienteHttp:
    def __init__(self, url: str, email: str, token: str,
                 sessao: Optional[requests.Session] = None, tentativas: int = 5):
        self.url = url.rstrip("/")
        self.host = urlparse(self.url).hostname
        self.tentativas = tentativas
        self.sessao = sessao or requests.Session()
        self.sessao.auth = (email, token)
        self.sessao.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            # libera endpoints experimentais do JSM
            "X-ExperimentalApi": "opt-in",
        })
        self._cloud_id: Optional[str] = None

    # ----------------------------------------------------------------- base
    def montar_url(self, caminho: str) -> str:
        """Aceita caminho relativo ao site (/rest/...) ou URL completa do site ou do
        gateway api.atlassian.com. "{cloudId}" e substituido. Qualquer outro host e
        recusado, para o token nunca sair para fora da Atlassian."""
        if "{cloudId}" in caminho:
            caminho = caminho.replace("{cloudId}", self.cloud_id())
        if not caminho.startswith("http"):
            return f"{self.url}/{caminho.lstrip('/')}"
        partes = urlparse(caminho)
        if partes.scheme != "https" or partes.hostname not in (self.host, HOST_GATEWAY):
            raise ValueError(f"Host nao permitido: {partes.hostname}. Use o site ({self.host}) ou {HOST_GATEWAY}.")
        return caminho

    def requisitar(self, metodo: str, caminho: str, com_status: bool = False, **kw) -> Any:
        """Uma requisicao com retry em 429/5xx. com_status=True devolve (status, corpo)."""
        url = self.montar_url(caminho)
        kw.setdefault("timeout", 60)
        resposta = None
        for tentativa in range(self.tentativas):
            resposta = self.sessao.request(metodo, url, **kw)
            if resposta.status_code == 429 or resposta.status_code >= 500:
                espera = min(float(resposta.headers.get("Retry-After", 2 ** tentativa)), 60)
                log.warning("HTTP %s em %s, nova tentativa em %.0fs", resposta.status_code, url, espera)
                time.sleep(espera)
                continue
            if not resposta.ok:
                erro = ErroAtlassian.de_resposta(resposta)
                dica = _dica_404(erro, url)
                if dica:
                    raise LookupError(dica) from erro
                raise erro
            corpo = resposta.json() if resposta.content else None
            return (resposta.status_code, corpo) if com_status else corpo
        raise ErroAtlassian.de_resposta(resposta)

    def get(self, caminho: str, params: Optional[dict] = None, **kw) -> Any:
        return self.requisitar("GET", caminho, params=params, **kw)

    def post(self, caminho: str, json: Optional[Any] = None, **kw) -> Any:
        return self.requisitar("POST", caminho, json=json, **kw)

    def cloud_id(self) -> str:
        if not self._cloud_id:
            self._cloud_id = self.get("/_edge/tenant_info")["cloudId"]
        return self._cloud_id

    # ------------------------------------------------------------ paginacao
    def paginar(self, metodo: str, caminho: str, params: Optional[dict] = None, corpo: Optional[Any] = None,
                limite: Optional[int] = None, inicio: int = 0, filtro: Optional[Dict[str, list]] = None,
                maximo_itens: int = 500, maximo_requisicoes: int = 50) -> Tuple[Any, JSON]:
        """Junta itens da lista principal seguindo a paginacao que a primeira resposta mostra.

        limite: quantos itens devolver (com filtro, quantos que casaram). Sem limite,
        segue ate acabar, respeitando maximo_itens e maximo_requisicoes.
        inicio: so para lista inteira (sem paginacao na API): posicao da fatia local.
        filtro: {chave: [valores]} por igualdade (texto); chave com ponto para aninhado.

        Devolve (dados, meta). dados tem a forma da API, com a lista principal no lugar
        e sem as chaves de controle de paginacao. meta traz `continuar` (params ou corpo
        exatos para a proxima chamada, ou None no fim) ou, na lista inteira, `total`,
        `inicio` e `proximo_inicio`; com filtro, `sem_correspondencia`.
        """
        alvo = min(limite or maximo_itens, maximo_itens)
        params = dict(params or {})
        corpo = dict(corpo) if isinstance(corpo, dict) else corpo
        _tamanho_inicial(metodo, caminho, params, corpo, alvo, bool(filtro))

        primeira = self.requisitar(metodo, caminho, params=params or None, json=corpo)
        rota = lista_principal(primeira)
        if rota is None:
            raise ValueError("A resposta nao tem lista para paginar ou filtrar; chame sem limite, inicio e filtro.")
        estilo = _estilo(primeira, rota)
        if inicio and estilo != "inteira":
            raise ValueError(f"inicio vale so para lista que a API entrega inteira; esta pagina por {estilo}. "
                             "Use os params (ou o corpo) devolvidos em continuar.")

        casa = _casador(filtro)
        if estilo == "inteira":
            todos = [i for i in _obter(primeira, rota) if casa(i)]
            inicio = max(0, inicio)
            parte = todos[inicio:inicio + alvo]
            proximo = inicio + len(parte)
            meta: JSON = {"total": len(todos), "inicio": inicio,
                          "proximo_inicio": proximo if proximo < len(todos) else None}
            return _montar(primeira, rota, parte), _com_filtro(meta, filtro, todos)

        itens: list = []
        pagina, requisicoes, continuar = primeira, 1, None
        while True:
            lidos = _obter(pagina, rota)
            casados = [i for i in lidos if casa(i)]
            faltam = alvo - len(itens)
            proxima = _proxima(estilo, pagina, rota, params, corpo, metodo)
            if estilo in ("startAt", "start") and not filtro and len(casados) > faltam:
                # corta no meio da pagina: a proxima comeca no primeiro item nao entregue
                itens += casados[:faltam]
                chave = "startAt" if estilo == "startAt" else "start"
                continuar = _continuacao(metodo, params, corpo, {chave: _deslocamento(pagina, estilo) + faltam})
                break
            itens += casados  # token: a pagina nunca e cortada, o token aponta para depois dela
            if proxima is None or not lidos:
                break
            if len(itens) >= alvo or requisicoes >= maximo_requisicoes:
                continuar = _continuacao(metodo, params, corpo, proxima)
                break
            if estilo in ("token", "aninhado"):
                _ajustar_tamanho(metodo, params, corpo, min(TAMANHO_PAGINA, alvo - len(itens)), bool(filtro))
            _aplicar(metodo, params, corpo, proxima)
            pagina = self.requisitar(metodo, caminho, params=params or None, json=corpo)
            requisicoes += 1
        meta = {"continuar": continuar}
        return _montar(primeira, rota, itens), _com_filtro(meta, filtro, itens, continuar is not None)


# ------------------------------------------------------------------ apoio
def _dica_404(erro: ErroAtlassian, url: str) -> Optional[str]:
    if erro.status != 404 or erro.corpo:
        return None
    caminho = urlparse(url).path
    return next((m for prefixo, m in DICAS_404_SEM_CORPO.items() if caminho.startswith(prefixo)), None)


def lista_principal(dado: Any) -> Optional[List[str]]:
    """Rota ate a lista principal: [] (a resposta e lista), [chave] ou [chave, "values"]."""
    if isinstance(dado, list):
        return []
    if not isinstance(dado, dict):
        return None
    listas = [k for k, v in dado.items() if isinstance(v, list)]
    for chave in CHAVES_LISTA:
        if chave in listas:
            return [chave]
    if len(listas) == 1:
        return listas
    aninhadas = [k for k, v in dado.items() if isinstance(v, dict) and isinstance(v.get("values"), list)]
    if len(aninhadas) == 1 and not listas:
        return [aninhadas[0], "values"]
    return None


def _obter(dado: Any, rota: List[str]) -> list:
    for chave in rota:
        dado = dado.get(chave) if isinstance(dado, dict) else None
    return dado or []


def _estilo(pagina: Any, rota: List[str]) -> str:
    if len(rota) == 2:
        return "aninhado"
    if not isinstance(pagina, dict):
        return "inteira"
    if "nextPageToken" in pagina:
        return "token"
    if "startAt" in pagina:
        return "startAt"
    if "start" in pagina and ("isLastPage" in pagina or "limit" in pagina):
        return "start"
    if "isLast" in pagina:  # busca JQL na ultima pagina: isLast sem token
        return "token"
    return "inteira"


def _deslocamento(pagina: JSON, estilo: str) -> int:
    return int(pagina.get("startAt" if estilo == "startAt" else "start") or 0)


def _proxima(estilo: str, pagina: Any, rota: List[str], params: dict, corpo: Any, metodo: str) -> Optional[JSON]:
    """O que muda na proxima requisicao, ou None no fim."""
    lidos = len(_obter(pagina, rota))
    if estilo == "token":
        token = pagina.get("nextPageToken")
        return None if not token or pagina.get("isLast") is True else {"nextPageToken": token}
    if estilo == "aninhado":
        token = (pagina.get(rota[0]) or {}).get("nextPageToken")
        return {"nextPageToken": token} if token else None
    if estilo == "startAt":
        proximo = _deslocamento(pagina, estilo) + lidos
        total = pagina.get("total")
        if pagina.get("isLast") is True or (total is not None and proximo >= total) or not lidos:
            return None
        return {"startAt": proximo}
    if estilo == "start":
        if pagina.get("isLastPage", True) or not lidos:
            return None
        return {"start": _deslocamento(pagina, estilo) + lidos}
    return None


def _no_corpo(metodo: str, corpo: Any) -> bool:
    return metodo != "GET" and isinstance(corpo, dict)


def _aplicar(metodo: str, params: dict, corpo: Any, mudanca: JSON) -> None:
    (corpo if _no_corpo(metodo, corpo) else params).update(mudanca)


def _continuacao(metodo: str, params: dict, corpo: Any, mudanca: JSON) -> JSON:
    if _no_corpo(metodo, corpo):
        return {"corpo": {**corpo, **mudanca}}
    return {"params": {**params, **mudanca}}


def _tamanho_inicial(metodo: str, caminho: str, params: dict, corpo: Any, alvo: int, com_filtro: bool) -> None:
    """Tamanho da primeira pagina quando o pedido nao define: o alvo (ate 100), ou 100 com filtro.
    Para o estilo token, que nao corta pagina, isso evita trazer mais que o pedido."""
    tamanho = TAMANHO_PAGINA if com_filtro else min(TAMANHO_PAGINA, alvo)
    if _no_corpo(metodo, corpo):
        corpo.setdefault("maxResults", tamanho)
    elif "maxResults" not in params and "limit" not in params:
        params["limit" if "/rest/servicedeskapi" in caminho else "maxResults"] = tamanho


def _ajustar_tamanho(metodo: str, params: dict, corpo: Any, tamanho: int, com_filtro: bool) -> None:
    if com_filtro or tamanho <= 0:
        return
    alvo = corpo if _no_corpo(metodo, corpo) else params
    if "maxResults" in alvo:
        alvo["maxResults"] = min(int(alvo["maxResults"]), tamanho)


def _valor(item: Any, chave: str) -> Any:
    for parte in chave.split("."):
        item = item.get(parte) if isinstance(item, dict) else None
    return item


def _textos(valor: Any) -> set:
    valores = valor if isinstance(valor, list) else [valor]
    return {str(v) for v in valores if v is not None}


def _casador(filtro: Optional[Dict[str, list]]):
    if not filtro:
        return lambda item: True
    pedidos = {chave: {str(v) for v in valores} for chave, valores in filtro.items()}
    return lambda item: all(_textos(_valor(item, c)) & v for c, v in pedidos.items())


def _com_filtro(meta: JSON, filtro: Optional[Dict[str, list]], itens: list, incompleto: bool = False) -> JSON:
    if filtro:
        faltando = {chave: sorted({str(v) for v in valores}
                                  - set().union(*(_textos(_valor(i, chave)) for i in itens)))
                    for chave, valores in filtro.items()}
        meta["sem_correspondencia"] = {c: v for c, v in faltando.items() if v}
        if incompleto:
            meta["sem_correspondencia_parcial"] = True
    return meta


def _montar(primeira: Any, rota: List[str], itens: list) -> Any:
    """A forma da primeira pagina, com os itens juntados no lugar e sem controle de paginacao."""
    if not rota:
        return itens
    dados = {k: v for k, v in primeira.items() if k not in CHAVES_PAGINACAO}
    if len(rota) == 1:
        dados[rota[0]] = itens
    else:
        dados[rota[0]] = {k: v for k, v in primeira[rota[0]].items() if k not in CHAVES_PAGINACAO}
        dados[rota[0]]["values"] = itens
    return dados


# ------------------------------------------------------------- singleton
_cliente: Optional[ClienteHttp] = None


def cliente() -> ClienteHttp:
    """Cliente do site configurado (config.py), criado na primeira chamada."""
    global _cliente
    if _cliente is None:
        from .. import config
        config.validar()
        _cliente = ClienteHttp(config.URL, config.EMAIL, config.TOKEN)
    return _cliente
