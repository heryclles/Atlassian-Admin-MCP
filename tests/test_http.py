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

    def test_erro_legivel_da_forms_api(self):
        """A Forms API devolve errors como lista de objetos, nao como mapa."""
        corpo = {"errors": [{"status": 422, "code": "INVALID_ANSWERS", "title": "Respostas invalidas",
                             "detail": "Pergunta 2 obrigatoria"}]}
        c, _ = cliente([Resposta(corpo, 422)])
        with self.assertRaises(ErroAtlassian) as ctx:
            c.put("/x")
        self.assertIn("Respostas invalidas: Pergunta 2 obrigatoria", str(ctx.exception))


class TestFormsNaIssue(unittest.TestCase):
    def forms(self, respostas):
        from atlassian_mcp_for_admins.apis.forms import Forms
        c, s = cliente([Resposta({"cloudId": "CID"})] + respostas)
        return Forms(c), s

    def test_acoes_usam_put_sem_corpo(self):
        f, s = self.forms([Resposta({"status": "submitted"})])
        f.acao("SUP-1", "F1", "submit")
        self.assertEqual(s.chamadas[1][:2], ("PUT", "https://api.atlassian.com/jira/forms/cloud/CID/issue/SUP-1/form/F1/action/submit"))
        self.assertIsNone(s.chamadas[1][3])

    def test_corpos_de_escrita(self):
        f, s = self.forms([Resposta({"id": "N"}), Resposta({}), Resposta({"copiedForms": [], "errors": []}),
                           Resposta({"copiedForms": [], "errors": []})])
        f.anexar("SUP-1", "T1")
        f.salvar_respostas("SUP-1", "F1", {"1": {"text": "x"}})
        f.copiar("SUP-1", "SUP-2", ["F1"])
        f.copiar("SUP-1", "SUP-2")
        corpos = [ch[3] for ch in s.chamadas[1:]]
        self.assertEqual(corpos, [{"formTemplate": {"id": "T1"}}, {"answers": {"1": {"text": "x"}}}, {"ids": ["F1"]}, {}])
        self.assertTrue(s.chamadas[3][1].endswith("/issue/SUP-1/form/copy/SUP-2"))

    def test_idioma_vira_request_language(self):
        f, s = self.forms([Resposta({"design": {}}), Resposta({"design": {}})])
        f.template("SUP", "F1", "en-US")
        f.template("SUP", "F1")
        self.assertEqual([ch[2] for ch in s.chamadas[1:]], [{"requestLanguage": "en-US"}, {}])


class TestTelas(unittest.TestCase):
    def test_parametros_so_com_o_informado(self):
        c, s = cliente([Resposta({"values": []}), Resposta({"values": []})])
        j = Jira(c)
        j.telas_pagina(filtro="Bug", ids=["1", "2"])
        j.esquemas_tela_pagina()
        self.assertEqual(s.chamadas[0][2], {"startAt": 0, "maxResults": 50, "queryString": "Bug", "id": ["1", "2"]})
        self.assertEqual(s.chamadas[1][2], {"startAt": 0, "maxResults": 50})

    def test_null_no_esquema_de_tela_chega_a_api(self):
        """null em create/edit/view tira a tela da operacao: nao pode sumir do corpo."""
        c, s = cliente([Resposta(None)])
        Jira(c).salvar_esquema_tela("5", telas={"create": "7", "view": None})
        self.assertEqual(s.chamadas[0][:2], ("PUT", "https://site.atlassian.net/rest/api/3/screenscheme/5"))
        self.assertEqual(s.chamadas[0][3], {"screens": {"create": "7", "view": None}})

    def test_corpos_de_campos_e_itens(self):
        c, s = cliente([Resposta({"id": "duedate"}), Resposta(None), Resposta(None), Resposta(None), Resposta(None)])
        j = Jira(c)
        j.adicionar_campo_aba("1", "2", "duedate")
        j.mover_campo_aba("1", "2", "duedate", posicao="First")
        j.adicionar_itens_tipo_tela("9", [{"issueTypeId": "10001", "screenSchemeId": "3"}])
        j.remover_itens_tipo_tela("9", ["10001"])
        j.associar_esquema_tipo_tela("9", "10000")
        self.assertEqual([ch[3] for ch in s.chamadas], [
            {"fieldId": "duedate"}, {"position": "First"},
            {"issueTypeMappings": [{"issueTypeId": "10001", "screenSchemeId": "3"}]},
            {"issueTypeIds": ["10001"]}, {"issueTypeScreenSchemeId": "9", "projectId": "10000"}])
        self.assertTrue(s.chamadas[1][1].endswith("/screens/1/tabs/2/fields/duedate/move"))

    def test_obter_tela_junta_abas_e_campos(self):
        from atlassian_mcp_for_admins.ferramentas import jira as ferramentas
        c, s = cliente([Resposta({"values": [{"id": 1, "name": "T", "self": "x"}]}),
                        Resposta([{"id": 10, "name": "A"}, {"id": 11, "name": "B"}]),
                        Resposta([{"id": "summary", "name": "Resumo"}]), Resposta([])])
        with mock.patch.object(ferramentas, "obter", return_value=mock.Mock(jira=Jira(c))):
            tela = ferramentas.jira_obter_tela("1")
        self.assertEqual(tela, {"id": 1, "name": "T", "tabs": [
            {"id": 10, "name": "A", "total_campos": 1, "fields": [{"id": "summary", "name": "Resumo"}]},
            {"id": 11, "name": "B", "total_campos": 0, "fields": []}]})

    def test_fatia_de_lista_inteira(self):
        from atlassian_mcp_for_admins.ferramentas.jira import _fatia
        self.assertEqual(_fatia(list("abcde"), 0, 2),
                         {"total": 5, "inicio": 0, "retornados": 2, "proximo_inicio": 2, "itens": ["a", "b"]})
        self.assertIsNone(_fatia(list("abcde"), 4, 2)["proximo_inicio"])
        self.assertEqual(_fatia(list("abc"), 9, 2)["itens"], [])
        self.assertEqual(set(_fatia(list("abc"), 0, 2, "campos")),
                         {"total", "inicio", "retornados", "proximo_inicio", "campos"})

    def test_tela_inexistente_vira_erro_previsto(self):
        c, _ = cliente([Resposta({"values": []})])
        with self.assertRaises(LookupError):
            Jira(c).tela("999")


class TestPrioridades(unittest.TestCase):
    def test_corpos_de_prioridade(self):
        c, s = cliente([Resposta({"id": "10"}), Resposta(None), Resposta(None), Resposta(None)])
        j = Jira(c)
        j.criar_prioridade("P1", "#fff", 11920)
        j.salvar_prioridade("10", cor="#000")
        j.mover_prioridades(["10", "11"], posicao="First")
        j.salvar_padrao_prioridade(None)
        self.assertEqual([ch[:2] for ch in s.chamadas][1:], [
            ("PUT", "https://site.atlassian.net/rest/api/3/priority/10"),
            ("PUT", "https://site.atlassian.net/rest/api/3/priority/move"),
            ("PUT", "https://site.atlassian.net/rest/api/3/priority/default")])
        self.assertEqual([ch[3] for ch in s.chamadas], [
            {"name": "P1", "statusColor": "#fff", "avatarId": 11920}, {"statusColor": "#000"},
            {"ids": ["10", "11"], "position": "First"}, {"id": None}])

    def test_esquema_manda_ids_inteiros_e_mapeamentos(self):
        """A API quer int64 nos ids e chave texto / valor inteiro nos mapeamentos."""
        c, s = cliente([Resposta({"id": "5"}), Resposta({"task": {}})])
        j = Jira(c)
        j.criar_esquema_prioridade("E", ["1", "2"], "2", projeto_ids=["100"], mapeamentos={"in": {3: "1"}})
        j.salvar_esquema_prioridade("5", remover_prioridades=["2"], adicionar_projetos=["101"],
                                    mapeamentos={"in": {"2": "1"}, "out": {}})
        self.assertEqual(s.chamadas[0][3], {"name": "E", "priorityIds": [1, 2], "defaultPriorityId": 2,
                                            "projectIds": [100], "mappings": {"in": {"3": 1}}})
        self.assertEqual(s.chamadas[1][3], {"priorities": {"remove": {"ids": [2]}},
                                            "projects": {"add": {"ids": [101]}},
                                            "mappings": {"in": {"2": 1}, "out": {}}})

    def test_sugestao_de_mapeamento_sem_blocos_vazios(self):
        c, s = cliente([Resposta({"values": []}), Resposta({"values": []})])
        j = Jira(c)
        j.prioridades_mapear_pagina("5", remover_prioridades=["2"])
        j.esquemas_prioridade_pagina(somente_padrao=True, expand="priorities")
        self.assertEqual(s.chamadas[0][3], {"schemeId": 5, "startAt": 0, "maxResults": 50,
                                            "priorities": {"remove": [2]}})
        self.assertEqual(s.chamadas[1][2], {"startAt": 0, "maxResults": 50, "onlyDefault": "true",
                                            "expand": "priorities"})

    def test_salvar_esquema_sem_alteracao_e_recusado(self):
        from atlassian_mcp_for_admins.ferramentas import jira as ferramentas
        with self.assertRaises(ValueError):
            ferramentas.jira_salvar_esquema_prioridade("5", mapeamentos={"in": {"1": 2}})


if __name__ == "__main__":
    unittest.main()
