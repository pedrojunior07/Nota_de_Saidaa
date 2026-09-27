"""Relatório de equipamentos entregues (por módulo: Saída ou Entrega).

Conta apenas notas CONCLUÍDAS — o equipamento só está entregue quando o
recetor assina «Recebido» — e usa a data de conclusão como data de entrega.
Funciona em SQLite e em MongoDB (USE_MONGO_NOTAS / USE_MONGO_ENTREGA).

O volume é pequeno (centenas/milhares de itens por ano), por isso as notas
concluídas são lidas e agregadas em Python: um só código para os dois modos.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app.utils.constants import EstadoNota

MODULOS = {
    "saida": {
        "titulo_pdf": "Nota de Saida - Direção de Informática",
        "nome": "Nota de Saída",
        "detalhe": "notas.detalhe",
    },
    "entrega": {
        "titulo_pdf": "Nota de Entrega — Direção de Informática",
        "nome": "Nota de Entrega",
        "detalhe": "entrega.detalhe",
    },
}

PERIODOS = {
    "mes": "Este mês",
    "ano": "Este ano",
    "personalizado": "Personalizado",
}

FILTROS_TEXTO = ("tipo", "departamento", "local", "motivo", "tecnico")


# ---------------------------------------------------------------------------
# Período
# ---------------------------------------------------------------------------
def intervalo(periodo: str, inicio: date | None, fim: date | None, hoje: date | None = None):
    """Devolve (inicio, fim) inclusivos para o período escolhido."""
    hoje = hoje or date.today()
    if periodo == "ano":
        return hoje.replace(month=1, day=1), hoje
    if periodo == "personalizado":
        inicio = inicio or hoje.replace(day=1)
        fim = fim or hoje
        if fim < inicio:
            inicio, fim = fim, inicio
        return inicio, fim
    return hoje.replace(day=1), hoje  # "mes" (omissão)


# ---------------------------------------------------------------------------
# Leitura das notas concluídas
# ---------------------------------------------------------------------------
def _mongo_ativo(tipo: str) -> bool:
    flag = "USE_MONGO_NOTAS" if tipo == "saida" else "USE_MONGO_ENTREGA"
    return os.environ.get(flag, "0").strip().lower() in {"1", "true", "yes", "on"}


def _notas_concluidas(tipo: str) -> list:
    concluida = EstadoNota.CONCLUIDA.value
    if _mongo_ativo(tipo):
        if tipo == "saida":
            from app.repositories.notas import MongoNotaRepository as Repo
        else:
            from app.repositories.entrega import MongoEntregaRepository as Repo
        return Repo().listar({"estado": concluida})
    if tipo == "saida":
        from app.models.nota import NotaSaida as Modelo
    else:
        from app.models.nota_entrega import NotaEntrega as Modelo
    return Modelo.query.filter(Modelo.estado == concluida).all()


def _data(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def _nome_pessoa(pessoa) -> str:
    if not pessoa:
        return ""
    return getattr(pessoa, "nome_exibicao", None) or getattr(pessoa, "nome", None) or ""


def _texto(valor) -> str:
    return (valor or "").strip()


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
@dataclass
class Relatorio:
    tipo: str
    inicio: date
    fim: date
    filtros: dict
    linhas: list = field(default_factory=list)       # uma por unidade entregue
    opcoes: dict = field(default_factory=dict)       # valores para os filtros

    # -- resumo ------------------------------------------------------------
    @property
    def total_equipamentos(self) -> int:
        return sum(l["quantidade"] for l in self.linhas)

    @property
    def total_notas(self) -> int:
        return len({l["nota_id"] for l in self.linhas})

    @property
    def total_colaboradores(self) -> int:
        return len({(l["email"] or l["colaborador"]).lower() for l in self.linhas})

    def _agrupar(self, chave: str) -> list[dict]:
        qtd, notas = Counter(), defaultdict(set)
        for l in self.linhas:
            nome = l[chave] or "—"
            qtd[nome] += l["quantidade"]
            notas[nome].add(l["nota_id"])
        return [
            {"nome": nome, "quantidade": q, "notas": len(notas[nome])}
            for nome, q in sorted(qtd.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    @property
    def por_tipo(self) -> list[dict]:
        return self._agrupar("tipo")

    @property
    def por_departamento(self) -> list[dict]:
        return self._agrupar("departamento")

    @property
    def filtros_ativos(self) -> list[tuple[str, str]]:
        rotulos = {"tipo": "Tipo", "departamento": "Departamento", "local": "Local",
                   "motivo": "Motivo", "tecnico": "Técnico"}
        return [(rotulos[k], v) for k, v in self.filtros.items() if v]


def gerar(tipo: str, inicio: date, fim: date, filtros: dict | None = None) -> Relatorio:
    filtros = {k: _texto((filtros or {}).get(k)) for k in FILTROS_TEXTO}
    no_periodo = []
    for nota in _notas_concluidas(tipo):
        entregue_em = _data(getattr(nota, "data_conclusao", None))
        if not entregue_em or not (inicio <= entregue_em <= fim):
            continue
        base = {
            "nota_id": nota.id,
            "data": entregue_em,
            "numero_nota": getattr(nota, "numero_documento", "") or "",
            "referencia": getattr(nota, "numero_referencia", "") or "",
            "colaborador": _texto(getattr(nota, "funcionario", "")),
            "email": _texto(getattr(nota, "email_funcionario", "")),
            "departamento": _texto(getattr(nota, "departamento", "")),
            "local": _texto(getattr(nota, "local_emissao", "")),
            "motivo": _texto(getattr(nota, "motivo", "")),
            "tecnico": _nome_pessoa(getattr(nota, "criador", None)),
        }
        for item in getattr(nota, "itens", None) or []:
            unidade = {
                **base,
                "tipo": _texto(getattr(item, "tipo_item", "")) or "Outro",
                "descricao": _texto(getattr(item, "descricao", "")),
                "numero_serie": _texto(getattr(item, "numero_serie", "")),
                "numero_sap": _texto(getattr(item, "numero_sap", "")),
                "quantidade": 1,
            }
            # Uma linha por unidade: um item "5 × Mouse" passa a 5 linhas, para
            # que cada linha do detalhe seja um equipamento e os totais batam.
            no_periodo.extend(dict(unidade) for _ in range(int(getattr(item, "quantidade", 0) or 0)))

    # Opções dos filtros: valores existentes no período (antes de filtrar),
    # para nunca oferecer uma escolha que dá zero resultados.
    opcoes = {k: sorted({l[k] for l in no_periodo if l[k]}, key=str.lower) for k in FILTROS_TEXTO}

    linhas = [l for l in no_periodo if all(not v or l[k] == v for k, v in filtros.items())]
    linhas.sort(key=lambda l: (l["data"], l["referencia"]), reverse=True)
    return Relatorio(tipo=tipo, inicio=inicio, fim=fim, filtros=filtros, linhas=linhas, opcoes=opcoes)
