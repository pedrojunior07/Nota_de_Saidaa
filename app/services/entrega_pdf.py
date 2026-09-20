"""Geração do PDF da Nota de Entrega (layout do exemplar DHL)."""

import os

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas

from app.models.configuracao import Configuracao
from app.services.pdf_service import ASSET_LOGO, _registar_fontes
from app.utils.assinatura_zonas import campos as _campos_assinatura
from app.utils.assinatura_zonas import enquadrar, largura_linha, posicao_padrao

LARGURA, ALTURA = A4
MARGEM_ESQ = 71
MARGEM_DIR = 526

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _numero_documento(nota):
    """Delega em nota.numero_documento — ver a nota equivalente em
    pdf_service.numero_documento() sobre porque não se pode formatar
    nota.id diretamente aqui (string no adaptador Mongo)."""
    return nota.numero_documento


def _cabecalho(c, fonte_b):
    if os.path.isfile(ASSET_LOGO):
        c.drawImage(ASSET_LOGO, MARGEM_ESQ, ALTURA - 78, width=48, height=48,
                    preserveAspectRatio=True, mask="auto")
    c.setFillColor(black)
    c.setFont(fonte_b, 15)
    c.drawString(MARGEM_ESQ + 66, ALTURA - 52, "Nota de Entrega — Direção de Informática")


def _wrap(c, texto, fonte, tamanho, largura_max):
    palavras = (texto or "").split()
    linhas, atual = [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if c.stringWidth(teste, fonte, tamanho) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas or [""]


def gerar_pdf_entrega(nota, pasta_pdf):
    os.makedirs(pasta_pdf, exist_ok=True)
    nome = f"nota_entrega_{_numero_documento(nota).replace('/', '-')}.pdf"
    caminho = os.path.join(pasta_pdf, nome)

    config = Configuracao.obter()
    fonte, fonte_b = _registar_fontes()

    c = pdfcanvas.Canvas(caminho, pagesize=A4)
    c.setTitle(f"Nota de Entrega {_numero_documento(nota)}")
    c.setAuthor(config.nome_instituicao)

    _cabecalho(c, fonte_b)

    y = ALTURA - 104
    c.setFont(fonte_b, 11)
    c.drawString(MARGEM_ESQ, y, f"No. Ref. {_numero_documento(nota)}")
    y -= 28

    # ---- DE / Att (caixa com borda, como no exemplar) ------------------
    caixa_topo = y + 14
    meio = MARGEM_ESQ + 250
    c.setFont(fonte_b, 10)
    c.drawString(MARGEM_ESQ + 6, y, "DE :")
    c.drawString(meio, y, "Att:")
    y -= 14
    c.setFont(fonte, 9.5)
    linhas_de = [
        config.nome_instituicao or "Standard Bank, Moçambique",
        config.morada or "Av. 10 de Novembro, n.º 420",
    ]
    if config.contacto:
        linhas_de.append(f"Tel: {config.contacto}")
    y_de = y
    for ln in linhas_de:
        c.drawString(MARGEM_ESQ + 16, y_de, ln)
        y_de -= 13
    c.setFont(fonte_b, 10)
    c.drawString(meio + 10, y, nota.funcionario)
    caixa_fundo = min(y_de, y - 13) - 8

    c.setStrokeColor(black)
    c.setLineWidth(0.9)
    c.rect(MARGEM_ESQ, caixa_fundo, MARGEM_DIR - MARGEM_ESQ, caixa_topo - caixa_fundo)
    c.line(meio - 10, caixa_topo, meio - 10, caixa_fundo)

    y = caixa_fundo - 18

    # ---- Assunto ------------------------------------------------------
    c.setFont(fonte_b, 11)
    c.drawString(MARGEM_ESQ, y, "ASSUNTO:   Nota de entrega")
    y -= 22
    c.setFont(fonte_b, 10)
    c.drawCentredString(LARGURA / 2, y, "Vimos pela presente proceder à entrega do seguinte material")
    y -= 22

    # ---- Tabela de itens: QTD. | DESTINO | DESCRIÇÃO -----------------
    col_qtd = MARGEM_ESQ
    col_dest = MARGEM_ESQ + 55
    col_desc = MARGEM_ESQ + 200
    topo = y
    c.setFont(fonte_b, 9.5)
    c.setStrokeColor(black)
    c.setLineWidth(0.8)
    c.line(MARGEM_ESQ, topo + 12, MARGEM_DIR, topo + 12)
    c.drawString(col_qtd, topo, "QTD.")
    c.drawString(col_dest, topo, "DESTINO")
    c.drawString(col_desc, topo, "DESCRIÇÃO")
    y = topo - 6
    c.line(MARGEM_ESQ, y, MARGEM_DIR, y)
    c.line(col_dest - 8, topo + 12, col_dest - 8, y)
    c.line(col_desc - 8, topo + 12, col_desc - 8, y)

    c.setFont(fonte, 9.5)
    for item in nota.itens:
        linhas_dest = _wrap(c, item.destino or "", fonte, 9.5, col_desc - col_dest - 12)
        linhas_desc = _wrap(c, item.descricao_impressa(), fonte, 9.5, MARGEM_DIR - col_desc)
        n = max(len(linhas_dest), len(linhas_desc), 1)
        y_linha = y - 14
        c.drawString(col_qtd + 4, y_linha, f"{item.quantidade:02d}")
        for i in range(n):
            yy = y_linha - i * 12
            if i < len(linhas_dest):
                c.drawString(col_dest, yy, linhas_dest[i])
            if i < len(linhas_desc):
                c.drawString(col_desc, yy, linhas_desc[i])
        y = y_linha - (n - 1) * 12 - 8
        c.setLineWidth(0.35)
        c.line(MARGEM_ESQ, y, MARGEM_DIR, y)
    c.setLineWidth(0.8)
    c.line(col_dest - 8, topo + 12, col_dest - 8, y)
    c.line(col_desc - 8, topo + 12, col_desc - 8, y)

    y -= 22
    c.setFont(fonte, 10)
    c.drawCentredString(LARGURA / 2, y, f"({(nota.motivo or 'Atribuição').strip()})")
    y -= 20
    if nota.observacao:
        for ln in _wrap(c, f"NB: {nota.observacao.strip()}", fonte, 10, MARGEM_DIR - MARGEM_ESQ):
            c.drawString(MARGEM_ESQ, y, ln)
            y -= 13
        y -= 6
    c.drawString(MARGEM_ESQ, y, f"Att: ({nota.email_funcionario})")
    y -= 20

    _desenhar_campos_adicionais(c, nota, fonte, fonte_b, y)

    _assinaturas(c, nota, fonte, fonte_b)

    data = nota.data_emissao
    if data:
        c.setFont(fonte, 10)
        c.drawCentredString(LARGURA / 2, 44,
                     f"{nota.local_emissao or 'Maputo'}, aos {data.day} de {MESES[data.month - 1]} de {data.year}")

    _rodape(c, config, fonte)
    c.save()
    return caminho


def _pt_y(pct):
    return ALTURA * (1 - pct / 100.0)


def _desenhar_campos_adicionais(c, nota, fonte, fonte_b, y, y_minimo=420):
    """Imprime os campos adicionais (definidos pelo Administrador) com valor
    preenchido, até ao limite de espaço livre acima do bloco de assinaturas."""
    from app.services import campos_dinamicos_service

    valores = campos_dinamicos_service.valores_para_exibir("entrega", nota.id)
    if not valores or y < y_minimo:
        return

    c.setFillColor(black)
    c.setFont(fonte_b, 9.5)
    c.drawString(MARGEM_ESQ, y, "Informações adicionais:")
    y -= 14
    c.setFont(fonte, 9)
    for rotulo, valor in valores:
        if y < y_minimo:
            break
        texto = f"{rotulo}: {valor or '—'}"
        c.drawString(MARGEM_ESQ + 8, y, texto[:110])
        y -= 12.5


def _assinaturas(c, nota, fonte, fonte_b):
    nomes = {
        "aprovador": nota.aprovador.nome if nota.aprovador else None,
        "entregue": nota.criador.nome if nota.criador else None,
        "recebido": nota.funcionario or None,
        "seguranca": nota.seguranca.nome if nota.seguranca else None,
    }
    meia = largura_linha("entrega") / 2
    for papel, campo in _campos_assinatura("entrega").items():
        cx = LARGURA * campo["cx"] / 100.0
        x0 = LARGURA * (campo["cx"] - meia) / 100.0
        x1 = LARGURA * (campo["cx"] + meia) / 100.0
        c.setFont(fonte_b, 10)
        c.setFillColor(black)
        c.drawCentredString(cx, _pt_y(campo["rotulo_y"]), campo["rotulo"])
        c.setStrokeColor(black)
        c.setLineWidth(0.9)
        c.setDash()
        c.line(x0, _pt_y(campo["linha_y"]), x1, _pt_y(campo["linha_y"]))
        if nomes[papel]:
            c.setFont(fonte, 9)
            c.drawCentredString(cx, _pt_y(campo["nome_y"]), nomes[papel])

    # PNG das assinaturas recolhidas
    for papel in ("aprovador", "entregue", "recebido", "seguranca"):
        _desenhar_png(c, nota, papel)


def _desenhar_png(c, nota, papel):
    from app.utils.assinatura import caminho_absoluto

    prefixo = f"assinatura_{papel}"
    ficheiro = caminho_absoluto(getattr(nota, f"{prefixo}_path"))
    if not ficheiro:
        return
    padrao = posicao_padrao(papel, "entrega")
    pos = enquadrar(papel, {
        eixo: (getattr(nota, f"{prefixo}_{eixo}") if getattr(nota, f"{prefixo}_{eixo}") is not None else padrao[eixo])
        for eixo in ("x", "y", "w", "h")
    }, tipo="entrega")
    largura = LARGURA * pos["w"] / 100.0
    altura = ALTURA * pos["h"] / 100.0
    x = LARGURA * pos["x"] / 100.0
    y = ALTURA - (ALTURA * pos["y"] / 100.0) - altura
    try:
        c.drawImage(ficheiro, x, y, width=largura, height=altura,
                    mask="auto", preserveAspectRatio=True, anchor="s")
    except Exception:
        pass


def _rodape(c, config, fonte):
    texto = (config.rodape_pdf or "").strip()
    if not texto:
        return
    y = 26
    c.setFont(fonte, 8)
    c.setFillColor(HexColor("#5B6572"))
    c.drawCentredString(LARGURA / 2, y, texto)
    c.setFillColor(black)
