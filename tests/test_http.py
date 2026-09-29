"""Testes da paginacao e do retry, sem rede. Rodar: python -m unittest discover -s tests"""
import copy
import unittest
from unittest import mock

from atlassian_mcp_for_admins.apis.jira import Jira
from atlassian_mcp_for_admins.nucleo.http import ClienteHttp, ErroAtlassian


class Resposta:
    def __init__(self, corpo=None, status=200, headers=None):
        self.corpo, self.status_code, self.headers = corpo, status, headers or {}
        self.ok = status < 400
        self.content = b"x" if corpo is not None else b""
        self.url, self.text = "https://x/teste", str(corpo)

    def json(self):
        return self.corpo


class SessaoFalsa:
    """Devolve as respostas na ordem e guarda as chamadas feitas."""
    def __init__(self, respostas):
        self.respostas, self.chamadas = list(respostas), []
        self.headers, self.auth = {}, None

    def request(self, metodo, url, **kw):
        self.chamadas.append((metodo, url, dict(kw.get("params") or {}), copy.deepcopy(kw.get("json"))))
        return self.respostas.pop(0)


def cliente(respostas):
    sessao = SessaoFalsa(respostas)
    return ClienteHttp("https://site.atlassian.net", "a@b.c", "t", sessao=sessao), sessao


class TestPaginacao(unittest.TestCase):
    def test_start_at_para_pelo_total(self):
        c, s = cliente([Resposta({"values": [1, 2], "total": 3}), Resposta({"values": [3], "total": 3})])
        self.assertEqual(list(c.paginar_start_at("/x", tamanho=2)), [1, 2, 3])
        self.assertEqual([ch[2]["startAt"] for ch in s.chamadas], [0, 2])

    def test_start_at_para_pelo_is_last(self):
        c, s = cliente([Resposta({"values": [1], "isLast": True})])
        self.assertEqual(list(c.paginar_start_at("/x")), [1])
        self.assertEqual(len(s.chamadas), 1)

    def test_start_at_respeita_maximo(self):
        c, s = cliente([Resposta({"values": [1, 2, 3], "total": 9})])
        self.assertEqual(list(c.paginar_start_at("/x", maximo=2)), [1, 2])

    def test_start_limit_is_last_page(self):
        c, s = cliente([Resposta({"values": [1, 2], "isLastPage": False}), Resposta({"values": [3], "isLastPage": True})])
        self.assertEqual(list(c.paginar_start_limit("/x", tamanho=2)), [1, 2, 3])
        self.assertEqual([ch[2]["start"] for ch in s.chamadas], [0, 2])

    def test_token_aninhado(self):
        c, s = cliente([Resposta({"workflows": {"values": [{"id": "a"}], "nextPageToken": "T"}}),
                        Resposta({"workflows": {"values": [{"id": "b"}], "nextPageToken": None}})])
        self.assertEqual([w["id"] for w in c.paginar_token_aninhado("/x", "workflows")], ["a", "b"])
        self.assertEqual(s.chamadas[1][2]["nextPageToken"], "T")

    def test_busca_jql_segue_next_page_token(self):
        c, s = cliente([Resposta({"issues": [{"key": "A-1"}], "nextPageToken": "N"}),
                        Resposta({"issues": [{"key": "A-2"}], "isLast": True})])
        self.assertEqual([i["key"] for i in Jira(c).buscar_jql("project = A")], ["A-1", "A-2"])
        self.assertEqual(s.chamadas[1][3]["nextPageToken"], "N")


class TestBuscaPagina(unittest.TestCase):
    def test_para_no_limite_e_devolve_token(self):
        c, s = cliente([Resposta({"issues": [{"key": "A-1"}, {"key": "A-2"}], "nextPageToken": "N"})])
        r = Jira(c).buscar_pagina("x", limite=2)
        self.assertEqual([i["key"] for i in r["issues"]], ["A-1", "A-2"])
        self.assertEqual(r["proximo_token"], "N")
        self.assertEqual(s.chamadas[0][3]["maxResults"], 2)

    def test_junta_paginas_ate_o_limite(self):
        c, s = cliente([Resposta({"issues": [{"key": f"A-{i}"} for i in range(100)], "nextPageToken": "N"}),
                        Resposta({"issues": [{"key": "B"}] * 20, "nextPageToken": "M"})])
        r = Jira(c).buscar_pagina("x", limite=120)
        self.assertEqual(len(r["issues"]), 120)
        self.assertEqual([ch[3]["maxResults"] for ch in s.chamadas], [100, 20])
        self.assertEqual(r["proximo_token"], "M")

    def test_fim_sem_token(self):
        c, _ = cliente([Resposta({"issues": [{"key": "A-1"}], "isLast": True, "nextPageToken": "lixo"})])
        self.assertIsNone(Jira(c).buscar_pagina("x", limite=50)["proximo_token"])


class TestHosts(unittest.TestCase):
    def test_recusa_host_de_fora(self):
        c, s = cliente([])
        for url in ("https://evil.example.com/x", "http://api.atlassian.com/x", "https://site.atlassian.net.evil.com/x"):
            with self.assertRaises(ValueError):
                c.get(url)
        self.assertEqual(s.chamadas, [])

    def test_aceita_site_e_gateway_e_troca_cloud_id(self):
        c, s = cliente([Resposta({"cloudId": "CID"}), Resposta({"ok": 1}), Resposta({"ok": 2})])
        c.get("https://api.atlassian.com/jira/forms/cloud/{cloudId}/x")
        c.get("rest/api/3/myself")
        self.assertEqual(s.chamadas[1][1], "https://api.atlassian.com/jira/forms/cloud/CID/x")
        self.assertEqual(s.chamadas[2][1], "https://site.atlassian.net/rest/api/3/myself")


class TestForms(unittest.TestCase):
    def test_corpo_de_formulario_vazio(self):
        from atlassian_mcp_for_admins.apis.forms import design_vazio, publicacao
        d = design_vazio("Teste")
        self.assertEqual(d["settings"]["name"], "Teste")
        self.assertEqual((d["questions"], d["sections"], d["conditions"]), ({}, {}, {}))
        self.assertEqual(publicacao([10])["portal"]["portalRequestTypeIds"], [10])


class TestNomes(unittest.TestCase):
    def test_prefixo_do_produto(self):
        from atlassian_mcp_for_admins.ferramentas import MODULOS
        prefixos = {"geral": "atlassian_", "jira": "jira_", "jsm": "jsm_", "forms": "forms_"}
        for m in MODULOS:
            prefixo = prefixos[m.__name__.split(".")[-1]]
            for f in m.FERRAMENTAS:
                self.assertTrue(f.__name__.startswith(prefixo), f.__name__)


class TestErros(unittest.TestCase):
    @mock.patch("atlassian_mcp_for_admins.nucleo.http.time.sleep")
    def test_retry_em_429(self, dormir):
        c, s = cliente([Resposta({}, 429, {"Retry-After": "1"}), Resposta({"ok": 1})])
        self.assertEqual(c.get("/x"), {"ok": 1})
        dormir.assert_called_once_with(1.0)

    def test_erro_legivel(self):
        c, _ = cliente([Resposta({"errorMessages": ["JQL invalida"], "errors": {}}, 400)])
        with self.assertRaises(ErroAtlassian) as ctx:
            c.get("/x")
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("JQL invalida", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
