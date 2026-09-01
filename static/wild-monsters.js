// Calculateur de synthese DQM - liste des monstres disponibles dans la nature
// Stockage: localStorage (aucun serveur necessaire, persiste entre les sessions
// et entre les zones - c'est une preference generale du joueur, pas liee a une
// zone en particulier).

(function () {
    "use strict";

    const STORAGE_KEY = "dqm_excluded_wild_monsters";

    function loadExcluded() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? new Set(JSON.parse(raw)) : new Set();
        } catch (e) {
            return new Set();
        }
    }

    function persistExcluded(set) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
        } catch (e) {
            // stockage indisponible (navigation privee, quota...) : on ignore,
            // la selection reste active pour la session en cours seulement.
        }
    }

    let excluded = loadExcluded();
    let currentData = [];

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    function updateHiddenField() {
        const input = document.getElementById("excluded_wild");
        if (input) input.value = Array.from(excluded).join(",");
    }

    function updateCount(total) {
        const el = document.getElementById("wild-monsters-count");
        if (el) el.textContent = `${total - excluded.size} / ${total} sélectionné(s)`;
    }

    function render() {
        const grid = document.getElementById("wild-monsters-grid");
        if (!grid) return;

        if (!currentData.length) {
            grid.innerHTML = '<p class="sidebar-empty">Aucun monstre sauvage connu pour cette zone.</p>';
            updateCount(0);
            updateHiddenField();
            return;
        }

        let html = "";
        let lastFamily = null;
        currentData.forEach((m) => {
            if (m.family !== lastFamily) {
                html += `<div class="wild-monsters-family">${escapeHtml(m.family)}</div>`;
                lastFamily = m.family;
            }
            const id = String(m.id);
            const checked = excluded.has(id) ? "" : "checked";
            const icon = m.icon
                ? `<img class="monster-icon" src="/static/icons/${m.icon}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`
                : '<img class="monster-icon" src="/static/icons/unknown-thumb.png" alt="" loading="lazy">';
            html += `
                <label class="wild-monster-item">
                    <input type="checkbox" data-id="${id}" ${checked}>
                    ${icon}
                    <span class="wild-monster-name">${escapeHtml(m.name)}</span>
                    <span class="wild-monster-rank dim">${escapeHtml(m.rank)}</span>
                </label>
            `;
        });
        grid.innerHTML = html;
        updateCount(currentData.length);
        updateHiddenField();

        grid.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
            cb.addEventListener("change", function () {
                const id = this.getAttribute("data-id");
                if (this.checked) {
                    excluded.delete(id);
                } else {
                    excluded.add(id);
                }
                persistExcluded(excluded);
                updateCount(currentData.length);
                updateHiddenField();
            });
        });
    }

    function fetchAndRender(zone) {
        const grid = document.getElementById("wild-monsters-grid");
        if (grid) grid.innerHTML = '<p class="sidebar-empty">Chargement…</p>';
        fetch("/api/monstres-sauvages?zone=" + encodeURIComponent(zone || ""))
            .then((r) => r.json())
            .then((data) => {
                currentData = data;
                render();
            })
            .catch(() => {
                if (grid) grid.innerHTML = '<p class="sidebar-empty">Erreur de chargement de la liste.</p>';
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const zoneField = document.getElementById("zone");
        fetchAndRender(zoneField ? zoneField.value : "");

        if (zoneField) {
            let debounceTimer = null;
            zoneField.addEventListener("input", function () {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => fetchAndRender(zoneField.value), 400);
            });
        }

        const checkAllBtn = document.getElementById("wild-check-all");
        const uncheckAllBtn = document.getElementById("wild-uncheck-all");

        if (checkAllBtn) {
            checkAllBtn.addEventListener("click", function () {
                excluded.clear();
                persistExcluded(excluded);
                render();
            });
        }
        if (uncheckAllBtn) {
            uncheckAllBtn.addEventListener("click", function () {
                currentData.forEach((m) => excluded.add(String(m.id)));
                persistExcluded(excluded);
                render();
            });
        }

        // S'assure que le champ cache est a jour meme si aucune case n'a
        // ete touchee (ex: l'utilisateur soumet le formulaire avant la fin
        // du chargement de la liste, ou n'y touche jamais).
        const form = document.getElementById("synth-form");
        if (form) {
            form.addEventListener("submit", updateHiddenField);
        }
    });
})();
