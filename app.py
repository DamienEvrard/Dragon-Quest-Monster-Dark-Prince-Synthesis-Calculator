# -*- coding: utf-8 -*-
"""
Interface web (Flask) - Calculateur de synthese DQM: The Dark Prince
=======================================================================
Lancer avec:  python3 app.py
Puis ouvrir:  http://127.0.0.1:5000 dans un navigateur.

3 onglets :
- Arbre de synthese : calculateur principal (formulaire + arbre + chaines de talents)
- Compendium        : liste de tous les monstres avec filtres
- Talents           : liste de tous les talents avec filtres
"""

import html
import json
import os

from flask import Flask, render_template, request, jsonify
from markupsafe import Markup

from synthese_core import (
    Database,
    get_reachable_location_ids,
    is_family_placeholder,
    is_capturable,
    build_wild_monsters_data,
)
from solver import solve, decompose_and_graft
from synthese_core import resolve_talent_chain, simplify_chain, find_blocking_talent, talent_exists_anywhere, get_talent_recipes

app = Flask(__name__)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1",
        port=int(os.environ.get("PORT", 5000))
    )
port = int(os.environ.get("PORT", 5000))

# Chargee une seule fois au demarrage du serveur
db = Database()

# --- Listes pour l'autocompletion (datalist) ---
_monster_name_set = set()
for m in db.monsters:
    if m["FrenchName"].strip():
        _monster_name_set.add(m["FrenchName"].strip())
    if m["Name"].strip():
        _monster_name_set.add(m["Name"].strip())
MONSTER_NAMES = sorted(_monster_name_set)

TALENT_NAMES = sorted({t["Name"] for t in db.talents if t["Name"]})
LOCATION_NAMES = [
    db.location_by_id[lid]["Name"]
    for lid in db.location_order
    if db.location_by_id[lid]["Name"]
]


def parse_excluded_wild_ids(raw_value):
    """Convertit la valeur brute du champ cache 'excluded_wild' (liste
    de MonsterId separes par des virgules, envoyee par
    static/wild-monsters.js a partir de son localStorage) en un
    frozenset exploitable par le solveur."""
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return frozenset()
    return frozenset(x.strip() for x in raw_value.split(",") if x.strip())


# ---------------------------------------------------------------------------
# Rendu HTML recursif de l'arbre de synthese des MONSTRES
# ---------------------------------------------------------------------------

def render_transition_banner(db, transitions):
    """Bandeau affiche entre 2 parents et leur resultat, indiquant
    quelle(s) synthese(s) de talent se declenchent a cette etape."""
    if not transitions:
        return ""
    parts = []
    for t in transitions:
        result_name = html.escape(db.talent_by_id[t["result_id"]]["Name"])
        prereq_names = [html.escape(db.talent_by_id[pid]["Name"]) for pid in t["prereq_ids"]]
        if t["category"] == "points":
            prereq = prereq_names[0]
            max_points = db.talent_max_points.get(t["prereq_ids"][0])
            level = db.recommended_level(set(t["prereq_ids"]))
            txt = (
                f'🔧 Les DEUX parents doivent avoir <strong>{prereq}</strong> → '
                f'devient <strong>{result_name}</strong> '
                f'(points combinés ≥ {max_points}) — 🎓 niveau {level}+'
            )
        else:
            a, b = prereq_names
            txt = (
                f'🔧 Un parent avec <strong>{a}</strong>, l\'autre avec <strong>{b}</strong> → '
                f'devient <strong>{result_name}</strong>'
            )
        parts.append(f'<div class="transition-line">{txt}</div>')
    return f'<div class="transition-banner">{"".join(parts)}</div>'


def render_solution_html(db, node, final_talent_ids, path="n0"):
    """Rendu HTML recursif du noeud unifie renvoye par solver.solve() :
    chaque noeud EST a la fois un monstre ET l'ensemble des talents qu'il
    doit transporter pour que la solution globale fonctionne."""
    name = html.escape(node["name"])
    icon_html = ""
    monster = db.monster_by_id.get(node.get("monster_id")) if node.get("monster_id") else None
    if monster and monster.get("Identifier"):
        icon_html = f'<img class="monster-icon" src="/static/icons/{monster["Identifier"]}-thumb.png" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
    else:
        icon_html = '<img class="monster-icon" src="/static/icons/unknown-thumb.png" alt="" loading="lazy">'
    badges = ""

    if node["capture_locations"]:
        locs = html.escape(", ".join(node["capture_locations"]))
        badges += f'<span class="badge badge-capture" title="Zone(s) de capture">📍 {locs}</span>'
    elif node["kind"] == "synth" and not node["parent1"]:
        badges += '<span class="badge badge-missing">❓ introuvable (zone/recette inconnue)</span>'

    required = node["required_talents"]
    final_here = required & final_talent_ids
    building_here = required - final_talent_ids

    if final_here:
        talents = html.escape(", ".join(sorted(db.talent_by_id[t]["Name"] for t in final_here)))
        badges += f'<span class="badge badge-final" title="Talent final demandé, transporté par ce monstre">🏆 {talents}</span>'

    if building_here:
        talents = html.escape(", ".join(sorted(db.talent_by_id[t]["Name"] for t in building_here)))
        badges += f'<span class="badge badge-building" title="Talent intermédiaire nécessaire, transporté par ce monstre">🔧 {talents}</span>'

    if node.get("recommended_level"):
        badges += f'<span class="badge badge-level" title="Niveau recommandé pour cette synthèse">🎓 niveau {node["recommended_level"]}+</span>'

    if node.get("grafted_talent"):
        badges += '<span class="badge badge-grafted" title="Ce talent a été construit indépendamment (arbre intermédiaire) puis introduit ici">🔀 arbre intermédiaire greffé</span>'

    recipes_html = ""
    has_children = bool(node["parent1"] and node["parent2"])
    if has_children:
        transition_html = render_transition_banner(db, node.get("transitions"))
        recipes_html = f'''
        <div class="recipe-block">
            {transition_html}
            <div class="parents">
                {render_solution_html(db, node["parent1"], final_talent_ids, f"{path}-a")}
                {render_solution_html(db, node["parent2"], final_talent_ids, f"{path}-b")}
            </div>
        </div>
        '''

    toggle_html = ""
    if has_children:
        toggle_html = '<button type="button" class="node-toggle" title="Masquer/afficher la suite de l\'arbre">−</button>'

    root_class = " root" if path == "n0" else ""

    return f'''
    <div class="node{root_class}" data-path="{path}">
        <div class="node-card">
            <div class="node-name">{icon_html}{name}</div>
            <div class="badges">{badges}</div>
            {toggle_html}
        </div>
        {recipes_html}
    </div>
    '''


# ---------------------------------------------------------------------------
# Routes - Arbre de synthese
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        active_tab="arbre",
        monster_names=MONSTER_NAMES,
        talent_names=TALENT_NAMES,
        location_names=LOCATION_NAMES,
    )


@app.route("/api/monstres-sauvages", methods=["GET"])
def api_monstres_sauvages():
    """Liste (JSON) de tous les monstres capturables dans la nature
    pour la zone indiquee (parametre 'zone', meme convention que le
    champ "Dernière zone explorée" du formulaire principal), utilisee
    par static/wild-monsters.js pour peupler la liste a cocher sous
    l'arbre de synthese."""
    zone = request.args.get("zone", "").strip()
    reachable = get_reachable_location_ids(db, zone)
    return jsonify(build_wild_monsters_data(db, reachable))


@app.route("/calculer", methods=["POST"])
def calculer():
    monster_name = request.form.get("monster", "").strip()
    talent_names = [
        request.form.get("talent1", "").strip(),
        request.form.get("talent2", "").strip(),
        request.form.get("talent3", "").strip(),
    ]
    last_zone = request.form.get("zone", "").strip()
    excluded_wild_ids = parse_excluded_wild_ids(request.form.get("excluded_wild", ""))

    error = None
    tree_html = None
    zone_warning = None
    monster_display_name = None
    unknown_talents = []
    unsolved = False
    search_exhausted = False
    solution_cost = None
    used_decomposition = False
    unassigned_talent_names = []
    impossible_talent_names = []

    monster = db.monster_by_name.get(monster_name.lower())
    if not monster:
        error = f"Monstre « {monster_name} » introuvable dans la base de donnees."
    else:
        monster_display_name = monster["FrenchName"] or monster["Name"]
        reachable = get_reachable_location_ids(db, last_zone)
        if reachable is None and last_zone:
            zone_warning = (
                f"Zone « {last_zone} » introuvable : le filtre de zone est desactive "
                f"(tous les monstres sont consideres comme accessibles)."
            )

        # Resolution UNIFIEE, en 3 etapes pour rester rapide dans la
        # majorite des cas tout en restant robuste sur les cas complexes
        # (cf. section "STRATEGIE DE SECOURS" dans solver.py) :
        #
        # 1) Tentative RAPIDE (budget reduit) : suffit pour la grande
        #    majorite des demandes (0-1 talent, ou plusieurs talents
        #    simples), quasi instantanee.
        # 2) Si ca echoue par manque de budget (pas par preuve
        #    d'impossibilite) : bascule sur la decomposition en ARBRES
        #    INTERMEDIAIRES (chaque talent resolu independamment puis
        #    greffe dans l'arbre de l'espece seule) - beaucoup moins
        #    couteuse en calcul, quasi instantanee aussi. Utilisee SI
        #    elle parvient a placer TOUS les talents demandes.
        # 3) En dernier recours seulement (si la decomposition ne
        #    parvient pas a tout placer, ex: talent complexe sans
        #    emplacement libre compatible) : recherche complete avec le
        #    budget maximal, plus lente (jusqu'a quelques secondes) mais
        #    la plus a meme de trouver une solution malgre tout.
        #
        # 'excluded_wild_ids' (monstres decoches par le joueur dans la
        # liste "Monstres disponibles dans la nature") est propage a
        # CHAQUE etape, pour ne jamais proposer un de ces monstres comme
        # individu capture directement dans l'arbre resultant.
        root, final_talent_ids, unknown_talents, search_exhausted = solve(
            db, monster["MonsterId"], talent_names, reachable, max_calls=300_000,
            excluded_wild_ids=excluded_wild_ids,
        )

        if root is None and search_exhausted:
            fast_final_ids = {
                db.talent_by_name[n.strip().lower()]["TalentId"]
                for n in talent_names if n.strip() and n.strip().lower() in db.talent_by_name
            }
            decomposed_tree, assigned, unassigned = decompose_and_graft(
                db, monster["MonsterId"], fast_final_ids, reachable,
                excluded_wild_ids=excluded_wild_ids,
            )

            if decomposed_tree is not None and not unassigned:
                # Succes COMPLET via decomposition (rapide) : tous les
                # talents ont pu etre places, inutile d'aller plus loin.
                root = decomposed_tree
                final_talent_ids = fast_final_ids
                search_exhausted = False
                used_decomposition = True
            else:
                # Distingue, parmi les talents non places par la
                # decomposition simplifiee, ceux qui restent
                # THEORIQUEMENT constructibles (chaine de talent
                # independante de l'espece encore valide) de ceux
                # VRAIMENT impossibles (aucune source dans les
                # donnees, quelle que soit l'espece ou le temps passe
                # a chercher).
                truly_impossible = set()
                still_buildable = set()
                for t in unassigned:
                    if talent_exists_anywhere(db, t) or get_talent_recipes(db, t):
                        still_buildable.add(t)
                    else:
                        truly_impossible.add(t)

                if still_buildable:
                    # Au moins un talent demande reste theoriquement
                    # possible mais n'a pas pu etre place par la
                    # decomposition simplifiee (pas d'emplacement libre
                    # compatible dans CETTE genealogie precise). Avant
                    # d'abandonner, on tente la RECHERCHE COMPLETE avec
                    # un budget TRES eleve - quel que soit le temps que
                    # cela prend - car elle explore des combinaisons
                    # que la decomposition ne peut pas trouver (elle
                    # n'est pas limitee aux emplacements "libres"
                    # identifies a l'avance).
                    full_root, full_final_ids, _, full_exhausted = solve(
                        db, monster["MonsterId"], talent_names, reachable, max_calls=15_000_000,
                        excluded_wild_ids=excluded_wild_ids,
                    )
                    if full_root is not None:
                        root = full_root
                        final_talent_ids = full_final_ids
                        used_decomposition = False
                        search_exhausted = False

                if root is None and decomposed_tree is not None and assigned:
                    # Ni la decomposition seule ni la recherche complete
                    # etendue n'ont permis de TOUT placer : on propose
                    # le meilleur resultat partiel trouve (celui de la
                    # decomposition), avec un message honnete et precis
                    # sur ce qui manque et pourquoi.
                    root = decomposed_tree
                    final_talent_ids = fast_final_ids
                    used_decomposition = True
                    search_exhausted = False

                    unassigned_talent_names = sorted(db.talent_by_id[t]["Name"] for t in still_buildable)
                    impossible_talent_names = []
                    for t in sorted(truly_impossible, key=lambda x: db.talent_by_id[x]["Name"]):
                        name = db.talent_by_id[t]["Name"]
                        fresh_chain = resolve_talent_chain(db, t, reachable)
                        blocker = find_blocking_talent(db, fresh_chain)
                        if blocker and blocker != name:
                            impossible_talent_names.append(f"{name} (bloqué par « {blocker} », sans aucune source connue)")
                        else:
                            impossible_talent_names.append(name)
                elif root is None:
                    # Rien du tout n'a pu etre assigne par la
                    # decomposition (aucun emplacement libre compatible
                    # nulle part, ou meme l'espece seule est
                    # infaisable) : dernier recours, la recherche
                    # complete a deja ete tentee ci-dessus si un talent
                    # semblait constructible ; sinon on la tente une
                    # derniere fois ici avec le budget standard.
                    root, final_talent_ids, unknown_talents, search_exhausted = solve(
                        db, monster["MonsterId"], talent_names, reachable,
                        excluded_wild_ids=excluded_wild_ids,
                    )

        if root is None:
            unsolved = True
        else:
            solution_cost = root["cost"]
            tree_html = Markup(render_solution_html(db, root, final_talent_ids))

    return render_template(
        "index.html",
        active_tab="arbre",
        monster_names=MONSTER_NAMES,
        talent_names=TALENT_NAMES,
        location_names=LOCATION_NAMES,
        error=error,
        tree_html=tree_html,
        zone_warning=zone_warning,
        monster_display_name=monster_display_name,
        unknown_talents=unknown_talents,
        unsolved=unsolved,
        search_exhausted=search_exhausted,
        solution_cost=solution_cost,
        used_decomposition=used_decomposition,
        unassigned_talent_names=unassigned_talent_names,
        impossible_talent_names=impossible_talent_names,
        form_values={
            "monster": monster_name,
            "talent1": talent_names[0],
            "talent2": talent_names[1],
            "talent3": talent_names[2],
            "zone": last_zone,
        },
    )

# ---------------------------------------------------------------------------
# Routes - Compendium (liste des monstres)
# ---------------------------------------------------------------------------

def build_compendium_data():
    data = []
    for m in db.monsters:
        if is_family_placeholder(m):
            continue
        locations = is_capturable_all(m["MonsterId"])
        primary_talents = []
        secondary_talents = []
        for mt in db.talents_by_monster.get(m["MonsterId"], []):
            talent = db.talent_by_id.get(mt["TalentId"])
            if not talent:
                continue
            skills = [
                {"name": db.skill_by_id[s["SkillId"]]["Name"], "points": int(s["Points"])}
                for s in db.skills_by_talent.get(talent["TalentId"], [])
                if s["SkillId"] in db.skill_by_id
            ]
            skills.sort(key=lambda s: s["points"])
            entry = {"name": talent["Name"], "talent_id": talent["TalentId"], "skills": skills}
            if mt["IsPrimary"].strip().lower() == "true":
                primary_talents.append(entry)
            else:
                secondary_talents.append(entry)
        family = db.family_by_id.get(m["FamilyId"], {}).get("Name", "?")
        rank = db.rank_by_id.get(m["RankId"], {}).get("Name", "?")
        data.append({
            "id": m["MonsterId"],
            "name_fr": m["FrenchName"] or None,
            "name_en": m["Name"],
            "display_name": m["FrenchName"] or m["Name"],
            "family": family,
            "rank": rank,
            "locations": locations,
            "primary_talents": primary_talents,
            "secondary_talents": secondary_talents,
            "icon": f"{m['Identifier']}-thumb.png" if m.get("Identifier") else None,
        })
    data.sort(key=lambda d: d["display_name"])
    return data


def is_capturable_all(monster_id):
    """Toutes les localisations connues (sans filtre de zone), pour le compendium."""
    found = []
    for ml in db.locations_by_monster.get(monster_id, []):
        loc = db.location_by_id.get(ml["LocationId"])
        if loc and loc["Name"] not in found:
            found.append(loc["Name"])
    return found


_COMPENDIUM_CACHE = None


@app.route("/compendium", methods=["GET"])
def compendium():
    global _COMPENDIUM_CACHE, _TALENTS_CACHE
    if _COMPENDIUM_CACHE is None:
        _COMPENDIUM_CACHE = build_compendium_data()
    if _TALENTS_CACHE is None:
        _TALENTS_CACHE = build_talents_data()

    families = sorted({d["family"] for d in _COMPENDIUM_CACHE})
    ranks = sorted({d["rank"] for d in _COMPENDIUM_CACHE})

    return render_template(
        "compendium.html",
        active_tab="compendium",
        monsters_json=Markup(json.dumps(_COMPENDIUM_CACHE, ensure_ascii=False)),
        talents_json=Markup(json.dumps(_TALENTS_CACHE, ensure_ascii=False)),
        families=families,
        ranks=ranks,
    )


# ---------------------------------------------------------------------------
# Routes - Talents (liste de tous les talents)
# ---------------------------------------------------------------------------

def build_talents_data():
    data = []
    for t in db.talents:
        tid = t["TalentId"]
        skills = [
            {
                "name": db.skill_by_id[s["SkillId"]]["Name"],
                "name_fr": db.skill_by_id[s["SkillId"]].get("FrenchName") or None,
                "points": int(s["Points"]),
            }
            for s in db.skills_by_talent.get(tid, [])
            if s["SkillId"] in db.skill_by_id
        ]
        skills.sort(key=lambda s: s["points"])

        traits = [
            {
                "name": db.trait_by_id[tr["TraitId"]]["Name"],
                "points": int(tr["Points"]),
            }
            for tr in db.traits_by_talent.get(tid, [])
            if tr["TraitId"] in db.trait_by_id
        ]
        traits.sort(key=lambda s: s["points"])

        # Ce talent est-il "parent" d'un autre (utilise dans une recette) ?
        unlocks = sorted(
            db.talent_by_id[rid]["Name"]
            for rid in db.talent_unlocks.get(tid, [])
            if rid in db.talent_by_id
        )

        # Prerequis de CE talent (s'il est lui-meme un resultat de synthese)
        prereq_sets = []
        for recipe in db.talent_recipes_by_result.get(tid, []):
            distinct = list(dict.fromkeys(recipe["combo"]))
            prereq_sets.append([db.talent_by_id[pid]["Name"] for pid in distinct if pid in db.talent_by_id])

        # Monstres qui l'apprennent nativement (pour info rapide)
        carriers = sorted(
            (db.monster_by_id[mid]["FrenchName"] or db.monster_by_id[mid]["Name"])
            for mid in db.monsters_by_talent.get(tid, [])
            if mid in db.monster_by_id and not is_family_placeholder(db.monster_by_id[mid])
        )

        data.append({
            "id": tid,
            "name": t["Name"],
            "name_fr": t.get("FrenchName") or None,
            "name_en": t["Name"],
            "display_name": t.get("FrenchName") or t["Name"],
            "skills": skills,
            "traits": traits,
            "unlocks": unlocks,
            "prereq_sets": prereq_sets,
            "carriers": carriers,
        })
    data.sort(key=lambda d: d["name"])
    return data


_TALENTS_CACHE = None


@app.route("/talents", methods=["GET"])
def talents_page():
    global _TALENTS_CACHE
    if _TALENTS_CACHE is None:
        _TALENTS_CACHE = build_talents_data()

    return render_template(
        "talents.html",
        active_tab="talents",
        talents_json=Markup(json.dumps(_TALENTS_CACHE, ensure_ascii=False)),
    )


if __name__ == "__main__":
    app.run(debug=True)
