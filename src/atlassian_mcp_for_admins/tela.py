"""Tela local para cadastrar e trocar o site Atlassian do plugin.

Sobe um servidor so em 127.0.0.1 e abre o navegador. Protecoes: chave aleatoria na
URL (vai no fragmento #k=, nunca ao servidor pelo endereco, e volta como cabecalho
X-Chave em toda chamada da API), Host conferido (contra DNS rebinding), Origin
conferido, sem CORS, e o token nunca volta para a pagina. Fecha sozinha apos 30
minutos sem uso ou pelo botao Fechar.

Rodar: python -m atlassian_mcp_for_admins.tela [--porta 8765] [--sem-navegador]
"""
import argparse
import json
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

import requests

from . import config, perfis
from .nucleo.http import ERROS_PREVISTOS, ClienteHttp

PORTA_PADRAO = 8765
OCIOSO_SEGUNDOS = 30 * 60
MAXIMO_CORPO = 64 * 1024
PAGINA_TOKEN = "https://id.atlassian.com/manage-profile/security/api-tokens"


# ------------------------------------------------------------------ operacoes
def estado() -> dict:
    """O que a pagina mostra. Nunca inclui token."""
    dados = perfis.carregar()
    sites = []
    for perfil_id, p in dados["sites"].items():
        try:
            tem_token = bool(perfis.token(perfil_id))
        except Exception:
            tem_token = False
        sites.append({"id": perfil_id, "nome": p["nome"], "url": p["url"], "email": p["email"],
                      "tem_token": tem_token, "ativo": perfil_id == dados["ativo"]})
    c = config.credenciais(com_repositorio=False)  # o que o plugin instalado usa
    avisos = []
    repositorio = config._carregar(config.ARQUIVO_REPOSITORIO)
    if all((repositorio.get(n) or "").strip() for n in config.NOMES):
        avisos.append(f"Existe {config.ARQUIVO_REPOSITORIO}: no servidor rodado deste repositorio "
                      "(desenvolvimento e testes) ele vence os perfis. O plugin instalado nao le esse arquivo.")
    if dados["ativo"] and c["origem"] and not str(c["origem"]).startswith("perfil"):
        avisos.append(f"O plugin esta usando {c['origem']}, que vence os perfis: o perfil ativo so vale "
                      "quando essa fonte estiver vazia.")
    ativo = next((s for s in sites if s["ativo"]), None)
    if ativo and not ativo["tem_token"]:
        avisos.append(f"O perfil ativo ({ativo['nome']}) esta sem token no cofre: edite e informe o token.")
    legado = config._fonte([config._carregar(config.ARQUIVO_USUARIO)])
    ja_importado = any(s["url"] == legado["url"] and s["email"] == legado["email"] for s in sites)
    return {"sites": sites,
            "em_uso": {"site": c["url"] or None, "email": c["email"] or None, "origem": c["origem"]},
            "avisos": avisos,
            "importar": {"site": legado["url"], "arquivo": str(config.ARQUIVO_USUARIO)}
            if config._completa(legado) and not ja_importado else None,
            "pagina_token": PAGINA_TOKEN}


def importar() -> str:
    """Cria um perfil a partir do ~/.config/atlassian-admin/.env (metodo anterior)."""
    legado = config._fonte([config._carregar(config.ARQUIVO_USUARIO)])
    if not config._completa(legado):
        raise ValueError(f"{config.ARQUIVO_USUARIO} nao tem JIRA_URL, JIRA_EMAIL e JIRA_TOKEN completos")
    nome = (urlparse(legado["url"]).hostname or "site").split(".")[0]
    return perfis.salvar_site(nome, legado["url"], legado["email"], legado["token"])


def testar(perfil_id: str) -> dict:
    """Conecta com o perfil: usuario autenticado e se tem permissao de admin do Jira."""
    p = perfis.carregar()["sites"].get(perfil_id)
    if not p:
        raise LookupError(f"Perfil {perfil_id} nao existe")
    token = perfis.token(perfil_id)
    if not token:
        return {"ok": False, "erro": "Perfil sem token no cofre"}
    http = ClienteHttp(p["url"], p["email"], token, tentativas=2)
    try:
        eu = http.get("/rest/api/3/myself")
        permissao = http.get("/rest/api/3/mypermissions", params={"permissions": "ADMINISTER"})
    except ERROS_PREVISTOS as erro:
        return {"ok": False, "erro": _explicar(erro, p["url"])}
    admin = ((permissao.get("permissions") or {}).get("ADMINISTER") or {}).get("havePermission")
    return {"ok": True, "usuario": eu.get("displayName"), "email": eu.get("emailAddress"), "admin": admin}


def _explicar(erro: Exception, url: str) -> str:
    """Mensagem curta para os erros comuns de conexao; o resto vai como veio."""
    status = getattr(erro, "status", None)
    if status == 401:
        return "E-mail ou API token invalido (HTTP 401). Gere um token novo e edite o perfil."
    if status == 403:
        return "A conta autenticou, mas nao tem acesso a este site (HTTP 403)."
    if status == 404:
        return f"{url} respondeu 404: confira se e a URL do site Atlassian."
    if isinstance(erro, requests.ConnectionError):
        return f"Nao foi possivel conectar a {url}: confira a URL e a rede."
    if isinstance(erro, requests.Timeout):
        return f"{url} demorou demais para responder."
    return str(erro)[:300]


# ---------------------------------------------------------------- servidor
class Tela(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, porta: int):
        super().__init__(("127.0.0.1", porta), Pedido)
        self.chave = secrets.token_urlsafe(24)
        self.ultimo_uso = time.monotonic()

    @property
    def porta(self) -> int:
        return self.server_address[1]

    @property
    def endereco(self) -> str:
        return f"http://127.0.0.1:{self.porta}/#k={self.chave}"

    def hosts(self) -> set:
        return {f"127.0.0.1:{self.porta}", f"localhost:{self.porta}"}


class Pedido(BaseHTTPRequestHandler):
    server: Tela
    server_version = "atlassian-admin-tela"

    def log_message(self, formato, *args):  # sem log de pedidos (nada de corpo nem chave)
        pass

    # ---- respostas
    def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dado) -> None:
        self._enviar(status, json.dumps(dado, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    # ---- protecoes
    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.server.hosts()

    def _api_ok(self) -> bool:
        origem = self.headers.get("Origin")
        if origem and urlparse(origem).netloc not in self.server.hosts():
            return False
        return secrets.compare_digest(self.headers.get("X-Chave", ""), self.server.chave)

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > MAXIMO_CORPO:
            raise ValueError("Corpo grande demais")
        dado = json.loads(self.rfile.read(tamanho) or b"{}")
        if not isinstance(dado, dict):
            raise ValueError("Corpo deve ser um objeto JSON")
        return dado

    # ---- roteamento
    def _tratar(self, metodo: str) -> None:
        self.server.ultimo_uso = time.monotonic()
        if not self._host_ok():
            return self._json(403, {"erro": "Host nao permitido"})
        caminho = urlparse(self.path).path
        if metodo == "GET" and caminho == "/":
            return self._enviar(200, PAGINA.encode("utf-8"), "text/html; charset=utf-8")
        if not caminho.startswith("/api/"):
            return self._json(404, {"erro": "Nao encontrado"})
        if not self._api_ok():
            return self._json(403, {"erro": "Chave invalida: abra a tela pelo endereco que o comando mostrou"})
        partes = caminho.strip("/").split("/")[1:]
        try:
            resposta = self._api(metodo, partes)
        except LookupError as erro:
            return self._json(404, {"erro": str(erro)})
        except (ValueError, RuntimeError) as erro:
            return self._json(400, {"erro": str(erro)})
        if resposta is None:
            return self._json(404, {"erro": "Nao encontrado"})
        self._json(200, resposta)

    def _api(self, metodo: str, partes: list) -> Optional[dict]:
        if metodo == "GET" and partes == ["estado"]:
            return estado()
        if metodo == "POST" and partes == ["sites"]:
            d = self._corpo()
            perfil_id = perfis.salvar_site(d.get("nome", ""), d.get("url", ""), d.get("email", ""),
                                           d.get("token") or None, d.get("id") or None)
            return {**estado(), "salvo": perfil_id}
        if metodo == "POST" and partes == ["importar"]:
            perfil_id = importar()
            return {**estado(), "salvo": perfil_id}
        if metodo == "POST" and partes == ["fechar"]:
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return {"fechado": True}
        if len(partes) == 3 and partes[0] == "sites" and metodo == "POST":
            if partes[2] == "ativar":
                perfis.ativar(partes[1])
                return estado()
            if partes[2] == "testar":
                return testar(partes[1])
        if len(partes) == 2 and partes[0] == "sites" and metodo == "DELETE":
            perfis.remover(partes[1])
            return estado()
        return None

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")

    def do_DELETE(self):
        self._tratar("DELETE")


def _vigiar(tela: Tela) -> None:
    while True:
        time.sleep(30)
        if time.monotonic() - tela.ultimo_uso > OCIOSO_SEGUNDOS:
            tela.shutdown()
            return


def abrir(porta: int = PORTA_PADRAO) -> Tela:
    try:
        return Tela(porta)
    except OSError:  # porta ocupada (outra tela aberta?): qualquer porta livre
        return Tela(0)


def main(argv: Optional[list] = None) -> None:
    argumentos = argparse.ArgumentParser(description="Tela de sites do plugin atlassian-admin")
    argumentos.add_argument("--porta", type=int, default=PORTA_PADRAO)
    argumentos.add_argument("--sem-navegador", action="store_true")
    opcoes = argumentos.parse_args(argv)
    tela = abrir(opcoes.porta)
    print(f"Tela de sites aberta em {tela.endereco}", flush=True)
    print("Fecha pelo botao Fechar ou apos 30 minutos sem uso.", flush=True)
    if not opcoes.sem_navegador:
        webbrowser.open(tela.endereco)
    threading.Thread(target=_vigiar, args=(tela,), daemon=True).start()
    try:
        tela.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tela.server_close()
    print("Tela de sites fechada.", flush=True)


PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sites Atlassian</title>
<style>
:root {
  --fundo: #f6f7f9; --cartao: #ffffff; --texto: #1d2125; --suave: #626f86; --borda: #dcdfe4;
  --destaque: #0c66e4; --destaque-texto: #ffffff; --ok: #1f845a; --ok-fundo: #dcfff1;
  --erro: #c9372c; --erro-fundo: #ffeceb; --aviso: #7f5f01; --aviso-fundo: #fff7d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fundo: #161a1d; --cartao: #22272b; --texto: #dee4ea; --suave: #9fadbc; --borda: #38414a;
    --destaque: #579dff; --destaque-texto: #161a1d; --ok: #4bce97; --ok-fundo: #1c3329;
    --erro: #f87168; --erro-fundo: #42221f; --aviso: #f5cd47; --aviso-fundo: #332e1b;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo); color: var(--texto);
  font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 0 0 12px; }
.sub { color: var(--suave); margin: 0 0 24px; }
.cartao { background: var(--cartao); border: 1px solid var(--borda); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
.em-uso { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.ponto { width: 10px; height: 10px; border-radius: 50%; background: var(--ok); flex: none; }
.ponto.off { background: var(--erro); }
.rotulo { color: var(--suave); font-size: 13px; }
.aviso { background: var(--aviso-fundo); color: var(--aviso); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 14px; }
.lista { display: grid; gap: 10px; }
.site { border: 1px solid var(--borda); border-radius: 10px; padding: 12px 14px; display: grid; gap: 6px; }
.site.ativo { border-color: var(--destaque); box-shadow: 0 0 0 1px var(--destaque) inset; }
.linha { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.nome { font-weight: 600; }
.host { color: var(--suave); font-size: 14px; word-break: break-all; }
.selo { font-size: 12px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--borda); color: var(--suave); }
.selo.ativo { background: var(--destaque); border-color: var(--destaque); color: var(--destaque-texto); }
.selo.erro { color: var(--erro); border-color: var(--erro); }
.acoes { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
button { font: inherit; font-size: 14px; border-radius: 6px; border: 1px solid var(--borda); background: transparent;
  color: var(--texto); padding: 6px 12px; cursor: pointer; }
button:hover { border-color: var(--suave); }
button.primario { background: var(--destaque); color: var(--destaque-texto); border-color: var(--destaque); }
button.perigo { color: var(--erro); }
button:disabled { opacity: .5; cursor: default; }
.resultado { font-size: 13px; border-radius: 6px; padding: 6px 10px; }
.resultado.ok { background: var(--ok-fundo); color: var(--ok); }
.resultado.erro { background: var(--erro-fundo); color: var(--erro); }
form { display: grid; gap: 12px; }
label { display: grid; gap: 4px; font-size: 13px; color: var(--suave); }
input { font: inherit; color: var(--texto); background: var(--fundo); border: 1px solid var(--borda); border-radius: 6px; padding: 8px 10px; }
input:focus { outline: 2px solid var(--destaque); outline-offset: -1px; }
.dupla { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 560px) { .dupla { grid-template-columns: 1fr; } .acoes { margin-left: 0; } }
a { color: var(--destaque); }
.vazio { color: var(--suave); }
.rodape { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: var(--suave); font-size: 13px; flex-wrap: wrap; }
.mensagem { min-height: 20px; font-size: 14px; }
.mensagem.erro { color: var(--erro); }
</style>
</head>
<body>
<main>
  <h1>Sites Atlassian</h1>
  <p class="sub">Plugin atlassian-admin. A troca de site vale na proxima chamada do plugin, sem reiniciar a sessao.</p>

  <div id="avisos"></div>

  <section class="cartao">
    <div class="em-uso">
      <span id="ponto" class="ponto"></span>
      <div>
        <div class="rotulo">Em uso pelo plugin agora</div>
        <div id="em-uso">...</div>
      </div>
    </div>
  </section>

  <section class="cartao">
    <h2>Sites salvos</h2>
    <div id="importar"></div>
    <div id="lista" class="lista"></div>
  </section>

  <section class="cartao">
    <h2 id="titulo-form">Adicionar site</h2>
    <form id="form" autocomplete="off">
      <input type="hidden" id="f-id">
      <div class="dupla">
        <label>Nome do perfil<input id="f-nome" required placeholder="Producao"></label>
        <label>URL do site<input id="f-url" required placeholder="https://empresa.atlassian.net"></label>
      </div>
      <div class="dupla">
        <label>E-mail da conta<input id="f-email" type="email" required placeholder="admin@empresa.com"></label>
        <label>API token<input id="f-token" type="password" placeholder="cole o token"></label>
      </div>
      <div class="rotulo">O token vai direto para o Keychain e nunca volta para esta pagina.
        <a id="link-token" target="_blank" rel="noopener noreferrer">Criar um API token</a></div>
      <div class="linha">
        <button type="submit" class="primario" id="f-salvar">Salvar</button>
        <button type="button" id="f-cancelar" hidden>Cancelar edicao</button>
        <span id="mensagem" class="mensagem"></span>
      </div>
    </form>
  </section>

  <div class="rodape">
    <span>Esta tela so escuta em 127.0.0.1 e fecha sozinha apos 30 minutos sem uso.</span>
    <button type="button" id="fechar">Fechar tela</button>
  </div>
</main>
<script>
"use strict";
const chave = new URLSearchParams(location.hash.slice(1)).get("k") || "";
const $ = (id) => document.getElementById(id);
let atual = null;

async function api(metodo, caminho, corpo) {
  const r = await fetch("/api/" + caminho, {
    method: metodo,
    headers: Object.assign({"X-Chave": chave}, corpo ? {"Content-Type": "application/json"} : {}),
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const dado = await r.json().catch(() => ({erro: "Resposta invalida"}));
  if (!r.ok) throw new Error(dado.erro || ("HTTP " + r.status));
  return dado;
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined && texto !== null) e.textContent = texto;
  return e;
}

function host(url) { try { return new URL(url).host; } catch (e) { return url; } }

function mensagem(texto, erro) {
  $("mensagem").textContent = texto || "";
  $("mensagem").className = "mensagem" + (erro ? " erro" : "");
}

function desenhar(e) {
  atual = e;
  const avisos = $("avisos");
  avisos.replaceChildren(...e.avisos.map((a) => el("div", "aviso", a)));

  const uso = e.em_uso;
  $("ponto").className = "ponto" + (uso.site ? "" : " off");
  $("em-uso").textContent = uso.site
    ? host(uso.site) + "  -  " + uso.email + "  (" + uso.origem + ")"
    : "Nenhum site configurado. Adicione um abaixo.";

  const imp = $("importar");
  imp.replaceChildren();
  if (e.importar) {
    const caixa = el("div", "aviso");
    caixa.append(el("span", null, "Ha credenciais de " + host(e.importar.site) + " em " + e.importar.arquivo + ". "));
    const b = el("button", null, "Importar como perfil");
    b.onclick = () => acao(() => api("POST", "importar"), "Importado");
    caixa.append(b);
    imp.append(caixa);
  }

  const lista = $("lista");
  if (!e.sites.length) {
    lista.replaceChildren(el("div", "vazio", "Nenhum site salvo ainda."));
    return;
  }
  lista.replaceChildren(...e.sites.map((s) => {
    const card = el("div", "site" + (s.ativo ? " ativo" : ""));
    const linha = el("div", "linha");
    linha.append(el("span", "nome", s.nome));
    if (s.ativo) linha.append(el("span", "selo ativo", "ativo"));
    if (!s.tem_token) linha.append(el("span", "selo erro", "sem token"));
    const acoes = el("div", "acoes");
    if (!s.ativo) {
      const b = el("button", "primario", "Usar este");
      b.onclick = () => acao(() => api("POST", "sites/" + encodeURIComponent(s.id) + "/ativar"), "Agora em uso: " + s.nome);
      acoes.append(b);
    }
    const testar = el("button", null, "Testar");
    const editar = el("button", null, "Editar");
    const remover = el("button", "perigo", "Remover");
    acoes.append(testar, editar, remover);
    linha.append(acoes);
    const detalhe = el("div", "host", host(s.url) + "  -  " + s.email);
    const resultado = el("div");
    card.append(linha, detalhe, resultado);

    testar.onclick = async () => {
      testar.disabled = true;
      resultado.className = "resultado";
      resultado.textContent = "Testando...";
      try {
        const r = await api("POST", "sites/" + encodeURIComponent(s.id) + "/testar");
        resultado.className = "resultado " + (r.ok ? "ok" : "erro");
        resultado.textContent = r.ok
          ? "Conectado como " + r.usuario + (r.admin ? " (admin do Jira)" : " (sem permissao de admin do Jira)")
          : r.erro;
      } catch (err) {
        resultado.className = "resultado erro";
        resultado.textContent = err.message;
      } finally { testar.disabled = false; }
    };
    editar.onclick = () => preencher(s);
    remover.onclick = () => {
      if (confirm("Remover o perfil " + s.nome + "? O token dele sai do Keychain.")) {
        acao(() => api("DELETE", "sites/" + encodeURIComponent(s.id)), "Removido: " + s.nome);
      }
    };
    return card;
  }));
}

function preencher(s) {
  $("f-id").value = s ? s.id : "";
  $("f-nome").value = s ? s.nome : "";
  $("f-url").value = s ? s.url : "";
  $("f-email").value = s ? s.email : "";
  $("f-token").value = "";
  $("f-token").placeholder = s ? "deixe vazio para manter o atual" : "cole o token";
  $("titulo-form").textContent = s ? "Editar " + s.nome : "Adicionar site";
  $("f-cancelar").hidden = !s;
  mensagem("");
  if (s) $("f-nome").focus();
}

async function acao(fazer, texto) {
  try {
    desenhar(await fazer());
    mensagem(texto);
  } catch (err) { mensagem(err.message, true); }
}

$("form").onsubmit = async (ev) => {
  ev.preventDefault();
  const corpo = {id: $("f-id").value || null, nome: $("f-nome").value, url: $("f-url").value,
                 email: $("f-email").value, token: $("f-token").value || null};
  $("f-salvar").disabled = true;
  try {
    const e = await api("POST", "sites", corpo);
    desenhar(e);
    preencher(null);
    mensagem("Salvo. Use Testar para conferir a conexao.");
  } catch (err) { mensagem(err.message, true); }
  finally { $("f-salvar").disabled = false; }
};
$("f-cancelar").onclick = () => preencher(null);
$("fechar").onclick = async () => {
  try { await api("POST", "fechar"); } catch (e) {}
  document.querySelector("main").replaceChildren(el("h1", null, "Tela fechada"),
    el("p", "sub", "Pode fechar esta aba. Para abrir de novo, use /atlassian-admin:sites."));
};

(async () => {
  if (!chave) {
    mensagem("Abra a tela pelo endereco completo que o comando mostrou (com #k=...).", true);
    return;
  }
  try {
    const e = await api("GET", "estado");
    $("link-token").href = e.pagina_token;
    desenhar(e);
  } catch (err) { mensagem(err.message, true); }
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main(sys.argv[1:])
