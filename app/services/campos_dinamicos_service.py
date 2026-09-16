"""Gestão dos campos dinâmicos (adicionais) e dos seus valores por nota."""

from app.extensions import db
from app.models.campo_dinamico import CampoDinamico, ValorCampoDinamico


def listar_todos():
    return CampoDinamico.query.order_by(CampoDinamico.ordem.asc(), CampoDinamico.id.asc()).all()


def listar_aplicaveis(tipo_documento, apenas_ativos=True):
    """Campos que aparecem no formulário de criação/edição de `tipo_documento`
    (``"saida"`` ou ``"entrega"``)."""
    consulta = CampoDinamico.query
    if apenas_ativos:
        consulta = consulta.filter_by(ativo=True)
    coluna = CampoDinamico.aplica_saida if tipo_documento == "saida" else CampoDinamico.aplica_entrega
    consulta = consulta.filter(coluna.is_(True))
    return consulta.order_by(CampoDinamico.ordem.asc(), CampoDinamico.id.asc()).all()


def obter(campo_id):
    return db.session.get(CampoDinamico, campo_id)


def _aplicar_dados(campo, dados):
    campo.nome = dados["nome"].strip().lower()
    campo.rotulo = dados["rotulo"].strip()
    campo.tipo = dados["tipo"]
    campo.opcoes = (dados.get("opcoes") or "").strip() or None
    campo.aplica_saida = bool(dados.get("aplica_saida"))
    campo.aplica_entrega = bool(dados.get("aplica_entrega"))
    campo.obrigatorio = bool(dados.get("obrigatorio"))
    campo.ativo = bool(dados.get("ativo", True))
    campo.ordem = dados.get("ordem") or 0


def criar(dados, utilizador):
    campo = CampoDinamico(criado_por=utilizador.id if utilizador else None)
    _aplicar_dados(campo, dados)
    db.session.add(campo)
    db.session.commit()
    return campo


def atualizar(campo, dados):
    _aplicar_dados(campo, dados)
    db.session.commit()
    return campo


def tem_valores(campo):
    return (
        db.session.query(ValorCampoDinamico.id).filter_by(campo_id=campo.id).first()
        is not None
    )


def remover(campo):
    """Só apaga campos sem histórico. Com valores já preenchidos em notas
    existentes, o correto é desativar (`ativo=False`) para não os perder."""
    if tem_valores(campo):
        raise ValueError(
            "Este campo já tem valores preenchidos em notas existentes. "
            "Desative-o em vez de o eliminar, para não perder esse histórico."
        )
    db.session.delete(campo)
    db.session.commit()


def alternar_ativo(campo):
    campo.ativo = not campo.ativo
    db.session.commit()
    return campo


# ---- valores por documento -------------------------------------------------

def obter_valores(tipo_documento, documento_id):
    """``{campo_id: valor}`` já guardados nesta nota."""
    linhas = ValorCampoDinamico.query.filter_by(
        documento_tipo=tipo_documento, documento_id=documento_id
    ).all()
    return {linha.campo_id: linha.valor for linha in linhas}


def guardar_valores(tipo_documento, documento_id, respostas):
    """``respostas``: ``{campo_id: valor_string_ou_None}``. Só grava campos
    aplicáveis e ativos; remove a linha quando o valor fica vazio."""
    campos = {c.id: c for c in listar_aplicaveis(tipo_documento)}
    existentes = {
        linha.campo_id: linha
        for linha in ValorCampoDinamico.query.filter_by(
            documento_tipo=tipo_documento, documento_id=documento_id
        ).all()
    }
    for campo_id, campo in campos.items():
        bruto = respostas.get(campo_id)
        valor = ("1" if bruto else "") if campo.tipo == "checkbox" else (bruto or "").strip()
        linha = existentes.get(campo_id)
        if not valor:
            if linha:
                db.session.delete(linha)
            continue
        if linha:
            linha.valor = valor
        else:
            db.session.add(
                ValorCampoDinamico(
                    campo_id=campo_id,
                    documento_tipo=tipo_documento,
                    documento_id=documento_id,
                    valor=valor,
                )
            )
    db.session.commit()


def validar_obrigatorios(tipo_documento, respostas):
    """Rótulos dos campos obrigatórios que ficaram por preencher."""
    faltam = []
    for campo in listar_aplicaveis(tipo_documento):
        if not campo.obrigatorio or campo.tipo == "checkbox":
            continue
        if not (respostas.get(campo.id) or "").strip():
            faltam.append(campo.rotulo)
    return faltam


def valores_para_exibir(tipo_documento, documento_id):
    """``[(rótulo, valor_formatado)]`` para o detalhe da nota e o PDF.

    Inclui campos entretanto desativados, para preservar o histórico já
    impresso/guardado numa nota concreta.
    """
    linhas = (
        db.session.query(ValorCampoDinamico, CampoDinamico)
        .join(CampoDinamico, ValorCampoDinamico.campo_id == CampoDinamico.id)
        .filter(
            ValorCampoDinamico.documento_tipo == tipo_documento,
            ValorCampoDinamico.documento_id == documento_id,
        )
        .order_by(CampoDinamico.ordem.asc(), CampoDinamico.id.asc())
        .all()
    )
    resultado = []
    for valor_row, campo in linhas:
        texto = valor_row.valor or ""
        if campo.tipo == "checkbox":
            texto = "Sim" if texto == "1" else "Não"
        resultado.append((campo.rotulo, texto))
    return resultado


def apagar_valores(tipo_documento, documento_id):
    ValorCampoDinamico.query.filter_by(
        documento_tipo=tipo_documento, documento_id=documento_id
    ).delete()
    db.session.commit()
