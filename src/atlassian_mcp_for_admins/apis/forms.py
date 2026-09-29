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

    def template(self, projeto: str, form_id: str, idioma: Optional[str] = None) -> JSON:
        params = {"requestLanguage": idioma} if idioma else None
        return self.http.get(f"{self._base()}/project/{projeto}/form/{form_id}", params=params)

    def criar_template(self, projeto: str, corpo: JSON) -> JSON:
        """corpo = {"design": {...}, "publish": {...}} (FormTemplateRequest)."""
        return self.http.post(f"{self._base()}/project/{projeto}/form", json=corpo)

    def salvar_template(self, projeto: str, form_id: str, corpo: JSON) -> JSON:
        return self.http.put(f"{self._base()}/project/{projeto}/form/{form_id}", json=corpo)

    def excluir_template(self, projeto: str, form_id: str) -> None:
        self.http.delete(f"{self._base()}/project/{projeto}/form/{form_id}")

    # --------------------------------------------------------------- portal
    # sd: id do service desk ou chave/id do projeto (a API aceita os dois)
    def do_request_type(self, sd, rt_id, idioma: Optional[str] = None) -> Optional[JSON]:
        """Template exibido no portal para o request type, ou None."""
        params = {"requestLanguage": idioma} if idioma else None
        try:
            return self.http.get(f"{self._base()}/servicedesk/{sd}/requesttype/{rt_id}/form", params=params)
        except ErroAtlassian as e:
            if e.status == 404:
                return None
            raise

    def dados_externos_request_type(self, sd, rt_id) -> JSON:
        return self.http.get(f"{self._base()}/servicedesk/{sd}/requesttype/{rt_id}/form/externaldata")

    # --------------------------------------------------------------- issues
    def da_issue(self, chave: str) -> List[JSON]:
        return self.http.get(f"{self._base()}/issue/{chave}/form")

    def formulario(self, chave: str, form_id: str) -> JSON:
        """Formulario completo da issue: design e state (respostas, status, visibilidade)."""
        return self.http.get(f"{self._base()}/issue/{chave}/form/{form_id}")

    def anexar(self, chave: str, template_id: str) -> JSON:
        return self.http.post(f"{self._base()}/issue/{chave}/form", json={"formTemplate": {"id": template_id}})

    def excluir_da_issue(self, chave: str, form_id: str) -> None:
        self.http.delete(f"{self._base()}/issue/{chave}/form/{form_id}")

    def salvar_respostas(self, chave: str, form_id: str, respostas: JSON) -> JSON:
        return self.http.put(f"{self._base()}/issue/{chave}/form/{form_id}", json={"answers": respostas})

    def acao(self, chave: str, form_id: str, acao: str) -> JSON:
        """acao: submit, reopen, external ou internal (PUT .../action/<acao>, sem corpo)."""
        return self.http.put(f"{self._base()}/issue/{chave}/form/{form_id}/action/{acao}")

    def copiar(self, origem: str, destino: str, form_ids: Optional[List[str]] = None) -> JSON:
        """Sem form_ids, a API copia todos os formularios da issue de origem."""
        corpo = {"ids": list(form_ids)} if form_ids else {}
        return self.http.post(f"{self._base()}/issue/{origem}/form/copy/{destino}", json=corpo)

    def respostas(self, chave: str, form_id: str) -> JSON:
        return self.http.get(f"{self._base()}/issue/{chave}/form/{form_id}/format/answers")

    def anexos(self, chave: str, form_id: str) -> JSON:
        return self.http.get(f"{self._base()}/issue/{chave}/form/{form_id}/attachment")

    def dados_externos(self, chave: str, form_id: str) -> JSON:
        return self.http.get(f"{self._base()}/issue/{chave}/form/{form_id}/externaldata")
