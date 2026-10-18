---
name: jsm-request-types
description: Service desks e request types do Jira Service Management pela servicedeskapi (/rest/servicedeskapi) - achar o serviceDeskId de um projeto, listar, ler, criar e excluir request types, campos do Jira exibidos no request type, grupos do portal, e as leituras de filas, issues da fila, organizacoes, clientes e SLAs de um pedido - com o que a API nao faz (editar request type, grupo, campos e icone sao manuais) e o caminho ate o formulario do portal. Use SEMPRE antes de chamar /rest/servicedeskapi, antes de criar ou excluir request types, e quando o pedido for "quais request types o projeto SUP tem", "que campos aparecem no request type X", "criar um tipo de solicitacao no portal", "quais filas o service desk tem" ou "como esta o SLA do pedido SUP-1".
---

# Service desks e request types do JSM

A servicedeskapi trabalha com o `serviceDeskId`, que nao e o id do projeto. Toda
lista dela pagina por `start` / `limit` (`values`, `isLastPage`), e `limite` na
`atlassian_ler` segue as paginas sozinho. O cabecalho `X-ExperimentalApi: opt-in`,
exigido pelos metodos experimentais, ja vai em toda chamada.

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar service desks | atlassian_ler | `GET /rest/servicedeskapi/servicedesk` | start/limit | `{id, projectId, projectKey, projectName}`; o `id` e o serviceDeskId |
| Obter service desk | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}` | nao | |
| Listar request types | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype` | start/limit | `searchQuery` (nome), `groupId` (grupo do portal) |
| Request types de todos os service desks | atlassian_ler | `GET /rest/servicedeskapi/requesttype` | start/limit | experimental; `searchQuery`, `serviceDeskId` (lista) |
| Obter request type | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}` | nao | |
| Criar request type | atlassian_escrever | `POST /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype` | nao | experimental; so `name`, `issueTypeId`, `description`, `helpText` |
| Excluir request type | atlassian_excluir | `DELETE /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}` | nao | experimental; nao desfaz |
| Campos do request type | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/field` | nao | campos do Jira no portal (fora do Forms), obrigatoriedade e valores validos |
| Grupos do portal | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/requesttypegroup` | start/limit | `{id, name}`; as abas que organizam os request types |
| Filas | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue` | start/limit | `includeCount=true` traz `issueCount`; cada fila tem `jql` e `fields` |
| Issues de uma fila | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/queue/{filaId}/issue` | start/limit | issues com os campos da fila; use `limite` |
| Organizacoes do service desk | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/organization` | start/limit | `{id, name}` |
| Clientes do service desk | atlassian_ler | `GET /rest/servicedeskapi/servicedesk/{serviceDeskId}/customer` | start/limit | experimental; `query` busca por nome ou e-mail |
| SLAs de um pedido | atlassian_ler | `GET /rest/servicedeskapi/request/{issueChave}/sla` | start/limit | `{id, name, ongoingCycle, completedCycles}` por metrica |
| Workspace do Assets | atlassian_ler | `GET /rest/servicedeskapi/assets/workspace` | start/limit | `values[].workspaceId`, usado no Forms e na API do Assets |

O formulario do Forms ligado a um request type nao vem desta API: e a Forms API
(skill `forms-design`), que aceita a chave do projeto no lugar do serviceDeskId.

## O modelo

```
Projeto de service desk (projectKey SUP, projectId 10000)
 └─ Service desk (id proprio, o serviceDeskId)
     ├─ Grupos do portal (requesttypegroup): abas onde os request types aparecem
     ├─ Request types: nome, descricao, ajuda, icone, issue type, grupos (groupIds)
     │   ├─ Campos do Jira exibidos no portal (/field)
     │   └─ Formulario do Forms (Forms API, publish.portal.portalRequestTypeIds)
     ├─ Filas (queue): JQL + colunas
     ├─ Organizacoes e clientes
     └─ Pedidos (issues) com SLAs
```

- Request type: `{id, name, description, helpText, issueTypeId, serviceDeskId,
  portalId, groupIds, icon}`. `issueTypeId` e o tipo de issue que nasce no Jira.
- Um request type sem grupo (`groupIds` vazio) existe, mas nao aparece no portal.

## Achar o serviceDeskId

`filtro` compara por igualdade exata, como texto. Use a chave do projeto em
maiusculas, como o Jira guarda (`SUP`, nao `sup`), ou filtre pelo `projectId`:

```
atlassian_ler(intencao="Achar o service desk do projeto SUP",
              caminho="/rest/servicedeskapi/servicedesk",
              filtro={"projectKey": ["SUP"]})

atlassian_ler(intencao="Achar o service desk do projeto de id 10000",
              caminho="/rest/servicedeskapi/servicedesk",
              filtro={"projectId": ["10000"]})
```

`sem_correspondencia` com o valor pedido: o projeto nao e de service desk, a chave
foi digitada diferente ou o usuario da conexao nao ve o service desk. Se o usuario
deu um numero sem dizer o que e, pode ser o id do service desk: teste tambem
`filtro={"id": [...]}`.

## Leituras

Request types de um service desk, so id e nome:

```
atlassian_ler(intencao="Listar os request types do service desk 1 (projeto SUP)",
              caminho="/rest/servicedeskapi/servicedesk/1/requesttype",
              limite=200, manter=["values.id", "values.name", "values.issueTypeId", "values.groupIds"])
```

Request types de um grupo do portal: `params={"groupId": "<grupoId>"}`. Por nome:
`params={"searchQuery": "acesso"}` (busca parcial) ou `filtro={"name": [...]}`
(igualdade exata).

Campos de um request type (os que o cliente preenche no portal, fora do Forms):

```
atlassian_ler(intencao="Listar os campos do request type 10 do service desk 1",
              caminho="/rest/servicedeskapi/servicedesk/1/requesttype/10/field")
```

A resposta traz `requestTypeFields` (cada um com `fieldId`, `name`, `description`,
`required`, `validValues`, `defaultValues`, `jiraSchema`, `visible`),
`canRaiseOnBehalfOf` e `canAddRequestParticipants`. `fieldId` e o id do campo no
Jira (`summary`, `customfield_10000`). A lista vem inteira; para recortar use
`manter=["requestTypeFields.fieldId", "requestTypeFields.name", "requestTypeFields.required"]`.

Filas com a contagem de issues:

```
atlassian_ler(intencao="Listar as filas do service desk 1 com a quantidade de issues",
              caminho="/rest/servicedeskapi/servicedesk/1/queue",
              params={"includeCount": "true"}, limite=100)
```

SLA de um pedido: `ongoingCycle` traz `breached`, `paused`, `breachTime`,
`goalDuration`, `elapsedTime` e `remainingTime` do ciclo em andamento;
`completedCycles`, os ciclos ja fechados. Metrica sem ciclo em andamento nao tem
`ongoingCycle`.

## Criar request type

A API (experimental) so recebe nome, descricao, texto de ajuda e issue type. Envie
sempre `description` e `helpText`, mesmo vazios (`""`). `issueTypeId` vai como
texto e precisa estar no esquema de tipos de issue do projeto (os tipos do
projeto vem em `issueTypes` de `GET /rest/api/3/project/{projetoChave}`):

```
{"name": "Pedir acesso", "issueTypeId": "10001",
 "description": "Acesso a sistemas internos", "helpText": "Informe o sistema e o motivo."}
```

```
atlassian_escrever(intencao="Criar o request type Pedir acesso no service desk 1 (projeto SUP), issue type 10001",
                   metodo="POST", caminho="/rest/servicedeskapi/servicedesk/1/requesttype",
                   corpo=<acima>)
```

A resposta traz o `id` do request type novo. O resto e manual, na tela de
configuracao do projeto:

- **Grupo do portal**: a API nao define. Sem grupo, o request type nao aparece no
  portal; avise o usuario.
- **Campos** e **icone**: manuais.
- **Formulario**: pela Forms API, incluindo o id novo em
  `publish.portal.portalRequestTypeIds` de um template (skill `forms-design`).

## O que a API nao faz

- Nao edita request type: nome, descricao, ajuda, issue type, grupo, campos e icone
  so mudam na tela. Para "renomear", oriente o usuario a fazer na tela; recriar
  (criar outro e excluir o antigo) troca o id e perde grupo, campos, icone e a
  ligacao com o formulario.
- Nao cria nem edita grupos do portal, filas ou SLAs (aqui so leitura).

## Excluir request type

`DELETE .../requesttype/{requestTypeId}` (experimental) nao tem volta. Antes:

1. Ler o request type e mostrar ao usuario nome, issue type e grupos.
2. Contar os pedidos abertos por ele: o campo Request Type na JQL
   (`project = SUP AND "Request Type" = "<nome>"`, `POST /rest/api/3/search/approximate-count`).
3. Ver se ha formulario ligado (`GET .../servicedesk/{serviceDeskId}/requesttype/{requestTypeId}/form`
   na Forms API; 404 = nenhum). O template continua existindo, so perde a ligacao.
4. Confirmar com o usuario e excluir.
