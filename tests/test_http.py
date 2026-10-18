"""Testes do cliente HTTP (paginacao, hosts, retry, erros), sem rede.
Rodar: python -m unittest discover -s tests"""
import copy
import unittest
from unittest import mock

from atlassian_mcp_for_admins.nucleo.http import ClienteHttp, ErroAtlassian, lista_principal


class Resposta:
    def __init__(self, corpo=None, status=200, headers=None):
        self.corpo, self.status_code, self.headers = corpo, status, headers or {}
        self.ok = status < 400
        self.content = b"x" if corpo is not None else b""
        self.url, self.text = "https://x/teste", "" if corpo is None else str(corpo)

    def json(self):
        if self.corpo is None:
            raise ValueError("sem corpo")
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


class TestListaPrincipal(unittest.TestCase):
    def test_rotas(self):
        self.assertEqual(lista_principal([1]), [])
        self.assertEqual(lista_principal({"values": [], "outra": []}), ["values"])
        self.assertEqual(lista_principal({"issues": [], "names": {}}), ["issues"])
        self.assertEqual(lista_principal({"x": 1, "coisas": []}), ["coisas"])
        self.assertEqual(lista_principal({"statusId": "1", "projects": {"values": []}}), ["projects", "values"])
        self.assertIsNone(lista_principal({"id": 1, "design": {}}))
        self.assertIsNone(lista_principal({"a": [], "b": []}))


class TestPaginar(unittest.TestCase):
    def test_start_at_segue_ate_o_total(self):
        c, s = cliente([Resposta({"startAt": 0, "maxResults": 2, "total": 3, "values": [1, 2]}),
                        Resposta({"startAt": 2, "maxResults": 2, "total": 3, "values": [3]})])
        dados, meta = c.paginar("GET", "/x", limite=10)
        self.assertEqual(dados, {"total": 3, "values": [1, 2, 3]})
        self.assertIsNone(meta["continuar"])
        self.assertEqual([ch[2]["startAt"] for ch in s.chamadas[1:]], [2])
        self.assertEqual(s.chamadas[0][2]["maxResults"], 10)

    def test_start_at_corta_no_limite_e_aponta_o_proximo(self):
        c, s = cliente([Resposta({"startAt": 0, "maxResults": 5, "isLast": False, "values": [1, 2, 3, 4, 5]})])
        dados, meta = c.paginar("GET", "/x", params={"maxResults": 5}, limite=3)
        self.assertEqual(dados["values"], [1, 2, 3])
        self.assertEqual(meta["continuar"], {"params": {"maxResults": 5, "startAt": 3}})

    def test_start_limit_do_servicedesk(self):
        c, s = cliente([Resposta({"start": 0, "limit": 2, "isLastPage": False, "values": [1, 2]}),
                        Resposta({"start": 2, "limit": 2, "isLastPage": True, "values": [3]})])
        dados, meta = c.paginar("GET", "/rest/servicedeskapi/servicedesk", limite=50)
        self.assertEqual(dados, {"values": [1, 2, 3]})
        self.assertEqual(s.chamadas[0][2], {"limit": 50})
        self.assertEqual(s.chamadas[1][2]["start"], 2)
        self.assertIsNone(meta["continuar"])

    def test_token_aninhado(self):
        c, s = cliente([Resposta({"statusId": "1", "workflows": {"values": [{"id": "a"}], "nextPageToken": "T"}}),
                        Resposta({"statusId": "1", "workflows": {"values": [{"id": "b"}]}})])
        dados, meta = c.paginar("GET", "/x", limite=10)
        self.assertEqual(dados, {"statusId": "1", "workflows": {"values": [{"id": "a"}, {"id": "b"}]}})
        self.assertEqual(s.chamadas[1][2]["nextPageToken"], "T")
        self.assertIsNone(meta["continuar"])

    def test_busca_jql_token_no_corpo_e_tamanho_exato(self):
        """O token aponta para depois da pagina: o maxResults pede so o que falta."""
        c, s = cliente([Resposta({"issues": [{"key": f"A-{i}"} for i in range(100)], "nextPageToken": "N"}),
                        Resposta({"issues": [{"key": "B"}] * 20, "nextPageToken": "M"})])
        dados, meta = c.paginar("POST", "/rest/api/3/search/jql", corpo={"jql": "x"}, limite=120)
        self.assertEqual(len(dados["issues"]), 120)
        self.assertEqual([ch[3]["maxResults"] for ch in s.chamadas], [100, 20])
        self.assertEqual(s.chamadas[1][3]["nextPageToken"], "N")
        self.assertEqual(meta["continuar"], {"corpo": {"jql": "x", "maxResults": 20, "nextPageToken": "M"}})
        self.assertNotIn("nextPageToken", dados)

    def test_busca_jql_ultima_pagina(self):
        c, _ = cliente([Resposta({"issues": [{"key": "A-1"}], "isLast": True, "nextPageToken": "lixo"})])
        dados, meta = c.paginar("POST", "/rest/api/3/search/jql", corpo={"jql": "x"}, limite=50)
        self.assertEqual(dados, {"issues": [{"key": "A-1"}]})
        self.assertIsNone(meta["continuar"])

    def test_busca_jql_so_isLast(self):
        c, _ = cliente([Resposta({"issues": [{"key": "A-1"}], "isLast": True})])
        _, meta = c.paginar("POST", "/rest/api/3/search/jql", corpo={"jql": "x"}, limite=5)
        self.assertEqual(meta, {"continuar": None})

    def test_lista_inteira_fatia_local(self):
        c, s = cliente([Resposta([{"id": i} for i in range(5)])])
        dados, meta = c.paginar("GET", "/x", limite=2, inicio=2)
        self.assertEqual(dados, [{"id": 2}, {"id": 3}])
        self.assertEqual(meta, {"total": 5, "inicio": 2, "proximo_inicio": 4})
        self.assertEqual(len(s.chamadas), 1)

    def test_inicio_em_lista_paginada_e_recusado(self):
        c, _ = cliente([Resposta({"startAt": 0, "values": [1], "isLast": False})])
        with self.assertRaises(ValueError):
            c.paginar("GET", "/x", inicio=5)

    def test_sem_lista_e_recusado(self):
        c, _ = cliente([Resposta({"id": 1})])
        with self.assertRaises(ValueError):
            c.paginar("GET", "/x", limite=5)

    def test_filtro_percorre_paginas_e_aponta_o_que_faltou(self):
        c, s = cliente([Resposta({"startAt": 0, "isLast": False, "values": [{"id": "a"}, {"id": "b"}]}),
                        Resposta({"startAt": 2, "isLast": True, "values": [{"id": "c"}, {"id": 10}]})])
        dados, meta = c.paginar("GET", "/x", filtro={"id": ["c", "10", "zz"]})
        self.assertEqual(dados["values"], [{"id": "c"}, {"id": 10}])
        self.assertEqual(meta["sem_correspondencia"], {"id": ["zz"]})
        self.assertIsNone(meta["continuar"])
        self.assertEqual(s.chamadas[0][2]["maxResults"], 100)

    def test_filtro_aninhado_e_em_lista(self):
        c, _ = cliente([Resposta([{"schema": {"type": "user"}, "tags": ["x", "y"]},
                                  {"schema": {"type": "date"}, "tags": ["y"]}])])
        dados, _ = c.paginar("GET", "/x", filtro={"schema.type": ["user"], "tags": ["x"]})
        self.assertEqual(len(dados), 1)

    def test_filtro_para_no_teto_de_requisicoes(self):
        paginas = [Resposta({"startAt": i, "isLast": False, "values": [{"id": i}]}) for i in range(3)]
        c, s = cliente(paginas)
        _, meta = c.paginar("GET", "/x", filtro={"id": ["99"]}, maximo_requisicoes=3)
        self.assertEqual(len(s.chamadas), 3)
        self.assertEqual(meta["continuar"], {"params": {"maxResults": 100, "startAt": 3}})
        self.assertTrue(meta["sem_correspondencia_parcial"])


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

    def test_erro_legivel_da_forms_api(self):
        """A Forms API devolve errors como lista de objetos, nao como mapa."""
        corpo = {"errors": [{"status": 422, "code": "INVALID_ANSWERS", "title": "Respostas invalidas",
                             "detail": "Pergunta 2 obrigatoria"}]}
        c, _ = cliente([Resposta(corpo, 422)])
        with self.assertRaises(ErroAtlassian) as ctx:
            c.requisitar("PUT", "/x")
        self.assertIn("Respostas invalidas: Pergunta 2 obrigatoria", str(ctx.exception))

    def test_404_sem_corpo_do_fieldschemes_explica_o_beta(self):
        c, _ = cliente([Resposta(None, 404)])
        with self.assertRaises(LookupError) as ctx:
            c.get("/rest/api/3/config/fieldschemes")
        self.assertIn("beta", str(ctx.exception))

    def test_404_com_corpo_continua_erro_da_api(self):
        c, _ = cliente([Resposta({"errorMessages": ["Nao existe"]}, 404)])
        with self.assertRaises(ErroAtlassian):
            c.get("/rest/api/3/config/fieldschemes/1")

    def test_404_sem_corpo_em_outro_caminho_continua_erro_da_api(self):
        c, _ = cliente([Resposta(None, 404)])
        with self.assertRaises(ErroAtlassian):
            c.get("/rest/api/3/screens/1")

    def test_com_status(self):
        c, _ = cliente([Resposta(None, 204)])
        self.assertEqual(c.requisitar("PUT", "/x", com_status=True, json={}), (204, None))


if __name__ == "__main__":
    unittest.main()
