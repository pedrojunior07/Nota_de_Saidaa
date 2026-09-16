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
    document.querySelectorAll("[data-href]").forEach((linha) => {
        const irPara = () => { window.location = linha.dataset.href; };
        linha.addEventListener("click", (ev) => {
            if (ev.target.closest("a, button")) return;
            irPara();
        });
        linha.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                irPara();
            }
        });
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
