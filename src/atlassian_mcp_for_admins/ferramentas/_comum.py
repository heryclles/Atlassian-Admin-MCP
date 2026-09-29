"""Ajudantes mecanicos compartilhados pelas ferramentas (nada de regra de negocio)."""
from typing import Any, Callable

# chaves que so fazem volume na conversa
RUIDO = {"self", "avatarUrls", "iconUrl", "expand", "_links", "_expands"}


def leitura(f: Callable) -> Callable:
    """Somente leitura: vira readOnlyHint no MCP."""
    f.somente_leitura = True
    return f


def escrita(f: Callable) -> Callable:
    """Altera dados no site: vira destructiveHint no MCP (o cliente pede confirmacao)."""
    f.somente_leitura = False
    return f


PLUGIN = "atlassian-admin"


def usa_skill(*skills: str) -> Callable:
    """Liga a ferramenta a skills do plugin que explicam o payload da API.

    Acrescenta a descricao da ferramenta a instrucao de carregar as skills antes de
    usar e registra o vinculo (`f.skills`), que os testes conferem contra skills/.
    """
    def decorar(f: Callable) -> Callable:
        f.skills = skills
        nomes = " e ".join(f"{PLUGIN}:{s}" for s in skills)
        aviso = (f"\n\nAntes de montar ou interpretar o payload, carregue a skill {nomes}: "
                 f"ela explica a estrutura que a API exige." if len(skills) == 1 else
                 f"\n\nAntes de montar ou interpretar o payload, carregue as skills {nomes}: "
                 f"elas explicam a estrutura que a API exige.")
        f.__doc__ = (f.__doc__ or "").rstrip() + aviso
        return f
    return decorar


def limpar(dado: Any) -> Any:
    """Remove links e avatares da resposta da API, recursivamente. O resto vem intacto."""
    if isinstance(dado, dict):
        return {k: limpar(v) for k, v in dado.items() if k not in RUIDO}
    if isinstance(dado, list):
        return [limpar(v) for v in dado]
    return dado


def faixa(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(int(valor), maximo))
