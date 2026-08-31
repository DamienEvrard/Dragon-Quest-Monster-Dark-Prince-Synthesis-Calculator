(function () {
    "use strict";

    const data = window.TALENTS_DATA || [];
    const tbody = document.getElementById("talent-table-body");
    const resultCount = document.getElementById("talent-result-count");

    const filterName = document.getElementById("filter-talent-name");
    const filterSkill = document.getElementById("filter-skill-name");

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    function skillLabel(s) {
        if (s.name_fr && s.name_fr !== s.name) {
            return `${escapeHtml(s.name_fr)} <span class="sub-name-inline">(${escapeHtml(s.name)})</span>`;
        }
        return escapeHtml(s.name);
    }

    function matches(talent) {
        const name = filterName.value.trim().toLowerCase();
        const skill = filterSkill.value.trim().toLowerCase();

        const hayName = ((talent.name_fr || "") + " " + talent.name).toLowerCase();
        if (name && !hayName.includes(name)) return false;
        if (skill) {
            const allSkillNames = talent.skills.map((s) => s.name + " " + (s.name_fr || ""))
                .concat(talent.traits.map((t) => t.name)).join(" ").toLowerCase();
            if (!allSkillNames.includes(skill)) return false;
        }
        return true;
    }

    function render() {
        const filtered = data.filter(matches);
        resultCount.textContent = `${filtered.length} talent(s)`;

        const rows = filtered.map((t) => {
            const prereqText = t.prereq_sets.length
                ? t.prereq_sets.map((set) => set.join(" + ")).join(" OU ")
                : "—";
            const unlocksText = t.unlocks.length ? t.unlocks.join(", ") : "—";
            const count = t.skills.length + t.traits.length;

            return `
                <tr class="talent-row" data-talent-id="${t.id}">
                    <td>
                        <strong>${escapeHtml(t.display_name)}</strong>
                        ${t.name_fr && t.name_fr !== t.name_en ? `<div class="sub-name">${escapeHtml(t.name_en)}</div>` : ""}
                    </td>
                    <td>${count}</td>
                    <td class="${t.prereq_sets.length ? '' : 'dim'}">${escapeHtml(prereqText)}</td>
                    <td class="${t.unlocks.length ? '' : 'dim'}">${escapeHtml(unlocksText)}</td>
                </tr>
            `;
        });

        tbody.innerHTML = rows.join("");
    }

    [filterName, filterSkill].forEach((el) => el.addEventListener("input", render));

    // --- Modal detail d'un talent ---
    const overlay = document.getElementById("modal-overlay");
    const modalTitle = document.getElementById("modal-title");
    const modalBody = document.getElementById("modal-body");

    tbody.addEventListener("click", function (evt) {
        const row = evt.target.closest(".talent-row");
        if (!row) return;
        const talent = data.find((t) => String(t.id) === row.getAttribute("data-talent-id"));
        if (!talent) return;

        modalTitle.textContent = talent.display_name + (talent.name_fr && talent.name_fr !== talent.name_en ? ` (${talent.name_en})` : "");

        let body = "";

        if (talent.prereq_sets.length) {
            body += `<p><strong>Prérequis pour l'obtenir par synthèse :</strong><br>`;
            body += talent.prereq_sets.map((set) => escapeHtml(set.join(" + "))).join("<br>OU<br>");
            body += `</p>`;
        }

        if (talent.unlocks.length) {
            body += `<p><strong>Ce talent est un prérequis pour :</strong> ${escapeHtml(talent.unlocks.join(", "))}</p>`;
        }

        const allEntries = talent.skills.concat(talent.traits);
        if (allEntries.length) {
            body += `<p><strong>Contenu (skills / bonus) :</strong></p><ul class="skill-list">`;
            body += allEntries.map((s) => {
                return `<li>${skillLabel(s)} <span class="dim">(${s.points} pts)</span></li>`;
            }).join("");
            body += `</ul>`;
        } else {
            body += `<p class="dim">Aucun skill/bonus recensé pour ce talent.</p>`;
        }

        if (talent.carriers.length) {
            body += `<p><strong>Monstres l'apprenant nativement :</strong> ${escapeHtml(talent.carriers.slice(0, 15).join(", "))}${talent.carriers.length > 15 ? "…" : ""}</p>`;
        }

        modalBody.innerHTML = body;
        overlay.classList.add("open");
    });

    document.getElementById("modal-close").addEventListener("click", () => overlay.classList.remove("open"));
    overlay.addEventListener("click", (evt) => {
        if (evt.target === overlay) overlay.classList.remove("open");
    });

    render();
})();
