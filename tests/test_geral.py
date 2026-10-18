"""Testes das ferramentas genericas, sem rede. Rodar: python -m unittest discover -s tests"""
import unittest
from unittest import mock

from atlassian_mcp_for_admins.ferramentas import geral
from tests.test_http import Resposta, cliente

INTENCAO = "Teste das ferramentas genericas"


class Base(unittest.TestCase):
    def usar(self, respostas):
        c, s = cliente(respostas)
        patch = mock.patch.object(geral, "cliente", return_value=c)
        patch.start()
        self.addCleanup(patch.stop)
        return s


class TestIntencao(Base):
    def test_obrigatoria_nas_tres(self):
        s = self.usar([])
        for chamada in (lambda: geral.atlassian_ler("", "/x"),
                        lambda: geral.atlassian_escrever("curta", "POST", "/x"),
                        lambda: geral.atlassian_excluir("   ", "/x")):
            with self.assertRaises(ValueError):
                chamada()
        self.assertEqual(s.chamadas, [])

    def test_vai_para_o_log_e_nao_para_a_api(self):
        s = self.usar([Resposta({"ok": 1})])
        with self.assertLogs("atlassian_mcp_for_admins.ferramentas.geral", level="INFO") as logs:
            geral.atlassian_ler(INTENCAO, "/rest/api/3/myself")
        self.assertIn(INTENCAO, "\n".join(logs.output))
        self.assertEqual(s.chamadas[0][2], {})


class TestLer(Base):
    def test_get_simples_limpa_ruido(self):
        s = self.usar([Resposta({"id": "1", "self": "https://x", "avatarUrls": {}})])
        self.assertEqual(geral.atlassian_ler(INTENCAO, "/rest/api/3/project/SUP"), {"id": "1"})
        self.assertEqual(s.chamadas[0][0], "GET")

    def test_post_so_para_consultas(self):
        s = self.usar([Resposta({"count": 3})])
        self.assertEqual(geral.atlassian_ler(INTENCAO, "/rest/api/3/search/approximate-count",
                                             corpo={"jql": "x"}), {"count": 3})
        self.assertEqual(s.chamadas[0][0], "POST")
        with self.assertRaises(ValueError) as ctx:
            geral.atlassian_ler(INTENCAO, "/rest/api/3/screens", corpo={"name": "x"})
        self.assertIn("atlassian_escrever", str(ctx.exception))

    def test_consulta_aceita_url_completa(self):
        s = self.usar([Resposta({"issues": [], "isLast": True})])
        geral.atlassian_ler(INTENCAO, "https://site.atlassian.net/rest/api/3/search/jql", corpo={"jql": "x"})
        self.assertEqual(s.chamadas[0][0], "POST")

    def test_limite_devolve_continuar(self):
        self.usar([Resposta({"issues": [{"key": "A-1"}], "nextPageToken": "N"})])
        r = geral.atlassian_ler(INTENCAO, "/rest/api/3/search/jql", corpo={"jql": "x"}, limite=1)
        self.assertEqual(r["issues"], [{"key": "A-1"}])
        self.assertEqual(r["continuar"]["corpo"]["nextPageToken"], "N")

    def test_limite_fora_da_faixa(self):
        self.usar([])
        for limite in (0, 501):
            with self.assertRaises(ValueError):
                geral.atlassian_ler(INTENCAO, "/x", limite=limite)

    def test_lista_inteira_com_inicio_vira_itens(self):
        self.usar([Resposta([{"id": i, "name": f"c{i}"} for i in range(3)])])
        r = geral.atlassian_ler(INTENCAO, "/rest/api/3/screens/1/tabs/2/fields", inicio=1, limite=1,
                                manter=["id"])
        self.assertEqual(r, {"itens": [{"id": 1}], "total": 3, "inicio": 1, "proximo_inicio": 2})

    def test_filtro(self):
        self.usar([Resposta({"startAt": 0, "isLast": True, "values": [{"id": "summary"}, {"id": "x"}]})])
        r = geral.atlassian_ler(INTENCAO, "/rest/api/3/fieldconfiguration/1/fields",
                                filtro={"id": ["summary", "customfield_10000"]})
        self.assertEqual(r["values"], [{"id": "summary"}])
        self.assertEqual(r["sem_correspondencia"], {"id": ["customfield_10000"]})

    def test_manter_aninhado(self):
        self.usar([Resposta({"id": 1, "updated": "x", "design": {"questions": {"1": {}}, "layout": [1] * 10}})])
        r = geral.atlassian_ler(INTENCAO, "https://api.atlassian.com/jira/forms/cloud/C/project/SUP/form/1",
                                manter=["id", "design.questions"])
        self.assertEqual(r, {"id": 1, "design": {"questions": {"1": {}}}})

    def test_manter_atravessa_listas(self):
        self.usar([Resposta({"values": [{"id": "1", "name": "a", "x": 1}], "total": 1})])
        r = geral.atlassian_ler(INTENCAO, "/x", manter=["values.id", "total"])
        self.assertEqual(r, {"values": [{"id": "1"}], "total": 1})

    def test_varios_caminhos_com_erro_no_meio(self):
        s = self.usar([Resposta([{"id": "a"}]), Resposta({"errorMessages": ["nao existe"]}, 404),
                       Resposta([{"id": "c"}])])
        r = geral.atlassian_ler(INTENCAO, ["/a", "/b", "/c"])
        self.assertEqual(r["/a"], [{"id": "a"}])
        self.assertIn("nao existe", r["/b"]["erro"])
        self.assertEqual(r["/c"], [{"id": "c"}])
        self.assertEqual(len(s.chamadas), 3)

    def test_varios_caminhos_limites(self):
        self.usar([])
        with self.assertRaises(ValueError):
            geral.atlassian_ler(INTENCAO, [])
        with self.assertRaises(ValueError):
            geral.atlassian_ler(INTENCAO, [f"/{i}" for i in range(21)])
        with self.assertRaises(ValueError):
            geral.atlassian_ler(INTENCAO, ["/a"], corpo={"jql": "x"})

    def test_trava_de_tamanho(self):
        self.usar([Resposta({"values": ["x" * 1000] * 60})])
        with self.assertRaises(ValueError) as ctx:
            geral.atlassian_ler(INTENCAO, "/x")
        self.assertIn("manter", str(ctx.exception))


class TestEscreverExcluir(Base):
    def test_escrever_envelope_com_status(self):
        s = self.usar([Resposta({"id": "10", "self": "x"}, 201)])
        r = geral.atlassian_escrever(INTENCAO, "post", "/rest/api/3/screens", corpo={"name": "Tela"})
        self.assertEqual(r, {"http": 201, "resposta": {"id": "10"}})
        self.assertEqual(s.chamadas[0][0], "POST")
        self.assertEqual(s.chamadas[0][3], {"name": "Tela"})

    def test_escrever_sem_corpo_na_resposta(self):
        self.usar([Resposta(None, 204)])
        self.assertEqual(geral.atlassian_escrever(INTENCAO, "PUT", "/x", corpo={}), {"http": 204, "resposta": None})

    def test_escrever_recusa_get_e_delete(self):
        s = self.usar([])
        for metodo, outra in (("GET", "atlassian_ler"), ("DELETE", "atlassian_excluir"), ("", "atlassian_ler")):
            with self.assertRaises(ValueError) as ctx:
                geral.atlassian_escrever(INTENCAO, metodo, "/x")
            self.assertIn(outra, str(ctx.exception))
        self.assertEqual(s.chamadas, [])

    def test_excluir_manda_delete_com_corpo(self):
        s = self.usar([Resposta({"results": []}, 207)])
        corpo = {"customfield_10000": {"schemeIds": [1]}}
        r = geral.atlassian_excluir(INTENCAO, "/rest/api/3/config/fieldschemes/fields", corpo=corpo)
        self.assertEqual(r["http"], 207)
        self.assertEqual(s.chamadas[0][0], "DELETE")
        self.assertEqual(s.chamadas[0][3], corpo)


class TestConexao(Base):
    def test_junta_usuario_e_cloud_id(self):
        self.usar([Resposta({"displayName": "Admin", "emailAddress": "a@b.c", "accountId": "1"}),
                   Resposta({"cloudId": "CID"})])
        r = geral.atlassian_conexao()
        self.assertEqual((r["usuario"], r["cloud_id"]), ("Admin", "CID"))


if __name__ == "__main__":
    unittest.main()
