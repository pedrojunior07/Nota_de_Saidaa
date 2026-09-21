/* Modal partilhado de desenho de assinatura (#sigCaptura).
 *
 * Assina-se só no <canvas>, com rato, ecrã tátil ou caneta — não há
 * suporte a signature pad de hardware. Um clique sem arrastar desenha
 * um ponto (rubrica curta); arrastar desenha um traço contínuo.
 *
 * Este módulo é o único dono do <dialog id="sigCaptura">: expõe
 * globalThis.SignatureCanvasModal.abrir({ titulo, ajuda, aoGuardar }) para
 * quem precisar de recolher uma assinatura desenhada, devolvendo sempre
 * um PNG (data URL) através do callback aoGuardar. Quem chama decide o
 * que fazer com esse PNG (posicionar sobre o documento, enviar para o
 * servidor, etc.) — este módulo não sabe nada sobre notas, papéis ou
 * posições.
 *
 * Utilizadores atuais:
 *   - signature_capture.js (recolher assinaturas da entrega, e desenhar
 *     a assinatura pessoal reutilizável do técnico)
 *   - signature_aprovacao.js (desenhar a assinatura pessoal reutilizável
 *     do aprovador)
 */
document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("sigCaptura");
    if (!modal) return;

    const canvas = document.getElementById("sigCanvas");
    const ctx = canvas.getContext("2d");
    const btnGuardar = document.getElementById("sigCapturaGuardar");
    const btnLimpar = document.getElementById("sigCapturaLimpar");
    const btnFechar = document.getElementById("sigCapturaFechar");
    const titulo = document.getElementById("sigCapturaTitulo");
    const ajuda = document.getElementById("sigCapturaAjuda");

    let temTraco = false;
    let aDesenhar = false;
    let ultimo = null;
    let aoGuardarAtual = null;

    function prepararCanvas() {
        const escala = globalThis.devicePixelRatio || 1;
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

    const pos = (ev) => {
        const r = canvas.getBoundingClientRect();
        return { x: ev.clientX - r.left, y: ev.clientY - r.top };
    };

    canvas.addEventListener("pointerdown", (ev) => {
        aDesenhar = true;
        ultimo = pos(ev);
        // Em alguns browsers/drivers de caneta, capturar o ponteiro pode
        // falhar (ex.: id de ponteiro já não é válido) — isso não deve
        // impedir o desenho de continuar a funcionar.
        try {
            canvas.setPointerCapture(ev.pointerId);
        } catch (error_) { console.debug(error_); /* ignorar — segue sem captura */ }
        // Desenha logo um ponto no local do toque/clique. Sem isto, um
        // clique sem arrastar (assinatura em forma de ponto/rubrica curta)
        // não desenhava nada e o botão "Guardar" ficava desativado, porque
        // só o pointermove marcava temTraco = true.
        ctx.beginPath();
        ctx.arc(ultimo.x, ultimo.y, ctx.lineWidth / 2, 0, Math.PI * 2);
        ctx.fillStyle = ctx.strokeStyle;
        ctx.fill();
        temTraco = true;
        atualizarGuardar();
        ev.preventDefault();
    });
    canvas.addEventListener("pointermove", (ev) => {
        if (!aDesenhar) return;
        // Eventos coalescidos = traço mais suave com caneta/touch de alta taxa.
        // Nem todas as canetas/tablets/browsers suportam isto de forma
        // fiável — se falhar, desenha só com o evento atual.
        let eventos;
        try {
            eventos = ev.getCoalescedEvents ? ev.getCoalescedEvents() : [ev];
        } catch (error_) {
            console.error(error_);
            eventos = [ev];
        }
        if (!eventos || !eventos.length) eventos = [ev];
        for (const e of eventos) {
            const p = pos(e);
            // Algumas canetas/tablets externas não relatam pressão fiável
            // (fica sempre 0, ou undefined) — nesse caso mantém a espessura
            // por omissão em vez de encolher o traço a zero.
            if (e.pointerType === "pen" && Number.isFinite(e.pressure) && e.pressure > 0) {
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
    // NOTA: "pointerleave" não é usado para parar o desenho — com o
    // ponteiro capturado (setPointerCapture acima), algumas
    // caneta/tablets ainda disparam "leave" ao levantar ligeiramente a
    // ponta antes do "pointerup" (deteção de hover), o que cortava o
    // traço a meio sem motivo. "pointerup"/"pointercancel" já cobrem
    // corretamente o fim do traço.

    function atualizarGuardar() {
        btnGuardar.disabled = !temTraco;
    }

    function abrir({ titulo: tit, ajuda: aju, aoGuardar } = {}) {
        aoGuardarAtual = typeof aoGuardar === "function" ? aoGuardar : null;
        if (titulo) titulo.textContent = tit || "Recolher assinatura";
        if (ajuda) ajuda.textContent = aju || "Assine no retângulo acima.";
        modal.showModal();
        document.body.classList.add("sig-capture-open");
        requestAnimationFrame(() => {
            prepararCanvas();
            atualizarGuardar();
        });
    }

    function fechar() {
        modal.close();
        document.body.classList.remove("sig-capture-open");
        aoGuardarAtual = null;
    }

    btnFechar?.addEventListener("click", fechar);
    btnLimpar?.addEventListener("click", limparCanvas);
    modal.addEventListener("click", (ev) => {
        if (ev.target === modal) fechar();
    });
    btnGuardar?.addEventListener("click", () => {
        if (btnGuardar.disabled) return;
        const imagem = canvas.toDataURL("image/png");
        const callback = aoGuardarAtual;
        fechar();
        callback?.(imagem);
    });
    globalThis.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && modal.open) fechar();
    });

    globalThis.SignatureCanvasModal = { abrir, fechar };
});
