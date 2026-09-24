/* Listagem de notas (saída e entrega):
 *  - lupa: mostra/oculta a área de pesquisa;
 *  - modal "Carregar nota existente": o nome é preenchido a partir do e-mail
 *    (clementina.elihud@standardbank.co.mz -> "Clementina Elihud"), com a
 *    mesma regra do formulário de nova nota; nunca por cima de um nome
 *    escrito à mão.
 */
document.addEventListener("DOMContentLoaded", () => {
    // ---- pesquisa recolhível ------------------------------------------------
    const btnPesquisa = document.getElementById("btnTogglePesquisa");
    const painel = document.getElementById("painelPesquisa");
    const sincronizar = () => {
        const aberto = !painel.hidden;
        btnPesquisa.setAttribute("aria-expanded", String(aberto));
        btnPesquisa.classList.toggle("is-active", aberto);
    };
    if (btnPesquisa && painel) {
        sincronizar();
        btnPesquisa.addEventListener("click", () => {
            painel.hidden = !painel.hidden;
            sincronizar();
            if (!painel.hidden) painel.querySelector("input, select")?.focus();
        });
    }

    // ---- nome a partir do e-mail (modal carregar nota) ----------------------
    const campoEmail = document.getElementById("carregarEmail");
    const campoNome = document.getElementById("carregarNome");
    if (!campoEmail || !campoNome) return;

    const nomeDeEmail = (email) =>
        (String(email || "").trim().split("@")[0] || "")
            .split(/[._\-+]+/)
            .filter(Boolean)
            .map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
            .join(" ");

    const atualizarNome = () => {
        const email = campoEmail.value.trim();
        if (!email.includes("@")) return;
        const atual = campoNome.value.trim();
        if (atual === "" || atual === campoNome.dataset.auto) {
            const derivado = nomeDeEmail(email);
            campoNome.value = derivado;
            campoNome.dataset.auto = derivado;
        }
    };
    campoEmail.addEventListener("input", atualizarNome);
    campoEmail.addEventListener("change", atualizarNome);
    campoNome.addEventListener("input", () => { delete campoNome.dataset.auto; });
});
