"""Regras de negócio da Nota de Saída."""

import os
from datetime import datetime

from flask import current_app
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models.item import ItemNota
from app.models.nota import NotaSaida
from app.repositories.notas import MongoNotaRepository, _NotaMongoAdapter
from app.services import historico_service
from app.services.pdf_service import gerar_pdf
from app.utils.constants import ESTADOS_LABEL, EstadoNota, Perfil
from app.utils.tempo import agora


def _mongo_notas_ativo() -> bool:
    """Activa a gravação de notas em Mongo por flag explícita, sem quebrar o app."""
    if os.environ.get("USE_MONGO_NOTAS", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    try:
        from app.repositories.base import get_db
        db_conn = get_db()
        return db_conn is not None
    except Exception:
        return False


def _criar_nota_mongo(dados, itens, utilizador, submeter=False, posicao_assinatura=None):
    """Cria uma nota em Mongo, espelhando exatamente o fluxo SQLAlchemy."""
    repo = MongoNotaRepository()
    nota = repo.criar(
        numero_referencia=dados["numero_referencia"].strip(),
        data_emissao=dados["data_emissao"],
        funcionario=dados["funcionario"].strip(),
        email_funcionario=dados["email_funcionario"].strip().lower(),
        departamento=dados["departamento"].strip(),
        motivo=dados["motivo"],
        observacao=(dados.get("observacao") or "").strip() or None,
        origem_local=(dados.get("origem_local") or "Sede IT").strip(),
        local_emissao=(dados.get("local_emissao") or "Maputo").strip(),
        criado_por=utilizador.id,
        criador_nome=utilizador.nome,
        criador_username=getattr(utilizador, "username", None),
        itens=itens,
        estado=EstadoNota.RASCUNHO.value,
    )
    _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao_assinatura)
    nota = repo.obter_por_id(nota.id)
    historico_service.registrar(nota, "Criou a nota de saída (rascunho).", utilizador)
    if submeter:
        _submeter(nota, utilizador)
    return repo.obter_por_id(nota.id)


def _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao=None):
    """Equivalente Mongo de aplicar_assinatura_entregue (ver mais abaixo)."""
    from app.utils.assinatura_zonas import enquadrar

    if utilizador.assinatura_path and not nota.assinatura_entregue_path:
        pos = enquadrar("entregue", posicao) if posicao else None
        repo.definir_assinatura(nota.id, "entregue", path=utilizador.assinatura_path, posicao=pos)
    elif posicao and nota.assinatura_entregue_path:
        pos = enquadrar("entregue", posicao)
        repo.definir_assinatura(nota.id, "entregue", posicao=pos)


def extrair_itens(formulario):
    """Lê as listas paralelas enviadas pelo formulário dinâmico de itens."""
    tipos = formulario.getlist("tipo_item")
    descricoes = formulario.getlist("descricao_item")
    series = formulario.getlist("numero_serie")
    quantidades = formulario.getlist("quantidade")

    saps = formulario.getlist("numero_sap")

    itens = []
    for i, tipo in enumerate(tipos):
        descricao = descricoes[i].strip() if i < len(descricoes) else ""
        serie = series[i].strip() if i < len(series) else ""
        sap = saps[i].strip() if i < len(saps) else ""
        try:
            quantidade = int(quantidades[i]) if i < len(quantidades) else 1
        except (TypeError, ValueError):
            quantidade = 1
        if not descricao:
            continue
        itens.append(
            {
                "tipo_item": tipo or "Outro",
                "descricao": descricao,
                "numero_serie": serie or None,
                "numero_sap": sap or None,
                "quantidade": max(quantidade, 1),
            }
        )
    return itens


def substituir_itens(nota, itens):
    nota.itens.clear()
    db.session.flush()
    for dados in itens:
        nota.itens.append(ItemNota(**dados))


def aplicar_assinatura_entregue(nota, utilizador, posicao=None):
    """Copia a PNG reutilizável do técnico e a posição escolhida no preview.

    Não apaga uma assinatura «Entregue Por» já recolhida (ex.: na signature pad).
    A posição é sempre enquadrada na área «Entregue Por» do documento.
    """
    from app.utils.assinatura_zonas import enquadrar

    if utilizador.assinatura_path:
        nota.assinatura_entregue_path = utilizador.assinatura_path
    if posicao:
        pos = enquadrar("entregue", posicao)
        nota.assinatura_entregue_x = pos["x"]
        nota.assinatura_entregue_y = pos["y"]
        nota.assinatura_entregue_w = pos["w"]
        nota.assinatura_entregue_h = pos["h"]


def criar_nota(dados, itens, utilizador, submeter=False, posicao_assinatura=None):
    if _mongo_notas_ativo():
        return _criar_nota_mongo(dados, itens, utilizador, submeter=submeter, posicao_assinatura=posicao_assinatura)

    nota = NotaSaida(
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
    substituir_itens(nota, itens)
    aplicar_assinatura_entregue(nota, utilizador, posicao_assinatura)
    historico_service.registrar(nota, "Criou a nota de saída (rascunho).", utilizador)
    if submeter:
        _submeter(nota, utilizador)
    db.session.commit()
    return nota


def carregar_nota(dados, ficheiro, utilizador):
    """Regista uma Nota de Saída já existente (documento externo, ex.: nota
    antiga digitalizada) diretamente na listagem, sem o fluxo normal de
    criação/itens/assinaturas. O PDF enviado é guardado tal como está e
    nunca é substituído (ver `pdf_carregado` e a rota de download)."""
    from app.utils.uploads import guardar_pdf_upload

    caminho_pdf, erro = guardar_pdf_upload(ficheiro)
    if erro:
        raise ValueError(erro)

    if _mongo_notas_ativo():
        repo = MongoNotaRepository()
        nota = repo.criar(
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
        )
        conclusao = agora() if dados["estado"] == EstadoNota.CONCLUIDA.value else None
        repo.definir_pdf(nota.id, caminho_pdf, carregado=True)
        if conclusao:
            repo.col.update_one({"_id": nota._oid}, {"$set": {"data_conclusao": conclusao}})
        rotulo_estado = ESTADOS_LABEL.get(dados["estado"], dados["estado"])
        historico_service.registrar(
            nota, f"Carregou a nota a partir de um PDF externo. Estado inicial: {rotulo_estado}.", utilizador
        )
        return repo.obter_por_id(nota.id)

    nota = NotaSaida(
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
    historico_service.registrar(
        nota, f"Carregou a nota a partir de um PDF externo. Estado inicial: {rotulo_estado}.", utilizador
    )
    db.session.commit()
    return nota


def atualizar_nota(nota, dados, itens, utilizador, submeter=False, posicao_assinatura=None):
    if isinstance(nota, _NotaMongoAdapter):
        repo = MongoNotaRepository()
        repo.atualizar_dados(
            nota.id,
            numero_referencia=dados["numero_referencia"],
            data_emissao=dados["data_emissao"],
            funcionario=dados["funcionario"],
            email_funcionario=dados["email_funcionario"],
            departamento=dados["departamento"],
            motivo=dados["motivo"],
            observacao=dados.get("observacao"),
            origem_local=dados.get("origem_local"),
            local_emissao=dados.get("local_emissao"),
            itens=itens,
        )
        _aplicar_assinatura_entregue_mongo(repo, nota, utilizador, posicao_assinatura)
        historico_service.registrar(nota, "Atualizou os dados da nota.", utilizador)
        if submeter:
            _submeter(nota, utilizador)
        return repo.obter_por_id(nota.id)

    nota.numero_referencia = dados["numero_referencia"].strip()
    nota.data_emissao = dados["data_emissao"]
    nota.funcionario = dados["funcionario"].strip()
    nota.email_funcionario = dados["email_funcionario"].strip().lower()
    nota.departamento = dados["departamento"].strip()
    nota.motivo = dados["motivo"]
    nota.observacao = (dados.get("observacao") or "").strip() or None
    nota.origem_local = (dados.get("origem_local") or "Sede IT").strip()
    nota.local_emissao = (dados.get("local_emissao") or "Maputo").strip()
    substituir_itens(nota, itens)
    aplicar_assinatura_entregue(nota, utilizador, posicao_assinatura)
    historico_service.registrar(nota, "Atualizou os dados da nota.", utilizador)
    if submeter:
        _submeter(nota, utilizador)
    db.session.commit()
    return nota


def _submeter(nota, utilizador):
    if not nota.assinaturas_entrega_ok:
        raise ValueError(
            "A nota precisa da assinatura «Entregue Por» antes de ser "
            "submetida para aprovação."
        )
    if isinstance(nota, _NotaMongoAdapter):
        MongoNotaRepository().submeter(nota.id)
        nota.estado = EstadoNota.PENDENTE_APROVACAO.value
        nota.comentario_decisao = None
        nota.revisao_tecnico_id = None
        historico_service.registrar(nota, "Submeteu a nota para aprovação.", utilizador)
        return
    nota.estado = EstadoNota.PENDENTE_APROVACAO.value
    nota.comentario_decisao = None
    nota.revisao_tecnico_id = None
    historico_service.registrar(nota, "Submeteu a nota para aprovação.", utilizador)


def submeter_nota(nota, utilizador):
    _submeter(nota, utilizador)
    if not isinstance(nota, _NotaMongoAdapter):
        db.session.commit()


def aprovar_nota(nota, utilizador, comentario=None, posicao_assinatura=None):
    """O aprovador assina em segundo lugar: a nota fica APROVADA e aguarda a
    assinatura de «Recebido» (recetor) para ser concluída."""
    if isinstance(nota, _NotaMongoAdapter):
        repo = MongoNotaRepository()
        pos = None
        if posicao_assinatura:
            from app.utils.assinatura_zonas import enquadrar
            pos = enquadrar("aprovador", posicao_assinatura)
        if utilizador.assinatura_path:
            repo.definir_assinatura(nota.id, "aprovador", path=utilizador.assinatura_path, posicao=pos)
            nota.assinatura_aprovador_path = utilizador.assinatura_path
        elif pos:
            repo.definir_assinatura(nota.id, "aprovador", posicao=pos)
        if pos:
            nota.assinatura_aprovador_x = pos["x"]
            nota.assinatura_aprovador_y = pos["y"]
            nota.assinatura_aprovador_w = pos["w"]
            nota.assinatura_aprovador_h = pos["h"]
        repo.aprovar(nota.id, aprovado_por=utilizador.id, comentario=comentario,
                     aprovador_nome=utilizador.nome, aprovador_username=getattr(utilizador, "username", None))
        nota.aprovado_por = utilizador.id
        from app.repositories.notas import _PessoaRefMongo
        nota.aprovador = _PessoaRefMongo(utilizador.id, getattr(utilizador, "username", None), utilizador.nome)
        nota.data_aprovacao = agora()
        nota.comentario_decisao = comentario or None
        nota.estado = EstadoNota.APROVADA.value
        acao = "Aprovou e assinou a nota de saída."
        if comentario:
            acao += f" Comentário: {comentario}"
        historico_service.registrar(nota, acao, utilizador)
        historico_service.registrar(nota, "A aguardar a assinatura de «Recebido».", None)
        return

    agora_dt = agora()
    nota.aprovado_por = utilizador.id
    nota.data_aprovacao = agora_dt
    nota.comentario_decisao = comentario or None
    if utilizador.assinatura_path:
        nota.assinatura_aprovador_path = utilizador.assinatura_path
    if posicao_assinatura:
        from app.utils.assinatura_zonas import enquadrar

        pos = enquadrar("aprovador", posicao_assinatura)
        nota.assinatura_aprovador_x = pos["x"]
        nota.assinatura_aprovador_y = pos["y"]
        nota.assinatura_aprovador_w = pos["w"]
        nota.assinatura_aprovador_h = pos["h"]
    acao = "Aprovou e assinou a nota de saída."
    if comentario:
        acao += f" Comentário: {comentario}"
    historico_service.registrar(nota, acao, utilizador)

    nota.estado = EstadoNota.APROVADA.value
    historico_service.registrar(nota, "A aguardar a assinatura de «Recebido».", None)
    db.session.commit()


def _concluir(nota, utilizador):
    """A assinatura de «Recebido» é a última do fluxo: conclui a nota e gera o PDF."""
    if isinstance(nota, _NotaMongoAdapter):
        agora_dt = agora()
        caminho = gerar_pdf(nota, current_app.config["PDF_FOLDER"])
        MongoNotaRepository().concluir(nota.id, pdf_path=caminho)
        nota.estado = EstadoNota.CONCLUIDA.value
        nota.data_conclusao = agora_dt
        nota.pdf_path = caminho
        historico_service.registrar(
            nota, "Nota concluída. PDF oficial gerado automaticamente.", utilizador
        )
        return
    agora_dt = agora()
    nota.estado = EstadoNota.CONCLUIDA.value
    nota.data_conclusao = agora_dt
    caminho = gerar_pdf(nota, current_app.config["PDF_FOLDER"])
    nota.pdf_path = caminho
    historico_service.registrar(
        nota, "Nota concluída. PDF oficial gerado automaticamente.", utilizador
    )


PAPEIS_ASSINATURA = {
    "entregue": ("assinatura_entregue", "Entregue Por"),
    "recebido": ("assinatura_recebido", "Recebido"),
    "seguranca": ("assinatura_seguranca", "Segurança"),
}


def guardar_assinatura_papel(nota, papel, dataurl, utilizador, posicao=None):
    """Grava a PNG de uma assinatura recolhida na entrega (pad / canvas)."""
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

    prefixo, rotulo = PAPEIS_ASSINATURA[papel]

    nome_fixo = f"sig_nota_{nota.id}_{papel}.png"
    fname, erro = guardar_dataurl_png(dataurl, nome_fixo)
    if erro:
        raise ValueError(erro)

    anterior = getattr(nota, f"{prefixo}_path")

    if isinstance(nota, _NotaMongoAdapter):
        repo = MongoNotaRepository()
        pos = None
        if posicao:
            from app.utils.assinatura_zonas import enquadrar
            pos = enquadrar(papel, posicao)
        repo.definir_assinatura(nota.id, papel, path=fname, posicao=pos)
        setattr(nota, f"{prefixo}_path", fname)
        if pos:
            for eixo in ("x", "y", "w", "h"):
                setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
        if anterior and anterior != fname:
            remover_ficheiro(anterior)
        historico_service.registrar(nota, f"Recolheu a assinatura «{rotulo}».", utilizador)
        if papel == "recebido" and nota.estado == EstadoNota.APROVADA.value:
            _concluir(nota, utilizador)
        return fname

    setattr(nota, f"{prefixo}_path", fname)
    if posicao:
        from app.utils.assinatura_zonas import enquadrar

        pos = enquadrar(papel, posicao)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
    if anterior and anterior != fname:
        remover_ficheiro(anterior)

    historico_service.registrar(nota, f"Recolheu a assinatura «{rotulo}».", utilizador)

    if papel == "recebido" and nota.estado == EstadoNota.APROVADA.value:
        _concluir(nota, utilizador)
    db.session.commit()
    return fname


def remover_assinatura_papel(nota, papel, utilizador):
    from app.utils.assinatura import remover_ficheiro

    if papel not in PAPEIS_ASSINATURA:
        raise ValueError("Papel de assinatura inválido.")
    prefixo, rotulo = PAPEIS_ASSINATURA[papel]
    anterior = getattr(nota, f"{prefixo}_path")

    if isinstance(nota, _NotaMongoAdapter):
        MongoNotaRepository().definir_assinatura(nota.id, papel, limpar=True)
        setattr(nota, f"{prefixo}_path", None)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", None)
        if anterior:
            remover_ficheiro(anterior)
        historico_service.registrar(nota, f"Removeu a assinatura «{rotulo}».", utilizador)
        return

    setattr(nota, f"{prefixo}_path", None)
    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"{prefixo}_{eixo}", None)
    if anterior:
        remover_ficheiro(anterior)
    historico_service.registrar(nota, f"Removeu a assinatura «{rotulo}».", utilizador)
    db.session.commit()


def atualizar_posicao_assinatura(nota, papel, posicao, utilizador):
    """Atualiza apenas a posição/escala de uma assinatura já recolhida."""
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

    from app.utils.assinatura_zonas import enquadrar

    pos = enquadrar(papel, posicao)

    if isinstance(nota, _NotaMongoAdapter):
        MongoNotaRepository().definir_assinatura(nota.id, papel, posicao=pos)
        for eixo in ("x", "y", "w", "h"):
            setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
        historico_service.registrar(nota, f"Reposicionou a assinatura «{rotulo}».", utilizador)
        return

    for eixo in ("x", "y", "w", "h"):
        setattr(nota, f"{prefixo}_{eixo}", pos[eixo])
    historico_service.registrar(nota, f"Reposicionou a assinatura «{rotulo}».", utilizador)
    db.session.commit()


def apagar_nota(nota):
    """Apaga uma nota e apenas os ficheiros de assinatura/PDF pertencentes à nota."""
    from app.utils.assinatura import remover_ficheiro

    if isinstance(nota, _NotaMongoAdapter):
        for caminho in (getattr(nota, "pdf_path", None),):
            if caminho:
                remover_ficheiro(caminho)
        for nome in (
            nota.assinatura_entregue_path,
            nota.assinatura_recebido_path,
            nota.assinatura_seguranca_path,
            nota.assinatura_aprovador_path,
        ):
            if nome and nome.startswith("sig_nota_"):
                remover_ficheiro(nome)
        return MongoNotaRepository().apagar(nota.id)

    for caminho in (nota.pdf_path,):
        if caminho:
            remover_ficheiro(caminho)
    for nome in (
        nota.assinatura_entregue_path,
        nota.assinatura_recebido_path,
        nota.assinatura_seguranca_path,
        nota.assinatura_aprovador_path,
    ):
        if nome and nome.startswith("sig_nota_"):
            remover_ficheiro(nome)
    from app.services import campos_dinamicos_service

    campos_dinamicos_service.apagar_valores("saida", nota.id)
    db.session.delete(nota)
    db.session.commit()
    return True


def rejeitar_nota(nota, utilizador, comentario=None):
    acao = "Rejeitou a nota de saída."
    if comentario:
        acao += f" Motivo: {comentario}"

    if isinstance(nota, _NotaMongoAdapter):
        MongoNotaRepository().rejeitar(nota.id, aprovado_por=utilizador.id, comentario=comentario,
                                        aprovador_nome=utilizador.nome, aprovador_username=getattr(utilizador, "username", None))
        nota.estado = EstadoNota.REJEITADA.value
        nota.aprovado_por = utilizador.id
        from app.repositories.notas import _PessoaRefMongo
        nota.aprovador = _PessoaRefMongo(utilizador.id, getattr(utilizador, "username", None), utilizador.nome)
        nota.data_aprovacao = agora()
        nota.comentario_decisao = comentario or None
        historico_service.registrar(nota, acao, utilizador)
        return

    nota.estado = EstadoNota.REJEITADA.value
    nota.aprovado_por = utilizador.id
    nota.data_aprovacao = agora()
    nota.comentario_decisao = comentario or None
    historico_service.registrar(nota, acao, utilizador)
    db.session.commit()


def _obter_tecnico_valido(tecnico_id):
    """Devolve o técnico (SQL ou Mongo, conforme USE_MONGO_USERS) se for válido."""
    if os.environ.get("USE_MONGO_USERS", "0").strip().lower() in {"1", "true", "yes", "on"}:
        from app.repositories.users import UserRepository

        tecnico = UserRepository().get(tecnico_id)
    else:
        from app.models.user import User

        tecnico = db.session.get(User, tecnico_id)
    if tecnico is None or not tecnico.ativo:
        raise ValueError("Técnico inválido.")
    if tecnico.perfil not in {Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value}:
        raise ValueError("Seleccione um técnico de informática.")
    return tecnico


def devolver_para_revisao(nota, utilizador, tecnico_id, motivo):
    """Devolve a nota a um técnico concreto para correção."""
    tecnico = _obter_tecnico_valido(tecnico_id)
    acao = f"Devolveu a nota para revisão a {tecnico.nome}. Motivo: {motivo}"

    if isinstance(nota, _NotaMongoAdapter):
        MongoNotaRepository().devolver_para_revisao(
            nota.id, tecnico_id=tecnico.id, motivo=motivo,
            tecnico_nome=tecnico.nome, tecnico_username=getattr(tecnico, "username", None),
        )
        nota.estado = EstadoNota.EM_REVISAO.value
        nota.revisao_tecnico_id = tecnico.id
        from app.repositories.notas import _PessoaRefMongo
        nota.revisao_tecnico = _PessoaRefMongo(tecnico.id, getattr(tecnico, "username", None), tecnico.nome)
        nota.comentario_decisao = motivo
        nota.aprovado_por = None
        nota.aprovador = _PessoaRefMongo()
        nota.data_aprovacao = None
        nota.assinatura_aprovador_path = None
        nota.assinatura_aprovador_x = None
        nota.assinatura_aprovador_y = None
        nota.assinatura_aprovador_w = None
        nota.assinatura_aprovador_h = None
        historico_service.registrar(nota, acao, utilizador)
        return

    nota.estado = EstadoNota.EM_REVISAO.value
    nota.revisao_tecnico_id = tecnico.id
    nota.comentario_decisao = motivo
    nota.aprovado_por = None
    nota.data_aprovacao = None
    nota.assinatura_aprovador_path = None
    nota.assinatura_aprovador_x = None
    nota.assinatura_aprovador_y = None
    nota.assinatura_aprovador_w = None
    nota.assinatura_aprovador_h = None
    historico_service.registrar(nota, acao, utilizador)
    db.session.commit()



def listar_tecnicos_ativos():
    """Técnicos elegíveis para revisão. O Administrador gere a plataforma e
    não interage com notas, por isso não entra nesta lista."""
    from app.models.user import User

    return (
        User.query.filter(
            User.ativo.is_(True),
            User.perfil.in_([Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value]),
        )
        .order_by(User.nome.asc())
        .all()
    )


def choices_tecnicos():
    return [(0, "Seleccione o técnico")] + [
        (u.id, f"{u.nome} — {u.username}") for u in listar_tecnicos_ativos()
    ]


def garantir_pdf(nota):
    """Regenera sempre o PDF para refletir o layout institucional atual."""
    caminho = gerar_pdf(nota, current_app.config["PDF_FOLDER"])
    nota.pdf_path = caminho
    db.session.commit()
    return caminho


def pesquisar(query_base, referencia=None, colaborador=None, estado=None, data_inicio=None, data_fim=None):
    consulta = query_base
    if referencia:
        consulta = consulta.filter(
            NotaSaida.numero_referencia.ilike(f"%{referencia.strip()}%")
        )
    if colaborador:
        termo = f"%{colaborador.strip()}%"
        consulta = consulta.filter(
            or_(
                NotaSaida.funcionario.ilike(termo),
                NotaSaida.email_funcionario.ilike(termo),
            )
        )
    if estado:
        consulta = consulta.filter(NotaSaida.estado == estado)
    if data_inicio:
        consulta = consulta.filter(NotaSaida.data_emissao >= data_inicio)
    if data_fim:
        consulta = consulta.filter(NotaSaida.data_emissao <= data_fim)
    return consulta.order_by(NotaSaida.data_criacao.desc())


def estatisticas(query_base=None):
    consulta = query_base if query_base is not None else NotaSaida.query
    def _safe_count(q):
        try:
            return q.count()
        except OperationalError:
            # Tentativa de remediar schema faltante em SQLite e re-tentar
            try:
                _apply_sqlite_signature_alterations()
            except Exception:
                # se não conseguir aplicar, repassar o erro original
                raise
            return q.count()

    return {
        "total": _safe_count(consulta),
        "rascunho": _safe_count(consulta.filter_by(estado=EstadoNota.RASCUNHO.value)),
        "pendentes": _safe_count(consulta.filter_by(estado=EstadoNota.PENDENTE_APROVACAO.value)),
        "em_revisao": _safe_count(consulta.filter_by(estado=EstadoNota.EM_REVISAO.value)),
        "rejeitadas": _safe_count(consulta.filter_by(estado=EstadoNota.REJEITADA.value)),
        # Depois do Aprovador assinar, a nota fica «aprovada» a aguardar a
        # assinatura de «Recebido» — só nesse momento passa a «concluída».
        "aprovadas": _safe_count(consulta.filter_by(estado=EstadoNota.APROVADA.value)),
        "concluidas": _safe_count(consulta.filter_by(estado=EstadoNota.CONCLUIDA.value)),
    }


def pesquisar_mongo(filtro_base, referencia=None, colaborador=None, estado=None, data_inicio=None, data_fim=None):
    """Equivalente Mongo de pesquisar(): filtro_base é um dict (ex.: o que
    _consulta_listagem_mongo() devolve consoante o perfil), devolve uma
    lista de _NotaMongoAdapter (já ordenada, mais recente primeiro)."""
    import re

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
            intervalo["$gte"] = _mongo_to_utc_data(data_inicio)
        if data_fim:
            intervalo["$lte"] = _mongo_to_utc_data(data_fim)
        filtro["data_emissao"] = intervalo
    return MongoNotaRepository().listar(filtro)


def _mongo_to_utc_data(valor):
    from datetime import datetime, timezone

    if isinstance(valor, datetime):
        return valor.replace(tzinfo=valor.tzinfo or timezone.utc)
    return datetime.combine(valor, datetime.min.time()).replace(tzinfo=timezone.utc)


def estatisticas_mongo(filtro_base=None):
    """Equivalente Mongo de estatisticas(), a partir do mesmo repositório
    usado para o dashboard."""
    filtro = dict(filtro_base or {})
    contar = lambda extra: MongoNotaRepository().contar({**filtro, **extra})
    return {
        "total": contar({}),
        "rascunho": contar({"estado": EstadoNota.RASCUNHO.value}),
        "pendentes": contar({"estado": EstadoNota.PENDENTE_APROVACAO.value}),
        "em_revisao": contar({"estado": EstadoNota.EM_REVISAO.value}),
        "rejeitadas": contar({"estado": EstadoNota.REJEITADA.value}),
        "aprovadas": contar({"estado": EstadoNota.APROVADA.value}),
        "concluidas": contar({"estado": EstadoNota.CONCLUIDA.value}),
    }


def _apply_sqlite_signature_alterations():
    """Aplica ALTER TABLE para adicionar colunas de assinatura se estivermos a usar SQLite.

    Destinado a ser um fallback em ambiente de desenvolvimento para corrigir schema
    quando as migrações não foram aplicadas.
    """
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if not uri.startswith("sqlite"):
        return
    db_path = uri.replace("sqlite:///", "").replace("/", os.sep)
    import sqlite3, os

    if not os.path.exists(db_path):
        return
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    def has_column(table, column):
        cur.execute(f"PRAGMA table_info('{table}')")
        cols = [row[1] for row in cur.fetchall()]
        return column in cols

    changes = []
    if not has_column("users", "assinatura_path"):
        cur.execute("ALTER TABLE users ADD COLUMN assinatura_path VARCHAR(255)")
        changes.append("users.assinatura_path")
    if not has_column("users", "assinatura_reutilizavel"):
        cur.execute("ALTER TABLE users ADD COLUMN assinatura_reutilizavel BOOLEAN NOT NULL DEFAULT 0")
        changes.append("users.assinatura_reutilizavel")
    if not has_column("notas_saida", "assinatura_entregue_path"):
        cur.execute("ALTER TABLE notas_saida ADD COLUMN assinatura_entregue_path VARCHAR(255)")
        changes.append("notas_saida.assinatura_entregue_path")
    if not has_column("notas_saida", "assinatura_aprovador_path"):
        cur.execute("ALTER TABLE notas_saida ADD COLUMN assinatura_aprovador_path VARCHAR(255)")
        changes.append("notas_saida.assinatura_aprovador_path")
    if not has_column("notas_saida", "revisao_tecnico_id"):
        cur.execute("ALTER TABLE notas_saida ADD COLUMN revisao_tecnico_id INTEGER")
        changes.append("notas_saida.revisao_tecnico_id")
    # posição/escala
    for col in (
        'assinatura_entregue_x','assinatura_entregue_y','assinatura_entregue_w','assinatura_entregue_h',
        'assinatura_aprovador_x','assinatura_aprovador_y','assinatura_aprovador_w','assinatura_aprovador_h',
    ):
        if not has_column('notas_saida', col):
            cur.execute(f"ALTER TABLE notas_saida ADD COLUMN {col} FLOAT")
            changes.append(f"notas_saida.{col}")

    if changes:
        con.commit()
    con.close()
