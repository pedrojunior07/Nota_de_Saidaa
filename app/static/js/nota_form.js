document.addEventListener("DOMContentLoaded", () => {
    const tabelaEl = document.getElementById("tabelaItens");
    const tabela = tabelaEl?.querySelector("tbody");
    const form = document.getElementById("formNota");
    const tpl = document.getElementById("tplItem");
    const btnAdd = document.getElementById("btnAddItem");
    const scrollArea = document.querySelector(".nota-form-scroll");
    const scrollHint = document.getElementById("notaScrollHint");

    // Tipos de item que também aceitam número de SAP (opcional). Vem do
    // servidor (TIPOS_ITEM_COM_SAP) via data-attribute; hard-coded como
    // salvaguarda caso o atributo não exista.
    let TIPOS_COM_SAP = ["Computador Portátil", "Computador Desktop", "PC", "Monitor"];
    try {
        const dados = JSON.parse(tabelaEl?.dataset.tiposSap || "null");
        if (Array.isArray(dados) && dados.length) TIPOS_COM_SAP = dados;
    } catch (_e) {
        /* usa a salvaguarda */
    }

    const alternarSap = (linha) => {
        const tipo = linha.querySelector('[name="tipo_item"]');
        const sap = linha.querySelector('[name="numero_sap"]');
        if (!tipo || !sap) return;
        // Usa readOnly (não disabled): um campo disabled não é enviado no
        // submit do formulário, o que desalinharia as listas paralelas de
        // itens lidas no servidor (extrair_itens).
        const aplica = TIPOS_COM_SAP.includes(tipo.value);
        sap.readOnly = !aplica;
        sap.classList.toggle("is-na", !aplica);
        sap.placeholder = aplica ? "Ex.: SAP-00123" : "Não aplicável";
        if (!aplica) sap.value = "";
    };

    const ligarTipo = (linha) => {
        const tipo = linha.querySelector('[name="tipo_item"]');
        tipo?.addEventListener("change", () => alternarSap(linha));
        alternarSap(linha);
    };

    const atualizarSeta = () => {
        if (!scrollArea || !scrollHint) return;
        const maxScroll = scrollArea.scrollHeight - scrollArea.clientHeight;
        const noFim = maxScroll > 4 && scrollArea.scrollTop >= maxScroll - 4;
        scrollHint.hidden = form ? form.checkValidity() : false;
        scrollHint.classList.toggle("is-up", noFim);
        scrollHint.setAttribute("aria-label", noFim ? "Voltar ao início do formulário" : "Descer no formulário");
        scrollHint.title = noFim ? "Voltar ao início do formulário" : "Descer no formulário";
    };

    // Motivo "Outro" -> mostra o campo para especificar
    const selMotivo = document.getElementById("motivo");
    const wrapOutro = document.getElementById("motivoOutroWrap");
    const inpOutro = document.getElementById("motivo_outro");
    const alternarOutro = () => {
        if (!selMotivo || !wrapOutro) return;
        const eOutro = selMotivo.value === "Outro";
        wrapOutro.hidden = !eOutro;
        if (inpOutro) {
            inpOutro.required = eOutro;
            if (!eOutro) inpOutro.value = "";
        }
        requestAnimationFrame(atualizarSeta);
    };
    selMotivo?.addEventListener("change", alternarOutro);
    alternarOutro();

    scrollArea?.addEventListener("scroll", atualizarSeta, { passive: true });
    scrollHint?.addEventListener("click", () => {
        if (!scrollArea) return;
        const maxScroll = scrollArea.scrollHeight - scrollArea.clientHeight;
        const noFim = scrollArea.scrollTop >= maxScroll - 4;
        scrollArea.scrollTo({ top: noFim ? 0 : maxScroll, behavior: "smooth" });
    });
    window.addEventListener("resize", atualizarSeta);
    form?.addEventListener("input", atualizarSeta);
    form?.addEventListener("change", atualizarSeta);
    atualizarSeta();

    const ligarRemocao = (linha) => {
        linha.querySelector(".btn-remove")?.addEventListener("click", () => {
            if (tabela.querySelectorAll(".linha-item").length === 1) {
                linha.querySelectorAll("input, select").forEach((campo) => {
                    if (campo.name === "quantidade") campo.value = 1;
                    else if (campo.name === "tipo_item") campo.value = "Outro";
                    else campo.value = "";
                });
                alternarSap(linha);
                requestAnimationFrame(atualizarSeta);
                guardarRascunhoLocal();
                return;
            }
            linha.remove();
            requestAnimationFrame(atualizarSeta);
            guardarRascunhoLocal();
        });
    };

    tabela?.querySelectorAll(".linha-item").forEach((linha) => {
        ligarRemocao(linha);
        ligarTipo(linha);
    });

    btnAdd?.addEventListener("click", () => {
        const linha = tpl.content.firstElementChild.cloneNode(true);
        tabela.appendChild(linha);
        ligarRemocao(linha);
        ligarTipo(linha);
        requestAnimationFrame(atualizarSeta);
        guardarRascunhoLocal();
    });

    // -----------------------------------------------------------------
    // Persistência temporária dos campos (só durante a sessão do browser)
    //
    // Guarda o que o utilizador escreveu em sessionStorage para não se
    // perder ao navegar para outra página. NÃO é um rascunho no servidor:
    // desaparece ao fechar o separador/browser ou ao terminar a sessão
    // (ver limparCacheFormularios() em app.js, ligado ao botão "Sair").
    // -----------------------------------------------------------------
    const CHAVE = "nds:form:" + window.location.pathname;
    const IGNORAR = new Set(["csrf_token", "guardar", "submeter"]);

    const camposSimples = () =>
        Array.from(form?.querySelectorAll("input, select, textarea") || []).filter((el) => {
            if (!el.name || IGNORAR.has(el.name)) return false;
            if (el.type === "file" || el.type === "hidden") return false;
            if (el.closest(".linha-item")) return false;
            return true;
        });

    const lerItens = () =>
        Array.from(tabela?.querySelectorAll(".linha-item") || []).map((linha) => ({
            tipo_item: linha.querySelector('[name="tipo_item"]')?.value || "Outro",
            quantidade: linha.querySelector('[name="quantidade"]')?.value || "1",
            descricao_item: linha.querySelector('[name="descricao_item"]')?.value || "",
            numero_serie: linha.querySelector('[name="numero_serie"]')?.value || "",
            numero_sap: linha.querySelector('[name="numero_sap"]')?.value || "",
        }));

    function guardarRascunhoLocal() {
        if (!form) return;
        try {
            const dados = { campos: {}, itens: lerItens(), ts: Date.now() };
            camposSimples().forEach((el) => {
                dados.campos[el.name] = el.value;
            });
            const temConteudo =
                Object.values(dados.campos).some((v) => v && v.trim() !== "") ||
                dados.itens.some((it) => it.descricao_item || it.numero_serie);
            if (temConteudo) {
                sessionStorage.setItem(CHAVE, JSON.stringify(dados));
            } else {
                sessionStorage.removeItem(CHAVE);
            }
        } catch (_e) {
            /* sessionStorage indisponível — ignora */
        }
    }

    function restaurarRascunhoLocal() {
        if (!form) return;
        let dados;
        try {
            dados = JSON.parse(sessionStorage.getItem(CHAVE) || "null");
        } catch (_e) {
            dados = null;
        }
        if (!dados) return;

        camposSimples().forEach((el) => {
            const valor = dados.campos?.[el.name];
            if (valor !== undefined && valor !== null) el.value = valor;
        });

        if (Array.isArray(dados.itens) && dados.itens.length && tabela && tpl) {
            tabela.querySelectorAll(".linha-item").forEach((l) => l.remove());
            dados.itens.forEach((it) => {
                const linha = tpl.content.firstElementChild.cloneNode(true);
                const set = (nome, v) => {
                    const campo = linha.querySelector(`[name="${nome}"]`);
                    if (campo) campo.value = v;
                };
                set("tipo_item", it.tipo_item || "Outro");
                set("quantidade", it.quantidade || "1");
                set("descricao_item", it.descricao_item || "");
                set("numero_serie", it.numero_serie || "");
                set("numero_sap", it.numero_sap || "");
                tabela.appendChild(linha);
                ligarRemocao(linha);
                ligarTipo(linha);
            });
        }
        requestAnimationFrame(atualizarSeta);
    }

    let temporizador;
    form?.addEventListener("input", () => {
        clearTimeout(temporizador);
        temporizador = setTimeout(guardarRascunhoLocal, 400);
    });
    form?.addEventListener("change", guardarRascunhoLocal);
    form?.addEventListener("submit", () => {
        try {
            sessionStorage.removeItem(CHAVE);
        } catch (_e) {
            /* ignora */
        }
    });

    restaurarRascunhoLocal();
    alternarOutro();  // caso o rascunho restaurado traga o motivo "Outro"
});
