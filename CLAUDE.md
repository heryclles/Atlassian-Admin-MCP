# Atlassian MCP for Admins

Plugin do Claude Code (`atlassian-admin`) para as APIs Atlassian Cloud de qualquer
site, com duas partes que nao existem separadas:
- servidor MCP de ferramentas administrativas (Python 3.12, SDK mcp 2.x, stdio);
- skills que explicam os payloads complexos dessas ferramentas.
Cresce por API conforme a necessidade.

## Principio: ferramentas abstratas, regra de negocio no pedido

- Uma ferramenta = uma operacao da API (listar, obter, criar, salvar, excluir).
  Nada de ferramenta que resolve um caso de negocio ("status migrated por projeto",
  "tempo medio de resolucao"). Esses casos sao pedidos no chat que combinam
  ferramentas.
- Devolver o que a API entrega, so sem ruido (`limpar` tira self, avatarUrls,
  _links...). Sem renomear campos, sem calcular, sem filtrar por regra.
- Paginacao e mecanica, fica na ferramenta: devolver o token/inicio para a
  proxima pagina em vez de trazer tudo de uma vez.
- Nao ha arquivos de saida: tudo volta para o chat.
- Ferramenta cujo payload nao se explica em poucas linhas (JSON de design do Forms,
  AQL do Assets...) exige skill. Nao se entrega uma sem a outra.

Idioma: portugues (pt-BR), sem acento em codigo, nomes de arquivo e chaves de
retorno. Docstrings das ferramentas em portugues: elas viram a descricao que o
Claude le para decidir quando usar cada ferramenta.

## Estrutura

```
.claude-plugin/
  plugin.json         manifesto: userConfig (credenciais), servidor MCP "api", skills
  marketplace.json    marketplace "atlassian-admin" com o proprio repo como plugin
skills/<skill>/SKILL.md   uma skill por payload complexo, ex. forms-design
src/atlassian_mcp_for_admins/
  config.py           credenciais: env do plugin (userConfig) e, se vazio, .env; sem projeto fixo
  nucleo/http.py      ClienteHttp: auth, retry 429/5xx, erros legiveis, paginacoes,
                      trava de host (so o site e api.atlassian.com), troca de {cloudId}
  apis/               uma classe por produto, sem MCP: jira.py, jsm.py, forms.py
                      obter() devolve o singleton Atlassian (at.jira, at.jsm, at.forms)
  ferramentas/        camada MCP, um modulo por produto (+ geral.py); cada um tem
                      FERRAMENTAS = [funcoes]
  servidor.py         registra todas as ferramentas e roda em stdio
tests/                test_http.py e test_plugin.py (sem rede), ao_vivo.py (leituras no
                      site real), mcp_stdio.py (protocolo)
```

## Organizacao por produto

Cada produto (API) da Atlassian usa o mesmo nome em tres lugares:

- `apis/<produto>.py`: classe com os metodos HTTP, exposta em `obter()` como `at.<produto>`.
- `ferramentas/<produto>.py`: as ferramentas MCP daquele produto.
- Nome da ferramenta: `<produto>_<verbo>_<objeto>`, ex. `jsm_criar_request_type`.
  Verbos: listar, obter, buscar, contar, criar, salvar, excluir, usos.

Como decidir o produto: pela API que serve o endpoint (a URL base), nunca pelo
assunto. Exemplos: o formulario de um request type vem da Forms API, entao fica em
`forms`, mesmo sendo "coisa do portal"; os campos do request type vem da
servicedeskapi, entao ficam em `jsm`; status e workflows sao da plataforma, entao
ficam em `jira`. Endpoint de produto novo cria o trio acima; nao misturar em
modulo existente.

`geral` nao e produto: guarda a conexao e as chamadas genericas
(`atlassian_get`, `atlassian_requisicao`), com prefixo `atlassian_`.

| Produto | URL base | Situacao |
|---|---|---|
| `jira` | `/rest/api/3` | feito |
| `jsm` | `/rest/servicedeskapi` | feito |
| `forms` | `https://api.atlassian.com/jira/forms/cloud/{cloudId}` | feito |
| `assets` | `https://api.atlassian.com/jsm/assets/workspace/{workspaceId}/v1` | futuro |
| `agile` (Jira Software: boards, sprints) | `/rest/agile/1.0` | futuro |
| `automation` | `https://api.atlassian.com/automation/public/jira/{cloudId}/rest/v1` | futuro |
| `confluence` | `/wiki/api/v2` | futuro |

## Como adicionar uma ferramenta

1. Identificar o produto pela URL base (secao acima). Metodo na classe de
   `apis/<produto>.py`; produto novo ganha modulo ligado em `apis/__init__.py`.
   Nunca chamar requests fora do `ClienteHttp`.
2. Funcao em `ferramentas/<produto>.py` com type hints, docstring clara e o
   decorador `@leitura` ou `@escrita`; incluir na lista `FERRAMENTAS`. Modulo
   novo entra em `MODULOS` de `ferramentas/__init__.py`.
3. Payload complexo? Skill em `skills/<produto>-<assunto>/SKILL.md` (frontmatter
   `name` e `description` com os gatilhos de uso) e o decorador
   `@usa_skill("<skill>")` na ferramenta. `test_plugin.py` falha se a skill citada
   nao existir ou se o exemplo JSON da skill nao passar na conferencia.
4. Caso em `tests/ao_vivo.py` e, se houver paginacao nova, teste em `test_http.py`.
5. Rodar os testes. A sessao atual so enxerga ferramentas novas apos reiniciar o
   servidor (nova sessao ou /mcp).

## Instalacao e credenciais

- Plugin de marketplace, sempre instalado por git: o Claude Code clona e a copia
  instalada so tem arquivos do commit. Duas formas (README):
  - repositorio publicado (github.com/heryclles/Atlassian-Admin-MCP):
    `claude plugin marketplace add heryclles/Atlassian-Admin-MCP`, usando o
    `marketplace.json` da raiz (nome `atlassian-admin`, plugin com `source: "./"`);
  - clone local: catalogo externo em `~/.claude/marketplaces-locais/...` com fonte
    `{"source": "url", "url": "file://<repo>"}`. O `marketplace add` recusa `file://`
    direto, e caminhos da maquina nao entram no repositorio.
- Nunca adicionar a pasta do repositorio como marketplace: nesse modo o Claude Code
  copia a pasta inteira (inclusive `.env` e `.venv`, fora do git) e o `uninstall`
  nao apaga a copia. `test_segredos_e_ambiente_fora_do_git` garante que `.env` e
  `.venv` estao no `.gitignore`.
- A copia instalada fica em `~/.claude/plugins/cache/<marketplace>/atlassian-admin/<versao>`
  e nao tem `.venv`: o servidor sobe com `uv run --project ${CLAUDE_PLUGIN_ROOT}
  --frozen --quiet`, e o ambiente fica em `${CLAUDE_PLUGIN_DATA}/venv`, que
  sobrevive a atualizacoes. Por isso o `uv.lock` e versionado e o uv precisa estar
  no PATH. Primeira subida monta o ambiente (segundos); as seguintes reaproveitam.
- Atualizar: commit, aumentar a versao do `plugin.json` (e do `pyproject.toml`),
  `claude plugin marketplace update <marketplace>` e
  `claude plugin update atlassian-admin@<marketplace>`. Vale na proxima sessao.
- Nao ha `.mcp.json` na raiz: ele viraria servidor de projeto e duplicaria o do plugin.
- Credenciais: opcoes `jira_url`, `jira_email`, `jira_token` (sensitive, Keychain),
  preenchidas pelo usuario em `/plugin configure atlassian-admin@<marketplace>` e
  passadas ao servidor como JIRA_URL/JIRA_EMAIL/JIRA_TOKEN. Sao obrigatorias, mas a
  obrigatoriedade fica no servidor: `servidor.main` valida na subida e encerra com
  codigo 1, e o /mcp mostra o servidor como falho com o motivo e o comando exato no
  log (`config.comando_configurar` deriva plugin e marketplace do CLAUDE_PLUGIN_ROOT).
  No manifesto elas ficam `required: false`: com `required` e a opcao vazia, o
  Claude Code nem tenta subir o servidor e o conector "api" aparece vazio, sem erro. Uma
  configuracao por instalacao, ou seja, um site por usuario. Nunca passar o token
  por `--config` na linha de comando nem digita-lo pelo usuario.
- Desenvolvimento: `uv sync` cria a `.venv` do repositorio; testes usam o `.env`
  da raiz (fallback do `config.py`), que nunca vai para o plugin instalado.

## Regras do servidor

- Nunca escrever em stdout (`print`): e o canal do protocolo. Log via `logging`
  (vai para stderr).
- Falha prevista vira texto para o Claude: o servidor envolve cada ferramenta com
  `com_erro_legivel`, que converte `ERROS_PREVISTOS` em `ToolError`. No SDK 2.x
  qualquer outra excecao chega so como "Error executing tool". Erro novo de
  dominio: levantar um tipo que esteja em `ERROS_PREVISTOS`.
- Respostas grandes estouram o limite de saida do MCP no Claude Code (~25 mil
  tokens). Oferecer `limite`, paginacao ou `partes` (como em `forms_obter`) em vez
  de devolver tudo.
- Escrita: decorador `@escrita` (o cliente pede confirmacao). A decisao de
  executar e do pedido; nao ha modo simulacao dentro da ferramenta.
- Nunca montar URL com host vindo de parametro sem passar pelo `montar_url`.
- Nome da ferramenta com no maximo 31 caracteres: servidor de plugin vira
  `mcp__plugin_atlassian-admin_api__<ferramenta>` e o limite total e 64
  (`test_nome_completo_cabe_no_limite` garante). Por isso o id do plugin e
  `atlassian-admin`; "Atlassian MCP for Admins" e so o nome de exibicao.
- Ambiente: `uv sync` cria a `.venv` com Python 3.12 gerenciado pelo uv. Python
  abaixo de 3.10 nao roda o SDK mcp.
- SDK mcp 2.x: a classe e `MCPServer` (`mcp.server.mcpserver`); `FastMCP` era da
  1.x. Anotacoes em snake_case (`read_only_hint`). Dependencia travada em `<3`.
- Teste ao vivo so chama ferramentas de leitura e descobre sozinho o que ler no
  site configurado. Escrita so e testada no site com pedido explicito do usuario,
  no projeto que ele indicar.

## Independente de site

O plugin roda em varios sites, cada um com seus projetos e suas regras. Nada neste
repositorio (codigo, skills, testes, este arquivo) pode citar site, projeto, campo,
id ou regra de um site especifico. Regras de um site ou de uma sessao ("nao alterar
o projeto X") valem so na conversa em que o usuario as deu. Exemplos usam valores
ficticios (`SUP`, `customfield_10000`, `https://empresa.atlassian.net`).
`test_plugin.py` falha se o host do site configurado aparecer em arquivo versionado.

## Conhecimento das APIs (vale para qualquer site)

- Campos Assets na JQL: usar o ARI completo
  `"<campo>" = "ari:cloud:cmdb::object/<workspaceId>/<objectId>"`. A chave do objeto
  (ABC-123) e o objectId sozinho retornam zero.
- Busca de issues: POST /rest/api/3/search/jql (nextPageToken); o GET /search saiu.
- Status e workflows exigem admin do Jira. Usos paginam por nextPageToken
  aninhado. Workflow pode guardar o nome antigo de um status renomeado.
- Request types: API so cria (nome, descricao, ajuda, issue type) e exclui; nao
  edita. Grupo do portal, campos e icone sao manuais. Formulario liga ao portal
  pelo `publish.portal.portalRequestTypeIds` do template (Forms API).

## Roteiro

- v0.1: leitura basica de Jira e JSM.
- v0.2: ferramentas abstratas de Jira, JSM e Forms e chamadas genericas.
- v0.3: plugin do Claude Code (servidor + skills), credenciais pelo userConfig,
  skill forms-design.
- v0.4 (atual): plugin de marketplace instalado por git, ambiente criado pelo uv na
  pasta de dados do plugin, erros previstos repassados ao Claude com o motivo.
- Proximos candidatos: Assets (objetos, esquemas, AQL), criacao e edicao de
  issues, transicoes, filas e SLAs do JSM, Confluence. Cada um com a skill do seu
  payload quando precisar (ex. assets-aql).
