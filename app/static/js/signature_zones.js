/* Mapa dos campos de assinatura (lado do cliente).
 *
 * Espelha app/utils/assinatura_zonas.py — mantê-los sincronizados.
 *
 *   "saida"   grelha 2x2:
 *       Autorizado Por (aprovador)  |  Recebido (recebido)
 *       Entregue Por  (entregue)    |  Segurança (seguranca)
 *   "entrega" a mesma grelha 2x2 (tal como no exemplar DHL):
 *       Autorizado por (aprovador)  |  Recebido por (recebido)
 *       Entregue por  (entregue)    |  Segurança (seguranca)
 *
 * Coordenadas em % da folha (proporção A4), origem no canto superior
 * esquerdo, Y para baixo.
 */
(function () {
    const CAMPOS_POR_TIPO = {
        saida: {
            aprovador: { rotulo: "Autorizado Por", cx: 32.5, linhaY: 72.5, rotuloY: 65.0, nomeY: 74.6 },
            recebido: { rotulo: "Recebido", cx: 75.0, linhaY: 72.5, rotuloY: 65.0, nomeY: 74.6 },
            entregue: { rotulo: "Entregue Por", cx: 32.5, linhaY: 89.0, rotuloY: 81.5, nomeY: 91.1 },
            seguranca: { rotulo: "Segurança", cx: 75.0, linhaY: 89.0, rotuloY: 81.5, nomeY: 91.1 },
        },
        entrega: {
            aprovador: { rotulo: "Autorizado por", cx: 28.0, linhaY: 74.0, rotuloY: 66.5, nomeY: 76.1 },
            recebido: { rotulo: "Recebido por", cx: 72.0, linhaY: 74.0, rotuloY: 66.5, nomeY: 76.1 },
            entregue: { rotulo: "Entregue por", cx: 28.0, linhaY: 88.0, rotuloY: 80.5, nomeY: 90.1 },
            seguranca: { rotulo: "Segurança", cx: 72.0, linhaY: 88.0, rotuloY: 80.5, nomeY: 90.1 },
        },
    };
    const LINHA_LARGURA_POR_TIPO = { saida: 32.0, entrega: 32.0 };
    const LARGURA_PADRAO_POR_TIPO = { saida: 30.0, entrega: 30.0 };
    const MARGEM_ACIMA_POR_TIPO = { saida: 9.0, entrega: 9.0 };
    const ALTURA_PADRAO_POR_TIPO = { saida: 7.0, entrega: 7.0 };

    const MARGEM_ABAIXO = 3.0;
    const BASE_ACIMA_LINHA = 1.5;
    const BASE_ABAIXO_LINHA = 1.0;
    const LARGURA_MINIMA = 8;
    const ALTURA_MINIMA = 4;

    const round2 = (n) => Math.round(n * 100) / 100;
    const limitar = (v, min, max) => Math.max(min, Math.min(max, v));

    const construir = (tipo) => {
        const CAMPOS = CAMPOS_POR_TIPO[tipo] || CAMPOS_POR_TIPO.saida;
        const LINHA_LARGURA = LINHA_LARGURA_POR_TIPO[tipo] || LINHA_LARGURA_POR_TIPO.saida;
        const LARGURA_PADRAO = LARGURA_PADRAO_POR_TIPO[tipo] || LARGURA_PADRAO_POR_TIPO.saida;
        const MARGEM_ACIMA = MARGEM_ACIMA_POR_TIPO[tipo] || MARGEM_ACIMA_POR_TIPO.saida;
        const ALTURA_PADRAO = ALTURA_PADRAO_POR_TIPO[tipo] || ALTURA_PADRAO_POR_TIPO.saida;
        const ZONAS = {};
        const DEFAULTS = {};
        for (const [papel, c] of Object.entries(CAMPOS)) {
            ZONAS[papel] = {
                xMin: round2(c.cx - LINHA_LARGURA / 2 - 3),
                xMax: round2(c.cx + LINHA_LARGURA / 2 + 3),
                yMin: round2(c.linhaY - MARGEM_ACIMA),
                yMax: round2(c.linhaY + MARGEM_ABAIXO),
            };
            DEFAULTS[papel] = {
                x: round2(c.cx - LARGURA_PADRAO / 2),
                y: round2(c.linhaY - ALTURA_PADRAO),
                w: LARGURA_PADRAO,
                h: ALTURA_PADRAO,
            };
        }
        const primeiro = Object.keys(DEFAULTS)[0];
        const posicaoPadrao = (papel) => ({ ...(DEFAULTS[papel] || DEFAULTS.entregue || DEFAULTS[primeiro]) });

        const enquadrar = (papel, pos) => {
            const z = ZONAS[papel];
            let { x, y, w, h } = pos || {};
            x = parseFloat(x); y = parseFloat(y); w = parseFloat(w); h = parseFloat(h);
            if ([x, y, w, h].some((n) => Number.isNaN(n))) return posicaoPadrao(papel);
            if (!z) {
                w = limitar(w, LARGURA_MINIMA, 100);
                h = limitar(h, ALTURA_MINIMA, 100);
                x = limitar(x, 0, 100 - w);
                y = limitar(y, 0, 100 - h);
                return { x, y, w, h };
            }
            w = limitar(w, LARGURA_MINIMA, z.xMax - z.xMin);
            h = limitar(h, ALTURA_MINIMA, z.yMax - z.yMin);
            x = limitar(x, z.xMin, z.xMax - w);
            y = limitar(y, z.yMin, z.yMax - h);
            const c = CAMPOS[papel];
            if (c) {
                const base = limitar(y + h, c.linhaY - BASE_ACIMA_LINHA, c.linhaY + BASE_ABAIXO_LINHA);
                y = limitar(base - h, z.yMin, z.yMax - h);
            }
            return { x: round2(x), y: round2(y), w: round2(w), h: round2(h) };
        };

        const limitesPx = (papel, folhaRect) => {
            const z = ZONAS[papel] || { xMin: 0, yMin: 0, xMax: 100, yMax: 100 };
            return {
                left: (z.xMin / 100) * folhaRect.width,
                top: (z.yMin / 100) * folhaRect.height,
                right: (z.xMax / 100) * folhaRect.width,
                bottom: (z.yMax / 100) * folhaRect.height,
                minW: (LARGURA_MINIMA / 100) * folhaRect.width,
                minH: (ALTURA_MINIMA / 100) * folhaRect.height,
            };
        };

        return {
            tipo, CAMPOS, ZONAS, DEFAULTS, LINHA_LARGURA,
            zona: (papel) => ZONAS[papel] || null,
            campo: (papel) => CAMPOS[papel] || null,
            posicaoPadrao, enquadrar, limitesPx,
        };
    };

    const variantes = { saida: construir("saida"), entrega: construir("entrega") };

    // API: window.SignatureZones é a variante "saida" (compat.), com forTipo().
    window.SignatureZones = Object.assign({}, variantes.saida, {
        forTipo: (tipo) => variantes[tipo] || variantes.saida,
    });
})();
