---
name: jira-notificacoes
description: Modelo dos esquemas de notificacao do Jira company-managed (/rest/api/3/notificationscheme, /events, /role) - projeto ligado a um esquema, evento de issue (sistema ou personalizado) e destinatarios de e-mail (responsavel, relator, observadores, usuario, grupo, papel de projeto, campo de usuario ou grupo) - com o parameter de cada tipo, onde achar os ids, quando usar expand, os corpos de criar, adicionar e associar ao projeto e o fluxo seguro de alteracao. Use SEMPRE antes de criar, alterar, copiar ou associar esquemas de notificacao, antes de adicionar ou remover destinatarios, e quando o pedido for "quem recebe e-mail quando..." ou "parar de notificar X no projeto Y".
---

# Esquemas de notificacao do Jira

Vale so para projetos **company-managed**. Projeto team-managed tem configuracao de
notificacao propria e as notificacoes de cliente do JSM tambem sao outra coisa:
nenhum dos dois passa por estes endpoints. Escritas exigem admin do Jira. Criar,
renomear e excluir esquema e `GET /rest/api/3/events` estao marcados como
experimentais na doc da Atlassian.

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar esquemas | atlassian_ler | `GET /rest/api/3/notificationscheme` | startAt | params id, projectId, onlyDefault=true; expand=all traz eventos e destinatarios (pesado) |
| Obter esquema | atlassian_ler | `GET /rest/api/3/notificationscheme/{esquemaId}` | nao | expand=all para ver eventos e destinatarios |
| Esquema de um projeto | atlassian_ler | `GET /rest/api/3/project/{projetoChave}/notificationscheme` | nao | chave ou id; expand=all; aceita admin do projeto |
| Projetos e seus esquemas | atlassian_ler | `GET /rest/api/3/notificationscheme/project` | startAt | params notificationSchemeId, projectId; pares projectId e notificationSchemeId |
| Criar esquema | atlassian_escrever | `POST /rest/api/3/notificationscheme` | nao | experimental; 201 com id; nasce sem projetos |
| Renomear ou trocar descricao | atlassian_escrever | `PUT /rest/api/3/notificationscheme/{esquemaId}` | nao | experimental; 204; so name e description |
| Excluir esquema | atlassian_excluir | `DELETE /rest/api/3/notificationscheme/{esquemaId}` | nao | experimental; 204; so esquema sem projetos |
| Adicionar destinatarios | atlassian_escrever | `PUT /rest/api/3/notificationscheme/{esquemaId}/notification` | nao | 204; acrescenta, nao substitui; ate 1000 por chamada |
| Remover um destinatario | atlassian_excluir | `DELETE /rest/api/3/notificationscheme/{esquemaId}/notification/{notificacaoId}` | nao | 204; id da notificacao, nao do evento |
| Trocar o esquema do projeto | atlassian_escrever | `PUT /rest/api/3/project/{projetoChave}` | nao | corpo so com notificationScheme (inteiro) |
| Listar eventos | atlassian_ler | `GET /rest/api/3/events` | inteira | experimental; id e nome, sistema e personalizados |
| Listar papeis de projeto | atlassian_ler | `GET /rest/api/3/role` | inteira | id e o parameter de ProjectRole |
| Achar usuario | atlassian_ler | `GET /rest/api/3/user/search` | nao | param query (nome ou e-mail); accountId e o parameter de User |
| Achar grupo | atlassian_ler | `GET /rest/api/3/groups/picker` | nao | param query (trecho do nome) |
| Listar campos | atlassian_ler | `GET /rest/api/3/field` | inteira | campos de usuario e de grupo para UserCustomField e GroupCustomField |

## O modelo

```
Projeto
 └─ 1 esquema de notificacao
     └─ evento (event.id)  ─>  notificacoes (quem recebe e-mail)
          ex. 1 Issue Created  ─> Reporter, CurrentAssignee, Group "suporte"
```

- Varios projetos dividem o mesmo esquema; o padrao do site (`onlyDefault=true` em
  `GET /rest/api/3/notificationscheme`) costuma ser o mais usado. Mudar um esquema
  muda o e-mail de todos os projetos dele.
- Eventos: `GET /rest/api/3/events` (id e nome). Os do sistema tem ids baixos
  (1 Issue Created, 2 Issue Updated, 3 Issue Assigned...); confira sempre pela lista,
  os personalizados variam por site. Evento personalizado nao se cria pela API.
- Cada notificacao tem `id` proprio (o da notificacao, nao o do evento): e ele que
  vai no caminho do DELETE `/notification/{notificacaoId}`.

## Destinatarios

| notificationType | parameter | Onde achar |
|---|---|---|
| `CurrentAssignee` | - | responsavel pela issue |
| `Reporter` | - | relator |
| `CurrentUser` | - | quem fez a acao |
| `ProjectLead` | - | lider do projeto |
| `ComponentLead` | - | lider do componente da issue |
| `AllWatchers` | - | observadores |
| `User` | accountId | `GET /rest/api/3/user/search` com `params={"query": "<nome ou e-mail>"}` |
| `Group` | nome do grupo | `GET /rest/api/3/groups/picker` com `params={"query": "<trecho>"}` |
| `ProjectRole` | id do papel | `GET /rest/api/3/role` |
| `UserCustomField` | id do campo de usuario | `GET /rest/api/3/field` (`schema.type` user, ou `schema.items` user nos de varios usuarios) |
| `GroupCustomField` | id do campo de grupo | `GET /rest/api/3/field` (`schema.type` group, ou `schema.items` group) |

`EmailAddress` nao funciona mais no Cloud: nao use. Nas respostas, grupo tambem vem
com o id em `recipient`; ao gravar, `parameter` do grupo e o nome.

```
atlassian_ler(intencao="Achar o id do papel de projeto Administrators",
              caminho="/rest/api/3/role", filtro={"name": ["Administrators"]},
              manter=["id", "name"])

atlassian_ler(intencao="Listar os campos customizados de usuario do site",
              caminho="/rest/api/3/field", filtro={"schema.type": ["user"]},
              manter=["id", "name"])
```

O `filtro` compara o nome inteiro (igualdade); para um trecho do nome, leia a lista
com `manter=["id", "name"]` e procure nela.

## Leituras

Listas de esquemas vao **sem expand** por padrao: so id, nome e descricao. Com
`expand=all`, cada esquema traz todos os eventos e destinatarios e a pagina fica
grande; use `limite` pequeno (ex. 5) e `manter`. Para um esquema so, `expand=all`
e o normal: sem ele nao vem nenhum evento.

| Pergunta | Como |
|---|---|
| Quem recebe e-mail no projeto X quando Y acontece | `GET /rest/api/3/project/{projetoChave}/notificationscheme` com `expand=all`; evento com `event.name` Y |
| Quais projetos usam o esquema | `GET /rest/api/3/notificationscheme/project` com `params={"notificationSchemeId": ["<id>"]}` e `limite` (todas as paginas) |
| Esquema de varios projetos | o mesmo endpoint com `params={"projectId": [...]}` |
| Esquema padrao do site | `GET /rest/api/3/notificationscheme` com `params={"onlyDefault": "true"}` |
| Onde um grupo ou usuario recebe e-mail | `GET /rest/api/3/notificationscheme` com `expand=all` e `limite=5`, seguindo `continuar`, procurando `parameter` |

```
atlassian_ler(intencao="Ver quem recebe e-mail em cada evento no projeto SUP",
              caminho="/rest/api/3/project/SUP/notificationscheme",
              params={"expand": "all"},
              manter=["id", "name", "notificationSchemeEvents.event",
                      "notificationSchemeEvents.notifications.id",
                      "notificationSchemeEvents.notifications.notificationType",
                      "notificationSchemeEvents.notifications.parameter"])

atlassian_ler(intencao="Listar os projetos que usam o esquema de notificacao 10100",
              caminho="/rest/api/3/notificationscheme/project",
              params={"notificationSchemeId": ["10100"]}, limite=200)
```

Outras opcoes de expand, separadas por virgula: `notificationSchemeEvents`, `user`,
`group`, `projectRole`, `field` (cada uma expande so aquele tipo de destinatario).

## Payloads

Criar (`POST /rest/api/3/notificationscheme`, chave `notificationSchemeEvents`) e
adicionar (`PUT /rest/api/3/notificationscheme/{esquemaId}/notification`, mesma
chave) usam a mesma lista. `event.id` e `parameter` sao texto; ate 1000
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

Corpos completos:

```
POST /rest/api/3/notificationscheme
{"name": "Suporte", "description": "E-mails do suporte",
 "notificationSchemeEvents": <lista acima>}

PUT /rest/api/3/notificationscheme/{esquemaId}/notification
{"notificationSchemeEvents": <lista acima>}

PUT /rest/api/3/notificationscheme/{esquemaId}
{"name": "Suporte N2", "description": "..."}

PUT /rest/api/3/project/{projetoChave}
{"notificationScheme": 10100}
```

- Criar: so `name` e obrigatorio (unico, sem diferenciar maiusculas, ate 255
  caracteres); o esquema nasce sem projetos.
- Adicionar: os destinatarios que ja existem continuam; muda o e-mail de todos os
  projetos do esquema.
- Renomear: so `name` e `description`. Destinatarios mudam pelos endpoints de
  notificacao.
- Trocar o esquema do projeto: nao ha endpoint proprio; vai pelo cadastro do
  projeto, com o corpo so com `notificationScheme` (inteiro). Mandar outras chaves
  alteraria o projeto.

Nao ha edicao de notificacao: para trocar um destinatario, remova pelo id dele e
adicione o novo.

```
atlassian_excluir(intencao="Tirar o grupo suporte-n1 (notificacao 10350) do evento Issue Created do esquema 10100",
                  caminho="/rest/api/3/notificationscheme/10100/notification/10350")

atlassian_escrever(intencao="Fazer o grupo suporte-n2 receber e-mail de Issue Created no esquema 10100",
                   metodo="PUT", caminho="/rest/api/3/notificationscheme/10100/notification",
                   corpo={"notificationSchemeEvents": [{"event": {"id": "1"},
                          "notifications": [{"notificationType": "Group", "parameter": "suporte-n2"}]}]})
```

## Copiar um esquema

A API nao copia. Ler o original (`GET /rest/api/3/notificationscheme/{esquemaId}`
com `expand=all`), montar a lista acima so com `event.id`, `notificationType` e
`parameter` de cada notificacao (sem `id`, `recipient` nem os objetos expandidos;
grupo pelo nome) e criar com `POST /rest/api/3/notificationscheme`.

## Fluxo seguro

1. Achar o esquema do projeto (`GET /rest/api/3/project/{projetoChave}/notificationscheme`)
   e quantos projetos o usam (`GET /rest/api/3/notificationscheme/project` com
   `notificationSchemeId`).
2. Mudanca so para um projeto num esquema compartilhado: copiar o esquema (secao
   acima), aplicar a mudanca na copia e trocar o esquema do projeto
   (`PUT /rest/api/3/project/{projetoChave}` com `notificationScheme`).
3. Mostrar ao usuario, por evento, quem passa a receber e quem deixa de receber, e
   pedir confirmacao: a mudanca vale para e-mails reais a partir dali.
4. Aplicar e conferir relendo o esquema com `expand=all`.

## Excluir

Exclua so esquema sem projetos (`GET /rest/api/3/notificationscheme/project` com
`notificationSchemeId` vazio); mova os projetos antes pelo
`PUT /rest/api/3/project/{projetoChave}`. Nao ha como desfazer.
