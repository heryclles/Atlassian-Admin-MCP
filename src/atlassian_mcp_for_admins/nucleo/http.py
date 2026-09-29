"""Cliente HTTP base das APIs Atlassian Cloud.

Resolve autenticacao (email + API token), retry em 429/5xx e os estilos de
paginacao que aparecem nas APIs:
  - startAt / maxResults (+ total / isLast) ............ maior parte da /rest/api/3
  - start / limit (+ isLastPage) ....................... /rest/servicedeskapi
  - nextPageToken dentro de um objeto aninhado ......... usos de status e workflow
A paginacao por nextPageToken da busca JQL fica em apis/jira.py.
"""
import logging
import time
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)
JSON = Dict[str, Any]
HOST_GATEWAY = "api.atlassian.com"


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

    def requisitar(self, metodo: str, caminho: str, **kw) -> Any:
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
                raise ErroAtlassian.de_resposta(resposta)
            return resposta.json() if resposta.content else None
        raise ErroAtlassian.de_resposta(resposta)

    def get(self, caminho: str, params: Optional[dict] = None, **kw) -> Any:
        return self.requisitar("GET", caminho, params=params, **kw)

    def post(self, caminho: str, json: Optional[Any] = None, **kw) -> Any:
        return self.requisitar("POST", caminho, json=json, **kw)

    def put(self, caminho: str, json: Optional[Any] = None, **kw) -> Any:
        return self.requisitar("PUT", caminho, json=json, **kw)

    def delete(self, caminho: str, **kw) -> Any:
        return self.requisitar("DELETE", caminho, **kw)

    def cloud_id(self) -> str:
        if not self._cloud_id:
            self._cloud_id = self.get("/_edge/tenant_info")["cloudId"]
        return self._cloud_id

    # ----------------------------------------------------------- paginacoes
    def paginar_start_at(self, caminho: str, params: Optional[dict] = None, chave: str = "values",
                         tamanho: int = 100, maximo: Optional[int] = None) -> Iterator[JSON]:
        params = dict(params or {})
        inicio = contagem = 0
        while True:
            params.update(startAt=inicio, maxResults=tamanho)
            pagina = self.get(caminho, params=params)
            itens = pagina if isinstance(pagina, list) else (pagina or {}).get(chave) or []
            for item in itens:
                yield item
                contagem += 1
                if maximo and contagem >= maximo:
                    return
            if isinstance(pagina, list) or not itens or pagina.get("isLast") is True:
                return
            inicio += len(itens)
            total = pagina.get("total")
            if total is not None and inicio >= total:
                return

    def paginar_start_limit(self, caminho: str, params: Optional[dict] = None,
                            tamanho: int = 100, maximo: Optional[int] = None) -> Iterator[JSON]:
        params = dict(params or {})
        inicio = contagem = 0
        while True:
            params.update(start=inicio, limit=tamanho)
            pagina = self.get(caminho, params=params) or {}
            itens = pagina.get("values") or []
            for item in itens:
                yield item
                contagem += 1
                if maximo and contagem >= maximo:
                    return
            if pagina.get("isLastPage", True) or not itens:
                return
            inicio += len(itens)

    def paginar_token_aninhado(self, caminho: str, chave: str, tamanho: int = 200) -> Iterator[JSON]:
        """Formato {chave: {values: [...], nextPageToken}}."""
        params: dict = {"maxResults": tamanho}
        while True:
            bloco = (self.get(caminho, params=params) or {}).get(chave) or {}
            yield from bloco.get("values") or []
            token = bloco.get("nextPageToken")
            if not token:
                return
            params["nextPageToken"] = token
