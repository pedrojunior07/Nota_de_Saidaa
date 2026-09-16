/* Campo "Para (e-mail)" da Nota de Saída.
 *
 * 1) Autocomplete: enquanto se escreve, sugere e-mails do diretório da
 *    instituição (endpoint /notas/diretorio/pesquisar — simulado até haver
 *    acesso ao Active Directory; muda-se só o backend com DIRECTORY_MODE=ldap).
 * 2) Nome automático: assim que há um e-mail @<dominio>, o "Nome do colaborador"
 *    é preenchido a partir da parte antes do "@"
 *    (clementina.elihud@standardbank.co.mz  ->  "Clementina Elihud").
 *    Só preenche se o campo estiver vazio ou ainda com um valor automático —
 *    nunca por cima de um nome escrito à mão.
 */
document.addEventListener("DOMContentLoaded", () => {
    const raiz = document.getElementById("destinatario");
    const campoEmail = document.getElementById("email_funcionario");
    const campoNome = document.getElementById("funcionario");
    const campoDep = document.getElementById("departamento");
    if (!raiz || !campoEmail || !campoNome) return;

    const url = raiz.dataset.searchUrl;
    const lista = document.getElementById("destinatarioResultados");
    const form = document.getElementById("formNota");

    let timer;
    let ultimoTermo = null;
    let activeIndex = -1;

    // ---- nome a partir do e-mail -------------------------------------------
    const nomeDeEmail = (email) => {
        const local = String(email || "").trim().split("@")[0] || "";
        return local
            .split(/[._\-+]+/)
            .filter(Boolean)
            .map((parte) => parte.charAt(0).toUpperCase() + parte.slice(1).toLowerCase())
            .join(" ")
            .trim();
    };

    const preencherNomeSePossivel = (email) => {
        const derivado = nomeDeEmail(email);
        if (!derivado) return;
        const atual = campoNome.value.trim();
        if (atual === "" || atual === campoNome.dataset.auto) {
            campoNome.value = derivado;
            campoNome.dataset.auto = derivado;
            form?.dispatchEvent(new Event("change"));
        }
    };

    const preencherDepSePossivel = (departamento) => {
        if (!departamento || !campoDep) return;
        const atual = campoDep.value.trim();
        if (atual === "" || atual === campoDep.dataset.auto) {
            campoDep.value = departamento;
            campoDep.dataset.auto = departamento;
        }
    };

    // se o utilizador editar o nome/departamento à mão, deixa de ser automático
    campoNome.addEventListener("input", () => { delete campoNome.dataset.auto; });
    campoDep?.addEventListener("input", () => { delete campoDep.dataset.auto; });

    campoEmail.addEventListener("change", () => {
        fecharLista();
        if (/^\S+@\S+\.\S+$/.test(campoEmail.value.trim())) preencherNomeSePossivel(campoEmail.value);
    });

    // ---- autocomplete -----------------------------------------------------
    const escape = (s) =>
        String(s || "").replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[c]));

    const fecharLista = () => {
        if (!lista) return;
        lista.hidden = true;
        lista.innerHTML = "";
        activeIndex = -1;
        campoEmail.setAttribute("aria-expanded", "false");
    };

    const escolher = (pessoa) => {
        campoEmail.value = pessoa.email || "";
        delete campoNome.dataset.auto;          // vamos repor o automático a seguir
        campoNome.value = "";
        preencherNomeSePossivel(pessoa.email);
        preencherDepSePossivel(pessoa.departamento);
        campoEmail.classList.remove("is-invalid");
        fecharLista();
        form?.dispatchEvent(new Event("change"));
        campoEmail.focus();
    };

    const render = (itens) => {
        if (!lista) return;
        activeIndex = -1;
        if (!itens.length) {
            lista.innerHTML = '<div class="destinatario-vazio">Sem resultados no diretório.</div>';
        } else {
            lista.innerHTML = itens
                .map(
                    (p, i) => `
                <button type="button" class="destinatario-item" role="option" data-i="${i}">
                    <span class="destinatario-item-txt">
                        <strong>${escape(p.email)}</strong>
                        <span>${escape(p.nome)}${p.departamento ? " · " + escape(p.departamento) : ""}</span>
                    </span>
                </button>`
                )
                .join("");
            lista.querySelectorAll(".destinatario-item").forEach((b) => {
                b.addEventListener("mousedown", (e) => e.preventDefault()); // não perder o foco
                b.addEventListener("click", () => escolher(itens[Number(b.dataset.i)]));
            });
        }
        lista.hidden = false;
        campoEmail.setAttribute("aria-expanded", "true");
    };

    const pesquisar = async (termo) => {
        try {
            const r = await fetch(`${url}?q=${encodeURIComponent(termo)}`, {
                headers: { "X-Requested-With": "fetch" },
            });
            const dados = r.ok ? await r.json() : { resultados: [] };
            if (campoEmail.value.trim() === termo) render(dados.resultados || []);
        } catch (_e) {
            fecharLista();
        }
    };

    campoEmail.addEventListener("input", () => {
        const termo = campoEmail.value.trim();
        clearTimeout(timer);
        if (termo.length < 2) { fecharLista(); return; }
        if (termo === ultimoTermo) return;
        ultimoTermo = termo;
        timer = setTimeout(() => pesquisar(termo), 250);
    });

    campoEmail.addEventListener("keydown", (e) => {
        const itens = lista ? lista.querySelectorAll(".destinatario-item") : [];
        if (!lista || lista.hidden || !itens.length) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, itens.length - 1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
        } else if (e.key === "Enter" && activeIndex >= 0) {
            e.preventDefault();
            itens[activeIndex].click();
            return;
        } else if (e.key === "Escape") {
            fecharLista();
            return;
        } else {
            return;
        }
        itens.forEach((b, i) => b.classList.toggle("is-active", i === activeIndex));
        itens[activeIndex]?.scrollIntoView({ block: "nearest" });
    });

    document.addEventListener("click", (e) => {
        if (!raiz.contains(e.target)) fecharLista();
    });

    // Estado inicial: nota em edição / rascunho restaurado já com e-mail mas sem
    // nome — deriva-o. (nota_form.js corre antes deste script.)
    if (campoEmail.value.trim() && !campoNome.value.trim()) {
        preencherNomeSePossivel(campoEmail.value);
    }
});
