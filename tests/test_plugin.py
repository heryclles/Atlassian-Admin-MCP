"""Amarra plugin, servidor e skills: um nao pode existir sem o outro. Sem rede."""
import json
import re

OBJETO_ASSETS = re.compile(r"^[0-9a-f-]{36}:\d+$")
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
            elif q["type"] == "ob":
                if not all(OBJETO_ASSETS.match(o) for o in opcoes):
                    erros.append(f"condicao {cid} usa objeto do Assets fora do formato workspaceId:objectId")
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


class TestFerramentas(unittest.TestCase):
    def test_conexao_e_tres_genericas_por_risco(self):
        marcas = {f.__name__: getattr(f, "somente_leitura", True) for f in todas()}
        self.assertEqual(marcas, {"atlassian_conexao": True, "atlassian_ler": True,
                                  "atlassian_escrever": False, "atlassian_excluir": False})


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


FERRAMENTAS_POR_METODO = {"GET": "atlassian_ler", "POST": "atlassian_escrever", "PUT": "atlassian_escrever",
                          "PATCH": "atlassian_escrever", "DELETE": "atlassian_excluir"}
BASES = ("/rest/api/3/", "/rest/servicedeskapi/", "/_edge/", "https://api.atlassian.com/jira/forms/cloud/{cloudId}/")
PAGINACOES = {"token", "startAt", "start/limit", "token aninhado", "inteira", "nao"}
CABECALHO = "| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |"


def endpoints(texto: str) -> list:
    """Linhas da tabela "## Endpoints": (operacao, ferramenta, metodo, caminho, paginacao)."""
    secao = texto.split("## Endpoints", 1)[1]
    linhas = secao.split(CABECALHO, 1)[1].strip().splitlines()[1:]
    saida = []
    for linha in linhas:
        if not linha.startswith("|"):
            break
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        metodo, caminho = celulas[2].strip("`").split(" ", 1)
        saida.append((celulas[0], celulas[1], metodo, caminho, celulas[3]))
    return saida


def skills() -> list:
    return sorted(p for p in PASTA_SKILLS.iterdir() if (p / "SKILL.md").is_file())


class TestSkills(unittest.TestCase):
    def test_toda_skill_citada_existe(self):
        citadas = {s for f in todas() for s in getattr(f, "skills", ())}
        self.assertEqual(citadas, {"atlassian-chamadas"})
        for f in todas():
            for skill in getattr(f, "skills", ()):
                self.assertIn(f"{PLUGIN}:{skill}", f.__doc__)

    def test_frontmatter_de_toda_skill(self):
        for pasta in skills():
            meta = frontmatter(pasta / "SKILL.md")
            self.assertEqual(meta["name"].strip(), pasta.name)
            self.assertGreater(len(meta["description"].strip()), 80, pasta.name)

    def test_toda_skill_esta_nas_instrucoes_do_servidor(self):
        from atlassian_mcp_for_admins.servidor import INSTRUCOES
        self.assertLess(len(INSTRUCOES), 4096)
        for pasta in skills():
            self.assertIn(pasta.name, INSTRUCOES)

    def test_tabela_de_endpoints(self):
        """Toda skill tem a tabela; ferramenta bate com o metodo; caminho comeca por URL base conhecida."""
        from atlassian_mcp_for_admins.ferramentas.geral import CONSULTAS_POST
        for pasta in skills():
            texto = (pasta / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Endpoints", texto, pasta.name)
            linhas = endpoints(texto)
            self.assertTrue(linhas, pasta.name)
            for operacao, ferramenta, metodo, caminho, paginacao in linhas:
                rotulo = f"{pasta.name}: {operacao}"
                esperada = ("atlassian_ler" if metodo == "POST" and caminho in CONSULTAS_POST
                            else FERRAMENTAS_POR_METODO.get(metodo))
                self.assertEqual(ferramenta, esperada, rotulo)
                self.assertTrue(caminho.startswith(BASES), rotulo)
                self.assertNotIn("?", caminho, rotulo)
                self.assertIn(paginacao, PAGINACOES, rotulo)

    def test_skills_citam_so_ferramentas_existentes(self):
        nomes = {f.__name__ for f in todas()}
        padrao = re.compile(r"\b(?:jira|jsm|forms|atlassian)_[a-z_]+")
        for pasta in skills():
            citadas = set(padrao.findall((pasta / "SKILL.md").read_text(encoding="utf-8")))
            self.assertLessEqual(citadas, nomes, pasta.name)

    def test_exemplos_da_skill_passam_na_conferencia(self):
        texto = (PASTA_SKILLS / "forms-design" / "SKILL.md").read_text(encoding="utf-8")
        for titulo in ("## Exemplo minimo", "## Exemplo: aviso condicional"):
            exemplo = texto.split(titulo)[1].split("```json")[1].split("```")[0]
            self.assertEqual(conferir_design(json.loads(exemplo)), [], titulo)

    def test_conferencia_pega_condicao_orfa(self):
        """Pergunta que mudou de tipo deixa condicao apontando para opcao que nao existe."""
        texto = (PASTA_SKILLS / "forms-design" / "SKILL.md").read_text(encoding="utf-8")
        design = json.loads(texto.split("## Exemplo: aviso condicional")[1].split("```json")[1].split("```")[0])
        design["questions"]["1"] = {"type": "tl", "label": "Sistema afetado", "validation": {"rq": True}}
        self.assertTrue(any("opcao inexistente" in e for e in conferir_design(design)))

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

    def test_exemplos_de_telas_usam_so_chaves_da_api(self):
        """Chaves de ScreenTypes e IssueTypeScreenSchemeMapping na especificacao do Jira."""
        texto = (PASTA_SKILLS / "jira-telas" / "SKILL.md").read_text(encoding="utf-8")
        blocos = [json.loads(b.split("```")[0]) for b in texto.split("```json")[1:]]
        telas = [b for b in blocos if isinstance(b, dict)]
        itens = [b for b in blocos if isinstance(b, list)]
        self.assertTrue(telas and itens)
        for b in telas:
            self.assertLessEqual(set(b), {"default", "create", "edit", "view"})
        self.assertIn("default", telas[0], "exemplo de criacao sem default")
        for lista in itens:
            self.assertIn("default", [i["issueTypeId"] for i in lista])
            for i in lista:
                self.assertEqual(set(i), {"issueTypeId", "screenSchemeId"})

    def test_mapeamentos_de_prioridade_no_formato_da_api(self):
        """PriorityMapping: so in/out, chave = id da prioridade antiga em texto, valor = id inteiro."""
        texto = (PASTA_SKILLS / "jira-prioridades" / "SKILL.md").read_text(encoding="utf-8")
        blocos = [json.loads(b.split("```")[0]) for b in texto.split("```json")[1:]]
        self.assertGreaterEqual(len(blocos), 2)
        for b in blocos:
            self.assertLessEqual(set(b), {"in", "out"})
            for pares in b.values():
                self.assertTrue(pares)
                for antiga, nova in pares.items():
                    self.assertTrue(antiga.isdigit(), antiga)
                    self.assertIsInstance(nova, int)

    def test_exemplos_de_configuracao_de_campo_usam_so_chaves_da_api(self):
        """Chaves de FieldConfigurationItem e FieldConfigurationToIssueTypeMapping na especificacao."""
        texto = (PASTA_SKILLS / "jira-config-campos" / "SKILL.md").read_text(encoding="utf-8")

        def exemplo(titulo):
            return json.loads(texto.split(titulo)[1].split("```json")[1].split("```")[0])

        itens = exemplo("### Itens de campo")
        self.assertTrue(itens)
        for i in itens:
            self.assertIn("id", i)
            self.assertLessEqual(set(i), {"id", "isHidden", "isRequired", "description", "renderer"})
            self.assertIn(i.get("renderer", "wiki-renderer"), {"wiki-renderer", "text-renderer"})
        mapeamento = exemplo("### Itens do esquema")
        self.assertIn("default", [m["issueTypeId"] for m in mapeamento])
        for m in mapeamento:
            self.assertEqual(set(m), {"issueTypeId", "fieldConfigurationId"})
            self.assertIsInstance(m["fieldConfigurationId"], str)

    def test_exemplo_de_notificacoes_usa_so_chaves_da_api(self):
        """Chaves de NotificationSchemeEventDetails e NotificationSchemeNotificationDetails."""
        texto = (PASTA_SKILLS / "jira-notificacoes" / "SKILL.md").read_text(encoding="utf-8")
        eventos = json.loads(texto.split("## Payloads")[1].split("```json")[1].split("```")[0])
        sem_parametro = {"CurrentAssignee", "Reporter", "CurrentUser", "ProjectLead", "ComponentLead", "AllWatchers"}
        com_parametro = {"User", "Group", "ProjectRole", "UserCustomField", "GroupCustomField"}
        self.assertTrue(eventos)
        for e in eventos:
            self.assertEqual(set(e), {"event", "notifications"})
            self.assertEqual(set(e["event"]), {"id"})
            self.assertIsInstance(e["event"]["id"], str)
            for n in e["notifications"]:
                tipo = n["notificationType"]
                self.assertIn(tipo, sem_parametro | com_parametro)
                self.assertEqual(set(n), {"notificationType", "parameter"} if tipo in com_parametro
                                 else {"notificationType"}, tipo)

    def test_exemplos_de_esquemas_de_campos_usam_so_chaves_da_api(self):
        """Chaves de UpdateFieldAssociationsRequestItem, RemoveFieldAssociationsRequestItem,
        UpdateFieldSchemeParametersRequest e ParameterRemovalDetails na especificacao do Jira."""
        texto = (PASTA_SKILLS / "jira-esquemas-campos" / "SKILL.md").read_text(encoding="utf-8")

        def exemplo(titulo):
            return json.loads(texto.split(titulo)[1].split("```json")[1].split("```")[0])

        for campo, itens in exemplo("### Adicionar campos").items():
            for i in itens:
                self.assertLessEqual(set(i), {"schemeIds", "restrictedToWorkTypes"}, campo)
                self.assertIn("schemeIds", i)
        for campo, item in exemplo("### Remover campos").items():
            self.assertEqual(set(item), {"schemeIds"}, campo)
        for campo, itens in exemplo("### Parametros").items():
            for i in itens:
                self.assertLessEqual(set(i), {"schemeIds", "parameters", "workTypeParameters"}, campo)
                self.assertLessEqual(set(i.get("parameters") or {}), {"isRequired", "description", "rendererType"})
                for t in i.get("workTypeParameters", []):
                    self.assertLessEqual(set(t), {"workTypeId", "isRequired", "description", "rendererType"})
                    self.assertIsInstance(t["workTypeId"], int)
        for campo, itens in exemplo("### Remover excecoes").items():
            for i in itens:
                self.assertEqual(set(i), {"schemeId", "workTypeIds", "parameters"}, campo)
                self.assertLessEqual(set(i["parameters"]), {"isRequired", "description", "rendererType"})


if __name__ == "__main__":
    unittest.main()
