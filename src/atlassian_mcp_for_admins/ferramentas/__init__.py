"""Camada MCP: a conexao e tres ferramentas genericas, divididas por risco.

As funcoes sao Python comum (testaveis sem MCP); a docstring vira a descricao e os
type hints o schema. O conhecimento de cada endpoint fica nas skills do plugin e a
regra de negocio no pedido feito no chat, que combina as chamadas.
"""
from . import geral

MODULOS = [geral]


def todas():
    return [f for m in MODULOS for f in m.FERRAMENTAS]
