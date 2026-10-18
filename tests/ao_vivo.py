"""Leituras no site configurado pelas ferramentas genericas, sem passar pelo MCP.

Nao depende de nenhum site: descobre sozinho um service desk, uma issue, um status,
um workflow, uma tela, um request type e um formulario para ler. Nada e escrito.
No fim, faz um GET em cada endpoint sem parametro de caminho das tabelas das skills:
endpoint documentado que responda 404 e erro da skill.

Rodar:  python -m tests.ao_vivo
Opcional: AO_VIVO_PROJETO=<chave de um projeto JSM> para escolher o projeto.
"""
import json
import logging
import os
import sys
import time

from atlassian_mcp_for_admins.ferramentas import geral
from atlassian_mcp_for_admins.nucleo.http import ErroAtlassian, cliente
from tests.test_plugin import PASTA_SKILLS, endpoints, skills

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
ctx: dict = {}
FORMS = "https://api.atlassian.com/jira/forms/cloud/{cloudId}"


class Pular(Exception):
    """O site nao tem o que este caso precisa."""


def ler(caminho, **kw):
    return geral.atlassian_ler("Teste ao vivo de leitura do plugin", caminho, **kw)


def exigir(*chaves):
    faltam = [c for c in chaves if c not in ctx]
    if faltam:
        raise Pular(f"sem {', '.join(faltam)} descoberto")


def host_recusado():
    try:
        ler("https://evil.example.com/rest/api/3/myself")
    except ValueError as e:
        return {"recusado": str(e)}
    raise AssertionError("host de fora foi aceito")


def descobrir_projeto():
    desks = ler("/rest/servicedeskapi/servicedesk", limite=100)["values"]
    if not desks:
        raise Pular("nenhum service desk visivel")
    escolhido = os.getenv("AO_VIVO_PROJETO")
    sd = next((d for d in desks if d["projectKey"] == escolhido), desks[0]) if escolhido else desks[0]
    ctx["projeto"], ctx["sd"] = sd["projectKey"], sd["id"]
    filtrado = ler("/rest/servicedeskapi/servicedesk", filtro={"projectKey": [sd["projectKey"]]})
    assert [d["id"] for d in filtrado["values"]] == [sd["id"]], "filtro por projectKey"
    ctx["projeto_id"] = ler(f"/rest/api/3/project/{sd['projectKey']}", manter=["id"])["id"]
    return {"projeto": sd["projectKey"], "service_desks_visiveis": len(desks)}


def paginar_tudo():
    """Percorre as paginas de uma JQL pequena com limite/continuar e confere com a contagem."""
    for janela in ("-1d", "-7d", "-30d", "-365d"):
        jql = f"project = {ctx['projeto']} AND created >= {janela}"
        total = ler("/rest/api/3/search/approximate-count", corpo={"jql": jql})["count"]
        if total:
            break
    else:
        raise Pular("projeto sem issues no ultimo ano")
    chaves, corpo, paginas = [], {"jql": jql, "fields": ["created"]}, 0
    while True:
        r = ler("/rest/api/3/search/jql", corpo=corpo, limite=70)
        chaves += [i["key"] for i in r["issues"]]
        paginas += 1
        if not r["continuar"] or len(chaves) >= 500:
            break
        corpo = r["continuar"]["corpo"]
    ctx["issue"], ctx["issues"] = chaves[0], chaves[:40]
    assert len(chaves) == len(set(chaves)), "chave repetida entre paginas"
    if not r["continuar"]:
        assert len(chaves) == total, f"coletado {len(chaves)} x contagem {total}"
    return {"jql": jql, "chamadas": paginas, "coletado": len(chaves), "contagem_api": total}


def status_e_usos():
    s = ler("/rest/api/3/statuses/search", params={"maxResults": 1})
    sid = s["values"][0]["id"]
    usos = ler([f"/rest/api/3/statuses/{sid}/workflowUsages", f"/rest/api/3/statuses/{sid}/projectUsages"],
               limite=200)
    return {"total_status": s["total"], **{c.rsplit("/", 1)[1]: list(r)[:3] for c, r in usos.items()}}


def workflows_todos():
    ids, params = [], None
    while True:
        r = ler("/rest/api/3/workflow/search", params=params, limite=200, manter=["values.id.entityId", "total"])
        ids += [w["id"]["entityId"] for w in r["values"]]
        if not r["continuar"]:
            break
        params = r["continuar"]["params"]
    ctx["workflow"] = ids[0]
    assert len(ids) == len(set(ids)) == r["total"], f"{len(ids)} x total {r['total']}"
    return {"percorridos": len(ids), "total_api": r["total"]}


def usos_workflow():
    exigir("workflow")
    w = ctx["workflow"]
    r = ler([f"/rest/api/3/workflow/{w}/projectUsages", f"/rest/api/3/workflow/{w}/workflowSchemes"], limite=50)
    assert not any("erro" in v for v in r.values()), r
    return {c.rsplit("/", 1)[1]: "ok" for c in r}


def cadeia_de_telas():
    """Projeto -> esquema por tipo -> item default -> esquema de tela -> tela -> abas -> campos."""
    r = ler("/rest/api/3/issuetypescreenscheme/project", params={"projectId": ctx["projeto_id"]})
    if not r["values"]:
        raise Pular("projeto sem esquema de tela por tipo de issue (team-managed?)")
    ctx["itss"] = r["values"][0]["issueTypeScreenScheme"]["id"]
    itens = ler("/rest/api/3/issuetypescreenscheme/mapping", params={"issueTypeScreenSchemeId": ctx["itss"]},
                filtro={"issueTypeId": ["default"]})["values"]
    esquema = ler("/rest/api/3/screenscheme", params={"id": itens[0]["screenSchemeId"]})["values"][0]
    ctx["tela"] = str(esquema["screens"].get("create") or esquema["screens"]["default"])
    abas = ler(f"/rest/api/3/screens/{ctx['tela']}/tabs")
    ctx["aba"] = str(abas[0]["id"])
    campos = ler([f"/rest/api/3/screens/{ctx['tela']}/tabs/{a['id']}/fields" for a in abas], limite=50,
                 manter=["id"])
    custom = [c["id"] for r in campos.values() for c in r["itens"] if c["id"].startswith("customfield_")]
    if custom:
        ctx["campo"] = custom[0]
    return {"tela": ctx["tela"], "abas": len(abas), "campos": sum(r["total"] for r in campos.values())}


def campos_da_aba_em_fatias():
    exigir("tela", "aba")
    caminho = f"/rest/api/3/screens/{ctx['tela']}/tabs/{ctx['aba']}/fields"
    inicio, n, chamadas = 0, 0, 0
    while inicio is not None and chamadas < 20:
        r = ler(caminho, inicio=inicio, limite=500, manter=["id"])
        n += len(r["itens"])
        inicio, chamadas = r["proximo_inicio"], chamadas + 1
    if inicio is None:
        assert n == r["total"], f"{n} x {r['total']}"
    return {"percorridos": n, "total": r["total"]}


def usos_campo():
    exigir("campo")
    return {"campo": ctx["campo"], "telas": ler(f"/rest/api/3/field/{ctx['campo']}/screens",
                                                params={"expand": "tab", "maxResults": 5})["total"]}


def prioridades_todas():
    r = ler("/rest/api/3/priority/search", limite=500, manter=["values.id", "total"])
    ids = [p["id"] for p in r["values"]]
    assert len(ids) == len(set(ids)) == r["total"], f"{len(ids)} x total {r['total']}"
    ctx["prioridade"] = ids[0]
    return {"percorridas": len(ids)}


def esquema_padrao_de_prioridade():
    r = ler("/rest/api/3/priorityscheme", params={"onlyDefault": "true", "expand": "priorities"})
    assert r["total"] == 1 and r["values"][0]["isDefault"], "esperado um unico esquema padrao"
    esquema = r["values"][0]
    ctx["esquema_prioridade"] = str(esquema["id"])
    ids = [p["id"] for p in esquema["priorities"]["values"]]
    assert esquema["defaultPriorityId"] in ids, "padrao fora das prioridades do esquema"
    return {"esquema": esquema["id"], "prioridades": len(ids)}


def prioridades_do_esquema():
    exigir("esquema_prioridade")
    r = ler(f"/rest/api/3/priorityscheme/{ctx['esquema_prioridade']}/priorities", limite=200)
    sequencias = [int(p["sequence"]) for p in r["values"]]
    assert sequencias == sorted(sequencias), "prioridades fora da ordem global"
    ctx["ultima_prioridade"] = r["values"][-1]["id"]
    return {"total": len(r["values"])}


def sugestao_de_mapeamento():
    """So calcula: POST de consulta pelo atlassian_ler."""
    exigir("esquema_prioridade", "ultima_prioridade")
    r = ler("/rest/api/3/priorityscheme/mappings", corpo={
        "schemeId": int(ctx["esquema_prioridade"]), "startAt": 0, "maxResults": 50,
        "priorities": {"add": [], "remove": [int(ctx["ultima_prioridade"])]}, "projects": {"add": []}})
    return {"removida": ctx["ultima_prioridade"], "a_mapear": [p["id"] for p in r["values"]]}


def cadeia_de_configuracao_de_campo():
    grupos = ler("/rest/api/3/fieldconfigurationscheme/project", params={"projectId": ctx["projeto_id"]})["values"]
    grupo = next(g for g in grupos if ctx["projeto_id"] in g["projectIds"])
    esquema = (grupo.get("fieldConfigurationScheme") or {}).get("id")
    if esquema:
        itens = ler("/rest/api/3/fieldconfigurationscheme/mapping", params={"fieldConfigurationSchemeId": esquema},
                    filtro={"issueTypeId": ["default"]})["values"]
        config = itens[0]["fieldConfigurationId"]
    else:
        config = str(ler("/rest/api/3/fieldconfiguration", params={"isDefault": "true"})["values"][0]["id"])
    ctx["config_campo"] = config
    return {"esquema": esquema or "padrao do site", "config": config}


def campos_da_configuracao():
    exigir("config_campo")
    r = ler(f"/rest/api/3/fieldconfiguration/{ctx['config_campo']}/fields", filtro={"id": ["summary", "nao_existe"]})
    assert [i["id"] for i in r["values"]] == ["summary"], r["values"]
    assert r["sem_correspondencia"] == {"id": ["nao_existe"]}, r["sem_correspondencia"]
    return {"summary": r["values"][0]}


def notificacoes_do_projeto():
    esquema = ler(f"/rest/api/3/project/{ctx['projeto']}/notificationscheme", params={"expand": "all"})
    usos = ler("/rest/api/3/notificationscheme/project", params={"notificationSchemeId": esquema["id"]}, limite=100)
    eventos = {e["id"] for e in ler("/rest/api/3/events")}
    citados = {e["event"]["id"] for e in esquema.get("notificationSchemeEvents", [])}
    assert citados <= eventos, f"eventos fora de /events: {citados - eventos}"
    return {"esquema": esquema["id"], "eventos": len(citados), "projetos_no_esquema": len(usos["values"])}


def papeis_por_nome():
    papeis = ler("/rest/api/3/role", manter=["name"])
    if not papeis:
        raise Pular("sem papeis de projeto")
    nome = papeis[0]["name"]
    r = ler("/rest/api/3/role", filtro={"name": [nome]})["itens"]
    assert r and all(p["name"] == nome for p in r), r
    return {"papeis": len(papeis), "filtrados": len(r)}


def esquema_de_campos_do_projeto():
    """API nova, em beta: pula se estiver desligada no site."""
    try:
        r = ler("/rest/api/3/config/fieldschemes", params={"projectId": ctx["projeto_id"]})
    except LookupError as e:
        raise Pular(str(e))
    if not r["values"]:
        raise Pular("projeto sem esquema de campos")
    ctx["esquema_campos"] = str(r["values"][0]["id"])
    return {"esquema": ctx["esquema_campos"]}


def campos_do_esquema_todos():
    exigir("esquema_campos")
    r = ler(f"/rest/api/3/config/fieldschemes/{ctx['esquema_campos']}/fields", limite=500, manter=["values.fieldId"])
    ids = [c["fieldId"] for c in r["values"]]
    assert len(ids) == len(set(ids)), "campo repetido entre paginas"
    um = ler(f"/rest/api/3/config/fieldschemes/{ctx['esquema_campos']}/fields", params={"fieldId": ids[0]})
    assert [c["fieldId"] for c in um["values"]] == [ids[0]], "filtro por campo nao funcionou"
    return {"percorridos": len(ids)}


def request_types():
    r = ler(f"/rest/servicedeskapi/servicedesk/{ctx['sd']}/requesttype", limite=100)
    if not r["values"]:
        raise Pular("service desk sem request types")
    ctx["rt"] = r["values"][0]["id"]
    return {"total": len(r["values"]), "primeiro": ctx["rt"]}


def request_type_inteiro():
    exigir("rt")
    base = f"/rest/servicedeskapi/servicedesk/{ctx['sd']}"
    r = ler([f"{base}/requesttype/{ctx['rt']}", f"{base}/requesttype/{ctx['rt']}/field", f"{base}/requesttypegroup"])
    assert not any(isinstance(v, dict) and "erro" in v for v in r.values()), r
    return {c.rsplit("/", 1)[1]: "ok" for c in r}


def formularios():
    r = ler(f"{FORMS}/project/{ctx['projeto']}/form")
    if r:
        ctx["form"] = r[0]["id"]
    return {"total": len(r)}


def formulario():
    exigir("form")
    f = ler(f"{FORMS}/project/{ctx['projeto']}/form/{ctx['form']}", manter=["id", "design.settings"])
    assert set(f["design"]) == {"settings"}, list(f["design"])
    return {"formulario": f["id"], "nome": f["design"]["settings"].get("name")}


def formulario_do_request_type():
    exigir("rt")
    base = f"{FORMS}/servicedesk/{ctx['sd']}/requesttype/{ctx['rt']}/form"
    try:
        f = ler(base, manter=["id"])
    except ErroAtlassian as e:
        if e.status == 404:
            return {"formulario": None}
        raise
    externos = ler(f"{base}/externaldata")
    return {"formulario": f.get("id"), "perguntas_externas": len(externos.get("fields") or [])}


def formulario_de_issue():
    """Acha uma issue com formulario entre as coletadas e le o formulario e os anexos."""
    exigir("issues")
    for chave in ctx["issues"]:
        itens = ler(f"{FORMS}/issue/{chave}/form")
        if itens:
            fid = itens[0]["id"]
            base = f"{FORMS}/issue/{chave}/form/{fid}"
            r = ler([base, f"{base}/format/answers", f"{base}/externaldata", f"{base}/attachment"],
                    manter=["state.status", "state.answers"])
            erros = {c: v for c, v in r.items() if isinstance(v, dict) and "erro" in v}
            assert not erros, erros
            return {"issue": chave, "status": r[base]["state"]["status"]}
    raise Pular("nenhuma das issues coletadas tem formulario")


def endpoints_das_skills():
    """GET de cada linha sem parametro de caminho: 404 = caminho errado na skill."""
    http, quebrados, conferidos = cliente(), [], 0
    for pasta in skills():
        for operacao, _, metodo, caminho, _ in endpoints((pasta / "SKILL.md").read_text(encoding="utf-8")):
            if metodo != "GET" or "{" in caminho.replace("{cloudId}", ""):
                continue
            conferidos += 1
            try:
                # /_edge e a Forms API nao aceitam query desconhecida; a /rest pagina com maxResults
                http.get(caminho, params={"maxResults": 1} if caminho.startswith("/rest/") else None)
            except ErroAtlassian as e:
                if e.status == 404:
                    quebrados.append(f"{pasta.name}: {caminho}")
            except LookupError:
                pass  # API em beta desligada no site
    assert not quebrados, quebrados
    return {"conferidos": conferidos}


CASOS = [
    ("atlassian_conexao", lambda: geral.atlassian_conexao()),
    ("trava de host", host_recusado),
    ("service desks + filtro", descobrir_projeto),
    ("busca JQL com continuar", paginar_tudo),
    ("issue", lambda: ler(f"/rest/api/3/issue/{ctx['issue']}", params={"fields": "summary,status"},
                          manter=["key", "fields"])),
    ("comentarios", lambda: {"lidos": len(ler(f"/rest/api/3/issue/{ctx['issue']}/comment", limite=3)["comments"])}),
    ("projetos", lambda: {"lidos": len(ler("/rest/api/3/project/search", params={"query": ctx["projeto"]},
                                           limite=10)["values"])}),
    ("campos por busca", lambda: {"lidos": len(ler("/rest/api/3/field/search", params={"query": "summary"},
                                                   limite=5)["values"])}),
    ("status + usos em lista", status_e_usos),
    ("workflows todos", workflows_todos),
    ("usos de workflow", usos_workflow),
    ("tipos de issue", lambda: {"total": len(ler("/rest/api/3/issuetype", manter=["id"]))}),
    ("cadeia de telas e tela inteira", cadeia_de_telas),
    ("campos da aba em fatias", campos_da_aba_em_fatias),
    ("campos disponiveis", lambda: {k: v for k, v in ler(f"/rest/api/3/screens/{ctx['tela']}/availableFields",
                                                         limite=5).items() if k != "itens"}
     if "tela" in ctx else (_ for _ in ()).throw(Pular("sem tela"))),
    ("telas do campo", usos_campo),
    ("prioridades todas", prioridades_todas),
    ("esquema de prioridade padrao", esquema_padrao_de_prioridade),
    ("prioridades do esquema", prioridades_do_esquema),
    ("mapeamento de prioridades (POST de consulta)", sugestao_de_mapeamento),
    ("cadeia de configuracao de campo", cadeia_de_configuracao_de_campo),
    ("campos da configuracao por filtro", campos_da_configuracao),
    ("notificacoes do projeto", notificacoes_do_projeto),
    ("papeis por filtro", papeis_por_nome),
    ("esquema de campos do projeto", esquema_de_campos_do_projeto),
    ("campos do esquema todos", campos_do_esquema_todos),
    ("request types", request_types),
    ("request type em lista", request_type_inteiro),
    ("formularios do projeto", formularios),
    ("formulario sem layout", formulario),
    ("formulario do request type", formulario_do_request_type),
    ("formulario de issue", formulario_de_issue),
    ("endpoints das skills", endpoints_das_skills),
]

falhas = pulados = 0
for nome, chamar in CASOS:
    inicio = time.time()
    try:
        texto = json.dumps(chamar(), ensure_ascii=False)
        print(f"OK    {nome:<44} {time.time() - inicio:5.1f}s {len(texto):>7} chars | {texto[:100]}")
    except Pular as p:
        pulados += 1
        print(f"PULOU {nome:<44} {p}")
    except Exception as e:
        falhas += 1
        print(f"ERRO  {nome:<44} {type(e).__name__}: {e}")
print(f"\n{len(CASOS) - falhas - pulados} ok, {pulados} pulados, {falhas} erros")
sys.exit(1 if falhas else 0)
