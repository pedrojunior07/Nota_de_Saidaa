"""PDF do relatório de equipamentos entregues (A4 horizontal, sem gráficos).

Cabeçalho igual ao das notas — logótipo + «Nota de Saida - Direção de
Informática» (ou «Nota de Entrega …») e «De: Sede IT» — repetido em todas as
páginas; rodapé com «Página N de M».
"""

from __future__ import annotations

import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.services.pdf_service import ASSET_LOGO
from app.services.relatorio_service import MODULOS, Relatorio

PAGINA = landscape(A4)
LARGURA, ALTURA = PAGINA
MARGEM = 18 * mm
TOPO_CONTEUDO = 42 * mm          # espaço reservado ao cabeçalho institucional
NAVY = colors.HexColor("#0033A1")
CINZA = colors.HexColor("#5f6b7a")
LINHA = colors.HexColor("#d5dbe3")
FUNDO = colors.HexColor("#f2f5f9")


def _estilos():
    base = ParagraphStyle("base", fontName="Times-Roman", fontSize=9.5, leading=12)
    return {
        "titulo": ParagraphStyle("titulo", parent=base, fontName="Times-Bold", fontSize=15, leading=19),
        "sub": ParagraphStyle("sub", parent=base, textColor=CINZA),
        "secao": ParagraphStyle("secao", parent=base, fontName="Times-Bold", fontSize=11.5,
                                leading=15, spaceBefore=10, spaceAfter=4, textColor=NAVY),
        "celula": ParagraphStyle("celula", parent=base, fontSize=8.5, leading=10.5, alignment=TA_LEFT),
        "kpi_v": ParagraphStyle("kpi_v", parent=base, fontName="Times-Bold", fontSize=16, leading=19),
        "kpi_r": ParagraphStyle("kpi_r", parent=base, fontSize=8.5, textColor=CINZA),
    }


class _CanvasNumerado(pdfcanvas.Canvas):
    """Canvas que conhece o total de páginas para escrever «Página N de M»."""

    def __init__(self, *args, cabecalho=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []
        self._cabecalho = cabecalho

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._cabecalho(self)
            self.setFont("Times-Roman", 8.5)
            self.setFillColor(CINZA)
            self.drawRightString(LARGURA - MARGEM, 10 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _desenhar_cabecalho(titulo: str, origem: str):
    def _desenhar(c):
        logo_tam = 16 * mm
        logo_y = ALTURA - MARGEM - logo_tam + 4 * mm
        texto_x = MARGEM
        if os.path.isfile(ASSET_LOGO):
            c.drawImage(ASSET_LOGO, MARGEM, logo_y, width=logo_tam, height=logo_tam,
                        preserveAspectRatio=True, mask="auto")
            texto_x = MARGEM + logo_tam + 10 * mm
        c.setFillColor(colors.black)
        c.setFont("Times-Bold", 16)
        c.drawString(texto_x, logo_y + logo_tam / 2 - 5.5, titulo)
        c.setFont("Times-Bold", 11)
        c.drawString(MARGEM, logo_y - 8 * mm, f"De: {origem}")
        c.setStrokeColor(LINHA)
        c.setLineWidth(0.8)
        c.line(MARGEM, logo_y - 11 * mm, LARGURA - MARGEM, logo_y - 11 * mm)
    return _desenhar


def _tabela(dados, larguras, alinhar_direita=(), estilos=None):
    t = Table(dados, colWidths=larguras, repeatRows=1)
    comandos = [
        ("FONT", (0, 0), (-1, 0), "Times-Bold", 8.5),
        ("FONT", (0, 1), (-1, -1), "Times-Roman", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    for col in alinhar_direita:
        comandos.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(comandos + (estilos or [])))
    return t


def gerar_pdf(rel: Relatorio, gerado_por: str, gerado_em: str, origem: str = "Sede IT") -> bytes:
    est = _estilos()
    mod = MODULOS[rel.tipo]
    util = LARGURA - 2 * MARGEM
    periodo = f"{rel.inicio:%d/%m/%Y} a {rel.fim:%d/%m/%Y}"

    story = [
        Paragraph("Relatório de equipamentos entregues", est["titulo"]),
        Paragraph(f"Período: <b>{periodo}</b> &nbsp;·&nbsp; Gerado por {gerado_por} em {gerado_em}", est["sub"]),
    ]
    if rel.filtros_ativos:
        story.append(Paragraph(
            "Filtros: " + " &nbsp;·&nbsp; ".join(f"{r}: <b>{v}</b>" for r, v in rel.filtros_ativos),
            est["sub"]))
    story.append(Spacer(1, 6))

    # -- resumo ---------------------------------------------------------------
    kpis = [
        (str(rel.total_equipamentos), "Equipamentos entregues"),
        (str(rel.total_colaboradores), "Colaboradores"),
    ]
    celulas = [[Paragraph(v, est["kpi_v"]) for v, _ in kpis], [Paragraph(r, est["kpi_r"]) for _, r in kpis]]
    resumo = Table(celulas, colWidths=[util / 2] * 2)
    resumo.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, LINHA),
        ("BACKGROUND", (0, 0), (-1, -1), FUNDO),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(resumo)

    # -- por tipo e por departamento (lado a lado) ------------------------------
    def _grupo(titulo, grupos, largura):
        dados = [[titulo, "Qtd.", "Notas"]] + [
            [Paragraph(g["nome"], est["celula"]), g["quantidade"], g["notas"]]
            for g in grupos
        ]
        if not grupos:
            dados.append(["Sem registos", "", ""])
        return _tabela(dados, [largura - 100, 50, 50], alinhar_direita=(1, 2))

    meia = (util - 8 * mm) / 2
    lado_a_lado = Table(
        [[Paragraph("Por tipo de equipamento", est["secao"]), Paragraph("Por departamento", est["secao"])],
         [_grupo("Tipo", rel.por_tipo, meia), _grupo("Departamento", rel.por_departamento, meia)]],
        colWidths=[meia + 4 * mm, meia + 4 * mm],
    )
    lado_a_lado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
    ]))
    story.append(lado_a_lado)

    # -- detalhe -------------------------------------------------------------
    cab = ["Data", "Nota", "Ref. Remedy", "Colaborador", "Departamento", "Tipo", "Descrição",
           "Nº de série", "Técnico"]
    larg = [20 * mm, 21 * mm, 30 * mm, 32 * mm, 26 * mm, 31 * mm, 38 * mm, 28 * mm]
    larg.append(util - sum(larg))
    c = est["celula"]
    dados = [cab] + [
        [f"{l['data']:%d/%m/%Y}", l["numero_nota"], l["referencia"], Paragraph(l["colaborador"], c),
         Paragraph(l["departamento"], c), Paragraph(l["tipo"], c), Paragraph(l["descricao"], c),
         Paragraph(l["numero_serie"] or "—", c), Paragraph(l["tecnico"], c)]
        for l in rel.linhas
    ]
    if not rel.linhas:
        dados.append(["Sem equipamentos entregues neste período."] + [""] * 8)
    detalhe = _tabela(dados, larg,
                      estilos=[("SPAN", (0, 1), (-1, 1))] if not rel.linhas else None)
    story.append(KeepTogether([Paragraph("Detalhe dos equipamentos entregues", est["secao"])]))
    story.append(detalhe)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGINA, leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=TOPO_CONTEUDO, bottomMargin=16 * mm,
        title=f"Relatório de equipamentos — {mod['nome']}", author=origem,
    )
    cabecalho = _desenhar_cabecalho(mod["titulo_pdf"], origem)
    doc.build(story, canvasmaker=lambda *a, **k: _CanvasNumerado(*a, cabecalho=cabecalho, **k))
    return buf.getvalue()
