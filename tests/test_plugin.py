"""Amarra plugin, servidor e skills: um nao pode existir sem o outro. Sem rede."""
import json
import re
import unittest
from pathlib import Path

from atlassian_mcp_for_admins.ferramentas import todas
from atlassian_mcp_for_admins.ferramentas._comum import PLUGIN

RAIZ = Path(__file__).resolve().parents[1]
MANIFESTO = json.loads((RAIZ / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
MARKETPLACE = json.loads((RAIZ / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
PASTA_SKILLS = RAIZ / MANIFESTO["skills"]


def frontmatter(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8")
    bloco = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    assert bloco, f"{caminho} sem frontmatter"
    return dict(linha.split(":", 1) for linha in bloco.group(1).splitlines() if ":" in linha)


def ids_no_layout(no, saida=None):
    saida = [] if saida is None else saida
    if isinstance(no, dict):
        if no.get("type") == "extension" and no.get("attrs", {}).get("extensionKey") == "question":
            saida.append(str(no["attrs"]["parameters"]["id"]))
        for v in no.values():
            ids_no_layout(v, saida)
    elif isinstance(no, list):
        for v in no:
            ids_no_layout(v, saida)
    return saida


def conferir_design(d: dict) -> list:
    """A conferencia da skill forms-design, em codigo."""
    erros = []
    for parte in ("settings", "questions", "sections", "conditions", "layout"):
        if parte not in d:
            erros.append(f"falta {parte}")
    no_layout = ids_no_layout(d.get("layout", []))
    if sorted(no_layout) != sorted(d.get("questions", {})):
        erros.append("perguntas do layout diferem de questions")
    if len(d.get("layout", [])) != len(d.get("sections", {})) + 1:
        erros.append("layout deve ter len(sections) + 1 documentos")
    for cid, c in d.get("conditions", {}).items():
        for sid in c["o"]["sIds"]:
            if sid not in d["sections"]:
                erros.append(f"condicao {cid} aponta para secao inexistente {sid}")
        for qid, opcoes in c["i"]["co"]["cIds"].items():
            q = d["questions"].get(qid)
            if not q:
                erros.append(f"condicao {cid} usa pergunta inexistente {qid}")
            elif not q.get("jiraField") and not set(opcoes) <= {o["id"] for o in q.get("choices", [])}:
                erros.append(f"condicao {cid} usa opcao inexistente da pergunta {qid}")
    return erros


class TestManifesto(unittest.TestCase):
    def test_nome_do_plugin_bate_com_o_codigo(self):
        self.assertEqual(MANIFESTO["name"], PLUGIN)
        self.assertIn(PLUGIN, [p["name"] for p in MARKETPLACE["plugins"]])

    def test_servidor_usa_credenciais_do_user_config(self):
        (servidor,) = MANIFESTO["mcpServers"].values()
        for var, chave in (("JIRA_URL", "jira_url"), ("JIRA_EMAIL", "jira_email"), ("JIRA_TOKEN", "jira_token")):
            self.assertEqual(servidor["env"][var], "${user_config.%s}" % chave)
            self.assertIn(chave, MANIFESTO["userConfig"])
        self.assertTrue(MANIFESTO["userConfig"]["jira_token"].get("sensitive"))

    def test_credenciais_opcionais(self):
        """A obrigatoriedade fica no servidor (test_servidor.py), nao no manifesto: com
        `required` e a opcao vazia, o Claude Code nem tenta subir o servidor e nao mostra
        erro nenhum. Opcionais no manifesto, o servidor tenta subir, recusa sem
        credencial e o /mcp mostra a falha com o motivo no log."""
        self.assertFalse(any(v.get("required") for v in MANIFESTO["userConfig"].values()))

    def test_credenciais_com_default_vazio(self):
        """O Cowork ignora servidor que referencia ${user_config.*} sem default (e nao
        pergunta os valores). Com default vazio ele sobe e le o .env do usuario."""
        for chave, opcao in MANIFESTO["userConfig"].items():
            self.assertEqual(opcao.get("default"), "", chave)

    def test_ambiente_criado_pelo_uv_na_pasta_de_dados(self):
        """A copia instalada nao tem .venv: o uv monta o ambiente em ${CLAUDE_PLUGIN_DATA},
        que sobrevive a atualizacoes, a partir do uv.lock (--frozen)."""
        (servidor,) = MANIFESTO["mcpServers"].values()
        self.assertEqual(servidor["command"], "uv")
        self.assertEqual(servidor["args"][:3], ["run", "--project", "${CLAUDE_PLUGIN_ROOT}"])
        self.assertIn("--frozen", servidor["args"])
        self.assertIn("--quiet", servidor["args"])  # stdout e do protocolo MCP
        self.assertEqual(servidor["env"]["UV_PROJECT_ENVIRONMENT"], "${CLAUDE_PLUGIN_DATA}/venv")
        self.assertTrue((RAIZ / "uv.lock").exists())

    def test_segredos_e_ambiente_fora_do_git(self):
        """A instalacao por git clona so o que esta no commit: .env e .venv precisam
        estar no .gitignore para nunca irem junto."""
        import subprocess
        for caminho in (".env", ".venv/"):
            r = subprocess.run(["git", "check-ignore", "-q", caminho], cwd=RAIZ)
            self.assertEqual(r.returncode, 0, f"{caminho} nao esta no .gitignore")

    def test_nome_completo_cabe_no_limite(self):
        """Ferramenta de plugin vira mcp__plugin_<plugin>_<servidor>__<ferramenta> (limite 64)."""
        (servidor,) = MANIFESTO["mcpServers"]
        prefixo = f"mcp__plugin_{PLUGIN}_{servidor}__"
        longos = [f.__name__ for f in todas() if len(prefixo + f.__name__) > 64]
        self.assertEqual(longos, [], f"maximo por ferramenta: {64 - len(prefixo)} caracteres")

    def test_sem_mcp_json_na_raiz(self):
        """Um .mcp.json na raiz tambem viraria servidor de projeto e duplicaria o do plugin."""
        self.assertFalse((RAIZ / ".mcp.json").exists())


class TestIndependenteDeSite(unittest.TestCase):
    def test_site_configurado_nao_aparece_no_repositorio(self):
        """O plugin roda em varios sites: nada versionado pode citar o site em uso."""
        import subprocess
        from urllib.parse import urlparse

        from atlassian_mcp_for_admins import config
        host = urlparse(config.URL).hostname
        if not host:
            self.skipTest("sem site configurado")
        subdominio = host.split(".")[0].lower()
        arquivos = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True).stdout.split()
        citam = [a for a in arquivos if a != "uv.lock" and (RAIZ / a).is_file()
                 and subdominio in (RAIZ / a).read_text(encoding="utf-8", errors="ignore").lower()]
        self.assertEqual(citam, [], f"arquivos citam o site {host}")


class TestSkills(unittest.TestCase):
    def test_toda_skill_citada_existe(self):
        citadas = {s for f in todas() for s in getattr(f, "skills", ())}
        self.assertTrue(citadas, "nenhuma ferramenta cita skill")
        for skill in citadas:
            arquivo = PASTA_SKILLS / skill / "SKILL.md"
            self.assertTrue(arquivo.exists(), f"skill {skill} citada mas ausente")
            meta = frontmatter(arquivo)
            self.assertEqual(meta["name"].strip(), skill)
            self.assertGreater(len(meta["description"].strip()), 80)

    def test_ferramentas_com_payload_complexo_citam_a_skill(self):
        por_nome = {f.__name__: f for f in todas()}
        esperado = {
            "forms-design": ("forms_criar", "forms_salvar", "forms_obter", "forms_obter_do_request_type",
                             "forms_obter_da_issue"),
            "forms-respostas": ("forms_salvar_respostas", "forms_obter_da_issue", "forms_obter_dados_externos",
                                "forms_obter_dados_externos_rt"),
        }
        for skill, nomes in esperado.items():
            for nome in nomes:
                self.assertIn(skill, getattr(por_nome[nome], "skills", ()), nome)
                self.assertIn(f"{PLUGIN}:{skill}", por_nome[nome].__doc__)

    def test_exemplo_da_skill_passa_na_conferencia(self):
        texto = (PASTA_SKILLS / "forms-design" / "SKILL.md").read_text(encoding="utf-8")
        exemplo = texto.split("## Exemplo minimo")[1].split("```json")[1].split("```")[0]
        design = json.loads(exemplo)
        self.assertEqual(conferir_design(design), [])

    def test_exemplo_de_respostas_usa_so_chaves_da_api(self):
        """Chaves de FormAnswerRequest na especificacao da Forms API."""
        texto = (PASTA_SKILLS / "forms-respostas" / "SKILL.md").read_text(encoding="utf-8")
        exemplo = texto.split("## Preencher e enviar")[1].split("```json")[1].split("```")[0]
        respostas = json.loads(exemplo)
        self.assertTrue(respostas)
        for qid, resposta in respostas.items():
            self.assertTrue(qid.isdigit(), qid)
            self.assertLessEqual(set(resposta), {"adf", "choices", "date", "files", "text", "time", "users"}, qid)
            self.assertTrue(all(isinstance(u, str) for u in resposta.get("users", [])), "users grava accountIds")


if __name__ == "__main__":
    unittest.main()
