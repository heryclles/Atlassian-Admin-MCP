---
name: jira-notificacoes
description: Modelo dos esquemas de notificacao do Jira company-managed - projeto ligado a um esquema, evento de issue (sistema ou personalizado) e destinatarios de e-mail (responsavel, relator, observadores, usuario, grupo, papel de projeto, campo de usuario ou grupo) - com o parameter de cada tipo, onde achar os ids, os payloads de criar e adicionar e o fluxo seguro de alteracao. Use SEMPRE antes de criar, alterar, copiar ou associar esquemas de notificacao, antes de adicionar ou remover destinatarios, e quando o pedido for "quem recebe e-mail quando..." ou "parar de notificar X no projeto Y".
---

# Esquemas de notificacao do Jira

Vale so para projetos **company-managed**. Projeto team-managed tem configuracao de
notificacao propria e as notificacoes de cliente do JSM tambem sao outra coisa:
nenhum dos dois passa por estas ferramentas. Escritas exigem admin do Jira.

## O modelo

```
Projeto
 └─ 1 esquema de notificacao
     └─ evento (event.id)  ─>  notificacoes (quem recebe e-mail)
          ex. 1 Issue Created  ─> Reporter, CurrentAssignee, Group "suporte"
```

- Varios projetos dividem o mesmo esquema; o padrao do site
  (`jira_listar_esquemas_notif(somente_padrao=True)`) costuma ser o mais usado.
  Mudar um esquema muda o e-mail de todos os projetos dele.
- Eventos: `jira_listar_eventos` (id e nome). Os do sistema tem ids baixos (1 Issue
  Created, 2 Issue Updated, 3 Issue Assigned...); confira sempre pela lista, os
  personalizados variam por site. Evento personalizado nao se cria pela API.
- Cada notificacao tem `id` proprio (o da notificacao, nao o do evento): e ele que
  `jira_remover_notificacao` usa.

## Destinatarios

| notificationType | parameter | Onde achar |
|---|---|---|
| `CurrentAssignee` | - | responsavel pela issue |
| `Reporter` | - | relator |
| `CurrentUser` | - | quem fez a acao |
| `ProjectLead` | - | lider do projeto |
| `ComponentLead` | - | lider do componente da issue |
| `AllWatchers` | - | observadores |
| `User` | accountId | `atlassian_get("/rest/api/3/user/search", {"query": "<nome ou e-mail>"})` |
| `Group` | nome do grupo | `atlassian_get("/rest/api/3/groups/picker", {"query": "<trecho>"})` |
| `ProjectRole` | id do papel | `jira_listar_papeis` |
| `UserCustomField` | id do campo de usuario | `jira_listar_campos` (schema.type user) |
| `GroupCustomField` | id do campo de grupo | `jira_listar_campos` (schema.type group) |

`EmailAddress` nao funciona mais no Cloud: nao use. Nas respostas, grupo tambem vem
com o id em `recipient`; ao gravar, `parameter` do grupo e o nome.

## Leituras

| Pergunta | Caminho |
|---|---|
| Quem recebe e-mail no projeto X quando Y acontece | `jira_obter_notif_projeto("X")`, evento com `event.name` Y |
| Quais projetos usam o esquema | `jira_listar_notif_projetos(esquema_ids=[id])` (todas as paginas) |
| Esquema de varios projetos | `jira_listar_notif_projetos(projeto_ids=[...])` |
| Onde um grupo ou usuario recebe e-mail | `jira_listar_esquemas_notif(incluir_notificacoes=True, limite=5)` pagina a pagina, procurando `parameter` |

## Payloads

Criar (`jira_criar_esquema_notif`, parametro `eventos`) e adicionar
(`jira_adicionar_notificacoes`) usam a mesma lista. `event.id` e texto; ate 1000
notificacoes por chamada.

```json
[{"event": {"id": "1"},
  "notifications": [{"notificationType": "Reporter"},
                    {"notificationType": "CurrentAssignee"},
                    {"notificationType": "Group", "parameter": "suporte-n2"}]},
 {"event": {"id": "6"},
  "notifications": [{"notificationType": "ProjectRole", "parameter": "10002"},
                    {"notificationType": "UserCustomField", "parameter": "customfield_10000"}]}]
```

Nao ha edicao de notificacao: para trocar um destinatario, `jira_remover_notificacao`
com o id dele e `jira_adicionar_notificacoes` com o novo.

## Copiar um esquema

A API nao copia. Ler o original com `jira_obter_esquema_notif`, montar a lista acima
so com `event.id`, `notificationType` e `parameter` de cada notificacao (sem `id`,
`recipient` nem os objetos expandidos) e chamar `jira_criar_esquema_notif`.

## Fluxo seguro

1. Achar o esquema do projeto (`jira_obter_notif_projeto`) e quantos projetos o usam
   (`jira_listar_notif_projetos(esquema_ids=[id])`).
2. Mudanca so para um projeto num esquema compartilhado: copiar o esquema (secao
   acima), aplicar a mudanca na copia e `jira_associar_esquema_notif(projeto, copia)`.
3. Mostrar ao usuario, por evento, quem passa a receber e quem deixa de receber, e
   pedir confirmacao: a mudanca vale para e-mails reais a partir dali.
4. Aplicar e conferir com `jira_obter_esquema_notif`.

## Excluir

Exclua so esquema sem projetos (`jira_listar_notif_projetos(esquema_ids=[id])` vazio);
mova os projetos antes com `jira_associar_esquema_notif`.
