---
name: sites
description: Abre a tela local do plugin atlassian-admin para cadastrar, testar e trocar o site Atlassian em uso (perfis com URL, e-mail e API token guardado no Keychain). Use quando o usuario pedir para trocar de site, conectar outro site Atlassian, cadastrar ou atualizar credencial ou token, quando o token venceu (HTTP 401), ou quando as ferramentas responderem "Credenciais ausentes".
---

# Tela de sites

A tela e uma pagina local (so em 127.0.0.1) onde o usuario guarda varios sites
Atlassian como perfis e escolhe qual o plugin usa. O token vai da pagina direto para
o cofre do sistema (Keychain no macOS); nunca passa pelo chat.

## Abrir

Rode em segundo plano (o comando fica no ar enquanto a tela estiver aberta):

```bash
UV_PROJECT_ENVIRONMENT="${CLAUDE_PLUGIN_DATA}/venv" uv run --project "${CLAUDE_PLUGIN_ROOT}" --frozen --quiet python -m atlassian_mcp_for_admins.tela
```

- O comando abre o navegador sozinho e imprime `Tela de sites aberta em http://127.0.0.1:<porta>/#k=<chave>`.
  Leia a saida e passe esse endereco ao usuario, caso o navegador nao tenha aberto.
- A tela fecha pelo botao "Fechar tela" ou apos 30 minutos sem uso.
- Se a porta 8765 estiver ocupada (outra tela aberta), ela abre em outra porta.

## Regras

- Nunca peca o token no chat, nem o passe em linha de comando: o usuario digita na
  tela.
- A troca de perfil vale na proxima chamada das ferramentas, sem reiniciar a sessao.
  Depois que o usuario disser que trocou, chame `atlassian_conexao` e confirme o site
  e a conta antes de seguir.
- Ids, chaves e nomes lidos de um site nao valem em outro. Depois de uma troca, releia
  o que for usar; nao reaproveite ids da conversa.
- As respostas de `atlassian_escrever` e `atlassian_excluir` trazem `site`: confira que
  e o site que o usuario pediu.
- Se a tela avisar que outra fonte vence os perfis, e o userConfig do plugin (ou o
  `.env` do repositorio, em desenvolvimento) que esta preenchido: o usuario limpa
  essas opcoes para o perfil valer.

## Ordem das credenciais

1. Ambiente (userConfig do plugin) e `.env` do repositorio, quando completos.
2. Perfil ativo da tela.
3. `~/.config/atlassian-admin/.env`, o metodo anterior. A tela oferece importar esse
   arquivo como perfil.
