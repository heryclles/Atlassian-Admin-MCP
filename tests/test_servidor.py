"""Subida do servidor, ordem das credenciais e perfis de site. Sem rede e sem o Keychain real."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from atlassian_mcp_for_admins import config, perfis, servidor
from atlassian_mcp_for_admins.nucleo import http

VAZIO = {"JIRA_URL": "", "JIRA_EMAIL": "", "JIRA_TOKEN": ""}


class CofreFalso:
    """No lugar do keyring: guarda os tokens num dicionario."""
    def __init__(self):
        self.tokens = {}

    def get_password(self, servico, usuario):
        return self.tokens.get((servico, usuario))

    def set_password(self, servico, usuario, senha):
        self.tokens[(servico, usuario)] = senha

    def delete_password(self, servico, usuario):
        del self.tokens[(servico, usuario)]


class ComPastaIsolada(unittest.TestCase):
    """sites.json, .env do repositorio e do usuario numa pasta temporaria; cofre falso."""
    def setUp(self):
        pasta = Path(tempfile.mkdtemp())
        self.cofre = CofreFalso()
        self.repositorio, self.usuario = pasta / "repo.env", pasta / "usuario.env"
        for alvo, valor in ((perfis, {"PASTA": pasta, "ARQUIVO": pasta / "sites.json"}),
                            (config, {"ARQUIVO_REPOSITORIO": self.repositorio, "ARQUIVO_USUARIO": self.usuario})):
            p = mock.patch.multiple(alvo, **valor)
            p.start()
            self.addCleanup(p.stop)
        for p in (mock.patch.object(perfis, "_cofre", return_value=self.cofre), mock.patch.dict(os.environ, VAZIO)):
            p.start()
            self.addCleanup(p.stop)

    def escrever(self, arquivo, url="https://arquivo.atlassian.net", email="a@b.c", token="t-arquivo"):
        arquivo.write_text(f"JIRA_URL={url}\nJIRA_EMAIL={email}\nJIRA_TOKEN={token}\n")


class TestPerfis(ComPastaIsolada):
    def test_criar_ativar_e_remover(self):
        a = perfis.salvar_site("Producao", "https://Empresa.atlassian.net/jira/", "a@b.c", "t1")
        b = perfis.salvar_site("Producao", "https://outra.atlassian.net", "x@y.z", "t2")
        self.assertEqual((a, b), ("producao", "producao-2"))
        self.assertEqual(perfis.ativo()["url"], "https://empresa.atlassian.net")  # o primeiro fica ativo
        perfis.ativar(b)
        self.assertEqual(perfis.ativo()["token"], "t2")
        perfis.remover(b)
        self.assertEqual(perfis.ativo()["id"], a)
        self.assertNotIn(("atlassian-admin", b), self.cofre.tokens)

    def test_token_fica_fora_do_arquivo_e_arquivo_privado(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "segredo")
        texto = perfis.ARQUIVO.read_text()
        self.assertNotIn("segredo", texto)
        self.assertEqual(perfis.ARQUIVO.stat().st_mode & 0o777, 0o600)

    def test_editar_sem_token_mantem_o_atual(self):
        pid = perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t1")
        perfis.salvar_site("Producao nova", "https://empresa.atlassian.net", "a@b.c", None, perfil_id=pid)
        self.assertEqual(perfis.ativo()["token"], "t1")
        self.assertEqual(perfis.ativo()["nome"], "Producao nova")

    def test_validacoes(self):
        with self.assertRaises(ValueError):
            perfis.salvar_site("X", "http://empresa.atlassian.net", "a@b.c", "t")
        with self.assertRaises(ValueError):
            perfis.salvar_site("X", "https://empresa.atlassian.net", "sem-arroba", "t")
        with self.assertRaises(ValueError):
            perfis.salvar_site("X", "https://empresa.atlassian.net", "a@b.c", "")
        with self.assertRaises(LookupError):
            perfis.ativar("nao-existe")


class TestOrdemDasCredenciais(ComPastaIsolada):
    def test_sem_nada_fica_incompleto(self):
        c = config.credenciais()
        self.assertEqual((c["url"], c["origem"]), ("", None))
        with self.assertRaises(RuntimeError) as ctx:
            config.validar()
        self.assertIn("/atlassian-admin:sites", str(ctx.exception))

    def test_arquivo_do_usuario_sem_perfil(self):
        self.escrever(self.usuario)
        self.assertEqual(config.credenciais()["origem"], str(self.usuario))

    def test_perfil_vence_o_arquivo_do_usuario(self):
        self.escrever(self.usuario)
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t-perfil")
        c = config.credenciais()
        self.assertEqual((c["url"], c["token"], c["origem"]),
                         ("https://empresa.atlassian.net", "t-perfil", "perfil Producao"))

    def test_ambiente_vence_o_perfil(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t-perfil")
        with mock.patch.dict(os.environ, {"JIRA_URL": "https://env.atlassian.net", "JIRA_EMAIL": "e@f.g",
                                          "JIRA_TOKEN": "t-env"}):
            c = config.credenciais()
        self.assertEqual((c["url"], c["origem"]), ("https://env.atlassian.net", "ambiente (userConfig do plugin)"))

    def test_user_config_sem_expandir_cai_no_perfil(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t-perfil")
        with mock.patch.dict(os.environ, {"JIRA_URL": "${user_config.jira_url}"}):
            self.assertEqual(config.credenciais()["origem"], "perfil Producao")

    def test_env_do_repositorio_vence_o_perfil(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t-perfil")
        self.escrever(self.repositorio, url="https://repo.atlassian.net")
        self.assertEqual(config.credenciais()["url"], "https://repo.atlassian.net")

    def test_arquivo_do_usuario_fora_do_repositorio(self):
        with mock.patch.object(config, "ARQUIVO_USUARIO", Path.home() / ".config" / "atlassian-admin" / ".env"):
            self.assertFalse(config.ARQUIVO_USUARIO.is_relative_to(config.RAIZ))


class TestTrocaSemReiniciar(ComPastaIsolada):
    def setUp(self):
        super().setUp()
        p = mock.patch.multiple(http, _cliente=None, _chave=None)
        p.start()
        self.addCleanup(p.stop)

    def test_cliente_segue_o_perfil_ativo(self):
        a = perfis.salvar_site("A", "https://a.atlassian.net", "a@b.c", "ta")
        b = perfis.salvar_site("B", "https://b.atlassian.net", "a@b.c", "tb")
        primeiro = http.cliente()
        self.assertIs(http.cliente(), primeiro)  # mesmo site: reaproveita a sessao
        perfis.ativar(b)
        self.assertEqual(http.cliente().url, "https://b.atlassian.net")
        self.assertEqual(http.origem, "perfil B")
        perfis.ativar(a)
        self.assertEqual(http.cliente().url, "https://a.atlassian.net")


class TestSubida(ComPastaIsolada):
    def test_sem_credencial_sobe_e_avisa(self):
        with mock.patch.object(servidor, "criar_servidor") as criar, \
                self.assertLogs("atlassian_mcp_for_admins.servidor", level="WARNING") as logs:
            servidor.main()
        criar.return_value.run.assert_called_once()
        self.assertIn("Credenciais ausentes", "\n".join(logs.output))

    def test_com_credencial_sobe(self):
        perfis.salvar_site("Producao", "https://empresa.atlassian.net", "a@b.c", "t")
        with mock.patch.object(servidor, "criar_servidor") as criar:
            servidor.main()
        criar.return_value.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
