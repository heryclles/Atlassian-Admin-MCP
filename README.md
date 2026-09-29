# Atlassian MCP for Admins

Plugin do Claude Code com ferramentas administrativas para Jira Cloud, Jira
Service Management e Jira Forms. O plugin junta duas coisas que nao existem
separadas:

- **Servidor MCP** (`src/`): cada operacao da API vira uma ferramenta.
- **Skills** (`skills/`): explicam os payloads complexos que as ferramentas
  recebem, como o JSON de design do Forms. Ferramenta que depende de skill avisa
  na propria descricao, e um teste garante que a skill existe.

## Instalar

Requer o [uv](https://docs.astral.sh/uv/) no PATH (`uv --version`). A instalacao
clona o repositorio por git: a copia instalada so tem arquivos do commit, nunca o
`.env` nem a `.venv`. Instale sempre pelo repositorio publicado no GitHub, cujo
`.claude-plugin/marketplace.json` serve de catalogo. Nunca adicione um clone local
como marketplace: nesse modo o Claude Code copia a pasta inteira, com os arquivos
fora do git.

```bash
claude plugin marketplace add heryclles/Atlassian-Admin-MCP
claude plugin install atlassian-admin@atlassian-admin
```

Na primeira sessao, o `uv` cria o ambiente Python do plugin na pasta de dados dele
(`~/.claude/plugins/data/atlassian-admin-atlassian-admin/venv`), a partir do `uv.lock`. Esse
ambiente sobrevive as atualizacoes.

## Credenciais

O servidor precisa da URL do site, do e-mail da conta administradora e de um
[API token](https://id.atlassian.com/manage-profile/security/api-tokens). O metodo
padrao, que funciona igual no Claude Code CLI e na aba Code do Claude Desktop, e um
arquivo no seu usuario:

```bash
mkdir -p ~/.config/atlassian-admin
cat > ~/.config/atlassian-admin/.env <<'ENV'
JIRA_URL=https://empresa.atlassian.net
JIRA_EMAIL=admin@empresa.com
JIRA_TOKEN=cole-o-token-aqui
ENV
chmod 600 ~/.config/atlassian-admin/.env
```

Troque os tres valores (URL sem barra no final) e abra uma sessao nova. O arquivo
fica fora do repositorio e da copia instalada: nao vai para o git, vale para
qualquer forma de instalacao e sobrevive as atualizacoes do plugin.

Conferir: `claude mcp list` deve mostrar `plugin:atlassian-admin:api ... Connected`.
Sem credencial o servidor nao sobe: o conector `api` aparece como falho, e o log
dele diz o que falta e o caminho do arquivo. Credencial errada (token vencido) so
aparece ao usar uma ferramenta; `atlassian_conexao` confere a conexao.

A aba Chat do Claude (web e Desktop) nao roda servidor MCP local: la o plugin so
carrega a skill. Veja a [tabela de componentes por app](https://claude.com/docs/plugins/platform-support).

### Outras fontes

O servidor usa o primeiro valor preenchido, nesta ordem. Na pratica, use so o
arquivo acima; as outras existem para casos especificos:

| Ordem | Fonte | Quando usar |
|---|---|---|
| 1 | Opcoes do plugin, via `/plugin configure atlassian-admin@atlassian-admin` (token no Keychain) | So no terminal do Claude Code; util para apontar uma instalacao para outro site, porque vence o arquivo |
| 2 | `.env` na raiz do repositorio | Desenvolvimento e testes (secao [Desenvolver](#desenvolver)) |
| 3 | `~/.config/atlassian-admin/.env` | **Padrao** |

## Atualizar

Depois de um commit publicado no GitHub, com a versao de `.claude-plugin/plugin.json`
aumentada:

```bash
claude plugin marketplace update atlassian-admin
claude plugin update atlassian-admin@atlassian-admin
```

A mudanca vale na proxima sessao.

## Desenvolver

Os testes rodam no repositorio, com a `.venv` local e as credenciais do `.env`
(`cp .env.example .env`), que nunca vai para o plugin instalado:

```bash
uv sync
```

## Testar

```bash
.venv/bin/python -m unittest discover -s tests   # sem rede: paginacao, plugin, skills
.venv/bin/python -m tests.ao_vivo                # leituras contra o site
.venv/bin/python -m tests.mcp_stdio              # o servidor pelo protocolo MCP
```

## Ferramentas

No Claude Code aparecem como `mcp__plugin_atlassian-admin_api__<nome>`.

| Grupo | Leitura | Escrita |
|---|---|---|
| Geral | `atlassian_conexao`, `atlassian_get` | `atlassian_requisicao` |
| Jira | `jira_buscar_issues`, `jira_contar_issues`, `jira_obter_issue`, `jira_listar_comentarios`, `jira_listar_projetos`, `jira_obter_projeto`, `jira_listar_campos`, `jira_listar_tipos_issue`, `jira_listar_status`, `jira_usos_status`, `jira_listar_workflows`, `jira_usos_workflow` | |
| Jira (telas) | `jira_listar_telas`, `jira_obter_tela`, `jira_listar_campos_disponiveis`, `jira_usos_campo`, `jira_listar_abas`, `jira_listar_campos_aba` | `jira_criar_tela`, `jira_salvar_tela`, `jira_excluir_tela`, `jira_criar_aba`, `jira_salvar_aba`, `jira_excluir_aba`, `jira_mover_aba`, `jira_adicionar_campo_aba`, `jira_remover_campo_aba`, `jira_mover_campo_aba` |
| Jira (esquemas de tela) | `jira_listar_esquemas_tela`, `jira_listar_esquemas_tipo_tela`, `jira_listar_itens_tipo_tela`, `jira_listar_tipo_tela_projetos`, `jira_usos_esquema_tipo_tela` | `jira_criar_esquema_tela`, `jira_salvar_esquema_tela`, `jira_excluir_esquema_tela`, `jira_criar_esquema_tipo_tela`, `jira_salvar_esquema_tipo_tela`, `jira_excluir_esquema_tipo_tela`, `jira_adicionar_itens_tipo_tela`, `jira_salvar_padrao_tipo_tela`, `jira_remover_itens_tipo_tela`, `jira_associar_esquema_tipo_tela` |
| Jira (prioridades) | `jira_listar_prioridades`, `jira_listar_esquemas_prioridade`, `jira_listar_prioridades_esquema`, `jira_usos_esquema_prioridade`, `jira_listar_prioridades_mapear`, `jira_obter_tarefa` | `jira_criar_prioridade`, `jira_salvar_prioridade`, `jira_excluir_prioridade`, `jira_mover_prioridades`, `jira_salvar_padrao_prioridade`, `jira_criar_esquema_prioridade`, `jira_salvar_esquema_prioridade`, `jira_excluir_esquema_prioridade` |
| JSM | `jsm_listar_service_desks`, `jsm_listar_request_types`, `jsm_obter_request_type`, `jsm_listar_campos_request_type`, `jsm_listar_grupos_request_type` | `jsm_criar_request_type`, `jsm_excluir_request_type` |
| Forms (templates) | `forms_listar`, `forms_obter`, `forms_obter_do_request_type`, `forms_obter_dados_externos_rt` | `forms_criar`, `forms_salvar`, `forms_excluir` |
| Forms (na issue) | `forms_listar_da_issue`, `forms_obter_da_issue`, `forms_obter_respostas`, `forms_obter_dados_externos`, `forms_listar_anexos` | `forms_criar_na_issue`, `forms_salvar_respostas`, `forms_enviar`, `forms_reabrir`, `forms_salvar_visibilidade`, `forms_copiar_entre_issues`, `forms_excluir_da_issue` |

`atlassian_get` e `atlassian_requisicao` cobrem qualquer endpoint sem ferramenta
propria. So aceitam o site configurado e `api.atlassian.com`: o token nunca vai
para outro host.

## Skills

| Skill | Ferramentas | Conteudo |
|---|---|---|
| `atlassian-admin:forms-design` | `forms_obter`, `forms_obter_do_request_type`, `forms_obter_da_issue`, `forms_criar`, `forms_salvar` | tipos de pergunta, validacao, opcoes, campos do Jira, Assets e conexoes de dados, secoes, condicoes, layout (avisos, titulos, colunas, aviso condicional), publicacao, traducao, fluxo seguro de edicao |
| `atlassian-admin:jira-telas` | `jira_listar_esquemas_tela`, `jira_criar_esquema_tela`, `jira_salvar_esquema_tela`, `jira_listar_esquemas_tipo_tela`, `jira_listar_itens_tipo_tela`, `jira_listar_tipo_tela_projetos`, `jira_criar_esquema_tipo_tela`, `jira_adicionar_itens_tipo_tela`, `jira_salvar_padrao_tipo_tela`, `jira_remover_itens_tipo_tela`, `jira_associar_esquema_tipo_tela`, `jira_mover_campo_aba` | cadeia projeto, esquema por tipo de issue, esquema de tela, tela, abas e campos; qual tela o projeto mostra; quem usa cada tela e esquema; payloads de telas e itens (default, null); ordem de abas e campos; restricoes de exclusao; fluxo seguro de edicao |
| `atlassian-admin:jira-prioridades` | `jira_criar_prioridade`, `jira_excluir_prioridade`, `jira_listar_esquemas_prioridade`, `jira_listar_prioridades_mapear`, `jira_criar_esquema_prioridade`, `jira_salvar_esquema_prioridade` | prioridade global e ordem, esquema com subconjunto e padrao, esquema padrao do site; quem usa cada esquema e o esquema de um projeto; icone por avatarId; mapeamentos in/out para migrar issues; fluxo seguro de alteracao, mover projeto de esquema, exclusao |
| `atlassian-admin:forms-respostas` | `forms_obter_da_issue`, `forms_salvar_respostas`, `forms_obter_dados_externos`, `forms_obter_dados_externos_rt` | resposta por tipo de pergunta, status e visibilidade, preencher e enviar, dados externos, rotulos de conexao de dados |
