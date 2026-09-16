/* Recolha das assinaturas da entrega (Entregue Por / Recebido / Segurança).
 *
 * O campo de assinatura fica à espera de UMA de duas vias:
 *   1. Desenho no <canvas> com pointer events — rato, ecrã tátil e caneta de
 *      tablet Windows (o #sigCanvas tem touch-action:none).
 *   2. Signature pad Wacom STU — botão «Assinar no pad Wacom», que usa o
 *      adaptador window.WacomSigPad (vendor/sigcaptx + wacom_sigpad.js) e
 *      devolve a assinatura como data-URL PNG, igual a canvas.toDataURL().
 *
 * Com data-pad-obrigatoria=1 (SIGNATURE_PAD_REQUIRED) só a via do pad Wacom
 * grava; a via do <canvas> fica bloqueada. Com =0 (dev) qualquer via serve.
 */
document.addEventListener("DOMContentLoaded", () => {
    const painel = document.getElementById("assinaturasEntrega");
    const modal = document.getElementById("sigCaptura");
    if (!painel || !modal) return;

    const NOTA_ID = painel.dataset.nota;
    const URL_BASE = painel.dataset.urlBase.replace(/\/$/, "");
    const PAD_OBRIGATORIA = painel.dataset.padObrigatoria === "1";
    // Mapa das áreas de assinatura (signature_zones.js). Cada assinatura só
    // pode ser posicionada dentro da sua própria célula do documento.
    const Zonas = (window.SignatureZones && window.SignatureZones.forTipo)
        ? window.SignatureZones.forTipo(painel.dataset.tipo || "saida")
        : window.SignatureZones;
    const csrf =
        document.querySelector('meta[name="csrf-token"]')?.content ||
        painel.querySelector('input[name="csrf_token"]')?.value ||
        "";

    // Configuração do pad Wacom (porta do serviço SigCaptX + licença), vinda do
    // template via <script id="wacomSigCaptxMeta">.
    const wacomMeta = (() => {
        try {
            return JSON.parse(document.getElementById("wacomSigCaptxMeta")?.textContent || "{}");
        } catch (_e) {
            return {};
        }
    })();
    window.WacomSigPad?.configure(wacomMeta);

    const canvas = document.getElementById("sigCanvas");
    const ctx = canvas.getContext("2d");
    const btnGuardar = document.getElementById("sigCapturaGuardar");
    const btnLimpar = document.getElementById("sigCapturaLimpar");
    const btnFechar = document.getElementById("sigCapturaFechar");
    const titulo = document.getElementById("sigCapturaTitulo");
    const ajuda = document.getElementById("sigCapturaAjuda");
    const padTexto = document.getElementById("sigPadTexto");
    const padEstado = document.getElementById("sigPadEstado");
    const btnPad = document.getElementById("sigCapturaPad");
    const btnSubmeter = document.getElementById("btnSubmeterNota");
    const submeterHint = document.getElementById("submeterHint");
    const posicionador = document.getElementById("sigRecebidoPreview");
    const posicionadorStage = document.getElementById("sigRecebidoStage");
    const posicionadorVoltar = document.getElementById("sigRecebidoVoltar");
    const posicionadorConfirmar = document.getElementById("sigRecebidoConfirmar");

    let papelAtual = null;
    let temTraco = false;
    let padOk = false;
    let imagemPendente = null;
    let posicaoPendente = null;
    let papelPosicao = null;
    let urlPendente = null;

    // ---- canvas ----------------------------------------------------------
    function prepararCanvas() {
        const escala = window.devicePixelRatio || 1;
        const largura = canvas.clientWidth || 640;
        const altura = canvas.clientHeight || 240;
        canvas.width = largura * escala;
        canvas.height = altura * escala;
        ctx.scale(escala, escala);
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = "#0b1f33";
        limparCanvas();
    }

    function limparCanvas() {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.restore();
        temTraco = false;
        atualizarGuardar();
    }

    let aDesenhar = false;
    let ultimo = null;

    const pos = (ev) => {
        const r = canvas.getBoundingClientRect();
        return { x: ev.clientX - r.left, y: ev.clientY - r.top };
    };

    canvas.addEventListener("pointerdown", (ev) => {
        if (btnGuardar.dataset.bloqueado === "1") return;
        aDesenhar = true;
        ultimo = pos(ev);
        canvas.setPointerCapture(ev.pointerId);
        ev.preventDefault();
    });
    canvas.addEventListener("pointermove", (ev) => {
        if (!aDesenhar) return;
        // Eventos coalescidos = traço mais suave com caneta/touch de alta taxa.
        const eventos = ev.getCoalescedEvents ? ev.getCoalescedEvents() : [ev];
        for (const e of eventos.length ? eventos : [ev]) {
            const p = pos(e);
            if (e.pointerType === "pen" && e.pressure > 0) {
                ctx.lineWidth = 1 + e.pressure * 2.4;
            }
            ctx.beginPath();
            ctx.moveTo(ultimo.x, ultimo.y);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
            ultimo = p;
        }
        temTraco = true;
        atualizarGuardar();
    });
    const pararDesenho = () => { aDesenhar = false; };
    canvas.addEventListener("pointerup", pararDesenho);
    canvas.addEventListener("pointercancel", pararDesenho);
    canvas.addEventListener("pointerleave", pararDesenho);

    function atualizarGuardar() {
        const bloqueado = PAD_OBRIGATORIA && !padOk;
        btnGuardar.dataset.bloqueado = bloqueado ? "1" : "0";
        btnGuardar.disabled = bloqueado || !temTraco;
    }

    // ---- pad Wacom STU (SigCaptX) --------------------------------------
    const MENSAGENS_PAD = {
        idle: ["is-warn", "A verificar pad Wacom…"],
        connecting: ["is-warn", "A ligar ao pad Wacom…"],
        ready: ["is-ok", "Pad Wacom pronto. Assine no pad ou no retângulo acima."],
        "no-service": ["is-warn", "Serviço Wacom indisponível — assine no retângulo (caneta/rato/touch)."],
        "no-licence": ["is-warn", "Licença Wacom em falta — assine no retângulo (caneta/rato/touch)."],
        error: ["is-warn", "Não foi possível ligar ao pad Wacom — assine no retângulo."],
    };

    function aplicarEstadoPad(estado) {
        if (!padEstado) return;
        let [cls, texto] = MENSAGENS_PAD[estado] || MENSAGENS_PAD.idle;
        if (PAD_OBRIGATORIA && estado !== "ready") {
            texto = "É obrigatório assinar no pad Wacom, mas o serviço não está disponível.";
        }
        padEstado.className = `sig-capture-pad-estado ${cls}`;
        if (padTexto) padTexto.textContent = texto;
        if (btnPad) btnPad.disabled = estado !== "ready";
    }

    function iniciarPad() {
        if (!window.WacomSigPad) {
            aplicarEstadoPad("no-service");
            return;
        }
        // Se uma tentativa anterior falhou (serviço/pad ligados entretanto),
        // volta a tentar; se já está pronto, resolve do cache instantaneamente.
        const anterior = window.WacomSigPad.getState();
        const forcar = ["no-service", "no-licence", "error"].includes(anterior);
        aplicarEstadoPad("connecting");
        window.WacomSigPad.init(forcar)
            .then(aplicarEstadoPad)
            .catch(() => aplicarEstadoPad("error"));
    }

    async function capturarNoPad() {
        if (!papelAtual || !window.WacomSigPad?.isReady()) return;
        const rotulo =
            painel.querySelector(`.sig-collect-row[data-papel="${papelAtual}"] .sig-collect-info strong`)
                ?.textContent || "";
        const textoAnterior = padTexto?.textContent;
        btnPad.disabled = true;
        if (padTexto) padTexto.textContent = "A aguardar a assinatura no pad Wacom…";
        try {
            const imagem = await window.WacomSigPad.capture({
                who: rotulo,
                why: `Nota de ${painel.dataset.tipo || "saída"} — ${rotulo}`,
            });
            const papel = papelAtual;
            if (["recebido", "seguranca", "entregue"].includes(papel)) {
                fechar();
                abrirPosicionador(imagem, papel);
                return;
            }
            const { ok, json } = await pedir(`${URL_BASE}/assinatura/${papel}`, { imagem });
            if (!ok) {
                window.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                return;
            }
            atualizarLinha(papel, json.url);
            window.showToast?.("Assinatura guardada.", "success");
            fechar();
        } catch (motivo) {
            const msgs = {
                cancel: "Captura cancelada no pad.",
                "pad-error": "Erro no pad Wacom. Verifique a ligação do dispositivo.",
                "not-licensed": "Licença Wacom inválida ou em falta para a captura.",
                "render-error": "Não foi possível gerar a imagem da assinatura.",
            };
            window.showToast?.(
                msgs[motivo] || "Falha na captura pelo pad Wacom.",
                motivo === "cancel" ? "info" : "danger",
            );
            if (padTexto && textoAnterior) padTexto.textContent = textoAnterior;
        } finally {
            if (btnPad) btnPad.disabled = !window.WacomSigPad?.isReady();
        }
    }

    btnPad?.addEventListener("click", capturarNoPad);

    // ---- abrir / fechar modal ------------------------------------------
    function abrir(papel, rotulo) {
        papelAtual = papel;
        titulo.textContent = `Recolher assinatura — ${rotulo}`;
        const usaPad = painel
            .querySelector(`.sig-collect-row[data-papel="${papel}"]`)
            ?.dataset.usaPad === "1";
        if (padEstado) padEstado.hidden = !usaPad;
        if (btnPad) {
            btnPad.hidden = !usaPad;
            btnPad.disabled = true;
        }
        ajuda.textContent = usaPad
            ? "Peça à pessoa para assinar no pad Wacom ou no retângulo acima."
            : "Assine no retângulo acima.";
        modal.showModal();
        document.body.classList.add("sig-capture-open");
        requestAnimationFrame(() => {
            prepararCanvas();
            if (usaPad) {
                // Com pad obrigatória, a via do <canvas> não grava — só o pad.
                padOk = !PAD_OBRIGATORIA;
                atualizarGuardar();
                iniciarPad();
            } else {
                padOk = true;
                atualizarGuardar();
            }
        });
    }

    function fechar() {
        modal.close();
        document.body.classList.remove("sig-capture-open");
        papelAtual = null;
    }

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
            window.removeEventListener("pointermove", mover);
            window.removeEventListener("pointerup", parar);
        };
        box.addEventListener("pointerdown", (ev) => {
            const folha = box.parentElement.getBoundingClientRect();
            const rect = box.getBoundingClientRect();
            const handle = ev.target.closest(".sig-handle");
            modo = handle ? handle.dataset.handle : "move";
            inicio = { x: ev.clientX, y: ev.clientY, left: rect.left - folha.left, top: rect.top - folha.top, width: rect.width, height: rect.height };
            window.addEventListener("pointermove", mover);
            window.addEventListener("pointerup", parar);
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

    btnFechar?.addEventListener("click", fechar);
    btnLimpar?.addEventListener("click", limparCanvas);
    modal.addEventListener("click", (ev) => {
        if (ev.target === modal) fechar();
    });

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

    btnGuardar?.addEventListener("click", async () => {
        if (!papelAtual || btnGuardar.disabled) return;
        btnGuardar.disabled = true;
        const imagem = canvas.toDataURL("image/png");
        // Recolhida a assinatura, o painel de recolha fecha e abre-se o
        // posicionador sobre o documento completo.
        if (["recebido", "seguranca", "entregue"].includes(papelAtual)) {
            btnGuardar.disabled = false;
            const papel = papelAtual;
            fechar();
            abrirPosicionador(imagem, papel);
            return;
        }
        const { ok, json } = await pedir(`${URL_BASE}/assinatura/${papelAtual}`, { imagem });
        if (!ok) {
            window.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
            btnGuardar.disabled = false;
            return;
        }
        atualizarLinha(papelAtual, json.url);
        window.showToast?.("Assinatura guardada.", "success");
        fechar();
    });

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
            window.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
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
        window.showToast?.("Assinatura guardada e posicionada.", "success");
        fecharPosicionador();
        fechar();
        // Na Nota de Entrega, a assinatura do Segurança conclui a nota.
        if (json.estado === "concluida") {
            setTimeout(() => window.location.reload(), 700);
            return;
        }
    });

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
                window.showToast?.(json.error || "Não foi possível carregar a assinatura.", "danger");
                return;
            }
            atualizarLinha("entregue", json.url);
            const row = painel.querySelector('.sig-collect-row[data-papel="entregue"]');
            row?.querySelector(".sig-upload-reutilizavel")?.remove();
            const btnEditar = document.createElement("button");
            btnEditar.type = "button";
            btnEditar.className = "sig-icon-btn sig-collect-edit";
            btnEditar.title = "Editar posição da assinatura";
            btnEditar.setAttribute("aria-label", "Editar posição da assinatura");
            btnEditar.innerHTML = '<i class="bi bi-arrows-move" aria-hidden="true"></i>';
            btnEditar.addEventListener("click", () => editarPosicao("entregue", json.url));
            row?.querySelector(".sig-collect-remove")?.before(btnEditar);
            window.showToast?.("Assinatura reutilizável guardada.", "success");
        });
    }

    async function editarPosicao(papel, url) {
        abrirPosicionador(null, papel, url);
    }

    async function remover(papel) {
        const { ok, json } = await pedir(`${URL_BASE}/assinatura/${papel}/remover`);
        if (!ok) {
            window.showToast?.(json.error || "Não foi possível remover.", "danger");
            return;
        }
        atualizarLinha(papel, null);
        window.showToast?.("Assinatura removida.", "info");
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
        row.querySelector(".sig-collect-btn")?.addEventListener("click", () => abrir(papel, rotulo));
        row.querySelector(".sig-collect-edit")?.addEventListener("click", () => {
            const url = row.querySelector(".sig-collect-preview img")?.src;
            if (url) editarPosicao(papel, url);
        });
        row.querySelector(".sig-upload-reutilizavel")?.addEventListener("click", carregarAssinaturaReutilizavel);
        row.querySelector(".sig-collect-remove")?.addEventListener("click", () => {
            if (confirm("Remover esta assinatura?")) remover(papel);
        });
    });

    window.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && !modal.hidden) fechar();
    });
});
