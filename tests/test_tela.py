"""Tela de sites: servidor local de verdade numa porta livre, sem rede externa nem Keychain real."""
import http.client
import json
import threading
from unittest import mock

from atlassian_mcp_for_admins import perfis, tela
from tests.test_servidor import ComPastaIsolada


class TestTela(ComPastaIsolada):
    def setUp(self):
        super().setUp()
        self.tela = tela.Tela(0)
        threading.Thread(target=self.tela.serve_forever, daemon=True).start()
        self.addCleanup(self.tela.server_close)
        self.addCleanup(self.tela.shutdown)

    def pedir(self, metodo, caminho, corpo=None, chave=True, host=None, origem=None):
        conexao = http.client.HTTPConnection("127.0.0.1", self.tela.porta, timeout=5)
        cabecalhos = {"Host": host or f"127.0.0.1:{self.tela.porta}"}
        if chave:
            cabecalhos["X-Chave"] = self.tela.chave if chave is True else chave
        if origem:
            cabecalhos["Origin"] = origem
        dados = None
        if corpo is not None:
            dados = json.dumps(corpo)
            cabecalhos["Content-Type"] = "application/json"
        conexao.request(metodo, caminho, body=dados, headers=cabecalhos)
        r = conexao.getresponse()
        texto = r.read().decode()
        conexao.close()
        return r.status, (json.loads(texto) if r.getheader("Content-Type", "").startswith("application/json") else texto)

    def test_pagina_abre_sem_chave_e_tem_csp(self):
        status, texto = self.pedir("GET", "/", chave=False)
        self.assertEqual(status, 200)
        self.assertIn("Sites Atlassian", texto)

    def test_api_exige_chave(self):
        self.assertEqual(self.pedir("GET", "/api/estado", chave=False)[0], 403)
        self.assertEqual(self.pedir("GET", "/api/estado", chave="errada")[0], 403)
        self.assertEqual(self.pedir("GET", "/api/estado")[0], 200)

    def test_recusa_host_e_origem_de_fora(self):
        self.assertEqual(self.pedir("GET", "/", host="evil.example.com")[0], 403)
        self.assertEqual(self.pedir("GET", "/api/estado", origem="https://evil.example.com")[0], 403)

    def test_cadastrar_ativar_e_remover_sem_devolver_token(self):
        status, e = self.pedir("POST", "/api/sites", {"nome": "Producao", "url": "https://empresa.atlassian.net",
                                                      "email": "a@b.c", "token": "segredo-1"})
        self.assertEqual(status, 200)
        self.assertNotIn("segredo-1", json.dumps(e))
        self.pedir("POST", "/api/sites", {"nome": "Homolog", "url": "https://hml.atlassian.net",
                                          "email": "a@b.c", "token": "segredo-2"})
        status, e = self.pedir("POST", "/api/sites/homolog/ativar")
        self.assertEqual([s["id"] for s in e["sites"] if s["ativo"]], ["homolog"])
        self.assertEqual(e["em_uso"]["origem"], "perfil Homolog")
        status, e = self.pedir("DELETE", "/api/sites/homolog")
        self.assertEqual([s["id"] for s in e["sites"]], ["producao"])
        self.assertEqual(self.pedir("DELETE", "/api/sites/homolog")[0], 404)

    def test_erro_de_validacao_volta_legivel(self):
        status, e = self.pedir("POST", "/api/sites", {"nome": "X", "url": "http://x", "email": "a@b.c", "token": "t"})
        self.assertEqual(status, 400)
        self.assertIn("https://", e["erro"])

    def test_importar_o_env_do_usuario(self):
        self.escrever(self.usuario, url="https://antigo.atlassian.net", token="t-antigo")
        status, e = self.pedir("GET", "/api/estado")
        self.assertEqual(e["importar"]["site"], "https://antigo.atlassian.net")
        status, e = self.pedir("POST", "/api/importar")
        self.assertEqual(e["salvo"], "antigo")
        self.assertIsNone(e["importar"])
        self.assertEqual(perfis.ativo()["token"], "t-antigo")

    def test_mostra_o_plugin_instalado_e_avisa_do_env_do_repositorio(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t")
        self.escrever(self.repositorio, url="https://repo.atlassian.net")
        e = tela.estado()
        self.assertEqual(e["em_uso"]["origem"], "perfil Producao")  # o plugin instalado nao le o .env do repo
        self.assertTrue(any(str(self.repositorio) in a for a in e["avisos"]))

    def test_testar_conta_admin(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t")
        respostas = {"/rest/api/3/myself": {"displayName": "Admin", "emailAddress": "a@b.c"},
                     "/rest/api/3/mypermissions": {"permissions": {"ADMINISTER": {"havePermission": True}}}}
        with mock.patch.object(tela.ClienteHttp, "get", side_effect=lambda c, **kw: respostas[c]):
            status, r = self.pedir("POST", "/api/sites/producao/testar")
        self.assertEqual(r, {"ok": True, "usuario": "Admin", "email": "a@b.c", "admin": True})

    def test_erros_de_conexao_explicados(self):
        import requests

        from atlassian_mcp_for_admins.nucleo.http import ErroAtlassian
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t")
        for erro, trecho in ((ErroAtlassian(401, "u", {}), "token invalido"),
                             (requests.ConnectionError("x"), "Nao foi possivel conectar")):
            with mock.patch.object(tela.ClienteHttp, "get", side_effect=erro):
                r = tela.testar("producao")
            self.assertFalse(r["ok"])
            self.assertIn(trecho, r["erro"])

    def test_fechar(self):
        self.assertEqual(self.pedir("POST", "/api/fechar")[1], {"fechado": True})
