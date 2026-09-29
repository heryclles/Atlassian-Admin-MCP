"""Chama as ferramentas de LEITURA contra o site configurado, sem passar pelo MCP.

Nao depende de nenhum site: descobre sozinho um service desk, uma issue, um status,
um workflow, um request type e um formulario para ler. As de escrita nao sao chamadas.

Rodar:  python -m tests.ao_vivo
Opcional: AO_VIVO_PROJETO=<chave de um projeto JSM> para escolher o projeto.
"""
import json
import logging
import os
import sys
import time

from atlassian_mcp_for_admins.ferramentas import forms, geral, jira, jsm

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
ctx: dict = {}


class Pular(Exception):
    """O site nao tem o que este caso precisa."""


def descobrir_projeto():
    desks = jsm.jsm_listar_service_desks()["service_desks"]
    if not desks:
        raise Pular("nenhum service desk visivel")
    escolhido = os.getenv("AO_VIVO_PROJETO")
    sd = next((d for d in desks if d["projectKey"] == escolhido), desks[0]) if escolhido else desks[0]
    ctx["projeto"] = sd["projectKey"]
    return {"projeto": sd["projectKey"], "service_desks_visiveis": len(desks)}


def paginar_tudo():
    """Percorre todas as paginas de uma JQL pequena e confere com a contagem e com repeticoes."""
    for janela in ("-1d", "-7d", "-30d", "-365d"):
        jql = f"project = {ctx['projeto']} AND created >= {janela}"
        total = jira.jira_contar_issues(jql)["total_aproximado"]
        if total:
            break
    else:
        raise Pular("projeto sem issues no ultimo ano")
    chaves, token, paginas = [], None, 0
    while True:
        r = jira.jira_buscar_issues(jql, campos=["created"], limite=70, proximo_token=token)
        chaves += [i["key"] for i in r["issues"]]
        paginas += 1
        token = r["proximo_token"]
        if not token or len(chaves) >= 500:
            break
    ctx["issue"], ctx["issues"] = chaves[0], chaves[:40]
    assert len(chaves) == len(set(chaves)), "chave repetida entre paginas"
    if not token:
        assert len(chaves) == total, f"coletado {len(chaves)} x contagem {total}"
    return {"jql": jql, "paginas": paginas, "coletado": len(chaves), "contagem_api": total,
            "percorreu_tudo": not token}


def status_e_usos():
    r = jira.jira_listar_status(limite=1)
    return {"total_status": r["total"], **jira.jira_usos_status(r["status"][0]["id"])}


def workflows_todos():
    inicio, n = 0, 0
    while True:
        r = jira.jira_listar_workflows(inicio=inicio, limite=200, incluir_status=False)
        n += len(r["values"])
        if n and "workflow" not in ctx:
            ctx["workflow"] = r["values"][0]["id"]["entityId"]
        if r.get("isLast") or not r["values"]:
            break
        inicio += len(r["values"])
    assert n == r["total"], f"{n} x total {r['total']}"
    return {"percorridos": n, "total_api": r["total"]}


def request_types():
    r = jsm.jsm_listar_request_types(ctx["projeto"])
    if not r["request_types"]:
        raise Pular("service desk sem request types")
    ctx["rt"] = r["request_types"][0]["id"]
    return {"total": r["total"], "primeiro": ctx["rt"]}


def formularios():
    r = forms.forms_listar(ctx["projeto"])
    if r["formularios"]:
        ctx["form"] = r["formularios"][0]["id"]
    return {"total": r["total"]}


def formulario():
    if "form" not in ctx:
        raise Pular("projeto sem formularios")
    d = forms.forms_obter(ctx["projeto"], ctx["form"])["design"]
    return {k: len(d.get(k) or {}) for k in ("questions", "sections", "conditions")}


def formulario_de_issue():
    """Acha uma issue com formulario entre as coletadas e le o formulario inteiro."""
    for chave in ctx["issues"]:
        itens = forms.forms_listar_da_issue(chave)["formularios"]
        if itens:
            ctx["issue_form"], ctx["form_issue"] = chave, itens[0]["id"]
            f = forms.forms_obter_da_issue(chave, itens[0]["id"])
            return {"issue": chave, "status": f["state"]["status"], "respostas": len(f["state"]["answers"])}
    raise Pular("nenhuma das issues coletadas tem formulario")


def na_issue(ferramenta):
    def chamar():
        if "form_issue" not in ctx:
            raise Pular("sem formulario em issue")
        return ferramenta(ctx["issue_form"], ctx["form_issue"])
    return chamar


def cadeia_de_telas():
    """Caminho da skill jira-telas: projeto -> esquema por tipo -> esquema de tela -> tela."""
    projeto_id = jira.jira_obter_projeto(ctx["projeto"])["id"]
    r = jira.jira_listar_tipo_tela_projetos([projeto_id])
    if not r["values"]:
        raise Pular("projeto sem esquema de tela por tipo de issue (team-managed?)")
    ctx["itss"] = r["values"][0]["issueTypeScreenScheme"]["id"]
    itens = jira.jira_listar_itens_tipo_tela([ctx["itss"]])["values"]
    padrao = next(i for i in itens if i["issueTypeId"] == "default")
    esquema = jira.jira_listar_esquemas_tela(ids=[padrao["screenSchemeId"]], incluir_usos=True)["values"][0]
    ctx["tela"] = str(esquema["screens"].get("create") or esquema["screens"]["default"])
    return {"itss": ctx["itss"], "itens": len(itens), "esquema_tela": esquema["id"], "tela_criar": ctx["tela"]}


def tela_inteira():
    if "tela" not in ctx:
        raise Pular("sem tela descoberta")
    t = jira.jira_obter_tela(ctx["tela"])
    custom = [c["id"] for a in t["tabs"] for c in a["fields"] if c["id"].startswith("customfield_")]
    if custom:
        ctx["campo"] = custom[0]
    ctx["aba"] = t["tabs"][0]["id"]
    return {"tela": t["name"], "abas": len(t["tabs"]), "total_campos": sum(a["total_campos"] for a in t["tabs"])}


def campos_da_aba_todos():
    """Percorre as partes de jira_listar_campos_aba e confere com o total."""
    if "aba" not in ctx:
        raise Pular("sem aba descoberta")
    inicio, n = 0, 0
    while inicio is not None:
        r = jira.jira_listar_campos_aba(ctx["tela"], ctx["aba"], inicio=inicio, limite=2000)
        n += r["retornados"]
        inicio = r["proximo_inicio"]
    assert n == r["total"], f"{n} x total {r['total']}"
    return {"percorridos": n}


def usos_campo():
    if "campo" not in ctx:
        raise Pular("tela sem campo customizado")
    return {"campo": ctx["campo"], "telas": jira.jira_usos_campo(ctx["campo"], limite=5)["total"]}


def na_tela(ferramenta):
    def chamar():
        if "tela" not in ctx:
            raise Pular("sem tela descoberta")
        return ferramenta(ctx["tela"])
    return chamar


def prioridades_todas():
    """Percorre as paginas de jira_listar_prioridades e confere com o total."""
    inicio, ids = 0, []
    while True:
        r = jira.jira_listar_prioridades(inicio=inicio, limite=10)
        ids += [p["id"] for p in r["values"]]
        if r.get("isLast") or not r["values"]:
            break
        inicio += len(r["values"])
    assert len(ids) == len(set(ids)) == r["total"], f"{len(ids)} x total {r['total']}"
    ctx["prioridade"] = ids[0]
    return {"percorridas": len(ids)}


def esquema_padrao_de_prioridade():
    r = jira.jira_listar_esquemas_prioridade(somente_padrao=True, incluir_prioridades=True)
    assert r["total"] == 1 and r["values"][0]["isDefault"], "esperado um unico esquema padrao"
    esquema = r["values"][0]
    ctx["esquema_prioridade"] = esquema["id"]
    ids = [p["id"] for p in esquema["priorities"]["values"]]
    assert esquema["defaultPriorityId"] in ids, "padrao fora das prioridades do esquema"
    return {"esquema": esquema["id"], "prioridades": len(ids)}


def prioridades_do_esquema():
    if "esquema_prioridade" not in ctx:
        raise Pular("sem esquema de prioridade descoberto")
    r = jira.jira_listar_prioridades_esquema(ctx["esquema_prioridade"])
    sequencias = [int(p["sequence"]) for p in r["values"]]
    assert sequencias == sorted(sequencias), "prioridades fora da ordem global"
    return {"total": r["total"]}


def sugestao_de_mapeamento():
    """So calcula: remover a ultima prioridade do esquema padrao exige mapear a propria."""
    if "esquema_prioridade" not in ctx:
        raise Pular("sem esquema de prioridade descoberto")
    ultima = jira.jira_listar_prioridades_esquema(ctx["esquema_prioridade"])["values"][-1]["id"]
    r = jira.jira_listar_prioridades_mapear(ctx["esquema_prioridade"], remover_prioridades=[ultima])
    return {"removida": ultima, "a_mapear": [p["id"] for p in r["values"]]}


def cadeia_de_configuracao_de_campo():
    """Caminho da skill jira-config-campos: projeto -> esquema -> item -> configuracao."""
    projeto_id = jira.jira_obter_projeto(ctx["projeto"])["id"]
    grupos = jira.jira_listar_config_projetos([projeto_id])["values"]
    grupo = next(g for g in grupos if projeto_id in g["projectIds"])
    esquema = (grupo.get("fieldConfigurationScheme") or {}).get("id")
    if esquema:
        itens = jira.jira_listar_itens_config([esquema])["values"]
        config = next(i for i in itens if i["issueTypeId"] == "default")["fieldConfigurationId"]
    else:
        config = str(jira.jira_listar_configs_campo(somente_padrao=True)["values"][0]["id"])
    ctx["config_campo"] = config
    return {"esquema": esquema or "padrao do site", "config": config}


def campos_da_configuracao():
    if "config_campo" not in ctx:
        raise Pular("sem configuracao de campo descoberta")
    pagina = jira.jira_listar_campos_config(ctx["config_campo"], limite=5)
    r = jira.jira_listar_campos_config(ctx["config_campo"], campo_ids=["summary", "nao_existe"])
    assert [i["id"] for i in r["values"]] == ["summary"] and r["nao_encontrados"] == ["nao_existe"]
    return {"total_itens": pagina["total"], "summary": r["values"][0]}


def notificacoes_do_projeto():
    """O esquema do projeto, os projetos que o usam e os eventos citados existem no site."""
    esquema = jira.jira_obter_notif_projeto(ctx["projeto"])
    usos = jira.jira_listar_notif_projetos(esquema_ids=[str(esquema["id"])], limite=100)
    eventos = {e["id"] for e in jira.jira_listar_eventos()["eventos"]}
    citados = {e["event"]["id"] for e in esquema.get("notificationSchemeEvents", [])}
    assert citados <= eventos, f"eventos fora de /events: {citados - eventos}"
    return {"esquema": esquema["id"], "eventos": len(citados), "projetos_no_esquema": usos["total"]}


def esquema_de_campos_do_projeto():
    """API nova, em beta: pula se estiver desligada no site."""
    projeto_id = jira.jira_obter_projeto(ctx["projeto"])["id"]
    try:
        r = jira.jira_listar_esquemas_campos(projeto_ids=[projeto_id])
    except LookupError as e:
        raise Pular(str(e))
    if not r["values"]:
        raise Pular("projeto sem esquema de campos")
    ctx["esquema_campos"] = str(r["values"][0]["id"])
    usos = jira.jira_usos_esquema_campos(ctx["esquema_campos"], projeto_ids=[projeto_id])
    assert usos["total"] == 1, "projeto nao aparece nos usos do proprio esquema"
    return {"esquema": ctx["esquema_campos"], "campos": r["values"][0].get("fieldsCount")}


def campos_do_esquema_todos():
    if "esquema_campos" not in ctx:
        raise Pular("sem esquema de campos descoberto")
    inicio, ids = 0, []
    while True:
        r = jira.jira_listar_campos_esquema(ctx["esquema_campos"], inicio=inicio, limite=100)
        ids += [c["fieldId"] for c in r["values"]]
        if r.get("isLast") or not r["values"]:
            break
        inicio += len(r["values"])
    assert len(ids) == len(set(ids)) == r["total"], f"{len(ids)} x total {r['total']}"
    um = jira.jira_listar_campos_esquema(ctx["esquema_campos"], campo_ids=[ids[0]])["values"]
    assert [c["fieldId"] for c in um] == [ids[0]], "filtro por campo nao funcionou"
    return {"percorridos": len(ids)}


def host_recusado():
    try:
        geral.atlassian_get("https://evil.example.com/rest/api/3/myself")
    except ValueError as e:
        return {"recusado": str(e)}
    raise AssertionError("host de fora foi aceito")


CASOS = [
    ("atlassian_conexao", lambda: geral.atlassian_conexao()),
    ("atlassian_get site", lambda: geral.atlassian_get("/rest/api/3/serverInfo")),
    ("trava de host", host_recusado),
    ("jsm_listar_service_desks", descobrir_projeto),
    ("atlassian_get gateway", lambda: geral.atlassian_get(
        f"https://api.atlassian.com/jira/forms/cloud/{{cloudId}}/project/{ctx['projeto']}/form")),
    ("jira_buscar_issues paginado", paginar_tudo),
    ("jira_obter_issue", lambda: jira.jira_obter_issue(ctx["issue"], campos=["summary", "status"])),
    ("jira_listar_comentarios", lambda: jira.jira_listar_comentarios(ctx["issue"], limite=3)),
    ("jira_listar_projetos", lambda: jira.jira_listar_projetos(filtro=ctx["projeto"])),
    ("jira_obter_projeto", lambda: jira.jira_obter_projeto(ctx["projeto"])),
    ("jira_listar_campos", lambda: jira.jira_listar_campos("summary")),
    ("jira_listar_status + usos", status_e_usos),
    ("jira_listar_workflows todos", workflows_todos),
    ("jira_usos_workflow", lambda: jira.jira_usos_workflow(ctx["workflow"])),
    ("jira_listar_tipos_issue", lambda: {"total": jira.jira_listar_tipos_issue()["total"]}),
    ("jira_listar_telas", lambda: {"total": jira.jira_listar_telas(limite=5)["total"]}),
    ("jira_listar_esquemas_tipo_tela", lambda: {"total": jira.jira_listar_esquemas_tipo_tela(limite=5)["total"]}),
    ("cadeia de telas do projeto", cadeia_de_telas),
    ("jira_obter_tela", tela_inteira),
    ("jira_listar_abas", na_tela(lambda t: {"total": jira.jira_listar_abas(t)["total"]})),
    ("jira_listar_campos_aba partes", campos_da_aba_todos),
    ("jira_listar_campos_disponiveis", na_tela(lambda t: {
        k: v for k, v in jira.jira_listar_campos_disponiveis(t, limite=5).items() if k != "campos"})),
    ("jira_usos_campo", usos_campo),
    ("jira_usos_esquema_tipo_tela", lambda: {"projetos": jira.jira_usos_esquema_tipo_tela(ctx["itss"])["total"]}
     if "itss" in ctx else (_ for _ in ()).throw(Pular("sem esquema descoberto"))),
    ("jira_listar_prioridades todas", prioridades_todas),
    ("jira_listar_prioridades esquemas", lambda: {"esquemas": jira.jira_listar_prioridades(
        ids=[ctx["prioridade"]], incluir_esquemas=True)["values"][0]["schemes"]["total"]}),
    ("jira_listar_esquemas_prioridade", lambda: {"total": jira.jira_listar_esquemas_prioridade(limite=5)["total"]}),
    ("esquema de prioridade padrao", esquema_padrao_de_prioridade),
    ("jira_listar_prioridades_esquema", prioridades_do_esquema),
    ("jira_usos_esquema_prioridade", lambda: {"projetos": jira.jira_usos_esquema_prioridade(
        ctx["esquema_prioridade"], limite=5)["total"]}),
    ("jira_listar_prioridades_mapear", sugestao_de_mapeamento),
    ("jira_listar_configs_campo", lambda: {"total": jira.jira_listar_configs_campo(limite=5)["total"]}),
    ("jira_listar_esquemas_config", lambda: {"total": jira.jira_listar_esquemas_config(limite=5)["total"]}),
    ("cadeia de configuracao de campo", cadeia_de_configuracao_de_campo),
    ("jira_listar_campos_config", campos_da_configuracao),
    ("jira_listar_esquemas_notif", lambda: {"total": jira.jira_listar_esquemas_notif(limite=5)["total"]}),
    ("jira_obter_notif_projeto + usos", notificacoes_do_projeto),
    ("jira_listar_papeis", lambda: {"total": jira.jira_listar_papeis()["total"]}),
    ("esquema de campos do projeto", esquema_de_campos_do_projeto),
    ("jira_listar_campos_esquema todos", campos_do_esquema_todos),
    ("jsm_listar_request_types", request_types),
    ("jsm_obter_request_type", lambda: jsm.jsm_obter_request_type(ctx["projeto"], ctx["rt"])),
    ("jsm_listar_campos_request_type", lambda: jsm.jsm_listar_campos_request_type(ctx["projeto"], ctx["rt"])),
    ("jsm_listar_grupos_request_type", lambda: jsm.jsm_listar_grupos_request_type(ctx["projeto"])),
    ("forms_listar", formularios),
    ("forms_obter", formulario),
    ("forms_obter_do_request_type", lambda: forms.forms_obter_do_request_type(ctx["projeto"], ctx["rt"])),
    ("forms_obter_dados_externos_rt", lambda: {"perguntas": len(
        forms.forms_obter_dados_externos_rt(ctx["projeto"], ctx["rt"])["fields"])}),
    ("forms_listar_da_issue", lambda: forms.forms_listar_da_issue(ctx["issue"])),
    ("forms_obter_da_issue", formulario_de_issue),
    ("forms_obter_respostas", na_issue(lambda c, f: {"total": forms.forms_obter_respostas(c, f)["total"]})),
    ("forms_obter_dados_externos", na_issue(lambda c, f: {"perguntas": len(
        forms.forms_obter_dados_externos(c, f)["fields"])})),
    ("forms_listar_anexos", na_issue(lambda c, f: {"perguntas": len(forms.forms_listar_anexos(c, f)["fields"])})),
]

falhas = pulados = 0
for nome, chamar in CASOS:
    inicio = time.time()
    try:
        texto = json.dumps(chamar(), ensure_ascii=False)
        print(f"OK    {nome:<32} {time.time() - inicio:5.1f}s {len(texto):>7} chars | {texto[:120]}")
    except Pular as p:
        pulados += 1
        print(f"PULOU {nome:<32} {p}")
    except Exception as e:
        falhas += 1
        print(f"ERRO  {nome:<32} {type(e).__name__}: {e}")
print(f"\n{len(CASOS) - falhas - pulados} ok, {pulados} pulados, {falhas} erros")
sys.exit(1 if falhas else 0)
