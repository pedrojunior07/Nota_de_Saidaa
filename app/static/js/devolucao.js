/* Devolução de equipamento — ícone no fim da coluna Estado (listas de notas).
 *
 *   verde (dev-nenhuma)  -> nada devolvido
 *   laranja (dev-parcial) -> parte dos itens devolvida
 *   cinzento (dev-total)  -> todos os itens devolvidos
 *
 * O ícone abre a janela: itens da nota (os já devolvidos aparecem marcados e
 * bloqueados), motivo, estado do equipamento e observação. Ao registar, só o
 * ícone dessa linha muda de cor — a página não recarrega.
 * Delegação no documento: funciona também após a paginação parcial.
 */
(() => {
    const modal = document.getElementById("devolucaoModal");
    if (!modal) return;

    const $ = (id) => document.getElementById(id);
    const form = $("devolucaoForm");
    const lista = $("devolucaoItens");
    const campos = $("devolucaoCampos");
    const erro = $("devolucaoErro");
    const guardar = $("devolucaoGuardar");
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const TITULOS = {
        nenhuma: "Registar devolução",
        parcial: "Devolução parcial — ver ou registar mais itens",
        total: "Todos os itens devolvidos",
    };
    let atual = { url: null, botao: null, modo: "itens" };

    const escapar = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    const mostrarErro = (msg) => {
        erro.textContent = msg || "";
        erro.hidden = !msg;
    };

    const opcoes = (select, valores) => {
        select.innerHTML = '<option value="" selected disabled>Seleccione…</option>'
            + valores.map((v) => `<option value="${escapar(v)}">${escapar(v)}</option>`).join("");
    };

    // ---- Notas carregadas (sem lista de itens): equipamento escrito à mão ----
    const linhaManual = (tipos) => `
        <div class="dev-manual-linha">
            <select class="form-select form-select-sm" data-campo="tipo_item" aria-label="Tipo">
                <option value="" selected disabled>Tipo…</option>
                ${tipos.map((t) => `<option value="${escapar(t)}">${escapar(t)}</option>`).join("")}
            </select>
            <input class="form-control form-control-sm" data-campo="descricao" placeholder="Descrição (ex.: Dell)" maxlength="255" aria-label="Descrição">
            <input class="form-control form-control-sm" data-campo="numero_serie" placeholder="Nº de série" maxlength="100" aria-label="Nº de série">
            <input class="form-control form-control-sm" data-campo="quantidade" type="number" min="1" value="1" aria-label="Quantidade">
            <button type="button" class="btn btn-sm btn-outline-secondary" data-dev-remover title="Remover" aria-label="Remover">
                <i class="bi bi-x-lg" aria-hidden="true"></i></button>
        </div>`;

    const desenharManual = (dados) => {
        const editavel = dados.pode_registar && !dados.completa;
        const jaDevolvidos = (dados.ja_devolvidos || []).map((i) => `
            <div class="dev-item is-devolvido">
                <span class="dev-item-texto">
                    <span><strong>${escapar(i.tipo_item)}</strong> — ${escapar(i.descricao)}</span>
                    ${i.numero_serie ? `<small>Nº série ${escapar(i.numero_serie)}</small>` : ""}
                    ${i.quantidade > 1 ? `<small>Qtd. ${i.quantidade}</small>` : ""}
                </span>
                <span class="dev-item-estado">Devolvido em ${escapar(i.data_devolucao)}</span>
            </div>`).join("");
        let html = '<p class="dev-aviso">Esta nota foi carregada a partir de um PDF e não tem a lista de equipamentos na plataforma. Indique o que está a ser devolvido.</p>';
        if (jaDevolvidos) html += jaDevolvidos;
        if (dados.completa) {
            html += '<p class="dev-aviso">A devolução desta nota está completa.</p>';
        } else if (editavel) {
            html += `<div id="devManualLinhas">${linhaManual(dados.tipos)}</div>
                <button type="button" class="btn btn-sm btn-outline-navy align-self-start" id="devManualAdicionar">
                    <i class="bi bi-plus-lg" aria-hidden="true"></i> Adicionar equipamento</button>
                <label class="dev-todos"><input type="checkbox" id="devManualCompleta"> Todo o material desta nota foi devolvido</label>`;
        }
        lista.innerHTML = html;
        campos.hidden = !editavel;
        guardar.hidden = !editavel;
        if (editavel) {
            opcoes($("devolucaoMotivo"), dados.motivos);
            opcoes($("devolucaoEstado"), dados.estados_equipamento);
            $("devolucaoObs").value = "";
            $("devManualAdicionar").addEventListener("click", () => {
                $("devManualLinhas").insertAdjacentHTML("beforeend", linhaManual(dados.tipos));
            });
        }
    };

    lista.addEventListener("click", (ev) => {
        const remover = ev.target.closest("[data-dev-remover]");
        if (!remover) return;
        const linhas = lista.querySelectorAll(".dev-manual-linha");
        if (linhas.length > 1) remover.closest(".dev-manual-linha").remove();
        else remover.closest(".dev-manual-linha").querySelectorAll("input, select").forEach((c) => {
            c.value = c.dataset.campo === "quantidade" ? "1" : "";
        });
    });

    const desenhar = (dados) => {
        $("devolucaoSubtitulo").textContent = `Nota ${dados.numero} · ${dados.colaborador || ""}`;
        atual.modo = dados.modo || "itens";
        if (atual.modo === "manual") return desenharManual(dados);
        const porDevolver = dados.itens.filter((i) => !i.devolvido);
        const editavel = dados.pode_registar && porDevolver.length > 0;

        const linhas = dados.itens.map((i) => `
            <label class="dev-item ${i.devolvido ? "is-devolvido" : ""}">
                <input type="checkbox" value="${escapar(i.id)}" ${i.devolvido ? "checked disabled" : ""} ${editavel ? "" : "disabled"}>
                <span class="dev-item-texto">
                    <span><strong>${escapar(i.tipo_item)}</strong> — ${escapar(i.descricao)}</span>
                    ${i.numero_serie ? `<small>Nº série ${escapar(i.numero_serie)}</small>` : ""}
                    ${i.quantidade > 1 ? `<small>Qtd. ${i.quantidade}</small>` : ""}
                </span>
                ${i.devolvido ? `<span class="dev-item-estado">Devolvido em ${escapar(i.data_devolucao)}</span>` : ""}
            </label>`).join("");

        const todos = editavel && porDevolver.length > 1
            ? `<label class="dev-todos"><input type="checkbox" id="devolucaoTodos"> Selecionar todos os itens por devolver</label>`
            : "";
        lista.innerHTML = (todos + linhas) || '<p class="text-muted small">Esta nota não tem itens.</p>';

        campos.hidden = !editavel;
        guardar.hidden = !editavel;
        if (editavel) {
            opcoes($("devolucaoMotivo"), dados.motivos);
            opcoes($("devolucaoEstado"), dados.estados_equipamento);
            $("devolucaoObs").value = "";
        } else if (porDevolver.length === 0 && dados.itens.length) {
            lista.insertAdjacentHTML("afterbegin", '<p class="dev-aviso">Todos os itens desta nota já foram devolvidos.</p>');
        }
        $("devolucaoTodos")?.addEventListener("change", (ev) => {
            lista.querySelectorAll('.dev-item input:not([disabled])').forEach((c) => { c.checked = ev.target.checked; });
        });
    };

    const abrir = async (botao) => {
        atual = { url: botao.dataset.devolucaoUrl, botao };
        mostrarErro("");
        lista.innerHTML = '<p class="text-muted small">A carregar…</p>';
        campos.hidden = true;
        guardar.hidden = true;
        modal.showModal();
        try {
            const resp = await fetch(atual.url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
            if (!resp.ok) throw new Error(String(resp.status));
            desenhar(await resp.json());
        } catch (_e) {
            lista.innerHTML = '<p class="dev-erro">Não foi possível carregar os itens desta nota.</p>';
        }
    };

    const atualizarIcone = (estado) => {
        const b = atual.botao;
        if (!b || !estado) return;
        b.classList.remove("dev-nenhuma", "dev-parcial", "dev-total");
        b.classList.add(`dev-${estado}`);
        b.title = TITULOS[estado];
        b.setAttribute("aria-label", TITULOS[estado]);
    };

    form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        mostrarErro("");
        const motivo = $("devolucaoMotivo").value;
        const estado = $("devolucaoEstado").value;
        const observacao = $("devolucaoObs").value.trim();
        const corpo = { motivo, estado_equipamento: estado, observacao };
        if (atual.modo === "manual") {
            const linhas = [...lista.querySelectorAll(".dev-manual-linha")].map((l) => {
                const v = (c) => l.querySelector(`[data-campo="${c}"]`).value.trim();
                return { tipo_item: v("tipo_item"), descricao: v("descricao"), numero_serie: v("numero_serie"), quantidade: v("quantidade") };
            }).filter((l) => l.tipo_item || l.descricao);
            if (!linhas.length) return mostrarErro("Acrescente pelo menos um equipamento devolvido.");
            if (linhas.some((l) => !l.tipo_item)) return mostrarErro("Escolha o tipo de cada equipamento.");
            if (linhas.some((l) => !l.descricao)) return mostrarErro("Escreva a descrição de cada equipamento.");
            corpo.itens_manuais = linhas;
            corpo.completa = $("devManualCompleta")?.checked || false;
        } else {
            corpo.itens = [...lista.querySelectorAll(".dev-item input:checked:not([disabled])")].map((c) => c.value);
            if (!corpo.itens.length) return mostrarErro("Selecione pelo menos um item.");
        }
        if (!motivo) return mostrarErro("Escolha o motivo da devolução.");
        if (!estado) return mostrarErro("Indique o estado do equipamento.");
        if (motivo === "Outro" && !observacao) return mostrarErro("Descreva o motivo na observação.");

        guardar.disabled = true;
        try {
            const resp = await fetch(atual.url, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                body: JSON.stringify(corpo),
            });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(json.error || "Não foi possível registar a devolução.");
            atualizarIcone(json.estado);
            modal.close();
            if (atual.botao?.hasAttribute("data-devolucao-recarregar")) {
                // Página de detalhe: mostrar logo o registo no painel «Devolução».
                sessionStorage.setItem("abrirPainelDevolucao", "1");
                window.location.reload();
                return;
            }
            globalThis.showToast?.(
                json.estado === "total" ? "Devolução registada: todos os itens devolvidos." : "Devolução registada.",
                "success");
        } catch (e) {
            mostrarErro(e.message);
        } finally {
            guardar.disabled = false;
        }
    });

    modal.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-dev-fechar]") || ev.target === modal) modal.close();
    });

    // Depois de registar no detalhe, reabrir o painel «Devolução».
    if (sessionStorage.getItem("abrirPainelDevolucao")) {
        sessionStorage.removeItem("abrirPainelDevolucao");
        const painel = document.getElementById("painelDevolucao");
        if (painel) { painel.open = true; painel.scrollIntoView({ block: "nearest" }); }
    }

    // O ícone está dentro de uma linha clicável: não deixar o clique abrir a nota.
    document.addEventListener("click", (ev) => {
        const botao = ev.target.closest("[data-devolucao-url]");
        if (!botao) return;
        ev.preventDefault();
        ev.stopPropagation();
        abrir(botao);
    }, true);
})();
