# Atlassian MCP for Admins

Plugin do Claude Code (`atlassian-admin`) para as APIs Atlassian Cloud de qualquer
site, com duas partes que nao existem separadas:
- servidor MCP (Python 3.12, SDK mcp 2.x, stdio) com quatro ferramentas genericas;
- skills, uma por area da API, com o conhecimento de cada endpoint.
Cresce por skill conforme a necessidade, nao por ferramenta.

## Principio: ferramentas genericas por risco, conhecimento nas skills

- Quatro ferramentas, e so: `atlassian_conexao` (site, usuario, cloudId),
  `atlassian_ler` (GET e POST de consulta), `atlassian_escrever` (POST, PUT, PATCH) e
  `atlassian_excluir` (DELETE). A divisao e por risco porque o Claude Code casa
  permissao de ferramenta MCP so pelo nome: o usuario libera a leitura e mantem a
  confirmacao nas outras duas.
- Nada de ferramenta por endpoint nem por caso de negocio. Endpoint novo e uma linha
  na tabela da skill da area; caso de negocio e pedido no chat que combina chamadas.
- `intencao` obrigatoria nas tres genericas: uma frase em portugues sobre o que a
  chamada faz. E o que o usuario le no transcript e no pedido de confirmacao (o
  Claude Code nao desenha card de resultado MCP); vai para o log, nunca para a API.
- Devolver o que a API entrega, so sem ruido (`limpar` tira self, avatarUrls,
  _links...). Sem renomear campos, sem calcular, sem filtrar por regra.
- So mecanica fica no codigo, como opcao generica de `atlassian_ler`: seguir
  paginacao (`limite`, `continuar`), fatiar lista inteira (`inicio`), filtrar por
  igualdade (`filtro`), recortar (`manter`), varios caminhos numa chamada e o teto de
  tamanho. Mecanismo novo entra assim, nunca como ferramenta especifica.
- Nao ha arquivos de saida: tudo volta para o chat.

Idioma: portugues (pt-BR), sem acento em codigo, nomes de arquivo, chaves de retorno
e skills. Docstrings das ferramentas em portugues: elas viram a descricao que o
Claude le.

## Estrutura

```
.claude-plugin/
  plugin.json         manifesto: userConfig (credenciais), servidor MCP "api", skills
  marketplace.json    marketplace "atlassian-admin" com o proprio repo como plugin
skills/<skill>/SKILL.md   uma skill por area da API (atlassian-chamadas, jira-telas, forms-design...)
src/atlassian_mcp_for_admins/
  config.py           credenciais: env do plugin (userConfig) e, se vazio, .env; sem projeto fixo
  nucleo/http.py      ClienteHttp: auth, retry 429/5xx, erros legiveis, ERROS_PREVISTOS,
                      paginar (detecta o estilo), trava de host, troca de {cloudId},
                      dicas de 404 sem corpo, cliente() (singleton do site)
  ferramentas/        camada MCP: geral.py com as quatro ferramentas e CONSULTAS_POST;
                      _comum.py com leitura/escrita, limpar, usa_skill
  servidor.py         INSTRUCOES (mapa prefixo de caminho -> skill), registra e roda em stdio
tests/                test_http.py, test_geral.py, test_plugin.py, test_servidor.py (sem rede),
                      ao_vivo.py (leituras no site real), mcp_stdio.py (protocolo)
```

## Skills por area

Cada skill cobre uma area da API e comeca pela secao `## Endpoints`, numa tabela
com este cabecalho exato (`test_plugin.py` confere):

```
| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
```

- Ferramenta bate com o metodo (GET e POST de `CONSULTAS_POST` -> atlassian_ler;
  POST, PUT, PATCH -> atlassian_escrever; DELETE -> atlassian_excluir).
- Metodo e caminho entre crases, sem query string; caminho comeca por `/rest/api/3/`,
  `/rest/servicedeskapi/`, `/_edge/` ou `https://api.atlassian.com/jira/forms/cloud/{cloudId}/`;
  parametros de caminho entre chaves em camelCase (`{telaId}`).
- Paginacao: `token`, `startAt`, `start/limit`, `token aninhado`, `inteira` ou `nao`.
- Depois da tabela: modelo dos objetos, receitas de leitura, payloads com exemplo,
  tipos dos ids no corpo (inteiro ou texto: quem monta o corpo e o Claude),
  armadilhas, fluxo seguro de alteracao e restricoes de exclusao.
- Skill cita so as quatro ferramentas (teste com regex). Exemplos ```json de
  algumas skills sao conferidos contra a especificacao da API; payload que nao e o
  conferido vai em bloco sem linguagem.
- Area nova: skill nova `skills/<produto>-<assunto>/` e o prefixo dela em
  `INSTRUCOES` (`test_plugin.py` exige toda skill nas instrucoes, que tem limite de
  4096 caracteres).
- `atlassian-chamadas` e a skill das proprias ferramentas; as tres genericas a citam
  por `@usa_skill`.

| Produto | URL base | Situacao |
|---|---|---|
| `jira` | `/rest/api/3` | feito |
| `jsm` | `/rest/servicedeskapi` | feito |
| `forms` | `https://api.atlassian.com/jira/forms/cloud/{cloudId}` | feito |
| `assets` | `https://api.atlassian.com/jsm/assets/workspace/{workspaceId}/v1` | futuro |
| `agile` (Jira Software: boards, sprints) | `/rest/agile/1.0` | futuro |
| `automation` | `https://api.atlassian.com/automation/public/jira/{cloudId}/rest/v1` | futuro |
| `confluence` | `/wiki/api/v2` | futuro |

Produto novo cuja URL base ainda nao esta em `BASES` de `test_plugin.py` entra la.
Host novo fora do site e de `api.atlassian.com` exige mudar `montar_url`.

## Como adicionar

1. Endpoint de area existente: linha na tabela e, se precisar, receita ou payload na
   skill. Conferir caminho e corpo na doc oficial (developer.atlassian.com).
2. POST que so le (busca, leitura em lote, calculo sem efeito): incluir o caminho
   exato em `CONSULTAS_POST` de `ferramentas/geral.py`, conferindo na especificacao
   que ele nao altera nada.
3. Mecanismo novo (outro estilo de paginacao, outra dica de erro): em
   `nucleo/http.py` (`paginar`, `DICAS_404_SEM_CORPO`) ou opcao de `atlassian_ler`,
   com teste em `test_http.py` ou `test_geral.py`.
4. Caso em `tests/ao_vivo.py` quando a leitura tem algo a conferir; o teste ao vivo
   ja faz GET em toda linha sem parametro de caminho das tabelas.
5. Rodar os testes. A sessao atual so enxerga mudancas no servidor apos reinicia-lo
   (nova sessao ou /mcp); skill nova vale na proxima sessao.

## Instalacao e credenciais

- Plugin de marketplace, sempre instalado pelo repositorio publicado
  (github.com/heryclles/Atlassian-Admin-MCP): `claude plugin marketplace add
  heryclles/Atlassian-Admin-MCP`, usando o `marketplace.json` da raiz (nome
  `atlassian-admin`, plugin com `source: "./"`). O Claude Code clona e a copia
  instalada so tem arquivos do commit, entao testar uma mudanca instalada exige
  commit e push. Nao documentar instalacao por clone local.
- Nunca adicionar a pasta do repositorio como marketplace: nesse modo o Claude Code
  copia a pasta inteira (inclusive `.env` e `.venv`, fora do git) e o `uninstall`
  nao apaga a copia. `test_segredos_e_ambiente_fora_do_git` garante que `.env` e
  `.venv` estao no `.gitignore`.
- A copia instalada fica em `~/.claude/plugins/cache/atlassian-admin/atlassian-admin/<versao>`
  e nao tem `.venv`: o servidor sobe com `uv run --project ${CLAUDE_PLUGIN_ROOT}
  --frozen --quiet`, e o ambiente fica em `${CLAUDE_PLUGIN_DATA}/venv`, que
  sobrevive a atualizacoes. Por isso o `uv.lock` e versionado e o uv precisa estar
  no PATH. Primeira subida monta o ambiente (segundos); as seguintes reaproveitam.
- Atualizar: commit e push, aumentar a versao do `plugin.json` (e do `pyproject.toml`),
  `claude plugin marketplace update atlassian-admin` e
  `claude plugin update atlassian-admin@atlassian-admin`. Vale na proxima sessao.
- Nao ha `.mcp.json` na raiz: ele viraria servidor de projeto e duplicaria o do plugin.
- Credenciais: `config.py` le JIRA_URL/JIRA_EMAIL/JIRA_TOKEN e vale o primeiro valor
  preenchido: (1) ambiente, que o Claude Code preenche com as opcoes `jira_url`,
  `jira_email`, `jira_token` (sensitive, Keychain) do userConfig via
  `/plugin configure atlassian-admin@atlassian-admin`, so no terminal; (2) `.env` da
  raiz do repositorio (desenvolvimento ou clone carregado direto); (3)
  `~/.config/atlassian-admin/.env` (`config.ARQUIVO_USUARIO`): o METODO PADRAO, o unico
  que o README ensina primeiro, porque funciona igual no CLI e na aba Code do
  Claude Desktop (que nao tem `/plugin configure`). Fica fora do repositorio e da
  copia instalada e sobrevive a atualizacoes. As outras fontes sao casos especificos. userConfig vazio
  chega como "" ou "${user_config.x}" e cai nos arquivos.
  Obrigatorias, mas a obrigatoriedade fica no servidor: `servidor.main` valida na
  subida e encerra com codigo 1, e o log mostra o caminho do arquivo padrao.
  No manifesto elas ficam `required: false` e `default: ""`: com `required` e a
  opcao vazia, o Claude Code nem tenta subir o servidor; sem `default`, o Cowork
  ignora o servidor (ele nao pergunta userConfig). Um site por usuario da maquina.
  Nunca passar o token por `--config` na linha de comando nem digita-lo pelo usuario.
- Aba Chat do Claude (web e Desktop) ignora servidor MCP local: la so a skill
  carrega. Tools no Chat exigiriam servidor remoto (http), fora do escopo atual.
- Desenvolvimento: `uv sync` cria a `.venv` do repositorio; testes usam o `.env`
  da raiz (fallback do `config.py`), que nunca vai para o plugin instalado.

## Regras do servidor

- Nunca escrever em stdout (`print`): e o canal do protocolo. Log via `logging`
  (vai para stderr).
- Falha prevista vira texto para o Claude: o servidor envolve cada ferramenta com
  `com_erro_legivel`, que converte `ERROS_PREVISTOS` (em `nucleo/http.py`) em
  `ToolError`. No SDK 2.x qualquer outra excecao chega so como "Error executing
  tool". Erro novo de dominio: levantar um tipo que esteja em `ERROS_PREVISTOS`.
- Teto de 50 mil caracteres na resposta de `atlassian_ler` (acima disso o Claude
  Code tira o resultado do chat): recusa com a orientacao de usar `limite`, `inicio`,
  `filtro`, `manter` ou os parametros do endpoint. Nunca truncar em silencio. Ha
  respostas reais muito acima disso (aba com milhares de campos, formulario grande).
- `limite` vai ate 500 itens por chamada; `filtro` percorre ate 50 requisicoes;
  caminho em lista aceita ate 20 caminhos.
- Escrita e exclusao devolvem `{"http": status, "resposta": corpo}` (201, 204, 207
  importam). A decisao de executar e do pedido; nao ha modo simulacao.
- Nunca montar URL com host vindo de parametro sem passar pelo `montar_url`.
- Nome da ferramenta com no maximo 31 caracteres: servidor de plugin vira
  `mcp__plugin_atlassian-admin_api__<ferramenta>` e o limite total e 64
  (`test_nome_completo_cabe_no_limite` garante). Por isso o id do plugin e
  `atlassian-admin`; "Atlassian MCP for Admins" e so o nome de exibicao.
- Ambiente: `uv sync` cria a `.venv` com Python 3.12 gerenciado pelo uv. Python
  abaixo de 3.10 nao roda o SDK mcp.
- SDK mcp 2.x: a classe e `MCPServer` (`mcp.server.mcpserver`); `FastMCP` era da
  1.x. Anotacoes em snake_case (`read_only_hint`). Dependencia travada em `<3`.
- Teste ao vivo so faz leitura e descobre sozinho o que ler no site configurado.
  Escrita so e testada no site com pedido explicito do usuario, no projeto que ele
  indicar.

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
- Telas, abas, esquemas de tela e esquemas de tela por tipo de issue: so projetos
  company-managed, exigem admin do Jira. Projeto -> esquema por tipo de issue ->
  esquema de tela -> tela; e o unico caminho de uma tela ate os projetos (skill
  jira-telas). Campos da aba e availableFields vem inteiros, sem paginacao, e a aba
  pode repetir o mesmo campo em sequencia: ler em fatias (inicio/proximo_inicio). /field/{id}/screens so aceita campo customizado.
- Prioridades sao globais, com uma ordem unica; o esquema de prioridade so escolhe
  quais entram e o padrao (defaultPriorityId). Ids vao como inteiro no corpo e os
  mapeamentos como {"in"|"out": {"<antiga>": <nova>}}. O esquema padrao do site se
  acha por onlyDefault=true (isDefault), nunca pelo nome. Alterar esquema e excluir
  prioridade sao assincronos: devolvem tarefa (/rest/api/3/task/{id});
  o DELETE de prioridade responde 303 e o requests segue ate a tarefa. POST
  /priorityscheme/mappings so calcula, mas conta como POST. iconUrl foi descontinuado:
  icone e avatarId (skill jira-prioridades).
- Comportamento dos campos tem duas APIs, ambas no plugin, e o pedido escolhe:
  a antiga, configuracao de campo e esquema de configuracao de campo
  (/fieldconfiguration..., obsoleta mas ativa; skill
  jira-config-campos), e a nova, esquemas de campos (/config/fieldschemes, beta por
  opt-in do site; skill jira-esquemas-campos). Com o
  beta desligado a nova responde 404 sem corpo, que vira LookupError explicando isso.
  Na antiga, ocultar um campo apaga obrigatorio, descricao e renderizador do item e
  cada configuracao traz todos os campos do site (mais de mil). Na nova nao ha
  "oculto" (o campo sai do esquema ou fica restrito a tipos de issue) e as escritas
  em lote respondem 207 com results por item quando parte falha. Contexto do campo
  customizado (opcoes, valor padrao) e outra API.
- Esquemas de notificacao: evento -> destinatarios (notificationType + parameter;
  grupo grava pelo nome, EmailAddress nao funciona mais). Nao ha edicao de
  notificacao (remover pelo id e adicionar) nem copia de esquema (ler e criar). O
  projeto troca de esquema pelo PUT /project/{chave} so com notificationScheme.
  Criar, renomear e excluir esquema e /events sao experimentais. Esquemas expandidos
  sao grandes: listar sem expand por padrao (skill jira-notificacoes).
- Status e workflows exigem admin do Jira. Usos paginam por nextPageToken
  aninhado. Workflow pode guardar o nome antigo de um status renomeado.
- Forms API: erros vem como lista `errors: [{title, detail}]` (o `ErroAtlassian`
  le os dois formatos). `serviceDeskId` aceita a chave do projeto. PDF, XLSX e a
  exportacao devolvem arquivo, entao ficam sem ferramenta (nao ha arquivo de
  saida); os endpoints /request/... repetem os de issue com a visao do cliente.
- Rotulos de opcao vindos de conexao de dados (`dcId`) sao texto externo sem
  limpeza: ferramenta que os devolve avisa na docstring para tratar como dado.
- Request types: API so cria (nome, descricao, ajuda, issue type) e exclui; nao
  edita. Grupo do portal, campos e icone sao manuais. Formulario liga ao portal
  pelo `publish.portal.portalRequestTypeIds` do template (Forms API).

## Roteiro

- v0.1: leitura basica de Jira e JSM.
- v0.2: ferramentas abstratas de Jira, JSM e Forms e chamadas genericas.
- v0.3: plugin do Claude Code (servidor + skills), credenciais pelo userConfig,
  skill forms-design.
- v0.4: plugin de marketplace instalado por git, ambiente criado pelo uv na
  pasta de dados do plugin, erros previstos repassados ao Claude com o motivo.
- v0.5: Forms API completa para JSON (formularios na issue: preencher,
  enviar, reabrir, visibilidade, copiar, dados externos, anexos), skill
  forms-respostas, erros da Forms API legiveis.
- v0.6: telas, abas, campos da aba, esquemas de tela e esquemas de tela
  por tipo de issue (ler, criar, editar, excluir, associar a projeto), tipos de
  issue, skill jira-telas, verbos adicionar/remover/mover/associar.
- v0.7: prioridades e esquemas de prioridade (ler, criar, editar,
  reordenar, excluir, mover projetos com mapeamento), tarefas assincronas,
  skill jira-prioridades.
- v0.8: comportamento dos campos nas duas APIs: configuracoes e
  esquemas de configuracao de campo (antiga, skill jira-config-campos) e esquemas
  de campos (nova em beta, skill jira-esquemas-campos): obrigatorio, oculto,
  descricao, renderizador, por tipo de issue, associar a projeto.
- v0.9: esquemas de notificacao (ler, criar, renomear, excluir,
  adicionar e remover destinatarios, associar a projeto), eventos, papeis de
  projeto, skill jira-notificacoes.
- v1.0 (atual): as 126 ferramentas especificas viram quatro (conexao e tres
  genericas por risco, com intencao obrigatoria, paginacao seguida pela ferramenta,
  filtro, manter, varios caminhos e teto de tamanho); o conhecimento de cada endpoint
  passa para as skills, uma por area, cada uma com a tabela de endpoints; skills
  novas atlassian-chamadas, jira-issues, jira-status-workflows e jsm-request-types.
- Proximos candidatos: contextos de campo customizado (opcoes, valor padrao),
  esquemas de tipo de issue, Assets (objetos, esquemas, AQL), criacao e edicao de
  issues, transicoes, Confluence. Cada um e uma skill nova (ex. assets-aql).
