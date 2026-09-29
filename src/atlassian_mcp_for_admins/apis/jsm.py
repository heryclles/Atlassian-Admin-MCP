"""Jira Service Management REST API (/rest/servicedeskapi)."""
from typing import Iterator, Optional

from ..nucleo.http import JSON, ClienteHttp

BASE = "/rest/servicedeskapi"


class Jsm:
    def __init__(self, http: ClienteHttp):
        self.http = http

    def service_desks(self) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk")

    def service_desk(self, projeto: str) -> JSON:
        """Localiza o service desk pela chave, id do projeto ou id do service desk."""
        alvo = projeto.strip().upper()
        for sd in self.service_desks():
            if alvo in (sd.get("projectKey", "").upper(), str(sd.get("projectId")), str(sd.get("id"))):
                return sd
        raise LookupError(f"Service desk nao encontrado para o projeto {projeto}")

    # -------------------------------------------------------- request types
    def request_types(self, sd_id) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/requesttype")

    def request_type(self, sd_id, rt_id) -> JSON:
        return self.http.get(f"{BASE}/servicedesk/{sd_id}/requesttype/{rt_id}")

    def request_type_campos(self, sd_id, rt_id) -> JSON:
        return self.http.get(f"{BASE}/servicedesk/{sd_id}/requesttype/{rt_id}/field")

    def grupos_request_type(self, sd_id) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/requesttypegroup")

    def criar_request_type(self, sd_id, nome: str, issue_type_id: str,
                           descricao: str = "", ajuda: str = "") -> JSON:
        """Experimental. So aceita nome, descricao, ajuda e issue type (sem grupo, campos ou icone)."""
        return self.http.post(f"{BASE}/servicedesk/{sd_id}/requesttype",
                              json={"name": nome, "issueTypeId": issue_type_id,
                                    "description": descricao or "", "helpText": ajuda or ""})

    def excluir_request_type(self, sd_id, rt_id) -> None:
        self.http.delete(f"{BASE}/servicedesk/{sd_id}/requesttype/{rt_id}")

    # ---------------------------------------------------- filas e chamados
    def filas(self, sd_id) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/queue", params={"includeCount": "true"})

    def issues_da_fila(self, sd_id, fila_id, maximo: Optional[int] = None) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/queue/{fila_id}/issue", maximo=maximo)

    def organizacoes(self, sd_id) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/organization")

    def clientes(self, sd_id) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/servicedesk/{sd_id}/customer")

    def sla(self, chave: str) -> Iterator[JSON]:
        return self.http.paginar_start_limit(f"{BASE}/request/{chave}/sla")
