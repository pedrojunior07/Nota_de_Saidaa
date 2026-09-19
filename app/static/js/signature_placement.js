document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("formNota");
    const metaEl = document.getElementById("notaPreviewMeta");
    const inputFile = document.getElementById("inputAssinatura");
    const btnUpload = document.getElementById("btnUploadAssinatura");
    const btnDesenhar = document.getElementById("btnDesenharAssinatura");
    const slot = document.getElementById("sigSlot");
    const preview = document.getElementById("sigPreview");
    const folha = document.getElementById("sigFolha");
    const hint = document.getElementById("sigHint");
    const btnSubmeter = document.getElementById("btnSubmeter");
    const btnVoltar = document.getElementById("sigVoltar");
    const btnConfirmar = document.getElementById("sigConfirmar");
    const csrf = form?.querySelector('input[name="csrf_token"]')?.value || "";
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));

    if (!form || !metaEl) return;
    const meta = JSON.parse(metaEl.textContent);
    let assinaturaUrl = meta.assinaturaUrl;
    let hintTimer = null;
    let confirmarSubmissao = false;

    // A assinatura «Entregue Por» só pode ocupar a sua área do documento.
    const PAPEL = "entregue";
    const Zonas = window.SignatureZones;
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

    const campo = (nome) => form.querySelector(`[name="${nome}"]`);
    const valorPos = (id) => parseFloat(document.getElementById(id).value) || 0;
    const gravarPos = (box) => {
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

    const atualizarSlot = (url) => {
        assinaturaUrl = url || null;
        const wrap = document.getElementById("sigThumbWrap");
        if (url) {
            slot?.classList.add("has-signature");
            wrap.innerHTML = `
                <img src="${url}" alt="Minha assinatura" class="sig-thumb">
                <button type="button" class="sig-delete-btn" id="btnApagarAssinatura" title="Eliminar assinatura" aria-label="Eliminar assinatura">
                    <i class="bi bi-trash"></i>
                </button>`;
            ligarApagar();
        } else {
            slot?.classList.remove("has-signature");
            wrap.innerHTML = "";
            if (inputFile) inputFile.value = "";
        }
    };

    const ligarApagar = () => {
        document.getElementById("btnApagarAssinatura")?.addEventListener("click", () => {
            const confirmModal = document.getElementById("confirmModal");
            const confirmMessage = document.getElementById("confirmModalMessage");
            const confirmAccept = document.getElementById("confirmModalAccept");
            const confirmCancel = document.getElementById("confirmModalCancel");
            if (!confirmModal || !confirmMessage || !confirmAccept || !confirmCancel) return;
            confirmMessage.textContent = "Eliminar a assinatura deste perfil?";
            confirmModal.showModal();
            confirmCancel.onclick = () => confirmModal.close();
            confirmAccept.onclick = async () => {
                confirmModal.close();
                const dados = new FormData();
                dados.append("csrf_token", csrf);
                if (meta.notaId) dados.append("nota_id", meta.notaId);
                try {
                    const res = await fetch(meta.deleteUrl, { method: "POST", headers: { "X-CSRFToken": csrf }, body: dados });
                    const json = await res.json();
                    if (!res.ok || !json.ok) {
                        window.showToast?.(json.error || "Não foi possível eliminar a assinatura.", "danger");
                        return;
                    }
                    atualizarSlot(null);
                } catch (_err) {
                    window.showToast?.("Falha de rede ao eliminar a assinatura.", "danger");
                }
            };
            confirmCancel.focus();
        });
    };

    btnUpload?.addEventListener("click", () => {
        if (assinaturaUrl) return;
        inputFile?.click();
    });
    btnDesenhar?.addEventListener("click", () => {
        if (assinaturaUrl) return;
        window.SignatureCanvasModal?.abrir({
            titulo: "Desenhar assinatura",
            ajuda: "Assine no retângulo acima. Fica guardada no seu perfil para reutilizar noutras notas.",
            aoGuardar: async (imagem) => {
                try {
                    const res = await fetch(meta.uploadUrl, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                        body: JSON.stringify({ imagem, nota_id: meta.notaId }),
                    });
                    const json = await res.json().catch(() => ({}));
                    if (!res.ok || !json.ok) {
                        window.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                        return;
                    }
                    atualizarSlot(json.url);
                    window.showToast?.("Assinatura guardada.", "success");
                } catch (_err) {
                    window.showToast?.("Falha de rede ao guardar a assinatura.", "danger");
                }
            },
        });
    });

    ligarApagar();

    inputFile?.addEventListener("change", async () => {
        const ficheiro = inputFile.files[0];
        if (!ficheiro) return;
        if (assinaturaUrl) {
            alert("Já existe uma assinatura neste perfil. Elimine-a para carregar outra.");
            inputFile.value = "";
            return;
        }
        if (ficheiro.type !== "image/png") {
            alert("A assinatura deve ser um ficheiro PNG.");
            inputFile.value = "";
            return;
        }
        const dados = new FormData();
        dados.append("signature", ficheiro);
        dados.append("csrf_token", csrf);
        if (meta.notaId) dados.append("nota_id", meta.notaId);
        try {
            const res = await fetch(meta.uploadUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrf },
                body: dados,
            });
            const json = await res.json();
            if (!res.ok || !json.ok) {
                alert(json.error || "Não foi possível guardar a assinatura.");
                inputFile.value = "";
                return;
            }
            atualizarSlot(json.url);
        } catch (_err) {
            alert("Falha de rede ao guardar a assinatura.");
        }
    });

    const itensHtml = () => {
        const linhas = [];
        form.querySelectorAll(".linha-item").forEach((linha) => {
            const qtd = linha.querySelector('[name="quantidade"]')?.value || "1";
            const desc = (linha.querySelector('[name="descricao_item"]')?.value || "").trim();
            const serie = (linha.querySelector('[name="numero_serie"]')?.value || "").trim();
            const sap = (linha.querySelector('[name="numero_sap"]')?.value || "").trim();
            if (!desc) return;
        let texto = serie ? `${desc}:${serie}` : desc;
        if (sap) texto += ` (SAP: ${sap})`;
        const q = String(Math.max(1, parseInt(qtd, 10) || 1)).padStart(2, "0");
        linhas.push(`<li><span>${esc(q)} ${esc(texto)}</span></li>`);
        });
        return linhas.join("") || "<li><span>—</span></li>";
    };

    const numeroRemedy = () => {
        const digitos = (campo("numero_referencia")?.value || "").replace(/\D/g, "");
        return `REQ${digitos}`;
    };

    const formatarData = (iso) => {
        if (!iso) return "";
        const [y, m, d] = iso.split("-");
        return `${d}/${m}/${String(y).slice(-2)}`;
    };

    const gridAssinaturasHtml = (nomeRecebido, nomeEntregue) => {
        const nomes = {
            aprovador: "", recebido: nomeRecebido || "",
            entregue: nomeEntregue || "", seguranca: "",
        };
        const campos = Zonas ? Zonas.CAMPOS : {};
        const lw = Zonas ? Zonas.LINHA_LARGURA : 32;
        let out = '<div class="folha-assinaturas">';
        for (const [papel, c] of Object.entries(campos)) {
            const esqPct = c.cx - lw / 2;
            out += `<span class="folha-campo-rotulo" style="left:${esqPct}%;width:${lw}%;top:${c.rotuloY}%">${esc(c.rotulo)}</span>`
                + `<span class="folha-campo-linha" style="left:${esqPct}%;width:${lw}%;top:${c.linhaY}%"></span>`;
            if (nomes[papel]) {
                out += `<span class="folha-campo-nome" style="left:${esqPct}%;width:${lw}%;top:${c.nomeY}%">${esc(nomes[papel])}</span>`;
            }
        }
        return out + "</div>";
    };

    const montarFolha = () => {
        const origem = campo("origem_local")?.value || "";
        const email = campo("email_funcionario")?.value || "";
        const nome = campo("funcionario")?.value || "";
        const local = campo("local_emissao")?.value || "";
        const data = formatarData(campo("data_emissao")?.value);
        const nota = campo("observacao")?.value || "";
        const motivo = campo("motivo")?.value || "";
        folha.innerHTML = `
            <div class="folha-corpo">
            <header class="folha-banner">
                <img src="/static/assets/logo_std_stacked%20-%20Cropped.png" alt="Standard Bank">
                <strong>Nota de Saida - Direção de Informática</strong>
            </header>
            <section class="folha-identificacao">
                <p class="folha-linha"><strong>De: ${esc(origem)}</strong></p>
                <p class="folha-linha"><strong>Para: ${esc(email)}</strong></p>
            </section>
            <p class="folha-ref">
                <strong>Nr. Ref.${esc(meta.nrRef)}</strong>
                <span>${esc(local)}, aos ${esc(data)}</span>
            </p>
            <p class="folha-remedy">${esc(numeroRemedy())}</p>
            <h3 class="folha-assunto">ASSUNTO: Nota de Saída</h3>
            <p class="folha-intro">Vimos pela presente nota fazer entrega do seguinte material</p>
            <section class="folha-materiais">
                <div class="folha-cols"><span>Quantidade</span><span>Descrição</span></div>
                <ul class="folha-itens">${itensHtml()}</ul>
            </section>
            <p class="folha-nota-campo">Nota: ${esc(nota)}</p>
            <p class="folha-motivo">Motivo: ${esc(motivo || "Atribuição")}</p>
            </div>
            ${gridAssinaturasHtml(nome, meta.criador)}
        `;
        const box = document.createElement("div");
        box.className = "sig-box";
        let seed = { x: valorPos("assinatura_x"), y: valorPos("assinatura_y"), w: valorPos("assinatura_w"), h: valorPos("assinatura_h") };
        if (Zonas) seed = Zonas.enquadrar(PAPEL, seed);
        box.style.left = `${seed.x}%`;
        box.style.top = `${seed.y}%`;
        box.style.width = `${seed.w}%`;
        box.style.height = `${seed.h}%`;
        box.innerHTML = `
            <img src="${assinaturaUrl}" alt="Minha assinatura">
            <span class="sig-handle nw" data-handle="nw"></span>
            <span class="sig-handle ne" data-handle="ne"></span>
            <span class="sig-handle sw" data-handle="sw"></span>
            <span class="sig-handle se" data-handle="se"></span>
        `;
        folha.appendChild(box);
        ativarArrasto(box);
    };

    const ativarArrasto = (box) => {
        let modo = null;
        let start = {};

        const onMove = (ev) => {
            if (!modo) return;
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
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
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
            window.addEventListener("pointermove", onMove);
            window.addEventListener("pointerup", onUp);
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

    const mostrarHint = () => {
        hint.hidden = false;
        hint.classList.add("is-visible");
        clearTimeout(hintTimer);
        hintTimer = setTimeout(() => hint.classList.remove("is-visible"), 5000);
    };

    const abrirPreview = () => {
        if (!assinaturaUrl) {
            alert("Carregue primeiro o PNG em «Minha assinatura».");
            inputFile?.click();
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

    btnSubmeter?.addEventListener("click", (ev) => {
        if (confirmarSubmissao) return;
        ev.preventDefault();
        if (!form.reportValidity()) return;
        if (!assinaturaUrl) {
            confirmarSubmissao = true;
            form.requestSubmit(btnSubmeter);
            return;
        }
        abrirPreview();
    });

    btnVoltar?.addEventListener("click", fecharPreview);
    hint?.addEventListener("click", () => hint.classList.remove("is-visible"));

    btnConfirmar?.addEventListener("click", () => {
        if (!assinaturaUrl) {
            window.showToast?.("Carregue a sua assinatura PNG antes de confirmar.", "danger");
            inputFile?.click();
            return;
        }
        if (!form.reportValidity()) return;
        const box = folha.querySelector(".sig-box");
        if (box) gravarPos(box);
        fecharPreview();
        confirmarSubmissao = true;
        const extra = document.createElement("input");
        extra.type = "hidden";
        extra.name = "submeter";
        extra.value = "Submeter para aprovação";
        form.appendChild(extra);
        form.requestSubmit(btnSubmeter);
    });
});
