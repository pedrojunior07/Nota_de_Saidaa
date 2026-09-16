"""Constantes de domínio partilhadas por modelos, formulários e templates."""

from enum import Enum


class Perfil(str, Enum):
    ADMINISTRADOR = "administrador"
    TECNICO = "tecnico"
    APROVADOR = "aprovador"
    # Acumula as permissões de Técnico e de Admin — só não aprova notas
    # (isso continua exclusivo do Aprovador).
    TECNICO_ADMIN = "tecnico_admin"


class EstadoNota(str, Enum):
    RASCUNHO = "rascunho"
    PENDENTE_APROVACAO = "pendente_aprovacao"
    EM_REVISAO = "em_revisao"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    CONCLUIDA = "concluida"


PERFIS_LABEL = {
    Perfil.ADMINISTRADOR.value: "Admin",
    Perfil.TECNICO.value: "Técnico",
    Perfil.APROVADOR.value: "Aprovador",
    Perfil.TECNICO_ADMIN.value: "Técnico Admin",
}

ESTADOS_LABEL = {
    EstadoNota.RASCUNHO.value: "Rascunho",
    EstadoNota.PENDENTE_APROVACAO.value: "Pendente Aprovação",
    EstadoNota.EM_REVISAO.value: "Em revisão",
    EstadoNota.APROVADA.value: "Aprovada",
    EstadoNota.REJEITADA.value: "Rejeitada",
    EstadoNota.CONCLUIDA.value: "Concluída",
}

ESTADOS_BADGE = {
    EstadoNota.RASCUNHO.value: "secondary",
    EstadoNota.PENDENTE_APROVACAO.value: "warning",
    EstadoNota.EM_REVISAO.value: "warning",
    EstadoNota.APROVADA.value: "info",
    EstadoNota.REJEITADA.value: "danger",
    EstadoNota.CONCLUIDA.value: "success",
}

TIPOS_ITEM = [
    "Computador Portátil",
    "Computador Desktop",
    "Monitor",
    "Tablet",
    "Celular",
    "Mouse",
    "Teclado",
    "Carregador",
    "Pasta",
    "Headset",
    "Outro",
]

# Tipos de item que, além do número de série (obrigatório), também podem
# levar um número de SAP (opcional).
TIPOS_ITEM_COM_SAP = [
    "Computador Portátil",
    "Computador Desktop",
    "Monitor",
]

MOTIVOS_ATRIBUICAO = [
    "Nova Atribuição",
    "Substituição",
    "Upgrade",
    "Avaria",
    "Outro",
]

# Valor da opção que exige um texto livre a especificar o motivo.
MOTIVO_OUTRO = "Outro"
