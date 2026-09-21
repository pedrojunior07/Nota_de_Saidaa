/* Recolha das assinaturas da entrega (Entregue Por / Recebido / Segurança)
 * e da assinatura pessoal reutilizável do técnico ("Entregue Por").
 *
 * O desenho da assinatura em si (canvas, ponto/traço, guardar/limpar) é
 * gerido pelo módulo partilhado signature_canvas.js — este ficheiro só
 * decide o que fazer com o PNG resultante: posicionar sobre o documento
 * (fluxo normal por nota) ou enviar diretamente para o perfil do
 * utilizador (assinatura reutilizável).
 */
document.addEventListener("DOMContentLoaded", () => {
    const painel = document.getElementById("assinaturasEntrega");
    if (!painel) return;

    const NOTA_ID = painel.dataset.nota;
    const URL_BASE = painel.dataset.urlBase.replace(/\/$/, "");
    // Mapa das áreas de assinatura (signature_zones.js). Cada assinatura só
    // pode ser posicionada dentro da sua própria célula do documento.
    const Zonas = globalThis.SignatureZones?.forTipo
        ? globalThis.SignatureZones.forTipo(painel.dataset.tipo || "saida")
        : globalThis.SignatureZones;
    const csrf =
        document.querySelector('meta[name="csrf-token"]')?.content ||
        painel.querySelector('input[name="csrf_token"]')?.value ||
        "";

    const btnSubmeter = document.getElementById("btnSubmeterNota");
    const submeterHint = document.getElementById("submeterHint");
    const posicionador = document.getElementById("sigRecebidoPreview");
    const posicionadorStage = document.getElementById("sigRecebidoStage");
    const posicionadorVoltar = document.getElementById("sigRecebidoVoltar");
    const posicionadorConfirmar = document.getElementById("sigRecebidoConfirmar");

    let imagemPendente = null;
    let posicaoPendente = null;
    let papelPosicao = null;
    let urlPendente = null;

    // ---- abrir o modal de desenho para um papel desta nota -------------
    function abrirRecolher(papel, rotulo) {
        globalThis.SignatureCanvasModal?.abrir({
            titulo: `Recolher assinatura — ${rotulo}`,
            ajuda: "Assine no retângulo acima.",
            aoGuardar: (imagem) => {
                if (["recebido", "seguranca", "entregue"].includes(papel)) {
                    abrirPosicionador(imagem, papel);
                    return;
                }
                pedir(`${URL_BASE}/assinatura/${papel}`, { imagem }).then(({ ok, json }) => {
                    if (!ok) {
                        globalThis.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                        return;
                    }
                    atualizarLinha(papel, json.url);
                    globalThis.showToast?.("Assinatura guardada.", "success");
                });
            },
        });
    }

    // ---- posicionador (arrastar/redimensionar sobre o documento) -------
    function fecharPosicionador() {
        posicionador.hidden = true;
        document.body.classList.remove("sig-preview-open");
        imagemPendente = null;
        posicaoPendente = null;
        papelPosicao = null;
        urlPendente = null;
    }

    function montarPosicionador() {
        const papel = papelPosicao || "recebido";
        const urlImagem = urlPendente || imagemPendente;

        // Clona a nota no estado atual (com as assinaturas já colocadas por
        // quem a criou/aprovou) para posicionar a nova assinatura sobre o
        // documento completo, tal como no fluxo do aprovador.
        const original = document.querySelector("#notaDocumento .folha-nota");
        let folha;
        if (original) {
            folha = original.cloneNode(true);
        } else {
            folha = document.createElement("div");
            folha.className = "folha-nota";
            folha.innerHTML = `
                <div class="folha-corpo">
                <header class="folha-banner"><strong>Nota de Saida - Direção de Informática</strong></header>
                <p class="folha-assunto">ASSUNTO: Nota de Saída</p>
                </div>`;
        }
        // Remove caixas de posicionamento e a assinatura do papel em edição
        // (para não a mostrar duas vezes); mantém as restantes assinaturas.
        folha.querySelectorAll(".sig-box").forEach((el) => el.remove());
        folha.querySelectorAll(`.folha-sig[data-papel="${papel}"]`).forEach((el) => el.remove());
        folha.querySelectorAll(".folha-sig[data-left]").forEach((sig) => {
            sig.style.left = `${sig.dataset.left}%`;
            sig.style.top = `${sig.dataset.top}%`;
            sig.style.width = `${sig.dataset.width}%`;
            sig.style.height = `${sig.dataset.height}%`;
        });

        const box = document.createElement("div");
        box.className = "sig-box";
        const padrao = Zonas ? Zonas.posicaoPadrao(papel) : { x: 52, y: 62, w: 28, h: 10 };
        const row = painel.querySelector(`.sig-collect-row[data-papel="${papel}"]`);
        const valorOuPadrao = (valor, padr) => Number.isNaN(parseFloat(valor)) ? padr : parseFloat(valor);
        let seed = {
            x: valorOuPadrao(row?.dataset.posX, padrao.x),
            y: valorOuPadrao(row?.dataset.posY, padrao.y),
            w: valorOuPadrao(row?.dataset.posW, padrao.w),
            h: valorOuPadrao(row?.dataset.posH, padrao.h),
        };
        if (Zonas) seed = Zonas.enquadrar(papel, seed);
        box.style.left = `${seed.x}%`;
        box.style.top = `${seed.y}%`;
        box.style.width = `${seed.w}%`;
        box.style.height = `${seed.h}%`;
        box.innerHTML = `<img src="${urlImagem}" alt="Assinatura">
            <span class="sig-handle nw" data-handle="nw"></span>
            <span class="sig-handle ne" data-handle="ne"></span>
            <span class="sig-handle sw" data-handle="sw"></span>
            <span class="sig-handle se" data-handle="se"></span>`;
        folha.appendChild(box);
        posicionadorStage.innerHTML = "";
        posicionadorStage.appendChild(folha);
        posicionadorStage.scrollTop = 0;
        ativarPosicionamento(box);
        return box;
    }

    function lerPosicao(box) {
        let pos = {
            x: parseFloat(box.style.left),
            y: parseFloat(box.style.top),
            w: parseFloat(box.style.width),
            h: parseFloat(box.style.height),
        };
        if (Zonas) pos = Zonas.enquadrar(papelPosicao || "recebido", pos);
        return pos;
    }

    function limitesZonaPx(folhaRect) {
        if (Zonas) return Zonas.limitesPx(papelPosicao || "recebido", folhaRect);
        return { left: 0, top: 0, right: folhaRect.width, bottom: folhaRect.height,
                 minW: folhaRect.width * 0.08, minH: folhaRect.height * 0.04 };
    }

    function ativarPosicionamento(box) {
        let modo = null;
        let inicio = null;
        const mover = (ev) => {
            if (!modo) return;
            const folha = box.parentElement.getBoundingClientRect();
            const dx = ev.clientX - inicio.x;
            const dy = ev.clientY - inicio.y;
            let left = inicio.left;
            let top = inicio.top;
            let width = inicio.width;
            let height = inicio.height;
            if (modo === "move") { left += dx; top += dy; }
            if (modo.includes("e")) width += dx;
            if (modo.includes("s")) height += dy;
            if (modo.includes("w")) { width -= dx; left += dx; }
            if (modo.includes("n")) { height -= dy; top += dy; }
            const lim = limitesZonaPx(folha);
            width = Math.max(lim.minW, Math.min(width, lim.right - lim.left));
            height = Math.max(lim.minH, Math.min(height, lim.bottom - lim.top));
            left = Math.min(Math.max(lim.left, left), lim.right - width);
            top = Math.min(Math.max(lim.top, top), lim.bottom - height);
            box.style.left = `${left / folha.width * 100}%`;
            box.style.top = `${top / folha.height * 100}%`;
            box.style.width = `${width / folha.width * 100}%`;
            box.style.height = `${height / folha.height * 100}%`;
        };
        const parar = () => {
            modo = null;
            globalThis.removeEventListener("pointermove", mover);
            globalThis.removeEventListener("pointerup", parar);
        };
        box.addEventListener("pointerdown", (ev) => {
            const folha = box.parentElement.getBoundingClientRect();
            const rect = box.getBoundingClientRect();
            const handle = ev.target.closest(".sig-handle");
            modo = handle ? handle.dataset.handle : "move";
            inicio = { x: ev.clientX, y: ev.clientY, left: rect.left - folha.left, top: rect.top - folha.top, width: rect.width, height: rect.height };
            globalThis.addEventListener("pointermove", mover);
            globalThis.addEventListener("pointerup", parar);
            ev.preventDefault();
        });
    }

    function abrirPosicionador(imagem, papel = "recebido", url = null) {
        imagemPendente = imagem;
        papelPosicao = papel;
        urlPendente = url;
        posicionador.hidden = false;
        document.body.classList.add("sig-preview-open");
        requestAnimationFrame(montarPosicionador);
    }

    // ---- guardar / remover -------------------------------------------
    async function pedir(url, corpo) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(corpo || {}),
        });
        let json = {};
        try { json = await res.json(); } catch (_e) { /* vazio */ }
        return { ok: res.ok && json.ok, json };
    }

    posicionadorVoltar?.addEventListener("click", fecharPosicionador);
    posicionadorConfirmar?.addEventListener("click", async () => {
        const box = posicionadorStage.querySelector(".sig-box");
        if (!box || (!imagemPendente && !urlPendente)) return;
        posicaoPendente = lerPosicao(box);
        const papel = papelPosicao || "recebido";
        const corpo = urlPendente
            ? { posicao: posicaoPendente }
            : { imagem: imagemPendente, posicao: posicaoPendente };
        const destino = urlPendente
            ? `${URL_BASE}/assinatura/${papel}/posicao`
            : `${URL_BASE}/assinatura/${papel}`;
        const { ok, json } = await pedir(destino, corpo);
        if (!ok) {
            globalThis.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
            return;
        }
        if (json.url) atualizarLinha(papel, json.url);
        const linha = painel.querySelector(`.sig-collect-row[data-papel="${papel}"]`);
        if (linha) {
            linha.dataset.posX = String(posicaoPendente.x);
            linha.dataset.posY = String(posicaoPendente.y);
            linha.dataset.posW = String(posicaoPendente.w);
            linha.dataset.posH = String(posicaoPendente.h);
        }
        globalThis.showToast?.("Assinatura guardada e posicionada.", "success");
        fecharPosicionador();
        // Na Nota de Entrega, a assinatura do Segurança conclui a nota.
        if (json.estado === "concluida") {
            setTimeout(() => globalThis.location.reload(), 700);
            return;
        }
    });

    // ---- assinatura pessoal reutilizável ("Entregue Por") ---------------
    function aplicarAssinaturaReutilizavelGuardada(url) {
        atualizarLinha("entregue", url);
        const row = painel.querySelector('.sig-collect-row[data-papel="entregue"]');
        row?.querySelector(".sig-upload-reutilizavel")?.remove();
        row?.querySelector(".sig-draw-reutilizavel")?.remove();
        const btnEditar = document.createElement("button");
        btnEditar.type = "button";
        btnEditar.className = "sig-icon-btn sig-collect-edit";
        btnEditar.title = "Editar posição da assinatura";
        btnEditar.setAttribute("aria-label", "Editar posição da assinatura");
        btnEditar.innerHTML = '<i class="bi bi-arrows-move" aria-hidden="true"></i>';
        btnEditar.addEventListener("click", () => editarPosicao("entregue", url));
        row?.querySelector(".sig-collect-remove")?.before(btnEditar);
    }

    async function carregarAssinaturaReutilizavel() {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/png";
        input.click();
        input.addEventListener("change", async () => {
            const ficheiro = input.files?.[0];
            if (!ficheiro) return;
            const dados = new FormData();
            dados.append("signature", ficheiro);
            dados.append("nota_id", NOTA_ID);
            const resposta = await fetch(painel.dataset.uploadUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrf },
                body: dados,
            });
            const json = await resposta.json().catch(() => ({}));
            if (!resposta.ok || !json.ok) {
                globalThis.showToast?.(json.error || "Não foi possível carregar a assinatura.", "danger");
                return;
            }
            aplicarAssinaturaReutilizavelGuardada(json.url);
            globalThis.showToast?.("Assinatura reutilizável guardada.", "success");
        });
    }

    function desenharAssinaturaReutilizavel() {
        globalThis.SignatureCanvasModal?.abrir({
            titulo: "Desenhar assinatura",
            ajuda: "Assine no retângulo acima. Fica guardada no seu perfil para reutilizar noutras notas.",
            aoGuardar: async (imagem) => {
                const { ok, json } = await pedir(painel.dataset.uploadUrl, { imagem, nota_id: NOTA_ID });
                if (!ok) {
                    globalThis.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                    return;
                }
                aplicarAssinaturaReutilizavelGuardada(json.url);
                globalThis.showToast?.("Assinatura reutilizável guardada.", "success");
            },
        });
    }

    async function editarPosicao(papel, url) {
        abrirPosicionador(null, papel, url);
    }

    async function remover(papel) {
        const { ok, json } = await pedir(`${URL_BASE}/assinatura/${papel}/remover`);
        if (!ok) {
            globalThis.showToast?.(json.error || "Não foi possível remover.", "danger");
            return;
        }
        atualizarLinha(papel, null);
        globalThis.showToast?.("Assinatura removida.", "info");
    }

    function atualizarLinha(papel, url) {
        const row = painel.querySelector(`.sig-collect-row[data-papel="${papel}"]`);
        if (!row) return;
        const preview = row.querySelector(".sig-collect-preview");
        const estado = row.querySelector(".sig-collect-estado");
        const btnRecolher = row.querySelector(".sig-collect-btn");
        const btnRemover = row.querySelector(".sig-collect-remove");
        const defEstado = (assinada) => {
            estado.className = `sig-collect-estado ${assinada ? "is-assinada" : "is-falta"}`;
            estado.title = assinada ? "Assinada" : "Em falta";
            estado.setAttribute("aria-label", assinada ? "Assinada" : "Em falta");
            estado.innerHTML = `<i class="bi ${assinada ? "bi-check-circle-fill" : "bi-dash-circle"}" aria-hidden="true"></i>`;
        };
        if (url) {
            preview.innerHTML = `<img src="${url}?t=${Date.now()}" alt="Assinatura">`;
            defEstado(true);
            btnRecolher.title = "Substituir assinatura";
            btnRecolher.setAttribute("aria-label", "Substituir assinatura");
            btnRemover.hidden = false;
        } else {
            preview.innerHTML = "";
            defEstado(false);
            btnRecolher.title = "Recolher assinatura";
            btnRecolher.setAttribute("aria-label", "Recolher assinatura");
            btnRemover.hidden = true;
        }
        sincronizarSubmeter();
    }

    function sincronizarSubmeter() {
        if (!btnSubmeter) return;
        const temEntregue = !!painel.querySelector('.sig-collect-row[data-papel="entregue"] .sig-collect-preview img');
        const temRecebido = !!painel.querySelector('.sig-collect-row[data-papel="recebido"] .sig-collect-preview img');
        const pronto = temEntregue && temRecebido;
        btnSubmeter.disabled = !pronto;
        if (submeterHint) submeterHint.hidden = pronto;
    }

    painel.querySelectorAll(".sig-collect-row").forEach((row) => {
        const papel = row.dataset.papel;
        const rotulo = row.querySelector(".sig-collect-info strong")?.textContent || "";
        row.querySelector(".sig-collect-btn")?.addEventListener("click", () => abrirRecolher(papel, rotulo));
        row.querySelector(".sig-collect-edit")?.addEventListener("click", () => {
            const url = row.querySelector(".sig-collect-preview img")?.src;
            if (url) editarPosicao(papel, url);
        });
        row.querySelector(".sig-upload-reutilizavel")?.addEventListener("click", carregarAssinaturaReutilizavel);
        row.querySelector(".sig-draw-reutilizavel")?.addEventListener("click", desenharAssinaturaReutilizavel);
        row.querySelector(".sig-collect-remove")?.addEventListener("click", () => {
            if (confirm("Remover esta assinatura?")) remover(papel);
        });
    });
});
