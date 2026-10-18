---
name: jira-esquemas-campos
description: Modelo dos esquemas de campos do Jira (API nova /rest/api/3/config/fieldschemes, em beta, que substitui configuracao de campo e esquema de configuracao de campo) - quais campos existem em cada projeto, obrigatorio, descricao (texto de ajuda) e renderizador, excecoes por tipo de issue, restricao a tipos de issue, associacao a projetos - com os endpoints, os payloads em lote, quais ids vao como inteiro, os resultados parciais (207) e o fluxo seguro de alteracao. Use SEMPRE antes de adicionar ou remover campos de esquemas, mudar obrigatoriedade, descricao ou renderizador de campos, criar, copiar, excluir ou associar esquemas de campos, e quando o pedido for "o campo X e obrigatorio no projeto Y", "deixar campo obrigatorio so para Bug" ou "por que o campo nao aparece".
---

# Esquemas de campos do Jira (API nova)

`/rest/api/3/config/fieldschemes`, em beta (endpoints experimentais): so responde em
sites que entraram no programa beta. Com a funcionalidade desligada, qualquer
chamada da 404 sem corpo, e o cliente HTTP do plugin ja converte isso num erro
explicando que a API esta desligada no site ou que o id nao existe. Ela substitui a
API antiga de configuracao de campo e esquema de configuracao de campo. Todos os
endpoints exigem admin do Jira. Chamadas: skill `atlassian-chamadas`.

As duas APIs ficam no plugin. Use esta quando o pedido falar em "API nova", "beta"
ou "esquema de campos"; a antiga (`/rest/api/3/fieldconfiguration...`, skill
`jira-config-campos`) quando falar em "API antiga", "legado" ou "configuracao de
campo". Sem indicacao, e se esta responder "desligada", use a antiga.

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar esquemas de campos | atlassian_ler | `GET /rest/api/3/config/fieldschemes` | startAt | `query` (nome ou descricao), `projectId` (lista): o esquema de um projeto |
| Obter esquema | atlassian_ler | `GET /rest/api/3/config/fieldschemes/{esquemaId}` | nao | nome, descricao, `fieldsCount`, `isDefault` |
| Criar esquema | atlassian_escrever | `POST /rest/api/3/config/fieldschemes` | nao | `{"name", "description"}`; nasce so com os campos essenciais |
| Copiar esquema | atlassian_escrever | `POST /rest/api/3/config/fieldschemes/{esquemaId}/clone` | nao | `{"name", "description"}`; copia campos e parametros, sem projetos |
| Renomear esquema | atlassian_escrever | `PUT /rest/api/3/config/fieldschemes/{esquemaId}` | nao | `{"name"}` e/ou `{"description"}` |
| Excluir esquema | atlassian_excluir | `DELETE /rest/api/3/config/fieldschemes/{esquemaId}` | nao | 400 no esquema do sistema, 409 se tiver projetos |
| Campos de um esquema | atlassian_ler | `GET /rest/api/3/config/fieldschemes/{esquemaId}/fields` | startAt | `fieldId` (lista); ate 100 por pagina |
| Parametros de um campo no esquema | atlassian_ler | `GET /rest/api/3/config/fieldschemes/{esquemaId}/fields/{campoId}/parameters` | nao | `parameters` e `workTypeParameters` |
| Projetos de um esquema | atlassian_ler | `GET /rest/api/3/config/fieldschemes/{esquemaId}/projects` | startAt | `projectId` (lista): confere se esses projetos estao nele |
| Esquema de cada projeto | atlassian_ler | `GET /rest/api/3/config/fieldschemes/projects` | startAt | `projectId` (lista); itens `{projectId, schemeId}`; temporario, para a transicao |
| Adicionar campos a esquemas | atlassian_escrever | `PUT /rest/api/3/config/fieldschemes/fields` | nao | lote; 200/207 com `results` ou 204 |
| Remover campos de esquemas | atlassian_excluir | `DELETE /rest/api/3/config/fieldschemes/fields` | nao | lote com `corpo`; 200/207 com `results` ou 204 |
| Alterar parametros | atlassian_escrever | `PUT /rest/api/3/config/fieldschemes/fields/parameters` | nao | lote; 200/207 com `results` ou 204 |
| Remover excecoes por tipo | atlassian_excluir | `DELETE /rest/api/3/config/fieldschemes/fields/parameters` | nao | lote com `corpo`; 200/207 com `results` ou 204 |
| Associar projetos a esquemas | atlassian_escrever | `PUT /rest/api/3/config/fieldschemes/projects` | nao | `{"<esquemaId>": {"projectIds": [...]}}`; 200/207 ou 204 |

Apoio (skill `jira-issues`): `GET /rest/api/3/project/{projetoChave}` (id do projeto e
`issueTypes`), `GET /rest/api/3/issuetype` (`workTypeId` = id do tipo de issue),
`GET /rest/api/3/field` (ids de campo, ex. `description`, `customfield_10000`).

## O que o esquema de campos decide

```
Projeto
 └─ 1 esquema de campos
     └─ campos associados (o que nao esta no esquema nao existe no projeto)
         ├─ parameters: isRequired, description, rendererType   (valem para todos os tipos)
         ├─ workTypeParameters: excecoes por tipo de issue      (sobrepoem parameters)
         └─ restrictedToWorkTypes: o campo so existe nesses tipos (vazio = todos)
```

- **Esquema de campos**: quais campos o projeto tem e como se comportam
  (obrigatorio, texto de ajuda, editor rico ou simples), por tipo de issue.
- **Tela** (skill `jira-telas`): onde o campo aparece (criar, editar, ver).
- **Contexto do campo customizado**: opcoes e valor padrao do campo (outra API).

"Oculto" nao existe mais: tirar o campo do esquema (`DELETE .../fields`) ou
restringi-lo a alguns tipos (`restrictedToWorkTypes`).

`workType` = tipo de issue: `workTypeId` e o id do tipo de issue.

## Leituras

| Pergunta | Caminho |
|---|---|
| Esquema de um projeto | id do projeto (`GET /rest/api/3/project/SUP`); `GET /rest/api/3/config/fieldschemes` com `params={"projectId": ["10000"]}` |
| Projetos de um esquema | `GET .../fieldschemes/{esquemaId}/projects` (com `limite` para todas as paginas) |
| Campos de um esquema e como se comportam | `GET .../fieldschemes/{esquemaId}/fields` com `limite` |
| O campo X no projeto Y | esquema do projeto; `GET .../{esquemaId}/fields` com `params={"fieldId": ["X"]}`: sem resultado = o campo nao existe no projeto |
| Obrigatorio para o tipo T | `workTypeParameters` do tipo T, se houver; senao `parameters.isRequired`. Se `restrictedToWorkTypes` nao estiver vazio e nao tiver T, o campo nem existe em T |
| O que da para mudar no campo | `allowedOperations` (ex. `REMOVE`, `CHANGE_REQUIRED`, `CHANGE_DESCRIPTION`): operacao fora da lista a API recusa |
| Quais campos sao obrigatorios | `GET .../{esquemaId}/fields` com `filtro={"parameters.isRequired": [true]}`; depois olhe as excecoes de cada tipo em `workTypeParameters` |

```
atlassian_ler(intencao="Ver como o campo Sistema afetado (customfield_10000) se comporta no esquema de campos 10000",
              caminho="/rest/api/3/config/fieldschemes/10000/fields",
              params={"fieldId": ["customfield_10000"]})
```

Nas respostas, `restrictedToWorkTypes` e `workTypeId` podem vir como texto
(`"10002"`); no corpo das escritas eles vao como inteiro (abaixo).

## Payloads (escritas em lote)

As quatro escritas de campos recebem um mapa `{id do campo: ...}`. Limites: 100
campos por chamada e 50 esquemas por item (no PUT de parametros, tambem ate 50
itens por campo).

**Tipos no corpo**: sao inteiros (`10000`, nunca `"10000"`) `schemeIds`, `schemeId`,
`restrictedToWorkTypes`, `workTypeId`, `workTypeIds` e `projectIds`. Texto: o id do
campo (chave do mapa) e, na associacao a projetos, o id do esquema usado como chave
do mapa (`"10000"`, por ser chave JSON).

### Adicionar campos

`PUT /rest/api/3/config/fieldschemes/fields`. Poe o campo nos esquemas.
`restrictedToWorkTypes` substitui a restricao atual; sem ele o campo vale para todos
os tipos. Tambem serve para mudar so a restricao de um campo que ja esta no esquema.

```json
{"customfield_10000": [{"schemeIds": [10000, 10001], "restrictedToWorkTypes": [10002]}],
 "customfield_10001": [{"schemeIds": [10000]}]}
```

### Remover campos

`DELETE /rest/api/3/config/fieldschemes/fields`, com o mapa em `corpo`. O campo
deixa de existir nos projetos desses esquemas (substitui o antigo "oculto"); ele
continua existindo no Jira.

```json
{"customfield_10000": {"schemeIds": [10000, 10001]}}
```

```
atlassian_excluir(intencao="Tirar o campo Sistema afetado (customfield_10000) dos esquemas de campos 10000 e 10001",
                  caminho="/rest/api/3/config/fieldschemes/fields",
                  corpo={"customfield_10000": {"schemeIds": [10000, 10001]}})
```

### Parametros

`PUT /rest/api/3/config/fieldschemes/fields/parameters`. `parameters` vale para
todos os tipos; `workTypeParameters` cria ou troca a excecao de cada tipo. Parametro
omitido ou `null` fica como esta. `rendererType`: `jira-text-renderer` (texto
simples) ou `atlassian-wiki-renderer` (editor rico), so em campos de texto. O campo
precisa estar no esquema antes.

```json
{"customfield_10000": [{"schemeIds": [10000],
                        "parameters": {"isRequired": false, "description": "Versao onde o erro aparece"},
                        "workTypeParameters": [{"workTypeId": 10002, "isRequired": true}]}]}
```

Exemplo acima: o campo e opcional no esquema 10000, mas obrigatorio para o tipo 10002.

### Remover excecoes

`DELETE /rest/api/3/config/fieldschemes/fields/parameters`, com o mapa em `corpo`.
O tipo volta a seguir `parameters`. `parameters` aqui e a lista de nomes:
`isRequired`, `description`, `rendererType`. Maximo de 100 remocoes por chamada
(tipos x nomes, somados em todos os itens).

```json
{"customfield_10000": [{"schemeId": 10000, "workTypeIds": [10002], "parameters": ["isRequired"]}]}
```

### Associar projetos

`PUT /rest/api/3/config/fieldschemes/projects`: chave = id do esquema (texto),
`projectIds` inteiros. Os projetos passam a ter os campos e parametros desse
esquema (troca todos os campos deles).

```
atlassian_escrever(intencao="Associar o projeto SUP (10000) ao esquema de campos 10001",
                   metodo="PUT", caminho="/rest/api/3/config/fieldschemes/projects",
                   corpo={"10001": {"projectIds": [10000]}})
```

## Resultados parciais

As escritas em lote respondem 200 ou 207 com `results`: um item por campo e esquema
(ou projeto), com `success` e `error` (texto ou `{code, message}`). **207 = parte
falhou**: leia cada item e diga ao usuario o que nao foi aplicado. 400 com
`results` = pedido bem formado mas com esquema ou campo inexistente (nada ou quase
nada aplicado: confira os itens). Resposta vazia (204, `resposta` null) = tudo
aplicado.

## Fluxo seguro

1. Achar o esquema do projeto e ver quem mais o usa
   (`GET .../fieldschemes/{esquemaId}/projects`). Mudanca no esquema vale para todos
   esses projetos.
2. Se o esquema for compartilhado e a mudanca for so para um projeto: copiar
   (`POST .../{esquemaId}/clone`) e depois associar o projeto ao esquema novo
   (`PUT .../fieldschemes/projects`). Confirmar com o usuario antes: trocar o esquema
   do projeto troca todos os campos dele.
3. Ler o estado atual do campo (`GET .../{esquemaId}/fields` com `fieldId`) e
   conferir `allowedOperations`.
4. Mostrar ao usuario o que muda e aplicar, uma escrita por vez. Conferir `results`.
5. Reler o campo para confirmar.
6. Campo obrigatorio: conferir se ele esta na tela de criacao do tipo
   (skill `jira-telas`); obrigatorio fora da tela impede criar a issue.

## Esquemas

- Criar (`POST /rest/api/3/config/fieldschemes`) nasce so com os campos essenciais
  do sistema, sem copiar nenhum esquema; para partir de um existente, use o
  `.../{esquemaId}/clone`. Os dois devolvem o id; o esquema novo nasce sem projetos.
- Excluir (`DELETE .../{esquemaId}`, responde `{"deleted": true, "id": ...}`): a API
  recusa o esquema do sistema (400) e esquema com projetos (409). Mova os projetos
  antes com `PUT .../fieldschemes/projects`. Nao ha desfazer.
