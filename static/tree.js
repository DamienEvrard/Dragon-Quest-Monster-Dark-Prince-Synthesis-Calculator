// Calculateur de synthese DQM - gestion des noeuds valides + arbres enregistres
// Stockage: localStorage (aucun serveur necessaire, tout reste sur le PC du joueur)

(function () {
    "use strict";

    const STORAGE_KEY = "dqm_saved_trees";

    function loadSavedTrees() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function persistSavedTrees(trees) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trees));
    }

    function getFormValues() {
        const form = document.getElementById("synth-form");
        if (!form) return null;
        return {
            monster: form.monster.value.trim(),
            talent1: form.talent1.value.trim(),
            talent2: form.talent2.value.trim(),
            talent3: form.talent3.value.trim(),
            zone: form.zone.value.trim(),
        };
    }

    function signatureOf(values) {
        return [values.monster, values.talent1, values.talent2, values.talent3, values.zone]
            .map((v) => (v || "").toLowerCase())
            .join("|");
    }

    let currentTreeId = null; // id de l'arbre en cours d'affichage, si deja enregistre

    function applyValidatedPaths(paths) {
        const set = new Set(paths || []);
        document.querySelectorAll("#tree-wrapper .node[data-path]").forEach((el) => {
            if (set.has(el.getAttribute("data-path"))) {
                el.classList.add("validated");
            }
        });
    }

    function setupNodeClicks() {
        const wrapper = document.getElementById("tree-wrapper");
        if (!wrapper) return;

        wrapper.addEventListener("click", function (evt) {
            const toggleBtn = evt.target.closest(".node-toggle");
            if (toggleBtn) {
                evt.stopPropagation();
                const node = toggleBtn.closest(".node");
                if (!node) return;
                const collapsed = node.classList.toggle("collapsed");
                toggleBtn.textContent = collapsed ? "+" : "−";
                toggleBtn.title = collapsed
                    ? "Afficher la suite de l'arbre"
                    : "Masquer la suite de l'arbre";
                return;
            }

            const card = evt.target.closest(".node-card");
            if (!card) return;
            const node = card.closest(".node");
            if (!node) return;

            node.classList.toggle("validated");

            // Auto-sauvegarde SEULEMENT si cet arbre a deja ete enregistre une fois
            if (currentTreeId) {
                const trees = loadSavedTrees();
                const entry = trees.find((t) => t.id === currentTreeId);
                if (entry) {
                    const path = node.getAttribute("data-path");
                    const idx = entry.validatedPaths.indexOf(path);
                    if (node.classList.contains("validated")) {
                        if (idx === -1) entry.validatedPaths.push(path);
                    } else {
                        if (idx !== -1) entry.validatedPaths.splice(idx, 1);
                    }
                    persistSavedTrees(trees);
                }
            }
        });
    }

    function renderSidebar() {
        const list = document.getElementById("saved-trees-list");
        if (!list) return;
        const trees = loadSavedTrees();

        if (trees.length === 0) {
            list.innerHTML = '<p class="sidebar-empty">Aucun arbre enregistré pour le moment.</p>';
            return;
        }

        list.innerHTML = "";
        trees.slice().reverse().forEach((entry) => {
            const card = document.createElement("div");
            card.className = "saved-tree-card";

            const talents = [entry.talent1, entry.talent2, entry.talent3].filter(Boolean).join(", ") || "—";
            const progress = entry.validatedPaths ? entry.validatedPaths.length : 0;

            card.innerHTML = `
                <div class="saved-tree-name">${escapeHtml(entry.monster)}</div>
                <div class="saved-tree-talents">🎯 ${escapeHtml(talents)}</div>
                <div class="saved-tree-progress">${progress} noeud(s) validé(s)</div>
                <div class="saved-tree-actions">
                    <button type="button" class="btn-load">Charger</button>
                    <button type="button" class="btn-delete">Supprimer</button>
                </div>
            `;
            card.querySelector(".btn-load").addEventListener("click", () => loadTree(entry));
            card.querySelector(".btn-delete").addEventListener("click", () => deleteTree(entry.id));
            list.appendChild(card);
        });
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    function loadTree(entry) {
        const form = document.getElementById("synth-form");
        if (!form) return;
        form.monster.value = entry.monster || "";
        form.talent1.value = entry.talent1 || "";
        form.talent2.value = entry.talent2 || "";
        form.talent3.value = entry.talent3 || "";
        form.zone.value = entry.zone || "";
        form.submit();
    }

    function deleteTree(id) {
        let trees = loadSavedTrees();
        trees = trees.filter((t) => t.id !== id);
        persistSavedTrees(trees);
        if (currentTreeId === id) currentTreeId = null;
        renderSidebar();
    }

    function setupSaveButton() {
        const btn = document.getElementById("btn-save-tree");
        if (!btn) return;

        const values = getFormValues();
        const sig = signatureOf(values);

        // Si un arbre avec la meme signature existe deja, on le reconnecte
        // automatiquement (pas besoin de re-cliquer sur Enregistrer), et on
        // restaure les noeuds valides deja enregistres.
        const trees = loadSavedTrees();
        const existing = trees.find((t) => t.signature === sig);
        if (existing) {
            currentTreeId = existing.id;
            applyValidatedPaths(existing.validatedPaths);
            btn.textContent = "✅ Arbre déjà enregistré";
            btn.disabled = true;
        }

        btn.addEventListener("click", function () {
            if (currentTreeId) return; // deja enregistre
            const newEntry = {
                id: "tree_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8),
                signature: sig,
                monster: values.monster,
                talent1: values.talent1,
                talent2: values.talent2,
                talent3: values.talent3,
                zone: values.zone,
                validatedPaths: Array.from(document.querySelectorAll("#tree-wrapper .node.validated[data-path]"))
                    .map((el) => el.getAttribute("data-path")),
                createdAt: Date.now(),
            };
            const allTrees = loadSavedTrees();
            allTrees.push(newEntry);
            persistSavedTrees(allTrees);
            currentTreeId = newEntry.id;
            btn.textContent = "✅ Arbre déjà enregistré";
            btn.disabled = true;
            renderSidebar();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupNodeClicks();
        setupSaveButton();
        renderSidebar();
    });
})();
