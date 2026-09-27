/**
 * Confirmação estilizada (usa o <dialog id="confirmModal"> do base.html) em
 * vez do confirm() nativo do browser. Devolve uma Promise<boolean>.
 *
 *   if (await confirmarAcao({ mensagem: "Remover?", rotuloAceitar: "Remover" })) ...
 */
globalThis.confirmarAcao = ({
    mensagem,
    titulo = "Confirmar eliminação",
    rotuloAceitar = "Apagar",
} = {}) => {
    const modal = document.getElementById("confirmModal");
    const elTitulo = document.getElementById("confirmModalTitle");
    const elMensagem = document.getElementById("confirmModalMessage");
    const btnAceitar = document.getElementById("confirmModalAccept");
    const btnCancelar = document.getElementById("confirmModalCancel");
    if (!modal || !elMensagem || !btnAceitar || !btnCancelar) {
        return Promise.resolve(globalThis.confirm(mensagem)); // salvaguarda
    }

    const tituloOriginal = elTitulo?.textContent;
    const rotuloOriginal = btnAceitar.textContent;
    const focoAnterior = document.activeElement;

    return new Promise((resolve) => {
        let aceite = false;
        const aoAceitar = () => {
            aceite = true;
            modal.close();
        };
        const aoCancelar = () => modal.close();
        // "close" dispara em todos os casos (aceitar, cancelar, Esc, clique
        // fora), por isso é aqui que se resolve e se limpa o estado.
        const aoFechar = () => {
            btnAceitar.removeEventListener("click", aoAceitar);
            btnCancelar.removeEventListener("click", aoCancelar);
            if (elTitulo) elTitulo.textContent = tituloOriginal;
            btnAceitar.textContent = rotuloOriginal;
            if (focoAnterior && document.contains(focoAnterior)) focoAnterior.focus();
            resolve(aceite);
        };

        if (elTitulo) elTitulo.textContent = titulo;
        elMensagem.textContent = mensagem;
        btnAceitar.textContent = rotuloAceitar;
        btnAceitar.addEventListener("click", aoAceitar);
        btnCancelar.addEventListener("click", aoCancelar);
        modal.addEventListener("close", aoFechar, { once: true });
        modal.showModal();
        btnCancelar.focus();
    });
};

document.addEventListener("DOMContentLoaded", () => {
    const confirmModal = document.getElementById("confirmModal");
    const confirmMessage = document.getElementById("confirmModalMessage");
    const confirmCancel = document.getElementById("confirmModalCancel");
    const confirmAccept = document.getElementById("confirmModalAccept");
    let pendingForm = null;
    let previousFocus = null;

    if (confirmModal) {
        document.addEventListener("submit", (event) => {
            const form = event.target.closest("form[data-confirm]");
            if (!form || pendingForm) return;
            event.preventDefault();
            pendingForm = form;
            previousFocus = document.activeElement;
            confirmMessage.textContent = form.dataset.confirm;
            confirmAccept.textContent = form.dataset.confirmLabel || "Apagar";
            confirmModal.showModal();
            confirmCancel.focus();
        });

        const closeConfirm = () => {
            if (confirmModal.open) confirmModal.close();
            if (previousFocus && document.contains(previousFocus)) previousFocus.focus();
            pendingForm = null;
            previousFocus = null;
        };

        confirmCancel.addEventListener("click", closeConfirm);
        confirmAccept.addEventListener("click", () => {
            const form = pendingForm;
            if (!form) return;
            pendingForm = null;
            confirmModal.close();
            form.submit();
        });
        confirmModal.addEventListener("click", (event) => {
            if (event.target === confirmModal) closeConfirm();
        });
        confirmModal.addEventListener("cancel", (event) => {
            event.preventDefault();
            closeConfirm();
        });
    }

    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    const toggle = document.getElementById("btnSidebar");
    const profile = document.getElementById("topbarProfile");
    const profileAvatar = document.getElementById("btnProfileAvatar");
    const profileToggle = document.getElementById("btnProfileToggle");
    const profileInfo = document.getElementById("topbarProfileInfo");

    const fechar = () => {
        sidebar?.classList.remove("open");
        backdrop?.classList.remove("show");
    };

    toggle?.addEventListener("click", () => {
        sidebar.classList.toggle("open");
        backdrop.classList.toggle("show");
    });
    backdrop?.addEventListener("click", fechar);

    const alternarPerfil = () => {
        const expandido = profile?.classList.toggle("expanded") || false;
        profileAvatar?.setAttribute("aria-expanded", String(expandido));
        profileToggle?.setAttribute("aria-expanded", String(expandido));
        profileAvatar?.setAttribute("aria-label", expandido ? "Ocultar perfil" : "Mostrar perfil");
        profileToggle?.setAttribute("aria-label", expandido ? "Ocultar perfil" : "Mostrar perfil");
        profileToggle?.setAttribute("title", expandido ? "Ocultar perfil" : "Mostrar perfil");
        profileInfo?.setAttribute("aria-hidden", String(!expandido));
    };

    profileAvatar?.addEventListener("click", alternarPerfil);
    profileToggle?.addEventListener("click", alternarPerfil);

    // Linhas de tabela clicáveis (data-href) — abrem o registo ao clicar ou Enter.
    // Delegação no documento: também funciona nas linhas que a paginação
    // parcial (mais abaixo) troca sem recarregar a página.
    document.addEventListener("click", (ev) => {
        const linha = ev.target.closest("[data-href]");
        if (!linha || ev.target.closest("a, button, input, select, label")) return;
        window.location = linha.dataset.href;
    });
    document.addEventListener("keydown", (ev) => {
        const linha = ev.target.closest?.("[data-href]");
        if (!linha || (ev.key !== "Enter" && ev.key !== " ")) return;
        ev.preventDefault();
        window.location = linha.dataset.href;
    });

    document.querySelectorAll(".folha-sig[data-left]").forEach((signature) => {
        signature.style.left = `${signature.dataset.left}%`;
        signature.style.top = `${signature.dataset.top}%`;
        signature.style.width = `${signature.dataset.width}%`;
        signature.style.height = `${signature.dataset.height}%`;
    });

    // Cache temporária dos formulários (ver nota_form.js): limpa-se ao terminar
    // sessão ou quando o utilizador autenticado muda no mesmo separador.
    const limparCacheFormularios = () => {
        try {
            Object.keys(sessionStorage)
                .filter((chave) => chave.startsWith("nds:form:"))
                .forEach((chave) => sessionStorage.removeItem(chave));
        } catch (_e) {
            /* sessionStorage indisponível */
        }
    };

    try {
        const utilizadorAtual = document.body.dataset.user || "";
        const guardado = sessionStorage.getItem("nds:user");
        if (guardado !== null && guardado !== utilizadorAtual) {
            limparCacheFormularios();
        }
        sessionStorage.setItem("nds:user", utilizadorAtual);
    } catch (_e) {
        /* ignora */
    }

    document.querySelectorAll(".sidebar-logout").forEach((link) => {
        link.addEventListener("click", limparCacheFormularios);
    });
});


/* Paginação parcial: ao mudar de página ou o nº de linhas, só o painel da
 * tabela é trocado — a página não recarrega nem se mexe. O endereço é
 * atualizado (pushState), por isso voltar/avançar e recarregar continuam a
 * funcionar. Se algo falhar, cai na navegação normal.
 */
(() => {
    const PAINEL = ".panel";
    const painelDe = (el) => el?.closest(PAINEL);

    const trocar = async (url, painel, { novoTamanho = false, historico = true } = {}) => {
        if (!painel) { window.location.href = url; return; }
        // Índice do painel entre os que têm tabela paginada (para o encontrar
        // na resposta, que tem a mesma estrutura).
        const paineis = [...document.querySelectorAll(PAINEL)].filter((p) => p.querySelector(".tabela-linhas, .historico-paginacao"));
        const indice = paineis.indexOf(painel);
        // Mantém a altura enquanto carrega e ao folhear (a última página pode ter
        // menos linhas) para nada abaixo "saltar"; ao mudar o nº de linhas, liberta.
        const altura = painel.getBoundingClientRect().height;
        painel.style.minHeight = novoTamanho ? "" : `${Math.max(altura, parseFloat(painel.style.minHeight) || 0)}px`;
        painel.classList.add("a-carregar");
        try {
            const resposta = await fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
            if (!resposta.ok || resposta.redirected) throw new Error(String(resposta.status));
            const doc = new DOMParser().parseFromString(await resposta.text(), "text/html");
            const novos = [...doc.querySelectorAll(PAINEL)].filter((p) => p.querySelector(".tabela-linhas, .historico-paginacao"));
            const novo = novos[indice];
            if (!novo) throw new Error("painel não encontrado");
            painel.innerHTML = novo.innerHTML;
            if (novoTamanho) painel.style.minHeight = "";
            if (historico) history.pushState({ paginacaoParcial: true }, "", url);
        } catch (_e) {
            window.location.href = url;
        } finally {
            painel.classList.remove("a-carregar");
        }
    };

    document.addEventListener("click", (ev) => {
        const link = ev.target.closest(".historico-paginacao a");
        if (!link || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) return;
        ev.preventDefault();
        trocar(link.href, painelDe(link));
    });

    document.addEventListener("change", (ev) => {
        const select = ev.target.closest(".tabela-linhas select");
        if (!select) return;
        ev.stopImmediatePropagation();
        trocar(new URL(select.value, location.href).href, painelDe(select), { novoTamanho: true });
    }, true);

    // Voltar/avançar do browser (e as setas do relatório) entre páginas da tabela.
    window.addEventListener("popstate", () => {
        const painel = document.querySelector(".tabela-linhas")?.closest(PAINEL)
            || document.querySelector(".historico-paginacao")?.closest(PAINEL);
        if (painel) trocar(location.href, painel, { historico: false });
        else window.location.reload();
    });
})();
