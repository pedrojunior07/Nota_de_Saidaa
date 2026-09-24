/* Posicionamento e confirmação da assinatura do Aprovador («Autorizado
 * Por») sobre o documento. O bloco "Minha assinatura" (desenhar/carregar/
 * apagar) vive em signature_perfil_manager.js, partilhado com
 * signature_placement.js e signature_profile.js — aqui só fica o que é
 * próprio deste ecrã: mostrar o documento real da nota e arrastar/
 * redimensionar a caixa da assinatura sobre ele.
 */
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("formDecisao");
    const metaEl = document.getElementById("aprovadorPreviewMeta");
    if (!form || !metaEl) return;

    const meta = JSON.parse(metaEl.textContent);
    const btnUpload = document.getElementById("btnUploadAssinatura");
    const preview = document.getElementById("sigPreview");
    const stage = document.getElementById("sigStage");
    const hint = document.getElementById("sigHint");
    const btnAprovar = document.getElementById("btnAprovar");
    const btnVoltar = document.getElementById("sigVoltar");
    const btnConfirmar = document.getElementById("sigConfirmar");
    const csrf = form.querySelector('input[name="csrf_token"]')?.value || "";

    const gestor = globalThis.GestorAssinaturaPerfil.criar({ meta, csrf, incluirNotaId: true });

    let hintTimer = null;
    let confirmarAprovacao = false;
    let folha = null;

    // A assinatura do aprovador («Autorizado Por») só pode ocupar a sua área.
    const PAPEL = "aprovador";
    const Zonas = globalThis.SignatureZones?.forTipo
        ? globalThis.SignatureZones.forTipo(meta.tipo || "saida")
        : globalThis.SignatureZones;
    const limitesZona = () => Zonas
        ? Zonas.limitesPx(PAPEL, folha.getBoundingClientRect())
        : (() => {
            const r = folha.getBoundingClientRect();
            return { left: 0, top: 0, right: r.width, bottom: r.height, minW: r.width * 0.08, minH: r.height * 0.04 };
        })();
    const enquadrarCaixa = (left, top, width, height) => {
        const lim = limitesZona();
        width = Math.max(lim.minW, Math.min(width, lim.right - lim.left));
        height = Math.max(lim.minH, Math.min(height, lim.bottom - lim.top));
        left = Math.min(Math.max(lim.left, left), lim.right - width);
        top = Math.min(Math.max(lim.top, top), lim.bottom - height);
        return { left, top, width, height };
    };

    const valorPos = (id) => parseFloat(document.getElementById(id).value) || 0;
    const gravarPos = (box) => {
        if (!folha) return;
        const rect = folha.getBoundingClientRect();
        const b = box.getBoundingClientRect();
        let pos = {
            x: (b.left - rect.left) / rect.width * 100,
            y: (b.top - rect.top) / rect.height * 100,
            w: b.width / rect.width * 100,
            h: b.height / rect.height * 100,
        };
        if (Zonas) pos = Zonas.enquadrar(PAPEL, pos);
        document.getElementById("assinatura_x").value = pos.x.toFixed(2);
        document.getElementById("assinatura_y").value = pos.y.toFixed(2);
        document.getElementById("assinatura_w").value = pos.w.toFixed(2);
        document.getElementById("assinatura_h").value = pos.h.toFixed(2);
    };

    const ativarArrasto = (box) => {
        let modo = null;
        let start = {};

        const onMove = (ev) => {
            if (!modo || !folha) return;
            const folhaRect = folha.getBoundingClientRect();
            const dx = ev.clientX - start.x;
            const dy = ev.clientY - start.y;
            let left = start.left;
            let top = start.top;
            let width = start.width;
            let height = start.height;
            if (modo === "move") {
                left = start.left + dx;
                top = start.top + dy;
            } else {
                if (modo.includes("e")) width = start.width + dx;
                if (modo.includes("s")) height = start.height + dy;
                if (modo.includes("w")) {
                    width = start.width - dx;
                    left = start.left + dx;
                }
                if (modo.includes("n")) {
                    height = start.height - dy;
                    top = start.top + dy;
                }
            }
            ({ left, top, width, height } = enquadrarCaixa(left, top, width, height));
            box.style.left = `${(left / folhaRect.width) * 100}%`;
            box.style.top = `${(top / folhaRect.height) * 100}%`;
            box.style.width = `${(width / folhaRect.width) * 100}%`;
            box.style.height = `${(height / folhaRect.height) * 100}%`;
        };

        const onUp = () => {
            if (!modo) return;
            modo = null;
            gravarPos(box);
            globalThis.removeEventListener("pointermove", onMove);
            globalThis.removeEventListener("pointerup", onUp);
        };

        box.addEventListener("pointerdown", (ev) => {
            const handle = ev.target.closest(".sig-handle");
            const folhaRect = folha.getBoundingClientRect();
            const b = box.getBoundingClientRect();
            modo = handle ? handle.dataset.handle : "move";
            start = {
                x: ev.clientX,
                y: ev.clientY,
                left: b.left - folhaRect.left,
                top: b.top - folhaRect.top,
                width: b.width,
                height: b.height,
            };
            box.setPointerCapture(ev.pointerId);
            globalThis.addEventListener("pointermove", onMove);
            globalThis.addEventListener("pointerup", onUp);
            ev.preventDefault();
        });

        box.addEventListener("wheel", (ev) => {
            ev.preventDefault();
            const folhaRect = folha.getBoundingClientRect();
            const b = box.getBoundingClientRect();
            const fator = ev.deltaY < 0 ? 1.06 : 0.94;
            let width = b.width * fator;
            let height = b.height * fator;
            let left = b.left - folhaRect.left;
            let top = b.top - folhaRect.top;
            ({ left, top, width, height } = enquadrarCaixa(left, top, width, height));
            box.style.width = `${(width / folhaRect.width) * 100}%`;
            box.style.height = `${(height / folhaRect.height) * 100}%`;
            box.style.left = `${(left / folhaRect.width) * 100}%`;
            box.style.top = `${(top / folhaRect.height) * 100}%`;
            gravarPos(box);
        }, { passive: false });
    };

    const montarFolha = () => {
        const original = document.querySelector("#notaDocumento .folha-nota");
        stage.innerHTML = "";
        folha = original.cloneNode(true);
        folha.querySelectorAll(".sig-box").forEach((el) => el.remove());
        const box = document.createElement("div");
        box.className = "sig-box";
        let seed = { x: valorPos("assinatura_x"), y: valorPos("assinatura_y"), w: valorPos("assinatura_w"), h: valorPos("assinatura_h") };
        if (Zonas) seed = Zonas.enquadrar(PAPEL, seed);
        box.style.left = `${seed.x}%`;
        box.style.top = `${seed.y}%`;
        box.style.width = `${seed.w}%`;
        box.style.height = `${seed.h}%`;
        box.innerHTML = `
            <img src="${gestor.assinaturaUrl}" alt="Minha assinatura">
            <span class="sig-handle nw" data-handle="nw"></span>
            <span class="sig-handle ne" data-handle="ne"></span>
            <span class="sig-handle sw" data-handle="sw"></span>
            <span class="sig-handle se" data-handle="se"></span>
        `;
        folha.appendChild(box);
        stage.appendChild(folha);
        ativarArrasto(box);
    };

    const mostrarHint = () => {
        hint.classList.add("is-visible");
        clearTimeout(hintTimer);
        hintTimer = setTimeout(() => hint.classList.remove("is-visible"), 5000);
    };

    const abrirPreview = () => {
        if (!gestor.assinaturaUrl) {
            globalThis.showToast?.("Carregue primeiro o PNG em «Minha assinatura».", "warning");
            btnUpload?.focus();
            return;
        }
        preview.hidden = false;
        document.body.classList.add("sig-preview-open");
        requestAnimationFrame(() => {
            montarFolha();
            mostrarHint();
        });
    };

    const fecharPreview = () => {
        preview.hidden = true;
        document.body.classList.remove("sig-preview-open");
        clearTimeout(hintTimer);
    };

    // Rejeitar é a única decisão negativa: exige o motivo. O técnico (vem
    // pré-seleccionado com quem criou a nota) só muda se o Aprovador quiser.
    const btnRejeitar = document.getElementById("btnRejeitar");
    btnRejeitar?.addEventListener("click", (ev) => {
        const comentario = form.querySelector('[name="comentario"]');
        if (!(comentario?.value || "").trim()) {
            ev.preventDefault();
            globalThis.showToast?.("Indique o motivo da rejeição.", "warning");
            comentario?.focus();
        }
    });

    btnAprovar?.addEventListener("click", (ev) => {
        if (confirmarAprovacao) return;
        ev.preventDefault();
        if (!gestor.assinaturaUrl) {
            globalThis.showToast?.("Carregue a sua assinatura PNG para concluir a aprovação.", "warning");
            btnUpload?.focus();
            return;
        }
        abrirPreview();
    });

    btnVoltar?.addEventListener("click", fecharPreview);
    hint?.addEventListener("click", () => hint.classList.remove("is-visible"));

    btnConfirmar?.addEventListener("click", () => {
        const box = folha?.querySelector(".sig-box");
        if (box) gravarPos(box);
        fecharPreview();
        confirmarAprovacao = true;
        const extra = document.createElement("input");
        extra.type = "hidden";
        extra.name = "aprovar";
        extra.value = "Aprovar";
        form.appendChild(extra);
        form.requestSubmit(btnAprovar);
    });
});
