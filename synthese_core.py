# -*- coding: utf-8 -*-
"""
Coeur logique du calculateur de synthese - Dragon Quest Monsters: The Dark Prince
===================================================================================
Chargement des CSV, construction recursive de l'arbre de synthese des
monstres (y compris synthese a 4 monstres via grands-parents), et
resolution des chaines de talents necessaires pour debloquer les
talents demandes par le joueur.

PREMIER JET avance - toujours sans optimisation de type "meilleur chemin"
(on explore toutes les alternatives), mais avec la vraie mecanique de
talents (cf. regles ci-dessous).

REGLE DE PROGRESSION DES ZONES :
    Le LocationId EST directement l'ordre de progression du jeu.
    Une zone est accessible si son LocationId <= LocationId de la
    "derniere zone exploree" donnee par le joueur.

REGLE DE DEBLOCAGE DES TALENTS (fournie par l'utilisateur) :
    Un talent peut etre le resultat d'une "synthese de talents"
    (TalentSynthesis / TalentSynthesisTalent), qui combine les talents
    de DEUX parents pour en debloquer un nouveau chez l'enfant. Deux cas :

    1) Talents a POINTS (Booster I->II->III->IV, Aficionado->Virtuoso...) :
       la recette ne cite qu'UN SEUL talent "prerequis" (ex: Attack
       Booster III <- Attack Booster II). Dans ce cas, il faut que LES
       DEUX parents possedent ce talent prerequis : leurs points
       combines doivent atteindre le maximum de points de ce talent
       (ex: 200 pts pour Attack Booster II) pour debloquer le suivant.
       -> on simplifie en exigeant que LES DEUX parents aient le talent
       prerequis (peu importe leur niveau exact, faute de donnee sur
       les points deja investis par un monstre individuel).

    2) Talents "simples" (plusieurs recettes alternatives citant 2
       talents DIFFERENTS, ex: Polariser <- Woosh Virtuoso + Sizz
       Virtuoso) : il suffit qu'un parent ait le premier talent et
       l'autre parent le second (une des combinaisons alternatives),
       quel que soit leur niveau.

    Chaque talent prerequis peut lui-meme necessiter sa propre chaine
    de synthese (ex: Zap Ward -> ... -> Zap Virtuoso -> Zap Afficionado),
    d'ou la resolution RECURSIVE (resolve_talent_chain).

SYNTHESE A 4 MONSTRES (grands-parents) :
    Certaines recettes de MonsterSynthesis.csv n'indiquent pas
    MonsterParent1Id / MonsterParent2Id mais 4 grands-parents
    (GrandParent1A + GrandParent1B -> parent1 "intermediaire",
     GrandParent2A + GrandParent2B -> parent2 "intermediaire").
    Ce sont ces grands-parents qui determinent la recette finale.
"""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_MIN_LEVEL = 10  # niveau minimum recommande, a defaut d'info plus precise


# ---------------------------------------------------------------------------
# 1. Chargement brut des CSV
# ---------------------------------------------------------------------------

def load_csv(filename):
    """Charge un CSV en liste de dictionnaires (une entree par ligne)."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Database:
    """Regroupe toutes les tables + quelques index utiles."""

    def __init__(self):
        self.monsters = load_csv("Monster.csv")
        self.synthesis = load_csv("MonsterSynthesis.csv")
        self.monster_locations = load_csv("MonsterLocation.csv")
        self.locations = load_csv("Location.csv")
        self.talents = load_csv("Talent.csv")
        self.monster_talents = load_csv("MonsterTalent.csv")
        self.ranks = load_csv("Rank.csv")
        self.families = load_csv("Family.csv")
        self.skills = load_csv("Skill.csv")
        self.talent_skills = load_csv("TalentSkill.csv")
        self.talent_traits = load_csv("TalentTrait.csv")
        self.traits = load_csv("Trait.csv")
        self.talent_synthesis = load_csv("TalentSynthesis.csv")
        self.talent_synthesis_talent = load_csv("TalentSynthesisTalent.csv")
        self.skill_point_levels = load_csv("SkillPointLevel.csv")

        self._build_indexes()

    def _build_indexes(self):
        # --- Monstres ---
        self.monster_by_id = {m["MonsterId"]: m for m in self.monsters}

        self.monster_by_name = {}
        for m in self.monsters:
            if m["Name"].strip():
                self.monster_by_name[m["Name"].strip().lower()] = m
            if m["FrenchName"].strip():
                self.monster_by_name[m["FrenchName"].strip().lower()] = m

        self.synth_by_result = {}
        for s in self.synthesis:
            self.synth_by_result.setdefault(s["MonsterResultId"], []).append(s)

        # --- Zones (LocationId = ordre de progression) ---
        self.location_order = sorted(
            (loc["LocationId"] for loc in self.locations),
            key=lambda lid: int(lid),
        )
        self.location_by_id = {loc["LocationId"]: loc for loc in self.locations}
        self.location_by_name = {
            loc["Name"].strip().lower(): loc for loc in self.locations
        }

        self.locations_by_monster = {}
        for ml in self.monster_locations:
            self.locations_by_monster.setdefault(ml["MonsterId"], []).append(ml)

        # --- Familles / rangs ---
        self.rank_by_id = {r["RankId"]: r for r in self.ranks}
        self.family_by_id = {f["FamilyId"]: f for f in self.families}

        # --- Talents ---
        self.talent_by_id = {t["TalentId"]: t for t in self.talents}
        self.talent_by_name = {t["Name"].strip().lower(): t for t in self.talents}

        self.talents_by_monster = {}
        for mt in self.monster_talents:
            self.talents_by_monster.setdefault(mt["MonsterId"], []).append(mt)

        self.talent_ids_by_monster = {}
        for mt in self.monster_talents:
            self.talent_ids_by_monster.setdefault(mt["MonsterId"], set()).add(mt["TalentId"])

        # Uniquement les talents "principaux" (IsPrimary=TRUE) de chaque
        # monstre - ce sont les SEULS talents natifs qu'un monstre
        # obtient automatiquement lors d'une SYNTHESE (par opposition a
        # une capture directe dans la nature, qui donne acces a TOUS
        # ses talents natifs, principal + secondaires). Cf.
        # get_synth_native_talents.
        self.primary_talent_ids_by_monster = {}
        for mt in self.monster_talents:
            if mt.get("IsPrimary", "").strip().lower() == "true":
                self.primary_talent_ids_by_monster.setdefault(mt["MonsterId"], set()).add(mt["TalentId"])

        # Monstres (reels) qui possedent chaque talent (pour recherche inverse)
        self.monsters_by_talent = {}
        for mt in self.monster_talents:
            self.monsters_by_talent.setdefault(mt["TalentId"], []).append(mt["MonsterId"])

        # --- Skills ---
        self.skill_by_id = {sk["SkillId"]: sk for sk in self.skills}
        self.skill_by_name = {sk["Name"].strip().lower(): sk for sk in self.skills}

        self.skills_by_talent = {}
        for row in self.talent_skills:
            self.skills_by_talent.setdefault(row["TalentId"], []).append(row)

        # --- Traits (utilises par les talents "booster") ---
        self.trait_by_id = {t["TraitId"]: t for t in self.traits}
        self.traits_by_talent = {}
        for row in self.talent_traits:
            self.traits_by_talent.setdefault(row["TalentId"], []).append(row)

        # Points max (skills + traits confondus) d'un talent -> utilise pour
        # savoir combien de points il faut cumuler pour le "remplir"
        self.talent_max_points = {}
        for row in self.talent_skills:
            tid = row["TalentId"]
            pts = int(row["Points"])
            self.talent_max_points[tid] = max(self.talent_max_points.get(tid, 0), pts)
        for row in self.talent_traits:
            tid = row["TalentId"]
            pts = int(row["Points"])
            self.talent_max_points[tid] = max(self.talent_max_points.get(tid, 0), pts)

        # --- Synthese de talents ---
        # TalentSynthesisId -> liste de TalentId (composants de la recette)
        self.talent_synthesis_combo = {}
        for row in self.talent_synthesis_talent:
            self.talent_synthesis_combo.setdefault(row["TalentSynthesisId"], []).append(row["TalentId"])

        # TalentResultId -> liste de recettes {talent_synthesis_id, combo: [...]}
        self.talent_recipes_by_result = {}
        for ts in self.talent_synthesis:
            combo = self.talent_synthesis_combo.get(ts["TalentSynthesisId"], [])
            self.talent_recipes_by_result.setdefault(ts["TalentResultId"], []).append({
                "talent_synthesis_id": ts["TalentSynthesisId"],
                "combo": combo,
            })

        # Talent -> quels talents il permet de debloquer (utilise dans quelle(s) recette(s))
        self.talent_unlocks = {}
        for row in self.talent_synthesis_talent:
            ts_id = row["TalentSynthesisId"]
            result_id = next(
                (ts["TalentResultId"] for ts in self.talent_synthesis if ts["TalentSynthesisId"] == ts_id),
                None,
            )
            if result_id:
                self.talent_unlocks.setdefault(row["TalentId"], set()).add(result_id)

        # --- Courbe de points cumules par niveau (SkillPointLevel.csv) ---
        # Le fichier fournit directement la colonne "Total" (points cumules
        # a ce niveau si un monstre concentre tout dans une seule ligne de
        # talent). Sert a estimer a quel niveau une synthese devient
        # possible.
        self.level_points_curve = sorted(
            ((int(r["Lvl"]), int(r["Total"])) for r in self.skill_point_levels),
            key=lambda x: x[0],
        )

    def approx_level_for_points(self, points):
        """Renvoie le niveau approximatif (MINIMUM) auquel un monstre
        pourrait avoir cumule assez de points pour atteindre 'points' TOUT
        SEUL, en supposant qu'il investit tout dans une seule ligne de
        talent. Renvoie None si meme le niveau max ne suffit pas (rare)."""
        for lvl, cumulative in self.level_points_curve:
            if cumulative >= points:
                return lvl
        return None

    def level_for_maxed_points(self, target_points):
        """Niveau MINIMUM auquel UN monstre, en investissant tous ses
        points de competence disponibles, a accumule assez de points
        pour MAXER 'target_points' (ex: 200 pts pour maxer Attack
        Booster II).

        IMPORTANT (correction) : lors d'une synthese "a points" (ex:
        Attack Booster II -> III), les DEUX parents doivent CHACUN avoir
        deja MAXE le talent prerequis - ce n'est PAS un pot commun ou
        les points des 2 parents s'additionnent. Le niveau requis est
        donc celui auquel UN SEUL monstre (courbe SkillPointLevel.csv)
        atteint 'target_points', et ce MEME niveau est exige des DEUX
        parents (pas de division par 2)."""
        if not target_points:
            return DEFAULT_MIN_LEVEL
        for lvl, cumulative in self.level_points_curve:
            if cumulative >= target_points:
                return max(lvl, DEFAULT_MIN_LEVEL)
        # meme au niveau max, un monstre seul n'atteint pas le seuil
        return self.level_points_curve[-1][0] if self.level_points_curve else DEFAULT_MIN_LEVEL

    def recommended_level(self, talent_ids):
        """Niveau recommande pour qu'un monstre (l'UN OU L'AUTRE des 2
        parents d'une synthese, le MEME niveau etant exige des deux)
        puisse porter les talents donnes DEJA MAXES.

        CORRECTION IMPORTANTE : lors d'une synthese "a points" (ex:
        Attack Booster II -> III), les recettes de TalentSynthesis.csv
        exigent que les DEUX parents aient INDIVIDUELLEMENT deja MAXE
        le talent prerequis - ce n'est jamais un cumul a deux (leurs
        points ne se combinent pas). Le niveau recommande est donc
        celui auquel UN SEUL monstre atteint le seuil de points requis
        (cf. level_for_maxed_points), et ce meme niveau s'applique aux
        DEUX parents.

        Si le noeud doit faire evoluer PLUSIEURS talents A LA FOIS sur
        UN MEME parent (ex: 2 talents actifs simultanement), le niveau
        doit permettre d'accumuler assez de points pour CHACUN d'eux
        independamment - chaque talent a sa propre barre de points a
        remplir, avec le MEME pool de points gagnes par niveau. Le
        seuil total necessaire POUR CE PARENT est donc la SOMME des
        seuils de chaque talent (pas seulement le plus exigeant), sinon
        on sous-estimerait le niveau reellement necessaire des que
        plusieurs talents evoluent simultanement sur le meme individu.

        Si aucun des talents n'a de seuil de points connu (ou liste
        vide), on applique le niveau minimum par defaut
        (DEFAULT_MIN_LEVEL)."""
        total_points = 0
        found_any = False
        for tid in talent_ids:
            max_points = self.talent_max_points.get(tid)
            if not max_points:
                continue
            total_points += max_points
            found_any = True
        if not found_any:
            return DEFAULT_MIN_LEVEL
        return max(self.level_for_maxed_points(total_points), DEFAULT_MIN_LEVEL)


# ---------------------------------------------------------------------------
# 2. Zones accessibles
# ---------------------------------------------------------------------------

def get_reachable_location_ids(db, last_zone_name):
    """Zones accessibles = LocationId <= LocationId de la derniere zone
    exploree (None si zone vide/introuvable -> filtre desactive)."""
    if not last_zone_name:
        return None
    key = last_zone_name.strip().lower()
    if key not in db.location_by_name:
        return None
    target_id = int(db.location_by_name[key]["LocationId"])
    return {lid for lid in db.location_by_id if int(lid) <= target_id}


def is_capturable(db, monster_id, reachable_locations):
    """Liste des lieux (noms, dedoublonnes) ou le monstre est capturable
    dans les zones accessibles."""
    found = []
    for ml in db.locations_by_monster.get(monster_id, []):
        if reachable_locations is None or ml["LocationId"] in reachable_locations:
            loc = db.location_by_id.get(ml["LocationId"])
            if loc and loc["Name"] not in found:
                found.append(loc["Name"])
    return found


def build_wild_monsters_data(db, reachable_locations):
    """Liste de tous les monstres REELS (pas les placeholders de
    famille/rang) capturables dans les zones accessibles - utilisee par
    la route /api/monstres-sauvages pour alimenter la liste a cocher
    "Monstres disponibles dans la nature" sous l'arbre de synthese.

    Trie par famille puis par nom, pour un affichage groupe lisible."""
    data = []
    for m in db.monsters:
        if is_family_placeholder(m):
            continue
        locations = is_capturable(db, m["MonsterId"], reachable_locations)
        if not locations:
            continue
        family = db.family_by_id.get(m["FamilyId"], {}).get("Name", "?")
        rank = db.rank_by_id.get(m["RankId"], {}).get("Name", "?")
        data.append({
            "id": m["MonsterId"],
            "name": m["FrenchName"] or m["Name"],
            "family": family,
            "rank": rank,
            "locations": locations,
            "icon": f"{m['Identifier']}-thumb.png" if m.get("Identifier") else None,
        })
    data.sort(key=lambda d: (d["family"], d["name"]))
    return data


def capture_difficulty(db, monster, reachable_locations):
    """Estime la DIFFICULTE REELLE d'obtention d'un monstre "feuille"
    (capturable ou obtenu via oeuf), utilisee pour departager entre
    plusieurs solutions ayant le meme nombre de syntheses. Un monstre
    "de bas rang" (G, F...) capturable dans une zone peu avancee est
    considere facile ; un monstre de rang eleve (meme capturable), ou
    capturable seulement dans une zone tres avancee, est considere
    difficile - typiquement les Limons/Slimes "Metal" (Metal Slime,
    Liquid Metal Slime, Metal King Slime), notoirement difficiles a
    obtenir en pratique malgre leur faible niveau apparent, ont un rang
    et/ou une zone bien plus eleves que les slimes de base.

    Le rang (ordinal 1=G a 9=X) domine le score ; la zone la plus
    accessible parmi les lieux de capture connus vient departager les
    cas de rang egal (poids reduit pour ne jamais l'emporter sur le
    rang)."""
    if monster is None:
        return 0.0
    try:
        rank_score = float(monster.get("RankId") or 0)
    except (TypeError, ValueError):
        rank_score = 0.0
    if rank_score > 9:
        rank_score = 0.0  # rang special (Any=10) : pas de penalite de rang

    earliest_zone = None
    for ml in db.locations_by_monster.get(monster["MonsterId"], []):
        if reachable_locations is not None and ml["LocationId"] not in reachable_locations:
            continue
        try:
            lid = int(ml["LocationId"])
        except (TypeError, ValueError):
            continue
        if earliest_zone is None or lid < earliest_zone:
            earliest_zone = lid

    zone_score = (earliest_zone / 100.0) if earliest_zone is not None else 0.0
    return rank_score + zone_score


def get_egg_source_label(monster):
    """Si un monstre n'a ni recette de synthese ni capture sauvage
    connue mais possede un EggTypeId, il est obtenu EXCLUSIVEMENT via
    l'eclosion d'un oeuf special (mecanisme confirme par recherche
    externe pour plusieurs monstres, ex: Robin 'ood / Ethereal Serpent
    - non modelise autrement par Monster.csv/MonsterSynthesis.csv).
    Renvoie un libelle descriptif, ou None si non applicable."""
    if monster and monster.get("EggTypeId", "").strip():
        return f"Œuf spécial (type {monster['EggTypeId']})"
    return None


def is_family_placeholder(monster):
    """Un monstre 'placeholder' represente TOUTE une famille/rang plutot
    qu'un monstre precis (ex: 'Slime Family (G)')."""
    return monster is not None and " Family (" in monster["Name"]


def rank_meets_minimum(candidate_rank_id, required_rank_id, required_is_any):
    """Un ingredient 'libre' de rang Y (ex: 'Slime Family (G)') accepte
    en realite N'IMPORTE QUEL monstre de la famille dont le rang est AU
    MOINS Y - le rang indique dans la recette est un MINIMUM requis,
    pas une correspondance exacte (confirme par l'utilisateur). Les
    RankId 1 a 9 sont ordonnes du plus faible (1=G) au plus fort
    (9=X), donc un candidat convient si son RankId est >= au RankId
    requis. Le rang special 'Any' (10) n'impose aucune contrainte de
    rang, quel que soit le rang du candidat."""
    if required_is_any:
        return True
    try:
        return int(candidate_rank_id) >= int(required_rank_id)
    except (TypeError, ValueError):
        return candidate_rank_id == required_rank_id


# ---------------------------------------------------------------------------
# 3. Resolution des chaines de talents (coeur de la demande)
# ---------------------------------------------------------------------------

_STAT_PROGRESSION_KEYWORDS = ("booster", "afficionado", "aficionado")


def is_stat_progression_talent(db, talent_id):
    """Un talent de type "Booster" (Attack/Defence/Agility/Wisdom/HP/MP
    Booster) ou "Afficionado" (lignes d'affinite elementaire, ex: Frizz
    Afficionado -> Frizz Virtuoso) suit une regle PARTICULIERE (fournie
    par l'utilisateur) : seul un individu CAPTURE DIRECTEMENT DANS LA
    NATURE peut posseder ce type de talent des le depart - un monstre
    obtenu par SYNTHESE ne l'obtient JAMAIS automatiquement (meme s'il
    s'agit du talent principal de son espece), il ne peut que
    l'HERITER d'un parent qui, en remontant la genealogie, finit par
    provenir d'une capture sauvage. Cf. get_synth_native_talents.

    Par ailleurs, pour synthetiser le palier superieur (ex: Attack
    Booster II -> III), LES DEUX parents doivent avoir deja maxe le
    talent prerequis (regle identique a tous les autres talents "a
    points")."""
    talent = db.talent_by_id.get(talent_id)
    if not talent:
        return False
    name = (talent.get("Name") or "").lower()
    return any(kw in name for kw in _STAT_PROGRESSION_KEYWORDS)


def get_synth_native_talents(db, monster_id):
    """Talents qu'un monstre obtient AUTOMATIQUEMENT lors d'une
    SYNTHESE (par opposition a une capture directe dans la nature) :
    uniquement son talent PRINCIPAL ('IsPrimary' = TRUE dans
    MonsterTalent.csv) - ses talents secondaires ne sont disponibles
    que s'ils sont herites d'un parent (transmission classique, cf.
    remaining/_assign_talents dans solver.py).

    De plus, les talents de type "Booster"/"Afficionado" (cf.
    is_stat_progression_talent) ne sont JAMAIS obtenus de cette facon,
    meme s'ils constituent le talent principal de l'espece : seul un
    individu CAPTURE dans la nature peut les posseder d'entree - ils
    doivent donc necessairement etre herites d'un parent qui remonte,
    en bout de chaine, a une capture sauvage."""
    primary = db.primary_talent_ids_by_monster.get(monster_id, set())
    return {t for t in primary if not is_stat_progression_talent(db, t)}


def get_talent_recipes(db, talent_id):
    """Renvoie les recettes de synthese de talent pour un talent donne,
    sous forme de liste de dicts:
        {"category": "points"|"simple", "combo": [...]}
    - "points": la recette ne cite qu'UN talent prerequis -> LES DEUX
      parents doivent deja l'avoir maxe (aucune exception : meme pour
      les talents "Booster"/"Afficionado", cf. is_stat_progression_talent).
    - "simple": la recette cite 2 talents differents -> un parent
      chacun, peu importe le niveau.
    """
    recipes = []
    for r in db.talent_recipes_by_result.get(talent_id, []):
        distinct = list(dict.fromkeys(r["combo"]))
        if len(distinct) == 1:
            recipes.append({"category": "points", "combo": distinct})
        elif len(distinct) == 2:
            recipes.append({"category": "simple", "combo": distinct})
    return recipes


def monsters_with_talent(db, talent_id, reachable_locations, limit=6, excluded=None):
    """Monstres REELS (pas les 'familles' placeholder) qui possedent ce
    talent nativement ET qui sont capturables dans les zones
    accessibles. Trie par DIFFICULTE D'OBTENTION croissante (cf.
    capture_difficulty : rang bas + zone peu avancee en premier), pas
    par ordre alphabetique - le premier de la liste est ainsi toujours
    le monstre le plus SIMPLE a obtenir pour porter ce talent. C'est
    important car ce premier candidat est celui choisi automatiquement
    pour completer le prerequis d'un noeud de synthese lors de la
    construction d'une chaine de talent independante (cf.
    resolve_talent_chain -> simplify_chain -> _chain_to_solver_node
    dans solver.py, utilisee pour greffer un ingredient "libre").
    Limite a 'limit' resultats.

    'excluded' (optionnel) : ensemble de MonsterId a exclure de la
    recherche - correspond aux monstres decoches par le joueur dans la
    liste "Monstres disponibles dans la nature" (cf.
    build_wild_monsters_data) : le solveur ne doit alors jamais les
    proposer comme individu sauvage a capturer."""
    excluded = excluded or frozenset()
    candidates = []
    for mid in db.monsters_by_talent.get(talent_id, []):
        if mid in excluded:
            continue
        monster = db.monster_by_id.get(mid)
        if not monster or is_family_placeholder(monster):
            continue
        locations = is_capturable(db, mid, reachable_locations)
        if locations:
            candidates.append({
                "monster_name": monster["FrenchName"] or monster["Name"],
                "locations": locations,
                "difficulty": capture_difficulty(db, monster, reachable_locations),
            })
    candidates.sort(key=lambda c: (c["difficulty"], c["monster_name"]))
    for c in candidates:
        del c["difficulty"]
    return candidates[:limit]


def talent_exists_anywhere(db, talent_id):
    """Un monstre REEL (pas placeholder) possede-t-il ce talent quelque
    part dans le jeu, meme si ce n'est pas dans une zone accessible pour
    l'instant ? Sert a distinguer 'pas encore accessible' de 'aucune
    source connue' (tous les talents sont normalement transmissibles par
    synthese - cf. demande utilisateur)."""
    for mid in db.monsters_by_talent.get(talent_id, []):
        monster = db.monster_by_id.get(mid)
        if monster and not is_family_placeholder(monster):
            return True
    return False


def find_blocking_talent(db, chain_node):
    """Pour une chaine de talent dont le cout est infini (aucune
    solution), identifie le talent PRECIS qui bloque tout (celui, en
    descendant recursivement, qui n'a NI porteur sauvage NI aucune
    recette de synthese connue). Utile pour donner un message d'erreur
    precis ("X est impossible A CAUSE DE Y") plutot qu'un simple
    "aucune solution".

    Renvoie le nom du talent bloquant, ou None si la chaine est en fait
    faisable (pas d'appel utile dans ce cas)."""
    if chain_node["wild_candidates"]:
        return None  # ce noeud n'est pas bloquant, il a une solution directe

    if not chain_node["options"]:
        return chain_node["talent_name"]  # trouve : aucune recette ET aucun porteur

    # Cherche si TOUTES les options echouent, et remonte le premier
    # blocage rencontre dans la premiere branche qui echoue
    for option in chain_node["options"]:
        for slot in option["slots"]:
            blocker = find_blocking_talent(db, slot)
            if blocker:
                # Verifie si CETTE option est bien celle qui echoue (si
                # un slot bloque, toute l'option "simple"/"points" echoue)
                return blocker
    return None


def resolve_talent_chain(db, talent_id, reachable_locations, _visited=None, _depth=0, _max_depth=6, _max_options=4, excluded_wild_ids=None):
    """Construit RECURSIVEMENT la chaine de synthese permettant d'obtenir
    un talent donne. Renvoie un dict:
        {
            "talent_id":, "talent_name":,
            "wild_candidates": [{"monster_name":, "locations":[...]}, ...],
            "exists_but_not_reachable": bool,  # existe chez un monstre reel
                                                # mais hors des zones actuelles
            "options": [
                {
                    "category": "points"|"simple",
                    "prereq_talent_name": ... (si "points"),
                    "max_points": ... (si "points"),
                    "slots": [ <noeud recursif>, ... ]  # 1 slot ("points") ou 2 slots ("simple")
                }, ...
            ],
            "truncated_options": bool  # s'il y avait plus d'alternatives que 'max_options'
        }

    'excluded_wild_ids' (optionnel) : ensemble de MonsterId decoches par
    le joueur dans la liste "Monstres disponibles dans la nature" - ils
    ne sont jamais proposes comme porteur sauvage direct, ni ici ni dans
    les slots recursifs."""
    if _visited is None:
        _visited = set()

    talent = db.talent_by_id.get(talent_id)
    talent_name = talent["Name"] if talent else f"?({talent_id})"

    wild_candidates = monsters_with_talent(db, talent_id, reachable_locations, excluded=excluded_wild_ids)

    node = {
        "talent_id": talent_id,
        "talent_name": talent_name,
        "wild_candidates": wild_candidates,
        "exists_but_not_reachable": (not wild_candidates) and talent_exists_anywhere(db, talent_id),
        "options": [],
        "truncated_options": False,
    }

    if _depth >= _max_depth or talent_id in _visited:
        return node

    visited_next = _visited | {talent_id}
    recipes = get_talent_recipes(db, talent_id)
    node["truncated_options"] = len(recipes) > _max_options

    for recipe in recipes[:_max_options]:
        if recipe["category"] == "points":
            prereq_id = recipe["combo"][0]
            sub = resolve_talent_chain(db, prereq_id, reachable_locations, visited_next, _depth + 1, _max_depth, _max_options, excluded_wild_ids)
            node["options"].append({
                "category": "points",
                "prereq_talent_name": db.talent_by_id[prereq_id]["Name"],
                "max_points": db.talent_max_points.get(prereq_id),
                "recommended_level": db.recommended_level({prereq_id}),
                "slots": [sub],
            })
        else:
            slots = [
                resolve_talent_chain(db, tid, reachable_locations, visited_next, _depth + 1, _max_depth, _max_options, excluded_wild_ids)
                for tid in recipe["combo"]
            ]
            node["options"].append({
                "category": "simple",
                "recommended_level": DEFAULT_MIN_LEVEL,
                "slots": slots,
            })

    return node


def flatten_chain_talent_ids(chain_node, acc=None):
    """Recupere TOUS les TalentId presents dans une chaine resolue
    (le talent lui-meme + tous ses prerequis, recursivement)."""
    if acc is None:
        acc = set()
    acc.add(chain_node["talent_id"])
    for option in chain_node["options"]:
        for slot in option["slots"]:
            flatten_chain_talent_ids(slot, acc)
    return acc


def simplify_chain(node):
    """Ne garde qu'UN SEUL chemin (le plus simple) dans une chaine de
    talents resolue, au lieu de toutes les alternatives.

    'Le plus simple' = le moins d'etapes de synthese de talents avant
    d'atteindre un monstre reellement capturable. Un talent deja
    capturable directement (wild_candidates non vide) est TOUJOURS
    considere comme le plus simple (cout 0), meme s'il existe aussi
    une recette de synthese.

    Renvoie (node_simplifie, cout). cout = inf si aucune solution.
    """
    if node["wild_candidates"]:
        node["options"] = []
        node["truncated_options"] = False
        return node, 0

    if not node["options"]:
        return node, float("inf")

    best_option = None
    best_cost = float("inf")

    for option in node["options"]:
        total = 1
        new_slots = []
        feasible = True
        for slot in option["slots"]:
            simplified_slot, slot_cost = simplify_chain(slot)
            if slot_cost == float("inf"):
                feasible = False
                break
            total += slot_cost
            new_slots.append(simplified_slot)
        if not feasible:
            continue
        if total < best_cost:
            best_cost = total
            best_option = dict(option)
            best_option["slots"] = new_slots

    if best_option is None:
        node["options"] = []
        node["truncated_options"] = False
        return node, float("inf")

    node["options"] = [best_option]
    node["truncated_options"] = False
    return node, best_cost


# ---------------------------------------------------------------------------
# 4. Construction recursive de l'arbre de synthese des MONSTRES
# ---------------------------------------------------------------------------

def build_synthesis_tree(db, monster_id, reachable_locations, target_result_id=None, _visited=None):
    """Construit RECURSIVEMENT l'arbre de synthese d'un monstre (especes).

    Prend en compte la synthese a 4 monstres : si une recette n'a pas de
    MonsterParent1Id/MonsterParent2Id mais des grands-parents, on cree un
    noeud "intermediaire" (espece resultante non fixee a l'avance) dont
    les propres parents sont les 2 grands-parents correspondants.

    Chaque noeud "monstre":
        {
            "kind": "monster",
            "monster_id":, "name":,
            "capture_locations": [...],
            "is_root": bool,
            "is_free": bool,   # placeholder famille/rang
            "recipes": [ {"parent1": <noeud>, "parent2": <noeud>}, ... ]
        }
    Noeud "intermediaire" (synthese a 4 monstres):
        {
            "kind": "intermediate",
            "name": "Fusion intermediaire (espece variable)",
            "recipes": [ {"parent1": <noeud>, "parent2": <noeud>} ]  # un seul choix : les 2 grands-parents
        }
    """
    if _visited is None:
        _visited = set()

    monster = db.monster_by_id.get(monster_id)
    name = monster["FrenchName"] or monster["Name"] if monster else f"?({monster_id})"

    node = {
        "kind": "monster",
        "monster_id": monster_id,
        "name": name,
        "capture_locations": is_capturable(db, monster_id, reachable_locations),
        "is_root": target_result_id is None,
        "is_free": is_family_placeholder(monster),
        "recipes": [],
    }

    if monster_id in _visited:
        return node
    visited_next = _visited | {monster_id}

    for recipe in db.synth_by_result.get(monster_id, []):
        parent1_id = recipe["MonsterParent1Id"]
        parent2_id = recipe["MonsterParent2Id"]

        if parent1_id and parent2_id:
            node["recipes"].append({
                "parent1": build_synthesis_tree(db, parent1_id, reachable_locations, monster_id, visited_next),
                "parent2": build_synthesis_tree(db, parent2_id, reachable_locations, monster_id, visited_next),
            })
            continue

        # Synthese a 4 monstres (grands-parents)
        gp1a = recipe["MonsterGrandParent1AId"]
        gp1b = recipe["MonsterGrandParent1BId"]
        gp2a = recipe["MonsterGrandParent2AId"]
        gp2b = recipe["MonsterGrandParent2BId"]
        if gp1a and gp1b and gp2a and gp2b:
            intermediate1 = {
                "kind": "intermediate",
                "name": "Fusion intermediaire (espece variable)",
                "recipes": [{
                    "parent1": build_synthesis_tree(db, gp1a, reachable_locations, monster_id, visited_next),
                    "parent2": build_synthesis_tree(db, gp1b, reachable_locations, monster_id, visited_next),
                }],
            }
            intermediate2 = {
                "kind": "intermediate",
                "name": "Fusion intermediaire (espece variable)",
                "recipes": [{
                    "parent1": build_synthesis_tree(db, gp2a, reachable_locations, monster_id, visited_next),
                    "parent2": build_synthesis_tree(db, gp2b, reachable_locations, monster_id, visited_next),
                }],
            }
            node["recipes"].append({"parent1": intermediate1, "parent2": intermediate2})

    return node


def flatten_tree_monster_ids(node, acc=None):
    """Recupere tous les MonsterId presents dans l'arbre (recursif),
    en ignorant les noeuds 'intermediate' (qui n'ont pas de monstre)."""
    if acc is None:
        acc = set()
    if node.get("kind") == "monster":
        acc.add(node["monster_id"])
    for recipe in node.get("recipes", []):
        flatten_tree_monster_ids(recipe["parent1"], acc)
        flatten_tree_monster_ids(recipe["parent2"], acc)
    return acc


def select_best_recipe(db, node, relevant_talent_ids):
    """OPTIMISATION (une seule recette par noeud) : quand un monstre a
    plusieurs recettes alternatives possibles, on n'en garde qu'UNE
    SEULE - celle dont la sous-arborescence contient le plus de talents
    pertinents pour les objectifs du joueur (relevant_talent_ids). A
    defaut de talent pertinent, on garde simplement la premiere recette
    trouvee dans les donnees."""
    recipes = node.get("recipes", [])
    if len(recipes) > 1:
        scored = []
        for idx, recipe in enumerate(recipes):
            ids1 = flatten_tree_monster_ids(recipe["parent1"])
            ids2 = flatten_tree_monster_ids(recipe["parent2"])
            score = sum(
                len(db.talent_ids_by_monster.get(mid, set()) & relevant_talent_ids)
                for mid in (ids1 | ids2)
            )
            scored.append((score, -idx, recipe))  # -idx : a score egal, garde la 1ere
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        node["recipes"] = [scored[0][2]]

    for recipe in node.get("recipes", []):
        select_best_recipe(db, recipe["parent1"], relevant_talent_ids)
        select_best_recipe(db, recipe["parent2"], relevant_talent_ids)

    return node


def detect_recipe_talent_transitions(db, parent1_talent_ids, parent2_talent_ids, relevant_talent_ids):
    """Pour une paire de parents (par leurs ensembles de TalentId),
    detecte quelles syntheses de talent PERTINENTES (parmi
    relevant_talent_ids) deviennent possibles en les combinant. C'est ce
    qui permet d'afficher, sur chaque recette, le talent "en cours de
    construction" et son niveau recommande."""
    transitions = []
    for result_id in relevant_talent_ids:
        recipes = db.talent_recipes_by_result.get(result_id, [])
        for recipe in recipes:
            distinct = list(dict.fromkeys(recipe["combo"]))
            if len(distinct) == 1:
                prereq = distinct[0]
                if prereq in parent1_talent_ids and prereq in parent2_talent_ids:
                    transitions.append({
                        "category": "points",
                        "result_name": db.talent_by_id[result_id]["Name"],
                        "prereq_name": db.talent_by_id[prereq]["Name"],
                        "max_points": db.talent_max_points.get(prereq),
                        "recommended_level": db.recommended_level({prereq}),
                    })
                    break
            elif len(distinct) == 2:
                a, b = distinct
                ok = (a in parent1_talent_ids and b in parent2_talent_ids) or \
                     (b in parent1_talent_ids and a in parent2_talent_ids)
                if ok:
                    transitions.append({
                        "category": "simple",
                        "result_name": db.talent_by_id[result_id]["Name"],
                        "combo_names": [db.talent_by_id[a]["Name"], db.talent_by_id[b]["Name"]],
                        "recommended_level": DEFAULT_MIN_LEVEL,
                    })
                    break
    return transitions


def find_substitute(db, placeholder_monster_id, relevant_talent_ids, reachable_locations):
    """Pour un monstre 'libre' (placeholder de famille/rang), cherche un
    monstre REEL de cette meme famille (et meme rang, sauf rang "Any")
    qui possede l'un des talents PERTINENTS (chaine complete des 3
    talents demandes, pas seulement les 3 talents finaux) ET qui est
    capturable dans les zones accessibles.
    """
    placeholder = db.monster_by_id.get(placeholder_monster_id)
    if not placeholder:
        return None

    family_id = placeholder["FamilyId"]
    rank_id = placeholder["RankId"]
    rank_is_any = db.rank_by_id.get(rank_id, {}).get("Identifier") == "any"

    candidates = [
        m for m in db.monsters
        if m["FamilyId"] == family_id
        and not is_family_placeholder(m)
        and rank_meets_minimum(m["RankId"], rank_id, rank_is_any)
    ]

    for talent_id in relevant_talent_ids:
        talent = db.talent_by_id.get(talent_id)
        if not talent:
            continue
        for cand in candidates:
            if talent_id in db.talent_ids_by_monster.get(cand["MonsterId"], set()):
                locations = is_capturable(db, cand["MonsterId"], reachable_locations)
                if locations:
                    return {
                        "monster_name": cand["FrenchName"] or cand["Name"],
                        "talent_name": talent["Name"],
                        "talent_id": talent_id,
                        "locations": locations,
                    }
    return None


def annotate_tree(db, node, final_talent_ids, relevant_talent_ids, reachable_locations):
    """Parcourt l'arbre (recursif) pour ajouter, sur CHAQUE noeud
    monstre :
    - "final_talents": parmi les talents pertinents que ce monstre
      possede, ceux qui sont un des 3 talents FINAUX demandes par le
      joueur (marques comme objectif final atteint a ce noeud).
    - "building_talents": les autres talents pertinents qu'il possede
      (prerequis intermediaires utiles a la chaine, "en construction").
    - "recommended_level": niveau recommande pour que ce monstre soit
      pret pour la synthese (base sur les points requis des talents
      pertinents qu'il porte, ou DEFAULT_MIN_LEVEL a defaut).
    - "substitute": pour une feuille 'libre' (placeholder), suggestion
      d'un monstre reel portant un des talents pertinents et capturable.
    """
    if node.get("kind") != "monster":
        for recipe in node.get("recipes", []):
            p1, p2 = recipe["parent1"], recipe["parent2"]
            if p1.get("kind") == "monster" and p2.get("kind") == "monster" and p1.get("monster_id") and p2.get("monster_id"):
                t1 = db.talent_ids_by_monster.get(p1["monster_id"], set())
                t2 = db.talent_ids_by_monster.get(p2["monster_id"], set())
                recipe["transitions"] = detect_recipe_talent_transitions(db, t1, t2, relevant_talent_ids)
            else:
                recipe["transitions"] = []
            annotate_tree(db, p1, final_talent_ids, relevant_talent_ids, reachable_locations)
            annotate_tree(db, p2, final_talent_ids, relevant_talent_ids, reachable_locations)
        return node

    if node.get("monster_id") is None:
        # Noeud synthetique issu d'une greffe de chaine de talent
        # (chain_to_tree_node) : deja entierement annote, on se contente
        # de recurser sans ecraser ses badges.
        for recipe in node.get("recipes", []):
            annotate_tree(db, recipe["parent1"], final_talent_ids, relevant_talent_ids, reachable_locations)
            annotate_tree(db, recipe["parent2"], final_talent_ids, relevant_talent_ids, reachable_locations)
        return node

    owned_ids = db.talent_ids_by_monster.get(node["monster_id"], set()) & relevant_talent_ids
    final_owned = owned_ids & final_talent_ids
    building_owned = owned_ids - final_talent_ids

    node["final_talents"] = sorted(db.talent_by_id[tid]["Name"] for tid in final_owned if tid in db.talent_by_id)
    node["building_talents"] = sorted(db.talent_by_id[tid]["Name"] for tid in building_owned if tid in db.talent_by_id)

    node["substitute"] = None
    if node["is_free"] and not node["recipes"]:
        node["substitute"] = find_substitute(db, node["monster_id"], relevant_talent_ids, reachable_locations)

    if not node["is_free"]:
        node["recommended_level"] = db.recommended_level(owned_ids)
    elif node["substitute"]:
        node["recommended_level"] = db.recommended_level({node["substitute"]["talent_id"]})
    else:
        node["recommended_level"] = None

    for recipe in node["recipes"]:
        p1, p2 = recipe["parent1"], recipe["parent2"]
        if p1.get("kind") == "monster" and p2.get("kind") == "monster" and p1.get("monster_id") and p2.get("monster_id"):
            t1 = db.talent_ids_by_monster.get(p1["monster_id"], set())
            t2 = db.talent_ids_by_monster.get(p2["monster_id"], set())
            recipe["transitions"] = detect_recipe_talent_transitions(db, t1, t2, relevant_talent_ids)
        else:
            recipe["transitions"] = []
        annotate_tree(db, p1, final_talent_ids, relevant_talent_ids, reachable_locations)
        annotate_tree(db, p2, final_talent_ids, relevant_talent_ids, reachable_locations)

    return node


# ---------------------------------------------------------------------------
# 5. Analyse des 3 talents demandes (deja appris ? deja dans l'arbre ? chaine ?)
# ---------------------------------------------------------------------------

def get_final_talent_ids(db, talent_names):
    """TalentId des talents demandes par le joueur (ceux trouves dans
    Talent.csv), utilise pour distinguer 'talent final' de 'talent
    intermediaire' sur l'arbre."""
    ids = set()
    for name in talent_names:
        name = (name or "").strip()
        if not name:
            continue
        talent = db.talent_by_name.get(name.lower())
        if talent:
            ids.add(talent["TalentId"])
    return ids


def find_covered_talents(db, tree, final_talent_ids):
    """OPTIMISATION : verifie, pour chaque talent final demande, s'il
    est deja porte NATIVEMENT par un monstre quelconque de l'arbre de
    synthese (hors racine). Si oui, inutile de resoudre/afficher une
    chaine de synthese pour ce talent : on indique juste ou il se
    trouve deja dans l'arbre.

    Renvoie {talent_id: [noms des monstres porteurs dans l'arbre]}.
    """
    covered = {}
    if not final_talent_ids:
        return covered
    for mid in flatten_tree_monster_ids(tree):
        if tree.get("kind") == "monster" and mid == tree["monster_id"]:
            continue  # la racine est traitee a part (status "root")
        owned = db.talent_ids_by_monster.get(mid, set()) & final_talent_ids
        if not owned:
            continue
        monster = db.monster_by_id.get(mid)
        name = (monster["FrenchName"] or monster["Name"]) if monster else mid
        for tid in owned:
            covered.setdefault(tid, []).append(name)
    return covered


def analyse_talents(db, tree, talent_names, reachable_locations):
    """Pour chaque talent demande :
    - deja possede nativement par le monstre final -> "root".
    - sinon, deja porte par un AUTRE monstre de l'arbre de synthese
      (optimisation : pas besoin de construire une chaine ailleurs)
      -> "covered_in_tree".
    - sinon -> on resout sa chaine de synthese, simplifiee au chemin
      le plus simple -> "chain".

    Renvoie une liste de dicts:
        {"input":, "found": bool, "talent_name":, "status": "root"|"covered_in_tree"|"chain"|"unknown",
         "chain": <noeud resolve_talent_chain simplifie ou None>,
         "carriers": [noms de monstres] (pour "covered_in_tree")}
    """
    results = []
    root_id = tree["monster_id"] if tree.get("kind") == "monster" else None
    final_ids = get_final_talent_ids(db, talent_names)
    covered = find_covered_talents(db, tree, final_ids)

    for talent_name in talent_names:
        talent_name = (talent_name or "").strip()
        if not talent_name:
            continue

        talent = db.talent_by_name.get(talent_name.lower())
        if not talent:
            results.append({
                "input": talent_name, "found": False, "talent_name": None,
                "status": "unknown", "chain": None, "carriers": [],
            })
            continue

        talent_id = talent["TalentId"]
        has_root = root_id and talent_id in db.talent_ids_by_monster.get(root_id, set())

        if has_root:
            results.append({
                "input": talent_name, "found": True, "talent_name": talent["Name"],
                "status": "root", "chain": None, "carriers": [],
            })
        elif talent_id in covered:
            results.append({
                "input": talent_name, "found": True, "talent_name": talent["Name"],
                "status": "covered_in_tree", "chain": None, "carriers": covered[talent_id],
            })
        else:
            chain = resolve_talent_chain(db, talent_id, reachable_locations)
            simplify_chain(chain)
            results.append({
                "input": talent_name, "found": True, "talent_name": talent["Name"],
                "status": "chain", "chain": chain, "carriers": [],
            })

    return results


def get_relevant_talent_ids(db, talent_analysis_results):
    """Union de tous les TalentId presents dans les chaines resolues +
    les talents finaux eux-memes (utilise pour surligner les noeuds de
    l'arbre de monstres et pour chercher des substituts pertinents)."""
    ids = set()
    for r in talent_analysis_results:
        if not r["found"]:
            continue
        talent = db.talent_by_name.get(r["input"].lower())
        if talent:
            ids.add(talent["TalentId"])
        if r["status"] == "chain" and r["chain"]:
            flatten_chain_talent_ids(r["chain"], ids)
    return ids


# ---------------------------------------------------------------------------
# 6. Greffe des chaines de talents DANS l'arbre de synthese des monstres
# ---------------------------------------------------------------------------
#
# Une chaine de talent (ex: Attack Booster IV) n'est pas une chaine
# d'especes : n'importe quel monstre peut porter Attack Booster I, II...
# Pour VRAIMENT voir "qui herite du talent a chaque niveau", on transforme
# la chaine resolue (resolve_talent_chain + simplify_chain) en un
# sous-arbre de la MEME FORME que l'arbre d'especes (memes cles : kind,
# name, capture_locations, final_talents, building_talents,
# recommended_level, recipes...), puis on la "greffe" a la place d'un
# ingredient "libre" (placeholder famille/rang) de l'arbre principal, qui
# n'avait de toute facon pas d'identite figee.

def chain_to_tree_node(db, chain_node, final_talent_ids):
    """Convertit un noeud de chaine de talent (resolve_talent_chain,
    deja simplifie a un seul chemin) en noeud "arbre de synthese"
    (meme forme que build_synthesis_tree), pour un rendu visuel unifie."""
    talent_id = chain_node["talent_id"]
    talent_name = chain_node["talent_name"]
    is_final = talent_id in final_talent_ids
    label = [talent_name]

    if chain_node["wild_candidates"]:
        candidate = chain_node["wild_candidates"][0]
        return {
            "kind": "monster",
            "monster_id": None,
            "name": candidate["monster_name"],
            "capture_locations": candidate["locations"],
            "is_root": False,
            "is_free": False,
            "final_talents": label if is_final else [],
            "building_talents": [] if is_final else label,
            "recommended_level": db.recommended_level({talent_id}),
            "substitute": None,
            "recipes": [],
        }

    if chain_node["options"]:
        option = chain_node["options"][0]
        if option["category"] == "points":
            slot = option["slots"][0]
            # les DEUX parents ont besoin du MEME talent prerequis : on
            # construit 2 sous-arbres independants (2 monstres distincts)
            child1 = chain_to_tree_node(db, slot, final_talent_ids)
            child2 = chain_to_tree_node(db, slot, final_talent_ids)
            transition = {
                "category": "points",
                "result_name": talent_name,
                "prereq_name": option["prereq_talent_name"],
                "max_points": option["max_points"],
                "recommended_level": option["recommended_level"],
            }
        else:
            child1 = chain_to_tree_node(db, option["slots"][0], final_talent_ids)
            child2 = chain_to_tree_node(db, option["slots"][1], final_talent_ids)
            transition = {
                "category": "simple",
                "result_name": talent_name,
                "combo_names": [s["talent_name"] for s in option["slots"]],
                "recommended_level": option["recommended_level"],
            }

        return {
            "kind": "monster",
            "monster_id": None,
            "name": f"Porteur de {talent_name}",
            "capture_locations": [],
            "is_root": False,
            "is_free": False,
            "final_talents": label if is_final else [],
            "building_talents": [] if is_final else label,
            "recommended_level": option["recommended_level"],
            "substitute": None,
            "recipes": [{"parent1": child1, "parent2": child2, "transitions": [transition]}],
        }

    # Impasse : aucun candidat sauvage, aucune synthese connue
    return {
        "kind": "monster",
        "monster_id": None,
        "name": f"? ({talent_name} : aucune source connue)",
        "capture_locations": [],
        "is_root": False,
        "is_free": False,
        "final_talents": [],
        "building_talents": [],
        "recommended_level": None,
        "substitute": None,
        "recipes": [],
    }


def _collect_free_leaves(node, acc):
    """Parcours pre-ordre : recupere les REFERENCES (memes objets, pas
    des copies) des feuilles 'libres' (placeholder famille/rang) sans
    substitut deja assigne, dans l'ordre d'apparition dans l'arbre."""
    if node.get("kind") == "monster":
        if node["is_free"] and not node["recipes"] and not node.get("substitute"):
            acc.append(node)
        for recipe in node["recipes"]:
            _collect_free_leaves(recipe["parent1"], acc)
            _collect_free_leaves(recipe["parent2"], acc)
    else:
        for recipe in node.get("recipes", []):
            _collect_free_leaves(recipe["parent1"], acc)
            _collect_free_leaves(recipe["parent2"], acc)


def graft_chains_into_tree(db, tree, talent_results, final_talent_ids):
    """Pour chaque talent demande dont le statut est 'chain' (pas
    natif, pas deja present ailleurs dans l'arbre), tente d'INSERER
    directement sa chaine de construction (8 -> 4 -> 2 -> 1 monstres,
    par exemple pour un talent a 4 niveaux) a la place d'un ingredient
    'libre' de l'arbre principal - pour voir d'un coup d'oeil qui
    herite du talent a chaque niveau, jusqu'au monstre final.

    Modifie l'arbre EN PLACE. Renvoie l'ensemble des talent_id qui ont
    pu etre greffes (les autres restent affiches separement, en bas de
    page, comme ressource independante)."""
    free_leaves = []
    _collect_free_leaves(tree, free_leaves)

    grafted_ids = set()
    leaf_index = 0

    for r in talent_results:
        if r["status"] != "chain" or not r["chain"]:
            continue
        if leaf_index >= len(free_leaves):
            break  # plus de place libre dans l'arbre principal

        leaf = free_leaves[leaf_index]
        original_family = leaf["name"]
        graft = chain_to_tree_node(db, r["chain"], final_talent_ids)

        leaf.clear()
        leaf.update(graft)
        leaf["graft_note"] = f"remplace l'ingrédient libre « {original_family} »"

        grafted_ids.add(r["chain"]["talent_id"])
        leaf_index += 1

    return grafted_ids
