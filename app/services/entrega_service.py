"""Regras de negócio da Nota de Entrega.

Fluxo (igual ao da Nota de Saída):
    rascunho → (técnico recolhe «Entregue Por») → submeter
    → pendente_aprovacao → (Aprovador aprova e assina «Autorizado por»)
    → aprovada → (técnico recolhe «Recebido», que conclui a nota)
    → concluida (PDF gerado)

A assinatura do «Segurança» é opcional e pode ser recolhida a qualquer
momento antes da conclusão — não bloqueia nem a submissão nem a conclusão.
"""

from flask import current_app
from sqlalchemy import or_

from app.extensions import db
from app.models.historico_entrega import HistoricoEntrega
from app.models.item_entrega import ItemEntrega
from app.models.nota_entrega import NotaEntrega
from app.models.user import User
from app.services.entrega_pdf import gerar_pdf_entrega
from app.utils.assinatura_zonas import enquadrar as _enquadrar
from app.utils.constants import ESTADOS_LABEL, EstadoNota, Perfil
from app.utils.tempo import agora


def enquadrar(papel, posicao):
    """Enquadra uma posição de assinatura na variante «entrega»."""
    return _enquadrar(papel, posicao, tipo="entrega")

PAPEIS_ASSINATURA = {
    "entregue": ("assinatura_entregue", "Entregue Por"),
    "recebido": ("assinatura_recebido", "Recebido"),
    "seguranca": ("assinatura_seguranca", "Segurança"),
}


def registrar(nota, acao, utilizador=None):
    nome = getattr(utilizador, "nome", None) or "Sistema"
    db.session.add(HistoricoEntrega(nota_id=nota.id, utilizador=nome, acao=acao))


# ---- itens ----------------------------------------------------------------

def extrair_itens(formulario):
    tipos = formulario.getlist("tipo_item")
    destinos = formulario.getlist("destino_item")
    descricoes = formulario.getlist("descricao_item")
    series = formulario.getlist("numero_serie")
    saps = formulario.getlist("numero_sap")
    quantidades = formulario.getlist("quantidade")

    itens = []
    for i, tipo in enumerate(tipos):
        descricao = descricoes[i].strip() if i < len(descricoes) else ""
        if not descricao:
            continue
        try:
            quantidade = int(quantidades[i]) if i < len(quantidades) else 1
        except (TypeError, ValueError):
            quantidade = 1
        itens.append(
            {
                "tipo_item": tipo or "Outro",
                "destino": (destinos[i].strip() if i < len(destinos) else "") or None,
                "descricao": descricao,
                "numero_serie": (series[i].strip() if i < len(series) else "") or None,
                "numero_sap": (saps[i].strip() if i < len(saps) else "") or None,
                "quantidade": max(quantidade, 1),
            }
        )
    return itens


def _substituir_itens(nota, itens):
    nota.itens.clear()
    db.session.flush()
    for dados in itens:
        nota.itens.append(ItemEntrega(**dados))


# ---- criação / edição ---------------------------------------------------

def _aplicar_dados(nota, dados):
    nota.numero_referencia = dados["numero_referencia"].strip()
    nota.data_emissao = dados["data_emissao"]
    nota.funcionario = dados["funcionario"].strip()
    nota.email_funcionario = dados["email_funcionario"].strip().lower()
    nota.departamento = dados["departamento"].strip()
    nota.motivo = dados["motivo"]
    nota.observacao = (dados.get("observacao") or "").strip() or None
    nota.origem_local = (dados.get("origem_local") or "Sede IT").strip()
    nota.local_emissao = (dados.get("local_emissao") or "Maputo").strip()


def _aplicar_assinatura_entregue(nota, utilizador, posicao=None):
    if utilizador.assinatura_path:
        nota.assinatura_entregue_path = utilizador.assinatura_path
    if posicao:
        pos = enquadrar("entregue", posicao)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"assinatura_entregue_{eixo}", pos[eixo])


def carregar_nota(dados, ficheiro, utilizador):
    """Regista uma Nota de Entrega já existente (documento externo, ex.: nota
    antiga digitalizada) diretamente na listagem, sem o fluxo normal de
    criação/itens/assinaturas. O PDF enviado é guardado tal como está e
    nunca é substituído (ver `pdf_carregado` e a rota de download)."""
    from app.utils.uploads import guardar_pdf_upload

    caminho_pdf, erro = guardar_pdf_upload(ficheiro)
    if erro:
        raise ValueError(erro)

    nota = NotaEntrega(
        numero_referencia=dados["numero_referencia"].strip(),
        data_emissao=dados["data_emissao"],
        funcionario=dados["funcionario"].strip(),
        email_funcionario=dados["email_funcionario"].strip().lower(),
        departamento="N/A",
        motivo="Nota carregada manualmente",
        origem_local=(dados.get("origem_local") or "Sede IT").strip(),
        local_emissao="Maputo",
        estado=dados["estado"],
        criado_por=utilizador.id,
        pdf_path=caminho_pdf,
        pdf_carregado=True,
    )
    if nota.estado == EstadoNota.CONCLUIDA.value:
        nota.data_conclusao = agora()
    db.session.add(nota)
    db.session.flush()
    rotulo_estado = ESTADOS_LABEL.get(nota.estado, nota.estado)
    registrar(
        nota, f"Carregou a nota a partir de um PDF externo. Estado inicial: {rotulo_estado}.", utilizador
    )
    db.session.commit()
    return nota


def criar_nota(dados, itens, utilizador, posicao_assinatura=None):
    nota = NotaEntrega(
        numero_referencia=dados["numero_referencia"].strip(),
        data_emissao=dados["data_emissao"],
        funcionario=dados["funcionario"].strip(),
        email_funcionario=dados["email_funcionario"].strip().lower(),
        departamento=dados["departamento"].strip(),
        motivo=dados["motivo"],
        observacao=(dados.get("observacao") or "").strip() or None,
        origem_local=(dados.get("origem_local") or "Sede IT").strip(),
        local_emissao=(dados.get("local_emissao") or "Maputo").strip(),
        estado=EstadoNota.RASCUNHO.value,
        criado_por=utilizador.id,
    )
    db.session.add(nota)
    db.session.flush()
    _substituir_itens(nota, itens)
    _aplicar_assinatura_entregue(nota, utilizador, posicao_assinatura)
    registrar(nota, "Criou a nota de entrega (rascunho).", utilizador)
    db.session.commit()
    return nota


def atualizar_nota(nota, dados, itens, utilizador, submeter=False, posicao_assinatura=None):
    _aplicar_dados(nota, dados)
    _substituir_itens(nota, itens)
    _aplicar_assinatura_entregue(nota, utilizador, posicao_assinatura)
    registrar(nota, "Atualizou os dados da nota.", utilizador)
    if submeter:
        _submeter(nota, utilizador)
    db.session.commit()
    return nota


# ---- submissão / aprovação / conclusão --------------------------------

def _submeter(nota, utilizador):
    if not nota.assinaturas_entrega_ok:
        raise ValueError(
            "A nota precisa da assinatura «Entregue Por» antes de ser "
            "submetida para aprovação."
        )
    nota.estado = EstadoNota.PENDENTE_APROVACAO.value
    nota.comentario_decisao = None
    nota.revisao_tecnico_id = None
    registrar(nota, "Submeteu a nota para aprovação.", utilizador)


def submeter_nota(nota, utilizador):
    _submeter(nota, utilizador)
    db.session.commit()


def aprovar_nota(nota, utilizador, comentario=None, posicao_assinatura=None):
    """O Aprovador assina «Autorizado por» em segundo lugar. A nota fica
    APROVADA e aguarda a assinatura de «Recebido» para ser concluída. A do
    Segurança é opcional e não bloqueia a conclusão."""
    nota.aprovado_por = utilizador.id
    nota.data_aprovacao = agora()
    nota.comentario_decisao = comentario or None
    if utilizador.assinatura_path:
        nota.assinatura_aprovador_path = utilizador.assinatura_path
    if posicao_assinatura:
        pos = enquadrar("aprovador", posicao_assinatura)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"assinatura_aprovador_{eixo}", pos[eixo])
    nota.estado = EstadoNota.APROVADA.value
    acao = "Aprovou e assinou «Autorizado por»."
    if comentario:
        acao += f" Comentário: {comentario}"
    registrar(nota, acao, utilizador)
    registrar(nota, "A aguardar a assinatura de «Recebido».", None)
    db.session.commit()


def rejeitar_nota(nota, utilizador, comentario=None):
    nota.estado = EstadoNota.REJEITADA.value
    nota.aprovado_por = utilizador.id
    nota.data_aprovacao = agora()
    nota.comentario_decisao = comentario or None
    acao = "Rejeitou a nota de entrega."
    if comentario:
        acao += f" Motivo: {comentario}"
    registrar(nota, acao, utilizador)
    db.session.commit()


def devolver_para_revisao(nota, utilizador, tecnico_id, motivo):
    tecnico = db.session.get(User, tecnico_id)
    if tecnico is None or not tecnico.ativo:
        raise ValueError("Técnico inválido.")
    if tecnico.perfil not in {Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value}:
        raise ValueError("Seleccione um técnico de informática.")
    nota.estado = EstadoNota.EM_REVISAO.value
    nota.revisao_tecnico_id = tecnico.id
    nota.comentario_decisao = motivo
    nota.aprovado_por = None
    nota.data_aprovacao = None
    nota.assinatura_aprovador_path = None
    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"assinatura_aprovador_{eixo}", None)
    registrar(nota, f"Devolveu a nota para revisão a {tecnico.nome}. Motivo: {motivo}", utilizador)
    db.session.commit()


# ---- assinaturas ------------------------------------------------------

def guardar_assinatura_papel(nota, papel, dataurl, utilizador, posicao=None):
    from app.utils.assinatura import guardar_dataurl_png, remover_ficheiro

    if papel not in PAPEIS_ASSINATURA:
        raise ValueError("Papel de assinatura inválido.")
    if papel == "entregue" and nota.estado not in {
        EstadoNota.RASCUNHO.value,
        EstadoNota.REJEITADA.value,
        EstadoNota.EM_REVISAO.value,
    }:
        raise ValueError("Já não é possível alterar esta assinatura.")
    if papel == "recebido" and nota.estado != EstadoNota.APROVADA.value:
        raise ValueError("A assinatura de «Recebido» só é recolhida depois da aprovação.")
    # A assinatura do Segurança é opcional: não tem restrição de ordem além
    # dos estados gerais já geridos por pode_gerir_assinaturas (ver rota).

    prefixo, rotulo = PAPEIS_ASSINATURA[papel]
    nome_fixo = f"sig_entrega_{nota.id}_{papel}.png"
    fname, erro = guardar_dataurl_png(dataurl, nome_fixo)
    if erro:
        raise ValueError(erro)

    anterior = getattr(nota, f"{prefixo}_path")
    setattr(nota, f"{prefixo}_path", fname)
    if posicao:
        pos = enquadrar(papel, posicao)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
    if anterior and anterior != fname:
        remover_ficheiro(anterior)

    registrar(nota, f"Recolheu a assinatura «{rotulo}».", utilizador)

    if papel == "seguranca":
        nota.seguranca_por = utilizador.id
        nota.data_seguranca = agora()
    if papel == "recebido" and nota.estado == EstadoNota.APROVADA.value:
        _concluir(nota, utilizador)
    db.session.commit()
    return fname


def _concluir(nota, utilizador):
    """A assinatura de «Recebido» é quem conclui a nota (a do Segurança é
    opcional e não faz parte deste gatilho)."""
    nota.estado = EstadoNota.CONCLUIDA.value
    nota.data_conclusao = agora()
    caminho = gerar_pdf_entrega(nota, current_app.config["PDF_FOLDER"])
    nota.pdf_path = caminho
    registrar(nota, "Nota de entrega concluída. PDF oficial gerado.", utilizador)


def remover_assinatura_papel(nota, papel, utilizador):
    from app.utils.assinatura import remover_ficheiro

    if papel not in PAPEIS_ASSINATURA:
        raise ValueError("Papel de assinatura inválido.")
    prefixo, rotulo = PAPEIS_ASSINATURA[papel]
    anterior = getattr(nota, f"{prefixo}_path")
    setattr(nota, f"{prefixo}_path", None)
    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"{prefixo}_{eixo}", None)
    if anterior:
        remover_ficheiro(anterior)
    if papel == "seguranca":
        nota.seguranca_por = None
        nota.data_seguranca = None
    registrar(nota, f"Removeu a assinatura «{rotulo}».", utilizador)
    db.session.commit()


def atualizar_posicao_assinatura(nota, papel, posicao, utilizador):
    if papel not in PAPEIS_ASSINATURA:
        raise ValueError("Papel de assinatura inválido.")
    prefixo, rotulo = PAPEIS_ASSINATURA[papel]
    if not getattr(nota, f"{prefixo}_path"):
        raise ValueError("Ainda não existe uma assinatura para posicionar.")
    if not isinstance(posicao, dict):
        raise ValueError("Posição de assinatura inválida.")
    for eixo in ("x", "y", "w", "h"):
        try:
            float(posicao.get(eixo))
        except (TypeError, ValueError):
            raise ValueError("Posição de assinatura inválida.")
    pos = enquadrar(papel, posicao)
    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
    registrar(nota, f"Reposicionou a assinatura «{rotulo}».", utilizador)
    db.session.commit()


# ---- consultas ------------------------------------------------------

def apagar_nota(nota):
    from app.utils.assinatura import remover_ficheiro

    if nota.pdf_path:
        remover_ficheiro(nota.pdf_path)
    for nome in (
        nota.assinatura_entregue_path,
        nota.assinatura_recebido_path,
        nota.assinatura_seguranca_path,
        nota.assinatura_aprovador_path,
    ):
        if nome and nome.startswith("sig_entrega_"):
            remover_ficheiro(nome)
    from app.services import campos_dinamicos_service

    campos_dinamicos_service.apagar_valores("entrega", nota.id)
    db.session.delete(nota)
    db.session.commit()


def garantir_pdf(nota):
    caminho = gerar_pdf_entrega(nota, current_app.config["PDF_FOLDER"])
    nota.pdf_path = caminho
    db.session.commit()
    return caminho


def choices_tecnicos():
    """Técnicos elegíveis para revisão. O Administrador gere a plataforma e
    não interage com notas, por isso não entra nesta lista."""
    tecnicos = (
        User.query.filter(
            User.ativo.is_(True),
            User.perfil.in_([Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value]),
        )
        .order_by(User.nome.asc())
        .all()
    )
    return [(0, "Seleccione o técnico")] + [(u.id, f"{u.nome} — {u.username}") for u in tecnicos]


def estatisticas(query_base=None):
    consulta = query_base if query_base is not None else NotaEntrega.query

    def _c(**kw):
        try:
            return consulta.filter_by(**kw).count()
        except Exception:
            db.session.rollback()
            return 0

    return {
        "total": (consulta.count() if hasattr(consulta, "count") else 0),
        "rascunho": _c(estado=EstadoNota.RASCUNHO.value),
        "pendentes": _c(estado=EstadoNota.PENDENTE_APROVACAO.value),
        "em_revisao": _c(estado=EstadoNota.EM_REVISAO.value),
        "aprovadas": _c(estado=EstadoNota.APROVADA.value),
        "rejeitadas": _c(estado=EstadoNota.REJEITADA.value),
        "concluidas": _c(estado=EstadoNota.CONCLUIDA.value),
    }


def pesquisar(query_base, referencia=None, colaborador=None, estado=None, data_inicio=None, data_fim=None):
    consulta = query_base
    if referencia:
        consulta = consulta.filter(NotaEntrega.numero_referencia.ilike(f"%{referencia.strip()}%"))
    if colaborador:
        termo = f"%{colaborador.strip()}%"
        consulta = consulta.filter(
            or_(NotaEntrega.funcionario.ilike(termo), NotaEntrega.email_funcionario.ilike(termo))
        )
    if estado:
        consulta = consulta.filter(NotaEntrega.estado == estado)
    if data_inicio:
        consulta = consulta.filter(NotaEntrega.data_emissao >= data_inicio)
    if data_fim:
        consulta = consulta.filter(NotaEntrega.data_emissao <= data_fim)
    return consulta.order_by(NotaEntrega.data_criacao.desc())
