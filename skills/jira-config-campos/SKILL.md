---
name: jira-config-campos
description: Modelo das configuracoes de campo e dos esquemas de configuracao de campo do Jira company-managed (API antiga /rest/api/3/fieldconfiguration e /fieldconfigurationscheme, obsoleta mas ativa na maioria dos sites) - projeto, esquema, item por tipo de issue, configuracao e os itens de cada campo (obrigatorio, oculto, descricao, renderizador) - com os endpoints, o caminho para descobrir como um campo se comporta num projeto, os payloads, os tipos dos ids no corpo e o fluxo seguro de alteracao. Use SEMPRE antes de mudar obrigatorio, oculto, descricao ou renderizador de campos pela API antiga, antes de criar, renomear, ligar, associar ou excluir configuracoes e esquemas de configuracao de campo, e quando o pedido for "o campo X e obrigatorio no projeto Y", "quais campos sao obrigatorios" ou "por que o campo nao aparece" num site sem o beta de esquemas de campos.
---

# Configuracoes de campo do Jira (API antiga)

`/rest/api/3/fieldconfiguration` e `/fieldconfigurationscheme`. A Atlassian marcou
como obsoletas em favor dos esquemas de campos (API nova, em beta, skill
`jira-esquemas-campos`), mas elas continuam sendo as que funcionam em sites sem o
beta. Se o pedido nao disser qual API usar: esta, a menos que
`GET /rest/api/3/config/fieldschemes` responda sem o aviso de "desligada".

Vale so para projetos **company-managed**; todos os endpoints exigem admin do Jira.
Chamadas: skill `atlassian-chamadas`.

## Endpoints

| Operacao | Ferramenta | Metodo e caminho | Paginacao | Observacao |
|---|---|---|---|---|
| Listar configuracoes de campo | atlassian_ler | `GET /rest/api/3/fieldconfiguration` | startAt | `id` (lista), `query` (nome ou descricao), `isDefault=true` (so a padrao do site) |
| Criar configuracao | atlassian_escrever | `POST /rest/api/3/fieldconfiguration` | nao | `{"name", "description"}`; nasce com todos os campos opcionais |
| Renomear configuracao | atlassian_escrever | `PUT /rest/api/3/fieldconfiguration/{configId}` | nao | sobrescreve `name` E `description` |
| Excluir configuracao | atlassian_excluir | `DELETE /rest/api/3/fieldconfiguration/{configId}` | nao | so a que nao esta em esquema |
| Itens (campos) de uma configuracao | atlassian_ler | `GET /rest/api/3/fieldconfiguration/{configId}/fields` | startAt | todos os campos do site (mais de mil); use `filtro` |
| Alterar itens | atlassian_escrever | `PUT /rest/api/3/fieldconfiguration/{configId}/fields` | nao | `{"fieldConfigurationItems": [...]}` |
| Listar esquemas de configuracao | atlassian_ler | `GET /rest/api/3/fieldconfigurationscheme` | startAt | `id` (lista); nao filtra por nome |
| Criar esquema | atlassian_escrever | `POST /rest/api/3/fieldconfigurationscheme` | nao | `{"name", "description"}`; nasce vazio |
| Renomear esquema | atlassian_escrever | `PUT /rest/api/3/fieldconfigurationscheme/{esquemaId}` | nao | sobrescreve `name` E `description` |
| Excluir esquema | atlassian_excluir | `DELETE /rest/api/3/fieldconfigurationscheme/{esquemaId}` | nao | so esquema sem projetos |
| Itens dos esquemas (tipo de issue -> configuracao) | atlassian_ler | `GET /rest/api/3/fieldconfigurationscheme/mapping` | startAt | `fieldConfigurationSchemeId` (lista, ate 50) |
| Adicionar ou trocar itens do esquema | atlassian_escrever | `PUT /rest/api/3/fieldconfigurationscheme/{esquemaId}/mapping` | nao | `{"mappings": [...]}` |
| Remover itens do esquema | atlassian_escrever | `POST /rest/api/3/fieldconfigurationscheme/{esquemaId}/mapping/delete` | nao | `{"issueTypeIds": [...]}`, ate 100 |
| Esquema de configuracao dos projetos | atlassian_ler | `GET /rest/api/3/fieldconfigurationscheme/project` | startAt | `projectId` (lista, ids numericos) |
| Associar esquema a projeto | atlassian_escrever | `PUT /rest/api/3/fieldconfigurationscheme/project` | nao | `{"fieldConfigurationSchemeId", "projectId"}`; `null` = esquema padrao |

Apoio (skill `jira-issues`): `GET /rest/api/3/project/{projetoChave}` (id e
`issueTypes`), `GET /rest/api/3/field` (ids de campo), `GET /rest/api/3/project/search`
(ids de todos os projetos).

## A cadeia

```
Projeto
 └─ 1 esquema de configuracao de campo            (fieldconfigurationscheme)
     ├─ item "default" ─> configuracao de campo    (tipos sem item proprio)
     └─ item <tipo>    ─> configuracao de campo    (fieldconfiguration)
                            └─ 1 item por campo do site:
                               isRequired, isHidden, description, renderer
```

- Projeto sem esquema proprio usa o esquema padrao do site, que aponta para a
  configuracao padrao (`GET /rest/api/3/fieldconfiguration` com
  `params={"isDefault": true}`).
- Varios projetos e tipos podem dividir a mesma configuracao: mudar um item muda
  todos eles.
- **Configuracao de campo**: como o campo se comporta. **Tela** (skill `jira-telas`):
  onde aparece. **Contexto do campo customizado**: opcoes e valor padrao (outra API).

| Item | Efeito |
|---|---|
| `isRequired` | Nao deixa criar ou editar a issue com o campo vazio |
| `isHidden` | O campo some do projeto e tipo, mesmo estando na tela |
| `description` | Texto de ajuda que aparece embaixo do campo |
| `renderer` | Campos de texto: `wiki-renderer` (editor rico) ou `text-renderer` (simples) |

## Como o campo X se comporta no projeto Y, tipo T

```
1. atlassian_ler(intencao="Ler o id e os tipos de issue do projeto SUP",
                 caminho="/rest/api/3/project/SUP",
                 manter=["id", "key", "issueTypes.id", "issueTypes.name"])

2. atlassian_ler(intencao="Ver o esquema de configuracao de campo do projeto SUP",
                 caminho="/rest/api/3/fieldconfigurationscheme/project",
                 params={"projectId": ["10000"]})
   -> values[]: {fieldConfigurationScheme, projectIds}

3. atlassian_ler(intencao="Ler os itens do esquema de configuracao de campo 10100",
                 caminho="/rest/api/3/fieldconfigurationscheme/mapping",
                 params={"fieldConfigurationSchemeId": ["10100"]})
   -> item de T; sem item proprio, vale issueTypeId "default". Da o fieldConfigurationId

4. atlassian_ler(intencao="Ver como os campos Ambiente e Sistema afetado se comportam na configuracao 10200",
                 caminho="/rest/api/3/fieldconfiguration/10200/fields",
                 filtro={"id": ["environment", "customfield_10000"]})
```

- Passo 2: grupo sem `fieldConfigurationScheme` = projeto no esquema padrao do site;
  a configuracao e a padrao (`isDefault=true`) e o passo 3 nao se aplica.
- Passo 4: a configuracao traz todos os campos do site (mais de mil em sites
  grandes). `filtro` percorre as paginas e devolve so os campos pedidos; os que
  vierem em `sem_correspondencia` nao estao na configuracao. Se vier
  `sem_correspondencia_parcial` com `continuar`, a varredura parou no teto: chame de
  novo com `continuar.params`.

"Quais campos sao obrigatorios no projeto": passos 1 a 3 para cada tipo e, para
cada configuracao, `filtro={"isRequired": [true]}` no passo 4 (com
`manter=["values.id", "values.isRequired"]` se a lista for grande). O mesmo com
`isHidden` para "quais campos estao ocultos".

"Quais projetos usam esta configuracao": `GET /rest/api/3/fieldconfigurationscheme/mapping`
sem `fieldConfigurationSchemeId` e com `filtro={"fieldConfigurationId": ["10200"]}`
da os esquemas que a usam; `GET /rest/api/3/fieldconfigurationscheme/project` com os
ids dos projetos (`/rest/api/3/project/search`) diz o esquema de cada um.

## Payloads e tipos

Ids no corpo vao como **texto**: `fieldConfigurationId`, `issueTypeId`,
`issueTypeIds`, `fieldConfigurationSchemeId` e `projectId` (o id numerico do projeto
em texto, `"10000"`). Nos caminhos, o id da configuracao e do esquema e numerico.

### Itens de campo

`PUT /rest/api/3/fieldconfiguration/{configId}/fields` com
`{"fieldConfigurationItems": [...]}`. So o que vier no item muda. `id` e o id do
campo.

```json
[{"id": "customfield_10000", "isRequired": true},
 {"id": "environment", "isHidden": true},
 {"id": "description", "description": "Passos para reproduzir", "renderer": "wiki-renderer"}]
```

```
atlassian_escrever(intencao="Tornar obrigatorio o campo Sistema afetado (customfield_10000) na configuracao de campo 10200",
                   metodo="PUT", caminho="/rest/api/3/fieldconfiguration/10200/fields",
                   corpo={"fieldConfigurationItems": [{"id": "customfield_10000", "isRequired": true}]})
```

- **Ocultar apaga** obrigatorio, descricao e renderizador do campo; reexibir volta aos
  valores padrao, nao aos anteriores. Antes de ocultar, anote o item atual.
- `renderer`: so `wiki-renderer` ou `text-renderer`, e so em campos de texto. Nao da
  para trocar o renderizador de campo com `autocomplete-renderer`.
- Campos essenciais do sistema (ex. `summary`, `issuetype`) sao sempre obrigatorios e
  visiveis no Jira: nao tente muda-los.
- Vale para todo projeto e tipo de issue que usa a configuracao. Responde 204.

### Itens do esquema

`PUT /rest/api/3/fieldconfigurationscheme/{esquemaId}/mapping` com
`{"mappings": [...]}`. Tipo de issue -> configuracao. Cria ou troca o item do tipo;
cada tipo uma vez so por chamada.

```json
[{"issueTypeId": "default", "fieldConfigurationId": "10000"},
 {"issueTypeId": "10001", "fieldConfigurationId": "10002"}]
```

- Remover itens: `POST .../{esquemaId}/mapping/delete` com
  `{"issueTypeIds": ["10001"]}` (ate 100); esses tipos voltam ao `default`.
- Associar projeto: `PUT /rest/api/3/fieldconfigurationscheme/project` com
  `{"fieldConfigurationSchemeId": "10100", "projectId": "10000"}`;
  `"fieldConfigurationSchemeId": null` volta ao esquema padrao do site. Muda
  obrigatorio e oculto de todos os campos do projeto.

## Fluxo seguro

1. Seguir a cadeia ate a configuracao do projeto e tipo.
2. Ver quem mais usa essa configuracao (secao acima). Se for compartilhada e a
   mudanca for so para um projeto ou tipo:
   - criar uma configuracao (`POST /rest/api/3/fieldconfiguration`; nasce com as
     propriedades da padrao, mas todos os campos opcionais) e reproduzir nela os
     itens que importam da configuracao atual;
   - se o esquema tambem for compartilhado, criar um esquema
     (`POST /rest/api/3/fieldconfigurationscheme`, nasce vazio) e copiar os itens
     atuais com `PUT .../{esquemaId}/mapping`;
   - ligar o tipo a configuracao nova (`PUT .../{esquemaId}/mapping`) e, se preciso,
     o projeto ao esquema novo (`PUT /rest/api/3/fieldconfigurationscheme/project`).
   Configuracao e esquema novos nao entram em uso sozinhos.
3. Mostrar ao usuario o plano e pedir confirmacao.
4. `PUT .../{configId}/fields` e conferir relendo com `filtro={"id": [...]}`.
5. Campo obrigatorio: conferir se ele esta na tela de criacao do tipo (skill
   `jira-telas`); obrigatorio fora da tela impede criar a issue.

## Renomear e excluir

- O PUT de configuracao e o de esquema sobrescrevem nome **e** descricao: repita a
  descricao atual no corpo para mante-la (`{"name": "Novo nome", "description":
  "<atual>"}`).
- Exclua so configuracao que nao esta em nenhum esquema (`mapping` com `filtro` no
  `fieldConfigurationId`) e esquema sem projetos (a especificacao nao diz o que a
  API faz nos outros casos). Excluir esquema nao exclui as configuracoes. Para
  esvaziar um esquema, associe os projetos a outro, ou ao padrao com
  `fieldConfigurationSchemeId: null`. Nao ha desfazer.
