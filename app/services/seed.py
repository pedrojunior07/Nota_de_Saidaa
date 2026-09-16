"""Dados iniciais para o sistema ficar utilizável após a primeira migração."""

from datetime import date, timedelta

from app.extensions import db
from app.models.configuracao import Configuracao
from app.models.historico import Historico
from app.models.item import ItemNota
from app.models.nota import NotaSaida
from app.models.user import User
from app.utils.constants import EstadoNota, Perfil
from app.utils.tempo import agora

PASSWORD_PADRAO = "Standard@2026"
USUARIOS_DEMO = [
    ("A100001", "Pedro António", Perfil.ADMINISTRADOR.value),
    ("A272754", "Carlos Mendes", Perfil.TECNICO.value),
    ("A200550", "Ana Macamo", Perfil.APROVADOR.value),
]
USUARIOS_DEMO = [
    (username, "Antonio Soto" if username == "A100001" else nome, perfil)
    for username, nome, perfil in USUARIOS_DEMO
]


def _garantir_usuario_demo(username, nome, perfil):
    utilizador = User.query.filter_by(username=username).first()
    if utilizador is None:
        utilizador = User(nome=nome, username=username, perfil=perfil, ativo=True)
        db.session.add(utilizador)
    else:
        utilizador.nome = nome
        utilizador.perfil = perfil
        utilizador.ativo = True
    utilizador.definir_password(PASSWORD_PADRAO)
    db.session.flush()
    return utilizador


def _numero_referencia_disponivel(base_ref):
    """Cria um número alternativo quando o valor-base já existe na BD."""
    prefix = "".join(ch for ch in base_ref if not ch.isdigit())
    digits = base_ref[len(prefix) :]
    inicio = int(digits) if digits.isdigit() else 1
    tentativa = base_ref
    indice = inicio
    while NotaSaida.query.filter_by(numero_referencia=tentativa).first():
        indice += 1
        tentativa = f"{prefix}{indice:0{len(digits)}d}"
    return tentativa


def executar_seed(forcar=False):
    """Cria/garante as contas demo e dados iniciais do sistema."""
    if not forcar and all(
        User.query.filter_by(username=username).first() for username, _, _ in USUARIOS_DEMO
    ):
        return False

    admin, tecnico, aprovador = [
        _garantir_usuario_demo(
            username,
            "Antonio Soto" if username == "A100001" else nome,
            perfil,
        )
        for username, nome, perfil in USUARIOS_DEMO
    ]

    if db.session.get(Configuracao, 1) is None:
        db.session.add(
            Configuracao(
                id=1,
                nome_instituicao="Standard Bank",
                direcao="Direção de Informática",
                morada="Av. 25 de Setembro, Maputo",
                contacto="+258 21 000 000",
                email_contacto="diana.k@example.org",
                rodape_pdf="Documento gerado eletronicamente — Nota de Saída de Equipamento",
                origem_de="Informática",
                origem_local="Sede IT",
                local_emissao="Maputo",
            )
        )

    hoje = date.today()
    agora_dt = agora()

    def _nota(**kwargs):
        ref = kwargs.get("numero_referencia")
        if ref:
            kwargs["numero_referencia"] = _numero_referencia_disponivel(ref)
        nota = NotaSaida(**kwargs)
        db.session.add(nota)
        db.session.flush()
        return nota

    n1 = _nota(
        numero_referencia="INC000100001",
        data_emissao=hoje - timedelta(days=12),
        funcionario="Maria Silva",
        email_funcionario="colaborador@standardbank.co.mz",
        departamento="Recursos Humanos",
        motivo="Atribuição a novo colaborador",
        observacao="Entrega de kit completo de posto de trabalho.",
        estado=EstadoNota.CONCLUIDA.value,
        criado_por=tecnico.id,
        aprovado_por=aprovador.id,
        data_aprovacao=agora_dt - timedelta(days=11),
        data_conclusao=agora_dt - timedelta(days=10),
        data_criacao=agora_dt - timedelta(days=12),
    )
    n1.itens.extend(
        [
            ItemNota(
                tipo_item="Computador Portátil",
                descricao="Dell Latitude 5440",
                numero_serie="DL5440-MZ-001",
                quantidade=1,
            ),
            ItemNota(
                tipo_item="Carregador",
                descricao="Carregador Dell 65W USB-C",
                numero_serie=None,
                quantidade=1,
            ),
            ItemNota(
                tipo_item="Pasta",
                descricao="Mala 15.6\" corporativa",
                numero_serie=None,
                quantidade=1,
            ),
        ]
    )
    db.session.add_all(
        [
            Historico(nota_id=n1.id, utilizador=tecnico.nome, acao="Criou a nota de saída (rascunho).", data_hora=agora_dt - timedelta(days=12)),
            Historico(nota_id=n1.id, utilizador=tecnico.nome, acao="Recolheu a assinatura «Entregue Por».", data_hora=agora_dt - timedelta(days=12, hours=-1)),
            Historico(nota_id=n1.id, utilizador=tecnico.nome, acao="Submeteu a nota para aprovação.", data_hora=agora_dt - timedelta(days=12, hours=-2)),
            Historico(nota_id=n1.id, utilizador=aprovador.nome, acao="Aprovou e assinou a nota de saída.", data_hora=agora_dt - timedelta(days=11)),
            Historico(nota_id=n1.id, utilizador=tecnico.nome, acao="Recolheu a assinatura «Recebido».", data_hora=agora_dt - timedelta(days=10, hours=12)),
            Historico(nota_id=n1.id, utilizador=tecnico.nome, acao="Nota concluída. PDF oficial gerado automaticamente.", data_hora=agora_dt - timedelta(days=11, hours=-1)),
        ]
    )

    n2 = _nota(
        numero_referencia="INC000100002",
        data_emissao=hoje - timedelta(days=3),
        funcionario="Maria Silva",
        email_funcionario="colaborador@standardbank.co.mz",
        departamento="Recursos Humanos",
        motivo="Upgrade de equipamento",
        observacao="Substituição do monitor do posto.",
        estado=EstadoNota.CONCLUIDA.value,
        criado_por=tecnico.id,
        aprovado_por=aprovador.id,
        data_aprovacao=agora_dt - timedelta(days=1),
        data_conclusao=agora_dt - timedelta(days=1),
        data_criacao=agora_dt - timedelta(days=3),
    )
    n2.itens.append(
        ItemNota(
            tipo_item="Monitor",
            descricao="Dell P2422H 24\"",
            numero_serie="MN-2422-7781",
            quantidade=1,
        )
    )
    db.session.add_all(
        [
            Historico(nota_id=n2.id, utilizador=tecnico.nome, acao="Criou a nota de saída (rascunho).", data_hora=agora_dt - timedelta(days=3)),
            Historico(nota_id=n2.id, utilizador=tecnico.nome, acao="Recolheu a assinatura «Entregue Por».", data_hora=agora_dt - timedelta(days=3, hours=-1)),
            Historico(nota_id=n2.id, utilizador=tecnico.nome, acao="Submeteu a nota para aprovação.", data_hora=agora_dt - timedelta(days=2)),
            Historico(nota_id=n2.id, utilizador=aprovador.nome, acao="Aprovou e assinou a nota de saída.", data_hora=agora_dt - timedelta(days=1)),
            Historico(nota_id=n2.id, utilizador=tecnico.nome, acao="Recolheu a assinatura «Recebido».", data_hora=agora_dt - timedelta(hours=20)),
            Historico(nota_id=n2.id, utilizador=tecnico.nome, acao="Nota concluída. PDF oficial gerado automaticamente.", data_hora=agora_dt - timedelta(hours=20)),
        ]
    )

    n3 = _nota(
        numero_referencia="INC000100003",
        data_emissao=hoje,
        funcionario="João Cossa",
        email_funcionario="hannah.h@example.com",
        departamento="Operações",
        motivo="Trabalho remoto",
        observacao="Kit temporário para teletrabalho.",
        estado=EstadoNota.PENDENTE_APROVACAO.value,
        criado_por=tecnico.id,
        data_criacao=agora_dt - timedelta(hours=5),
    )
    n3.itens.extend(
        [
            ItemNota(
                tipo_item="Computador Portátil",
                descricao="HP EliteBook 840 G10",
                numero_serie="HP840-MZ-441",
                quantidade=1,
            ),
            ItemNota(
                tipo_item="Headset",
                descricao="Jabra Evolve 20",
                numero_serie=None,
                quantidade=1,
            ),
        ]
    )
    db.session.add_all(
        [
            Historico(nota_id=n3.id, utilizador=tecnico.nome, acao="Criou a nota de saída (rascunho).", data_hora=agora_dt - timedelta(hours=5)),
            Historico(nota_id=n3.id, utilizador=tecnico.nome, acao="Submeteu a nota para aprovação.", data_hora=agora_dt - timedelta(hours=4)),
        ]
    )

    n4 = _nota(
        numero_referencia="INC000100004",
        data_emissao=hoje - timedelta(days=1),
        funcionario="Paula Nhantumbo",
        email_funcionario="xena.w@example.org",
        departamento="Crédito",
        motivo="Substituição de equipamento",
        observacao="Mouse com avaria reportada.",
        estado=EstadoNota.REJEITADA.value,
        criado_por=tecnico.id,
        aprovado_por=aprovador.id,
        data_aprovacao=agora_dt - timedelta(hours=8),
        comentario_decisao="Número de série não confere com o inventário.",
        data_criacao=agora_dt - timedelta(days=1),
    )
    n4.itens.append(
        ItemNota(
            tipo_item="Mouse",
            descricao="Logitech M185",
            numero_serie="LG-M185-992",
            quantidade=1,
        )
    )
    db.session.add_all(
        [
            Historico(nota_id=n4.id, utilizador=tecnico.nome, acao="Criou a nota de saída (rascunho).", data_hora=agora_dt - timedelta(days=1)),
            Historico(nota_id=n4.id, utilizador=tecnico.nome, acao="Submeteu a nota para aprovação.", data_hora=agora_dt - timedelta(days=1)),
            Historico(
                nota_id=n4.id,
                utilizador=aprovador.nome,
                acao="Rejeitou a nota de saída. Motivo: Número de série não confere com o inventário.",
                data_hora=agora_dt - timedelta(hours=8),
            ),
        ]
    )

    n5 = _nota(
        numero_referencia="INC000100005",
        data_emissao=hoje,
        funcionario="Sérgio Langa",
        email_funcionario="olivia.t@example.org",
        departamento="Tesouraria",
        motivo="Atribuição a novo colaborador",
        observacao=None,
        estado=EstadoNota.RASCUNHO.value,
        criado_por=tecnico.id,
        data_criacao=agora_dt - timedelta(hours=1),
    )
    n5.itens.append(
        ItemNota(
            tipo_item="Teclado",
            descricao="Teclado Dell KB216",
            numero_serie=None,
            quantidade=1,
        )
    )
    db.session.add(
        Historico(nota_id=n5.id, utilizador=tecnico.nome, acao="Criou a nota de saída (rascunho).", data_hora=agora_dt - timedelta(hours=1))
    )

    db.session.commit()
    return True
