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
