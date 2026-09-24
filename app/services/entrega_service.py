"""Regras de negócio da Nota de Entrega.

Fluxo (igual ao da Nota de Saída):
    rascunho → (técnico recolhe «Entregue Por») → submeter
    → pendente_aprovacao → (Aprovador aprova e assina «Autorizado por»)
    → aprovada → (técnico recolhe «Recebido», que conclui a nota)
    → concluida (PDF gerado)

A assinatura do «Segurança» é opcional e pode ser recolhida a qualquer
momento antes da conclusão — não bloqueia nem a submissão nem a conclusão.

Tal como a Nota de Saída, suporta um caminho MongoDB paralelo, ligado
pela flag de ambiente USE_MONGO_ENTREGA (ver app/repositories/entrega.py).
"""

import os

from flask import current_app
from sqlalchemy import or_

from app.extensions import db
from app.models.historico_entrega import HistoricoEntrega
from app.models.item_entrega import ItemEntrega
from app.models.nota_entrega import NotaEntrega
from app.repositories.mongo_common import LOCAL_EMISSAO_OMISSAO, ORIGEM_LOCAL_OMISSAO
from app.repositories.entrega import MongoEntregaRepository, _NotaEntregaMongoAdapter
from app.repositories.mongo_common import PessoaRefMongo
from app.services.entrega_pdf import gerar_pdf_entrega
from app.utils.assinatura_zonas import enquadrar as _enquadrar
from app.utils.constants import ESTADOS_LABEL, EstadoNota
from app.utils.tempo import agora


def _mongo_entrega_ativo() -> bool:
    if os.environ.get("USE_MONGO_ENTREGA", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    try:
        from app.repositories.base import get_db
        return get_db() is not None
    except Exception:
        return False


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
    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().adicionar_historico(nota.id, nome, acao)
        return
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
    nota.origem_local = (dados.get("origem_local") or ORIGEM_LOCAL_OMISSAO).strip()
    nota.local_emissao = (dados.get("local_emissao") or "Maputo").strip()


def _aplicar_assinatura_entregue(nota, utilizador, posicao=None):
    if utilizador.assinatura_path:
        nota.assinatura_entregue_path = utilizador.assinatura_path
    if posicao:
        pos = enquadrar("entregue", posicao)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"assinatura_entregue_{eixo}", pos[eixo])


def _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao=None):
    if utilizador.assinatura_path and not nota.assinatura_entregue_path:
        pos = enquadrar("entregue", posicao) if posicao else None
        repo.definir_assinatura(nota.id, "entregue", path=utilizador.assinatura_path, posicao=pos)
    elif posicao and nota.assinatura_entregue_path:
        pos = enquadrar("entregue", posicao)
        repo.definir_assinatura(nota.id, "entregue", posicao=pos)


def carregar_nota(dados, ficheiro, utilizador):
    """Regista uma Nota de Entrega já existente (documento externo, ex.: nota
    antiga digitalizada) diretamente na listagem, sem o fluxo normal de
    criação/itens/assinaturas. O PDF enviado é guardado tal como está e
    nunca é substituído (ver `pdf_carregado` e a rota de download)."""
    from app.utils.uploads import guardar_pdf_upload

    caminho_pdf, erro = guardar_pdf_upload(ficheiro)
    if erro:
        raise ValueError(erro)

    if _mongo_entrega_ativo():
        repo = MongoEntregaRepository()
        nota = repo.criar(
            {
                "numero_referencia": dados["numero_referencia"],
                "data_emissao": dados["data_emissao"],
                "funcionario": dados["funcionario"],
                "email_funcionario": dados["email_funcionario"],
                "departamento": "N/A",
                "motivo": "Nota carregada manualmente",
                "origem_local": dados.get("origem_local"),
                "local_emissao": LOCAL_EMISSAO_OMISSAO,
            },
            criado_por=utilizador.id,
            criador_nome=utilizador.nome_exibicao,
            criador_username=getattr(utilizador, "username", None),
            estado=dados["estado"],
        )
        repo.definir_pdf(nota.id, caminho_pdf, carregado=True)
        if dados["estado"] == EstadoNota.CONCLUIDA.value:
            repo.col.update_one({"_id": nota._oid}, {"$set": {"data_conclusao": agora()}})
        rotulo_estado = ESTADOS_LABEL.get(dados["estado"], dados["estado"])
        registrar(nota, f"Carregou a nota a partir de um PDF externo. Estado inicial: {rotulo_estado}.", utilizador)
        return repo.obter_por_id(nota.id)

    nota = NotaEntrega(
        numero_referencia=dados["numero_referencia"].strip(),
        data_emissao=dados["data_emissao"],
        funcionario=dados["funcionario"].strip(),
        email_funcionario=dados["email_funcionario"].strip().lower(),
        departamento="N/A",
        motivo="Nota carregada manualmente",
        origem_local=(dados.get("origem_local") or ORIGEM_LOCAL_OMISSAO).strip(),
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
    if _mongo_entrega_ativo():
        repo = MongoEntregaRepository()
        nota = repo.criar(
            dados,
            criado_por=utilizador.id,
            criador_nome=utilizador.nome_exibicao,
            criador_username=getattr(utilizador, "username", None),
            itens=itens,
            estado=EstadoNota.RASCUNHO.value,
        )
        _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao_assinatura)
        nota = repo.obter_por_id(nota.id)
        registrar(nota, "Criou a nota de entrega (rascunho).", utilizador)
        return repo.obter_por_id(nota.id)

    nota = NotaEntrega(
        numero_referencia=dados["numero_referencia"].strip(),
        data_emissao=dados["data_emissao"],
        funcionario=dados["funcionario"].strip(),
        email_funcionario=dados["email_funcionario"].strip().lower(),
        departamento=dados["departamento"].strip(),
        motivo=dados["motivo"],
        observacao=(dados.get("observacao") or "").strip() or None,
        origem_local=(dados.get("origem_local") or ORIGEM_LOCAL_OMISSAO).strip(),
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


def atualizar_nota(nota, dados, itens, utilizador, submeter=False, posicao_assinatura=None,
                   aprovador_id=None):
    if isinstance(nota, _NotaEntregaMongoAdapter):
        repo = MongoEntregaRepository()
        repo.atualizar_dados(nota.id, dados, itens=itens)
        _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao_assinatura)
        registrar(nota, "Atualizou os dados da nota.", utilizador)
        if submeter:
            _submeter(nota, utilizador, aprovador_id)
        return repo.obter_por_id(nota.id)

    _aplicar_dados(nota, dados)
    _substituir_itens(nota, itens)
    _aplicar_assinatura_entregue(nota, utilizador, posicao_assinatura)
    registrar(nota, "Atualizou os dados da nota.", utilizador)
    if submeter:
        _submeter(nota, utilizador, aprovador_id)
    db.session.commit()
    return nota


# ---- submissão / aprovação / conclusão --------------------------------

def _resolver_aprovador(nota, aprovador_id):
    """Aprovador escolhido pelo técnico; sem escolha, reutiliza o da última
    submissão (ex.: ao resubmeter uma nota rejeitada)."""
    from app.services import fluxo_utilizadores

    escolhido = aprovador_id if aprovador_id not in (None, "", "0", 0) else None
    escolhido = escolhido or getattr(nota, "aprovador_designado_id", None)
    if not escolhido:
        raise ValueError("Seleccione o aprovador a quem enviar a nota.")
    return fluxo_utilizadores.obter_aprovador_valido(escolhido)


def _submeter(nota, utilizador, aprovador_id=None):
    if not nota.assinaturas_entrega_ok:
        raise ValueError(
            "A nota precisa da assinatura «Entregue Por» antes de ser "
            "submetida para aprovação."
        )
    aprovador = _resolver_aprovador(nota, aprovador_id)
    acao = f"Submeteu a nota para aprovação a {aprovador.nome_exibicao}."
    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().submeter(nota.id, aprovador=aprovador)
        nota.estado = EstadoNota.PENDENTE_APROVACAO.value
        nota.comentario_decisao = None
        nota.revisao_tecnico_id = None
        nota.aprovador_designado_id = aprovador.id
        nota.aprovador_designado = PessoaRefMongo(
            aprovador.id, getattr(aprovador, "username", None), aprovador.nome_exibicao
        )
        registrar(nota, acao, utilizador)
        return
    nota.estado = EstadoNota.PENDENTE_APROVACAO.value
    nota.comentario_decisao = None
    nota.revisao_tecnico_id = None
    nota.aprovador_designado_id = aprovador.id
    registrar(nota, acao, utilizador)


def submeter_nota(nota, utilizador, aprovador_id=None):
    _submeter(nota, utilizador, aprovador_id)
    if not isinstance(nota, _NotaEntregaMongoAdapter):
        db.session.commit()


def aprovar_nota(nota, utilizador, comentario=None, posicao_assinatura=None):
    """O Aprovador assina «Autorizado por» em segundo lugar. A nota fica
    APROVADA e aguarda a assinatura de «Recebido» para ser concluída. A do
    Segurança é opcional e não bloqueia a conclusão."""
    if isinstance(nota, _NotaEntregaMongoAdapter):
        repo = MongoEntregaRepository()
        pos = enquadrar("aprovador", posicao_assinatura) if posicao_assinatura else None
        if utilizador.assinatura_path:
            repo.definir_assinatura(nota.id, "aprovador", path=utilizador.assinatura_path, posicao=pos)
            nota.assinatura_aprovador_path = utilizador.assinatura_path
        elif pos:
            repo.definir_assinatura(nota.id, "aprovador", posicao=pos)
        if pos:
            for eixo in ("x", "y", "w", "h"):
                setattr(nota, f"assinatura_aprovador_{eixo}", pos[eixo])
        repo.aprovar(nota.id, aprovado_por=utilizador.id, comentario=comentario,
                     aprovador_nome=utilizador.nome_exibicao, aprovador_username=getattr(utilizador, "username", None))
        nota.aprovado_por = utilizador.id
        nota.aprovador = PessoaRefMongo(utilizador.id, getattr(utilizador, "username", None), utilizador.nome_exibicao)
        nota.data_aprovacao = agora()
        nota.comentario_decisao = comentario or None
        nota.estado = EstadoNota.APROVADA.value
        acao = "Aprovou e assinou «Autorizado por»."
        if comentario:
            acao += f" Comentário: {comentario}"
        registrar(nota, acao, utilizador)
        registrar(nota, "A aguardar a assinatura de «Recebido».", None)
        return

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


def rejeitar_nota(nota, utilizador, comentario=None, tecnico_id=None):
    """Única decisão negativa (substitui "Rejeitar" + "Devolver para revisão").

    O motivo é obrigatório. A nota fica REJEITADA e editável pelo criador e,
    se o Aprovador escolher outro técnico, também por esse técnico. A
    assinatura do Aprovador é limpa: volta a assinar se aprovar depois.
    """
    from app.services import fluxo_utilizadores

    comentario = (comentario or "").strip()
    if not comentario:
        raise ValueError("Indique o motivo da rejeição.")
    tecnico = None
    if tecnico_id not in (None, "", "0", 0):
        tecnico = fluxo_utilizadores.obter_tecnico_valido(tecnico_id)
    acao = f"Rejeitou a nota de entrega. Motivo: {comentario}"
    if tecnico and str(tecnico.id) != str(nota.criado_por):
        acao += f" — atribuída a {tecnico.nome_exibicao} para correção."

    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().rejeitar(
            nota.id, aprovado_por=utilizador.id, comentario=comentario,
            aprovador_nome=utilizador.nome_exibicao,
            aprovador_username=getattr(utilizador, "username", None),
            tecnico=tecnico,
        )
        nota.aprovado_por = utilizador.id
        nota.aprovador = PessoaRefMongo(utilizador.id, getattr(utilizador, "username", None), utilizador.nome_exibicao)
        nota.revisao_tecnico = PessoaRefMongo(
            *( (tecnico.id, getattr(tecnico, "username", None), tecnico.nome_exibicao) if tecnico else () )
        )
    else:
        nota.aprovado_por = utilizador.id
    nota.estado = EstadoNota.REJEITADA.value
    nota.data_aprovacao = agora()
    nota.comentario_decisao = comentario
    nota.revisao_tecnico_id = tecnico.id if tecnico else None
    nota.assinatura_aprovador_path = None
    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"assinatura_aprovador_{eixo}", None)
    registrar(nota, acao, utilizador)
    if not isinstance(nota, _NotaEntregaMongoAdapter):
        db.session.commit()


# ---- assinaturas ------------------------------------------------------

def _validar_papel_assinatura(nota, papel):
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


def _registar_seguranca(nota, utilizador, mongo):
    nota.seguranca_por = utilizador.id
    nota.data_seguranca = agora()
    if mongo:
        MongoEntregaRepository().definir_seguranca(
            nota.id,
            seguranca_por=utilizador.id,
            seguranca_nome=utilizador.nome_exibicao,
            seguranca_username=getattr(utilizador, "username", None),
        )
        nota.seguranca = PessoaRefMongo(utilizador.id, getattr(utilizador, "username", None), utilizador.nome_exibicao)


def guardar_assinatura_papel(nota, papel, dataurl, utilizador, posicao=None):
    from app.utils.assinatura import guardar_dataurl_png, remover_ficheiro

    _validar_papel_assinatura(nota, papel)
    prefixo, rotulo = PAPEIS_ASSINATURA[papel]
    nome_fixo = f"sig_entrega_{nota.id}_{papel}.png"
    fname, erro = guardar_dataurl_png(dataurl, nome_fixo)
    if erro:
        raise ValueError(erro)

    anterior = getattr(nota, f"{prefixo}_path")
    pos = enquadrar(papel, posicao) if posicao else None

    setattr(nota, f"{prefixo}_path", fname)
    if pos:
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", pos[eixo])

    mongo = isinstance(nota, _NotaEntregaMongoAdapter)
    if mongo:
        MongoEntregaRepository().definir_assinatura(nota.id, papel, path=fname, posicao=pos)
    if anterior and anterior != fname:
        remover_ficheiro(anterior)

    registrar(nota, f"Recolheu a assinatura «{rotulo}».", utilizador)

    if papel == "seguranca":
        _registar_seguranca(nota, utilizador, mongo)
    if papel == "recebido" and nota.estado == EstadoNota.APROVADA.value:
        _concluir(nota, utilizador)
    if not mongo:
        db.session.commit()
    return fname


def _concluir(nota, utilizador):
    """A assinatura de «Recebido» é quem conclui a nota (a do Segurança é
    opcional e não faz parte deste gatilho)."""
    if isinstance(nota, _NotaEntregaMongoAdapter):
        caminho = gerar_pdf_entrega(nota, current_app.config["PDF_FOLDER"])
        MongoEntregaRepository().concluir(nota.id, pdf_path=caminho)
        nota.estado = EstadoNota.CONCLUIDA.value
        nota.data_conclusao = agora()
        nota.pdf_path = caminho
        registrar(nota, "Nota de entrega concluída. PDF oficial gerado.", utilizador)
        return
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

    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().definir_assinatura(nota.id, papel, limpar=True)
        setattr(nota, f"{prefixo}_path", None)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", None)
        if anterior:
            remover_ficheiro(anterior)
        if papel == "seguranca":
            nota.seguranca_por = None
            nota.seguranca = PessoaRefMongo()
            nota.data_seguranca = None
        registrar(nota, f"Removeu a assinatura «{rotulo}».", utilizador)
        return

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

    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().definir_assinatura(nota.id, papel, posicao=pos)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
        registrar(nota, f"Reposicionou a assinatura «{rotulo}».", utilizador)
        return

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

    if isinstance(nota, _NotaEntregaMongoAdapter):
        return MongoEntregaRepository().apagar(nota.id)

    from app.services import campos_dinamicos_service

    campos_dinamicos_service.apagar_valores("entrega", nota.id)
    db.session.delete(nota)
    db.session.commit()
    return True


def garantir_pdf(nota):
    caminho = gerar_pdf_entrega(nota, current_app.config["PDF_FOLDER"])
    if isinstance(nota, _NotaEntregaMongoAdapter):
        MongoEntregaRepository().definir_pdf(nota.id, caminho, carregado=nota.pdf_carregado)
        nota.pdf_path = caminho
        return caminho
    nota.pdf_path = caminho
    db.session.commit()
    return caminho


def choices_tecnicos():
    """Técnicos elegíveis (dropdown da rejeição) — SQLite ou Mongo."""
    from app.services import fluxo_utilizadores

    return fluxo_utilizadores.choices_tecnicos()


def choices_aprovadores():
    """Aprovadores ativos (dropdown da submissão) — SQLite ou Mongo."""
    from app.services import fluxo_utilizadores

    return fluxo_utilizadores.choices_aprovadores()


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


def estatisticas_mongo(filtro_base=None):
    filtro = dict(filtro_base or {})
    contar = lambda extra: MongoEntregaRepository().contar({**filtro, **extra})
    return {
        "total": contar({}),
        "rascunho": contar({"estado": EstadoNota.RASCUNHO.value}),
        "pendentes": contar({"estado": EstadoNota.PENDENTE_APROVACAO.value}),
        "em_revisao": contar({"estado": EstadoNota.EM_REVISAO.value}),
        "aprovadas": contar({"estado": EstadoNota.APROVADA.value}),
        "rejeitadas": contar({"estado": EstadoNota.REJEITADA.value}),
        "concluidas": contar({"estado": EstadoNota.CONCLUIDA.value}),
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


def pesquisar_mongo(filtro_base, referencia=None, colaborador=None, estado=None, data_inicio=None, data_fim=None):
    import re
    from datetime import datetime, timezone

    filtro = dict(filtro_base or {})
    if referencia:
        filtro["numero_referencia"] = {"$regex": re.escape(referencia.strip()), "$options": "i"}
    if colaborador:
        termo = {"$regex": re.escape(colaborador.strip()), "$options": "i"}
        filtro["$or"] = [{"funcionario": termo}, {"email_funcionario": termo}]
    if estado:
        filtro["estado"] = estado
    if data_inicio or data_fim:
        intervalo = {}
        if data_inicio:
            intervalo["$gte"] = datetime.combine(data_inicio, datetime.min.time()).replace(tzinfo=timezone.utc)
        if data_fim:
            intervalo["$lte"] = datetime.combine(data_fim, datetime.min.time()).replace(tzinfo=timezone.utc)
        filtro["data_emissao"] = intervalo
    return MongoEntregaRepository().listar(filtro)
