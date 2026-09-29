"""Subida do servidor: sem credencial ele nao conecta e explica o motivo. Sem rede."""
import os
import unittest
from unittest import mock

from atlassian_mcp_for_admins import config, servidor


class TestCredencialObrigatoria(unittest.TestCase):
    def test_sem_credencial_encerra_com_erro_antes_de_subir(self):
        with mock.patch.multiple(config, URL="", EMAIL="", TOKEN=""), \
                mock.patch.object(servidor, "criar_servidor") as criar, \
                self.assertLogs("atlassian_mcp_for_admins.servidor", level="ERROR") as logs, \
                self.assertRaises(SystemExit) as saida:
            servidor.main()
        self.assertEqual(saida.exception.code, 1)
        criar.assert_not_called()
        mensagem = "\n".join(logs.output)
        self.assertIn("Credenciais ausentes: JIRA_URL, JIRA_EMAIL, JIRA_TOKEN", mensagem)
        self.assertIn("/plugin configure", mensagem)

    def test_com_credencial_sobe(self):
        with mock.patch.multiple(config, URL="https://empresa.atlassian.net", EMAIL="a@b.c", TOKEN="t"), \
                mock.patch.object(servidor, "criar_servidor") as criar:
            servidor.main()
        criar.return_value.run.assert_called_once()

    def test_url_sem_https_tambem_impede_a_subida(self):
        with mock.patch.multiple(config, URL="empresa.atlassian.net", EMAIL="a@b.c", TOKEN="t"), \
                mock.patch.object(servidor, "criar_servidor") as criar, \
                self.assertLogs("atlassian_mcp_for_admins.servidor", level="ERROR"), \
                self.assertRaises(SystemExit):
            servidor.main()
        criar.assert_not_called()


class TestComandoConfigurar(unittest.TestCase):
    def test_deriva_plugin_e_marketplace_da_pasta_instalada(self):
        raiz = "/Users/x/.claude/plugins/cache/meu-marketplace/atlassian-admin/0.4.4"
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": raiz}):
            self.assertEqual(config.comando_configurar(), "/plugin configure atlassian-admin@meu-marketplace")

    def test_fora_do_plugin_usa_texto_generico(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": ""}):
            self.assertIn("<marketplace>", config.comando_configurar())


if __name__ == "__main__":
    unittest.main()
