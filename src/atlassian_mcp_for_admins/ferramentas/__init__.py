"""Camada MCP: uma ferramenta por operacao da API, sem regra de negocio.

Cada modulo expoe FERRAMENTAS = [funcoes]. As funcoes sao Python comum
(testaveis sem MCP); a docstring vira a descricao e os type hints o schema.
A regra de negocio fica no pedido feito no chat, que combina as ferramentas.
"""
from . import forms, geral, jira, jsm

MODULOS = [geral, jira, jsm, forms]


def todas():
    return [f for m in MODULOS for f in m.FERRAMENTAS]
