"""Sobe o servidor pelo transporte stdio (como o Claude Code faz), lista as
ferramentas e chama atlassian_conexao. Exige Python 3.10+ com o pacote instalado.

Rodar: .venv/bin/python -m tests.mcp_stdio
"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "atlassian_mcp_for_admins"])
    async with stdio_client(params) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            ferramentas = (await sessao.list_tools()).tools
            print(f"{len(ferramentas)} ferramentas:")
            for f in ferramentas:
                somente_leitura = getattr(f.annotations, "read_only_hint", None)
                print(f"  {f.name:<26} leitura={somente_leitura}")
            resultado = await sessao.call_tool("atlassian_conexao", {})
            print("atlassian_conexao ->", resultado.content[0].text[:300])
            if getattr(resultado, "is_error", False):
                sys.exit(1)
            # falha prevista: o motivo precisa chegar ao cliente, nao so "Error executing tool"
            falha = await sessao.call_tool("atlassian_get", {"caminho": "https://evil.example.com/x"})
            texto = falha.content[0].text
            print("falha prevista ->", texto[:200])
            if not getattr(falha, "is_error", False) or "Host nao permitido" not in texto:
                print("ERRO: o motivo da falha nao chegou ao cliente")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
