(function () {
    "use strict";

    const data = window.MONSTERS_DATA || [];
    const talentsData = window.TALENTS_DATA || [];
    const talentsById = {};
    talentsData.forEach((t) => { talentsById[String(t.id)] = t; });

    const tbody = document.getElementById("monster-table-body");
    const resultCount = document.getElementById("result-count");

    const filterName = document.getElementById("filter-name");
    const filterFamily = document.getElementById("filter-family");
    const filterRank = document.getElementById("filter-rank");
    const filterLocation = document.getElementById("filter-location");
    const filterTalent = document.getElementById("filter-talent");

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    function matches(monster) {
        const name = filterName.value.trim().toLowerCase();
        const family = filterFamily.value;
        const rank = filterRank.value;
        const location = filterLocation.value.trim().toLowerCase();
        const talent = filterTalent.value.trim().toLowerCase();

        if (name) {
            const hay = (monster.name_fr || "" ) + " " + monster.name_en;
            if (!hay.toLowerCase().includes(name)) return false;
        }
        if (family && monster.family !== family) return false;
        if (rank && monster.rank !== rank) return false;
        if (location && !monster.locations.join(" ").toLowerCase().includes(location)) return false;
        if (talent) {
            const allTalents = monster.primary_talents.concat(monster.secondary_talents);
            const found = allTalents.some((t) => {
                if (t.name.toLowerCase().includes(talent)) return true;
                const full = talentsById[String(t.talent_id)];
                return full && full.name_fr && full.name_fr.toLowerCase().includes(talent);
            });
            if (!found) return false;
        }
        return true;
    }

    function talentChips(talents) {
        return talents.map((t) => {
            const full = talentsById[String(t.talent_id)];
            const label = full ? full.display_name : t.name;
            const title = full && full.name_fr && full.name_fr !== full.name_en ? ` title="${escapeHtml(full.name_en)}"` : "";
            return `<span class="talent-chip" data-talent-id="${t.talent_id}"${title}>${escapeHtml(label)}</span>`;
        }).join(" ");
    }

    function iconHtml(monster) {
        if (!monster.icon) return '<img class="monster-icon" src="/static/icons/unknown-thumb.png" alt="" loading="lazy">';
        return `<img class="monster-icon" src="/static/icons/${monster.icon}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`;
    }

    function render() {
        const filtered = data.filter(matches);
        resultCount.textContent = `${filtered.length} monstre(s)`;

        const rows = filtered.map((m) => {
            const primaryHtml = talentChips(m.primary_talents) || '<span class="dim">—</span>';
            const secondaryHtml = talentChips(m.secondary_talents) || '<span class="dim">—</span>';

            return `
                <tr>
                    <td>${iconHtml(m)}</td>
                    <td>
                        <strong>${escapeHtml(m.display_name)}</strong>
                        ${m.name_fr && m.name_fr !== m.name_en ? `<div class="sub-name">${escapeHtml(m.name_en)}</div>` : ""}
                    </td>
                    <td>${escapeHtml(m.family)}</td>
                    <td>${escapeHtml(m.rank)}</td>
                    <td>${m.locations.length ? escapeHtml(m.locations.join(", ")) : '<span class="dim">—</span>'}</td>
                    <td>${primaryHtml}</td>
                    <td>${secondaryHtml}</td>
                </tr>
            `;
        });

        tbody.innerHTML = rows.join("");
    }

    [filterName, filterFamily, filterRank, filterLocation, filterTalent].forEach((el) =>
        el.addEventListener("input", render)
    );

    // --- Modal detail COMPLET d'un talent (identique a la page Talents) ---
    const overlay = document.getElementById("modal-overlay");
    const modalTitle = document.getElementById("modal-title");
    const modalBody = document.getElementById("modal-body");

    function skillLabel(s) {
        if (s.name_fr && s.name_fr !== s.name) {
            return `${escapeHtml(s.name_fr)} <span class="sub-name-inline">(${escapeHtml(s.name)})</span>`;
        }
        return escapeHtml(s.name);
    }

    tbody.addEventListener("click", function (evt) {
        const chip = evt.target.closest(".talent-chip");
        if (!chip) return;
        const talent = talentsById[chip.getAttribute("data-talent-id")];
        if (!talent) return;

        modalTitle.textContent = talent.display_name + (talent.name_fr && talent.name_fr !== talent.name_en ? ` (${talent.name_en})` : "");

        let body = "";

        if (talent.prereq_sets && talent.prereq_sets.length) {
            body += `<p><strong>Prérequis pour l'obtenir par synthèse :</strong><br>`;
            body += talent.prereq_sets.map((set) => escapeHtml(set.join(" + "))).join("<br>OU<br>");
            body += `</p>`;
        }

        if (talent.unlocks && talent.unlocks.length) {
            body += `<p><strong>Ce talent est un prérequis pour :</strong> ${escapeHtml(talent.unlocks.join(", "))}</p>`;
        }

        const allEntries = (talent.skills || []).concat(talent.traits || []);
        if (allEntries.length) {
            body += `<p><strong>Contenu (skills / bonus) :</strong></p><ul class="skill-list">`;
            body += allEntries.map((s) => `<li>${skillLabel(s)} <span class="dim">(${s.points} pts)</span></li>`).join("");
            body += `</ul>`;
        } else {
            body += `<p class="dim">Aucun skill/bonus recensé pour ce talent.</p>`;
        }

        if (talent.carriers && talent.carriers.length) {
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
