/* Gerir a assinatura pessoal reutilizável (desenhar / carregar / apagar),
 * sem workflow de posicionamento — para páginas onde só interessa definir
 * ou ver essa assinatura (ex.: formulário de criar/editar Nota de
 * Entrega). A posição sobre o documento impresso é definida à parte, na
 * página de detalhe da nota (tal como já acontece com a Nota de Saída).
 */
document.addEventListener("DOMContentLoaded", () => {
    const metaEl = document.getElementById("perfilAssinaturaMeta");
    if (!metaEl) return;
    const meta = JSON.parse(metaEl.textContent);

    const slot = document.getElementById("sigSlot");
    const inputFile = document.getElementById("inputAssinatura");
    const btnUpload = document.getElementById("btnUploadAssinatura");
    const btnDesenhar = document.getElementById("btnDesenharAssinatura");
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

    let assinaturaUrl = meta.assinaturaUrl;

    const atualizarSlot = (url) => {
        assinaturaUrl = url || null;
        const wrap = document.getElementById("sigThumbWrap");
        if (!wrap) return;
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
                try {
                    const res = await fetch(meta.deleteUrl, {
                        method: "POST",
                        headers: { "X-CSRFToken": csrf },
                        body: new URLSearchParams({ csrf_token: csrf }),
                    });
                    const json = await res.json().catch(() => ({}));
                    if (!res.ok || !json.ok) {
                        globalThis.showToast?.(json.error || "Não foi possível eliminar a assinatura.", "danger");
                        return;
                    }
                    atualizarSlot(null);
                    globalThis.showToast?.("Assinatura eliminada.", "info");
                } catch (error_) {
                    console.error(error_);
                    globalThis.showToast?.("Falha de rede ao eliminar a assinatura.", "danger");
                }
            };
            confirmCancel.focus();
        });
    };
    ligarApagar();

    btnUpload?.addEventListener("click", () => {
        if (assinaturaUrl) return;
        inputFile?.click();
    });

    btnDesenhar?.addEventListener("click", () => {
        if (assinaturaUrl) return;
        globalThis.SignatureCanvasModal?.abrir({
            titulo: "Desenhar assinatura",
            ajuda: "Assine no retângulo acima. Fica guardada no seu perfil para reutilizar noutras notas.",
            aoGuardar: async (imagem) => {
                try {
                    const res = await fetch(meta.uploadUrl, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                        body: JSON.stringify({ imagem }),
                    });
                    const json = await res.json().catch(() => ({}));
                    if (!res.ok || !json.ok) {
                        globalThis.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                        return;
                    }
                    atualizarSlot(`${json.url}?t=${Date.now()}`);
                    globalThis.showToast?.("Assinatura guardada.", "success");
                } catch (error_) {
                    console.error(error_);
                    globalThis.showToast?.("Falha de rede ao guardar a assinatura.", "danger");
                }
            },
        });
    });

    inputFile?.addEventListener("change", async () => {
        const ficheiro = inputFile.files?.[0];
        if (!ficheiro) return;
        if (assinaturaUrl) {
            globalThis.showToast?.("Já existe uma assinatura neste perfil. Elimine-a para carregar outra.", "warning");
            inputFile.value = "";
            return;
        }
        if (ficheiro.type !== "image/png") {
            globalThis.showToast?.("A assinatura deve ser um ficheiro PNG.", "warning");
            inputFile.value = "";
            return;
        }
        const dados = new FormData();
        dados.append("signature", ficheiro);
        try {
            const res = await fetch(meta.uploadUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrf },
                body: dados,
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
                globalThis.showToast?.(json.error || "Não foi possível guardar a assinatura.", "danger");
                inputFile.value = "";
                return;
            }
            atualizarSlot(`${json.url}?t=${Date.now()}`);
            globalThis.showToast?.("Assinatura guardada.", "success");
        } catch (error_) {
            console.error(error_);
            globalThis.showToast?.("Falha de rede ao guardar a assinatura.", "danger");
            inputFile.value = "";
        }
    });
});
