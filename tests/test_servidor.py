"""Subida do servidor: sem credencial ele nao conecta e explica o motivo. Sem rede."""
import os
import unittest
from pathlib import Path
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
        self.assertIn(str(config.ARQUIVO_USUARIO), mensagem)

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


class TestOrdemDeLeitura(unittest.TestCase):
    """Ambiente (userConfig) primeiro, depois .env do repositorio, depois o do usuario."""
    REPOSITORIO = {"JIRA_URL": "https://repo.atlassian.net"}
    USUARIO = {"JIRA_URL": "https://usuario.atlassian.net", "JIRA_TOKEN": "t-usuario"}

    def ler(self, nome, ambiente):
        with mock.patch.dict(os.environ, ambiente):
            return config.ler(nome, [self.REPOSITORIO, self.USUARIO])

    def test_ambiente_vence(self):
        self.assertEqual(self.ler("JIRA_URL", {"JIRA_URL": "https://env.atlassian.net"}),
                         "https://env.atlassian.net")

    def test_user_config_vazio_ou_sem_expandir_cai_nos_arquivos(self):
        for vazio in ("", "  ", "${user_config.jira_url}"):
            self.assertEqual(self.ler("JIRA_URL", {"JIRA_URL": vazio}), "https://repo.atlassian.net")

    def test_arquivo_do_usuario_quando_o_repositorio_nao_tem(self):
        self.assertEqual(self.ler("JIRA_TOKEN", {"JIRA_TOKEN": ""}), "t-usuario")

    def test_sem_nada_fica_vazio(self):
        self.assertEqual(self.ler("JIRA_EMAIL", {"JIRA_EMAIL": ""}), "")

    def test_arquivo_do_usuario_fora_do_repositorio(self):
        self.assertEqual(config.ARQUIVO_USUARIO, Path.home() / ".config" / "atlassian-admin" / ".env")
        self.assertFalse(config.ARQUIVO_USUARIO.is_relative_to(config.RAIZ))


if __name__ == "__main__":
    unittest.main()
