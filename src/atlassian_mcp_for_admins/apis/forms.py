"""Jira Forms (ProForma) REST API, em api.atlassian.com com cloudId."""
from typing import List, Optional

from ..nucleo.http import JSON, ClienteHttp, ErroAtlassian


def design_vazio(nome: str, idioma: str = "pt-BR") -> JSON:
    """Design minimo aceito pela API: sem perguntas, secoes ou condicoes."""
    return {
        "settings": {"name": nome, "language": idioma, "primaryLocale": idioma,
                     "translatedLocale": idioma, "submit": {"lock": False, "pdf": False}},
        "layout": [{"version": 1, "type": "doc", "content": [{"type": "paragraph", "content": []}]}],
        "conditions": {}, "sections": {}, "questions": {},
    }


def publicacao(portal_request_type_ids: Optional[List[int]] = None,
               criacao_request_type_ids: Optional[List[int]] = None,
               criacao_issue_type_ids: Optional[List[int]] = None) -> JSON:
    """Bloco "publish" do template: onde o formulario aparece."""
    return {
        "jira": {"issueCreateIssueTypeIds": list(criacao_issue_type_ids or []),
                 "issueCreateRequestTypeIds": list(criacao_request_type_ids or []),
                 "recommendedIssueRequestTypeIds": [], "submitOnCreate": True, "validateOnCreate": True},
        "portal": {"portalRequestTypeIds": list(portal_request_type_ids or []),
                   "submitOnCreate": True, "validateOnCreate": True},
    }


class Forms:
    def __init__(self, http: ClienteHttp):
        self.http = http

    def _base(self) -> str:
        return f"https://api.atlassian.com/jira/forms/cloud/{self.http.cloud_id()}"

    # ------------------------------------------------------------ templates
    def templates(self, projeto: str) -> List[JSON]:
        return self.http.get(f"{self._base()}/project/{projeto}/form")

    def template(self, projeto: str, form_id: str) -> JSON:
        return self.http.get(f"{self._base()}/project/{projeto}/form/{form_id}")

    def criar_template(self, projeto: str, corpo: JSON) -> JSON:
        """corpo = {"design": {...}, "publish": {...}} (FormTemplateRequest)."""
        return self.http.post(f"{self._base()}/project/{projeto}/form", json=corpo)

    def salvar_template(self, projeto: str, form_id: str, corpo: JSON) -> JSON:
        return self.http.put(f"{self._base()}/project/{projeto}/form/{form_id}", json=corpo)

    def excluir_template(self, projeto: str, form_id: str) -> None:
        self.http.delete(f"{self._base()}/project/{projeto}/form/{form_id}")

    def do_request_type(self, sd_id, rt_id) -> Optional[JSON]:
        """Template exibido no portal para o request type, ou None."""
        try:
            return self.http.get(f"{self._base()}/servicedesk/{sd_id}/requesttype/{rt_id}/form")
        except ErroAtlassian as e:
            if e.status == 404:
                return None
            raise

    # --------------------------------------------------------------- issues
    def da_issue(self, chave: str) -> List[JSON]:
        return self.http.get(f"{self._base()}/issue/{chave}/form")

    def respostas(self, chave: str, form_id: str) -> JSON:
        return self.http.get(f"{self._base()}/issue/{chave}/form/{form_id}/format/answers")
