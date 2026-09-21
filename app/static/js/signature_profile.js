/* Gerir a assinatura pessoal reutilizável (desenhar / carregar / apagar),
 * sem workflow de posicionamento — para páginas onde só interessa definir
 * ou ver essa assinatura (ex.: formulário de criar/editar Nota de
 * Entrega). A posição sobre o documento impresso é definida à parte, na
 * página de detalhe da nota (tal como já acontece com a Nota de Saída).
 *
 * O bloco em si (desenhar/carregar/apagar) vive em
 * signature_perfil_manager.js, partilhado com signature_aprovacao.js e
 * signature_placement.js.
 */
document.addEventListener("DOMContentLoaded", () => {
    const metaEl = document.getElementById("perfilAssinaturaMeta");
    if (!metaEl) return;
    const meta = JSON.parse(metaEl.textContent);
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

    globalThis.GestorAssinaturaPerfil.criar({ meta, csrf, incluirNotaId: false });
});
