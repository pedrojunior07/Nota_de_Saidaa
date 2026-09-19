"""Geração do PDF da Nota de Saída no formato do documento institucional."""

import os

from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from app.models.configuracao import Configuracao

LARGURA, ALTURA = A4
MARGEM_ESQ = 71
MARGEM_DIR = 526
ASSET_LOGO = os.path.join(
    os.path.dirname(__file__), "..", "static", "assets", "logo_std_stacked - Cropped.png"
)


def _registar_fontes():
    """Usa Times New Roman do Windows quando existir, senão Times do ReportLab."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    regular = os.path.join(windir, "Fonts", "times.ttf")
    negrito = os.path.join(windir, "Fonts", "timesbd.ttf")
    if os.path.isfile(regular) and os.path.isfile(negrito):
        try:
            pdfmetrics.getFont("TimesNewRoman")
        except KeyError:
            pdfmetrics.registerFont(TTFont("TimesNewRoman", regular))
            pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", negrito))
        return "TimesNewRoman", "TimesNewRoman-Bold"
    return "Times-Roman", "Times-Bold"


def numero_documento(nota):
    """Nr. Ref. no formato do exemplar: 000003/2026."""
    ano = nota.data_emissao.year if nota.data_emissao else 2026
    return f"{nota.id:06d}/{ano}"


def _linhas_item(item):
    """As 3 linhas impressas por item: descrição, depois Nr. de Série e SAP
    sempre explícitos (mostra "N/A" quando não aplicável), cada um na sua
    própria linha para nunca ficarem ambíguos ou difíceis de ler."""
    serie = item.numero_serie or "N/A"
    sap = item.numero_sap or "N/A"
    return (item.descricao or item.tipo_item), f"Nr. Série: {serie}", f"SAP: {sap}"


def _wrap(c, texto, fonte, tamanho, largura_max):
    """Quebra `texto` em linhas que cabem em `largura_max`, palavra a palavra."""
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


def _linha_com_tracos(c, x, y, texto, x_fim, fonte, tamanho=11):
    c.setFont(fonte, tamanho)
    c.setFillColor(black)
    c.drawString(x, y, texto)
    largura = c.stringWidth(texto + " ", fonte, tamanho)
    x0 = x + largura
    if x0 < x_fim:
        c.setStrokeColor(black)
        c.setDash(1.2, 1.4)
        c.setLineWidth(0.7)
        c.line(x0, y + 1, x_fim, y + 1)
        c.setDash()


def _cabecalho_banco(c):
    """Cabeçalho compacto: logótipo à esquerda e, ao seu lado direito, o título
    da nota — ambos ao mesmo nível vertical e com uma boa separação."""
    logo_x = MARGEM_ESQ
    logo_tam = 56
    logo_y = ALTURA - 82
    gap = 34                       # separação entre o logótipo e o texto
    titulo_x = MARGEM_ESQ

    if os.path.isfile(ASSET_LOGO):
        c.drawImage(
            ASSET_LOGO,
            logo_x,
            logo_y,
            width=logo_tam,
            height=logo_tam,
            preserveAspectRatio=True,
            mask="auto",
        )
        titulo_x = logo_x + logo_tam + gap

    c.setFillColor(black)
    tam_fonte = 18
    c.setFont("Times-Bold", tam_fonte)
    # linha de base do texto centrada verticalmente com o logótipo
    titulo_y = logo_y + logo_tam / 2 - tam_fonte * 0.34
    c.drawString(titulo_x, titulo_y, "Nota de Saida - Direção de Informática")


def gerar_pdf(nota, pasta_pdf):
    """Gera o PDF no layout do exemplar institucional (uma página A4)."""
    os.makedirs(pasta_pdf, exist_ok=True)
    nome_ficheiro = f"nota_saida_{numero_documento(nota).replace('/', '-')}.pdf"
    caminho = os.path.join(pasta_pdf, nome_ficheiro)

    config = Configuracao.obter()
    fonte, fonte_b = _registar_fontes()

    c = pdfcanvas.Canvas(caminho, pagesize=A4)
    c.setTitle(f"Nota de Saída {numero_documento(nota)}")
    c.setAuthor(config.nome_instituicao)

    _cabecalho_banco(c)

    origem_local = nota.origem_local or config.origem_local or "Sede IT"
    local = nota.local_emissao or config.local_emissao or "Maputo"
    data_txt = nota.data_emissao.strftime("%d/%m/%y") if nota.data_emissao else ""

    c.setFont(fonte_b, 11)
    c.drawString(MARGEM_ESQ, ALTURA - 120, f"De: {origem_local}")

    c.setFont(fonte_b, 10)
    c.drawString(MARGEM_ESQ, ALTURA - 148, f"Para: {nota.email_funcionario}")

    c.setFont(fonte_b, 12)
    c.drawString(MARGEM_ESQ, ALTURA - 176, f"Nr. Ref.{numero_documento(nota)}")
    c.setFont(fonte, 12)
    data_linha = f"{local}, aos {data_txt}"
    c.drawRightString(MARGEM_DIR, ALTURA - 176, data_linha)
    c.setLineWidth(1.1)
    c.line(MARGEM_ESQ - 1.5, ALTURA - 180, MARGEM_DIR, ALTURA - 180)

    c.setFont(fonte_b, 11)
    c.drawString(MARGEM_ESQ, ALTURA - 198, nota.numero_remedy)

    c.setFont(fonte_b, 12)
    c.drawCentredString(LARGURA / 2, ALTURA - 232, "ASSUNTO: Nota de Saída")

    c.setFont(fonte_b, 12)
    c.drawCentredString(
        LARGURA / 2,
        ALTURA - 274,
        "Vimos pela presente nota fazer entrega do seguinte material",
    )

    # ---- Tabela de itens: Quantidade (coluna estreita, centrada) | Descrição --
    qtd_centro = MARGEM_ESQ + 46          # centro da coluna Quantidade
    divisor_x = MARGEM_ESQ + 130          # linha vertical entre as colunas
    col_desc_x = divisor_x + 22           # início da coluna Descrição

    cabecalho_y = ALTURA - 314
    linha_topo = cabecalho_y + 14
    linha_cabecalho = cabecalho_y - 9

    c.setFillColor(black)
    c.setStrokeColor(black)
    c.setDash()

    c.setFont(fonte_b, 11)
    c.drawCentredString(qtd_centro, cabecalho_y, "Quantidade")
    c.drawString(col_desc_x, cabecalho_y, "Descrição")

    c.setLineWidth(0.9)
    c.line(MARGEM_ESQ, linha_topo, MARGEM_DIR, linha_topo)
    c.line(MARGEM_ESQ, linha_cabecalho, MARGEM_DIR, linha_cabecalho)

    linha_altura_min = 26.5
    tamanho_desc = 11            # linha principal (modelo do item)
    tamanho_meta = 9.5           # linhas secundárias (Nr. Série / SAP), indentadas
    indent_meta = 12
    entrelinha_titulo = 13       # espaçamento entre linhas do título, se quebrar
    espaco_antes_meta = 12       # do fim do título até à linha "Nr. Série"
    entrelinha_meta = 10.5       # de "Nr. Série" até "SAP"
    largura_desc_disponivel = MARGEM_DIR - col_desc_x - 4
    y = linha_cabecalho
    for item in nota.itens:
        titulo, linha_serie, linha_sap = _linhas_item(item)
        linhas_titulo = _wrap(c, titulo, fonte, tamanho_desc, largura_desc_disponivel)

        y_texto = y - 17.5
        c.setFont(fonte, 11)
        c.drawCentredString(qtd_centro, y_texto, f"{item.quantidade:02d}")

        c.setFont(fonte, tamanho_desc)
        for i, linha_txt in enumerate(linhas_titulo):
            c.drawString(col_desc_x, y_texto - i * entrelinha_titulo, linha_txt)
        y_ultimo_titulo = y_texto - (len(linhas_titulo) - 1) * entrelinha_titulo

        y_serie = y_ultimo_titulo - espaco_antes_meta
        y_sap = y_serie - entrelinha_meta
        c.setFont(fonte, tamanho_meta)
        c.drawString(col_desc_x + indent_meta, y_serie, linha_serie)
        c.drawString(col_desc_x + indent_meta, y_sap, linha_sap)

        linha_altura = max(linha_altura_min, (y - y_sap) + 9)
        y -= linha_altura
        c.setLineWidth(0.35)
        c.line(MARGEM_ESQ, y, MARGEM_DIR, y)

    c.setLineWidth(0.7)
    c.line(divisor_x, linha_topo, divisor_x, y)

    y = min(y - 22, ALTURA - 452)
    nota_txt = nota.observacao.strip() if nota.observacao else ""
    if nota_txt:
        c.setFont(fonte, 11)
        c.drawString(MARGEM_ESQ, y, f"Nota: {nota_txt}")
        y -= 30

    motivo = (nota.motivo or "Atribuição").strip()
    c.setFont(fonte, 11)
    c.setFillColor(black)
    c.drawString(MARGEM_ESQ, y, f"Motivo: {motivo}")
    y -= 20

    _desenhar_campos_adicionais(c, nota, fonte, fonte_b, y)

    _desenhar_grelha_assinaturas(c, nota, fonte, fonte_b)
    _desenhar_assinatura_png(c, nota)
    _rodape(c, config, fonte)

    c.save()
    return caminho


def _rodape(c, config, fonte):
    """Rodapé configurável (Configurações → «Rodapé do PDF»)."""
    texto = (config.rodape_pdf or "").strip()
    if not texto:
        return
    from reportlab.lib.colors import HexColor

    y = 34
    c.setStrokeColor(HexColor("#B7BEC7"))
    c.setLineWidth(0.5)
    c.setDash()
    c.line(MARGEM_ESQ, y + 12, MARGEM_DIR, y + 12)
    c.setFont(fonte, 8)
    c.setFillColor(HexColor("#5B6572"))
    c.drawCentredString(LARGURA / 2, y, texto)
    c.setFillColor(black)


def _pt_y(pct):
    """Converte % da página (a contar do topo) para pontos (a contar da base)."""
    return ALTURA * (1 - pct / 100.0)


def _desenhar_campos_adicionais(c, nota, fonte, fonte_b, y, y_minimo=310):
    """Imprime os campos adicionais (definidos pelo Administrador) com valor
    preenchido, até ao limite de espaço livre acima da grelha de assinaturas."""
    from app.services import campos_dinamicos_service

    valores = campos_dinamicos_service.valores_para_exibir("saida", nota.id)
    if not valores or y < y_minimo:
        return

    c.setFillColor(black)
    c.setFont(fonte_b, 10.5)
    c.drawString(MARGEM_ESQ, y, "Informações adicionais:")
    y -= 15
    c.setFont(fonte, 10)
    for rotulo, valor in valores:
        if y < y_minimo:
            break
        texto = f"{rotulo}: {valor or '—'}"
        c.drawString(MARGEM_ESQ + 8, y, texto[:110])
        y -= 13.5


def _desenhar_grelha_assinaturas(c, nota, fonte, fonte_b):
    """Rótulo + linha + nome de cada campo, nas posições exatas do mapa de zonas
    (app/utils/assinatura_zonas.py). O preview HTML usa as mesmas percentagens,
    por isso o que se posiciona no preview é o que sai no PDF."""
    from app.utils.assinatura_zonas import CAMPOS_ASSINATURA, LINHA_LARGURA

    nomes = {
        "aprovador": nota.aprovador.nome if nota.aprovador else None,
        "recebido": nota.funcionario or None,
        "entregue": nota.criador.nome if nota.criador else None,
        "seguranca": None,
    }
    meia = LINHA_LARGURA / 2
    for papel, campo in CAMPOS_ASSINATURA.items():
        cx = LARGURA * campo["cx"] / 100.0
        x0 = LARGURA * (campo["cx"] - meia) / 100.0
        x1 = LARGURA * (campo["cx"] + meia) / 100.0
        c.setFont(fonte_b, 11)
        c.setFillColor(black)
        c.drawCentredString(cx, _pt_y(campo["rotulo_y"]), campo["rotulo"])
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.setDash()
        c.line(x0, _pt_y(campo["linha_y"]), x1, _pt_y(campo["linha_y"]))
        if nomes[papel]:
            c.setFont(fonte, 10)
            c.drawCentredString(cx, _pt_y(campo["nome_y"]), nomes[papel])


def _desenhar_assinatura_png(c, nota):
    """Desenha as PNG das assinaturas na grelha 2x2 do exemplar.

    Cada assinatura é enquadrada na sua área (ver app/utils/assinatura_zonas.py):
    Autorizado Por (cima-esq.) · Recebido (cima-dir.)
    Entregue Por  (baixo-esq.) · Segurança (baixo-dir.)
    """
    from app.utils.assinatura_zonas import enquadrar, posicao_padrao

    papeis = (
        ("assinatura_aprovador", "aprovador"),
        ("assinatura_recebido", "recebido"),
        ("assinatura_entregue", "entregue"),
        ("assinatura_seguranca", "seguranca"),
    )
    for prefixo, papel in papeis:
        if not getattr(nota, f"{prefixo}_path"):
            continue
        padrao = posicao_padrao(papel)
        pos = enquadrar(papel, {
            "x": _ou(getattr(nota, f"{prefixo}_x"), padrao["x"]),
            "y": _ou(getattr(nota, f"{prefixo}_y"), padrao["y"]),
            "w": _ou(getattr(nota, f"{prefixo}_w"), padrao["w"]),
            "h": _ou(getattr(nota, f"{prefixo}_h"), padrao["h"]),
        })
        _desenhar_uma_assinatura(
            c, getattr(nota, f"{prefixo}_path"),
            pos["x"], pos["y"], pos["w"], pos["h"],
        )


def _ou(valor, omissao):
    return omissao if valor is None else valor


def _desenhar_uma_assinatura(c, path, x_pct, y_pct, w_pct, h_pct):
    from app.utils.assinatura import caminho_absoluto

    ficheiro = caminho_absoluto(path)
    if not ficheiro:
        return
    largura = LARGURA * (w_pct / 100.0)
    altura = ALTURA * (h_pct / 100.0)
    x = LARGURA * (x_pct / 100.0)
    y = ALTURA - (ALTURA * (y_pct / 100.0)) - altura
    try:
        # anchor="s": a assinatura assenta no fundo da caixa (sobre a linha),
        # tal como `object-position: center bottom` no preview HTML.
        c.drawImage(
            ficheiro,
            x,
            y,
            width=largura,
            height=altura,
            mask="auto",
            preserveAspectRatio=True,
            anchor="s",
        )
    except Exception:
        pass
