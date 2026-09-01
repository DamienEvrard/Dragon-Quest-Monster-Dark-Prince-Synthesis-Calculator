# -*- coding: utf-8 -*-
"""
Nouveau moteur de resolution - Dragon Quest Monsters: The Dark Prince
=========================================================================
REFONTE COMPLETE (remplace l'ancienne approche "arbre d'especes d'abord,
talents ensuite" par une resolution UNIFIEE).

Le probleme resolu est exactement celui-ci :

    "Construire un arbre de synthese qui permet d'obtenir simultanement
    le monstre final ET les talents demandes, en minimisant le nombre
    de syntheses."

------------------------------------------------------------------
IDEE CENTRALE
------------------------------------------------------------------
Un noeud de l'arbre n'est plus seulement un MONSTRE, c'est :

    (espece, ensemble de talents qu'il doit transporter)

Deux noeuds de la meme espece mais avec des talents differents a
transporter sont deux etats DIFFERENTS (ils peuvent avoir des couts et
des recettes differentes). C'est pour ca que le cache (memoisation) est
indexe sur (monsterId, frozenset(talents requis)).

------------------------------------------------------------------
REGLE DE SYNTHESE (rappel)
------------------------------------------------------------------
Une synthese de monstres est TOUJOURS : Parent1 + Parent2 -> Resultat.
Le resultat herite des talents SELECTIONNES parmi ceux des deux parents
(regle donnee par l'utilisateur). On modelise ca ainsi : pour que le
resultat porte un talent T qu'il ne connait pas nativement, il faut que
ce talent soit obtenu en combinant les parents, selon 3 cas (deja geres
par get_talent_recipes dans synthese_core.py) :

    1) Talent "a points" (Booster, Aficionado->Virtuoso...) : LES DEUX
       parents doivent porter le palier immediatement inferieur.
    2) Talent "simple" a 2 prerequis differents (ex: Hair Splitter) :
       un parent porte le premier prerequis, l'autre porte le second.
    3) Talent "feuille" (aucune recette de synthese de talent connue) :
       UN SEUL des deux parents doit le porter (nativement, ou via sa
       propre chaine de synthese).

------------------------------------------------------------------
GARANTIE DE PROPAGATION DES TALENTS
------------------------------------------------------------------
Un talent, une fois obtenu sur un individu (par capture ou par une
premiere synthese), n'est jamais "perdu" : il continue a se transmettre
a chaque synthese ulterieure tant qu'un des deux parents le porte
encore (regle "feuille" ci-dessus). Consequence : des qu'un talent
demande existe QUELQUE PART dans les donnees (nativement chez au moins
un monstre reel), une solution existe TOUJOURS pour l'amener jusqu'au
monstre final - il suffit de le faire porter par un seul parent a
chaque etape de la chaine qui mene a ce monstre. Le solveur essaie
cette option de propagation simple EN PRIORITE (avant les options plus
couteuses de synthese de talent) afin de garantir qu'une solution
valide est toujours trouvee avant que le budget de recherche ne
s'epuise, meme si elle n'est pas la plus optimisee possible.

------------------------------------------------------------------
ARBRES INTERMEDIAIRES ("greffe")
------------------------------------------------------------------
En complement de la resolution unifiee ci-dessus, le solveur a la
possibilite de construire, pour chaque talent demande, un arbre
INTERMEDIAIRE independant du monstre final : "quelle est la maniere la
moins couteuse d'obtenir CE talent, sur N'IMPORTE QUELLE espece ?"
(reutilise resolve_talent_chain/simplify_chain de synthese_core.py).

Cet arbre intermediaire est ensuite "introduit" (greffe) dans l'arbre
principal partout ou une place libre s'y prete : un ingredient "libre"
(placeholder de famille/rang) dont la famille/rang correspond
exactement a l'espece racine de l'arbre intermediaire. La greffe n'est
utilisee que si elle est MOINS couteuse que la recherche normale
(candidat par candidat) a cet emplacement ; sinon, la recherche
normale reste utilisee. Un noeud greffe est marque
`"grafted_talent": True` pour etre signale dans l'affichage.

Limite assumee : la greffe ne s'applique qu'aux emplacements ou
'required_talents' a cet endroit est un singleton (un seul talent),
qui couvre la grande majorite des cas pratiques (chaque etape d'une
chaine "points" ne demande qu'un seul talent par parent).
------------------------------------------------------------------
EXCLUSION DE MONSTRES SAUVAGES ("liste des monstres disponibles")
------------------------------------------------------------------
Le joueur peut decocher, dans la liste "Monstres disponibles dans la
nature" affichee sous l'arbre, des monstres qu'il ne souhaite pas
utiliser comme individu capture directement dans la nature (ex: il ne
veut pas farmer tel monstre, ou considere qu'il n'y a pas acces pour
l'instant). Cette exclusion est representee par 'excluded_wild_ids'
(un frozenset de MonsterId), qui circule a travers TOUTES les
fonctions de resolution de ce fichier.

Un monstre exclu n'est simplement plus jamais propose comme feuille
"capture sauvage" (cout 0) : il reste en revanche parfaitement
utilisable comme RESULTAT d'une synthese (le joueur peut tres bien
vouloir l'obtenir par elevage plutot que par capture). C'est cette
nuance qui justifie de ne desactiver que l'Option 1 ("capture
sauvage") de solve_monster, sans toucher au reste de la recherche.
------------------------------------------------------------------
HYPOTHESES / SIMPLIFICATIONS ASSUMEES (a lire avant de faire confiance
aux resultats)
------------------------------------------------------------------
- Un individu d'une espece a TOUJOURS acces a ses talents "natifs"
  (MonsterTalent.csv), qu'il soit capture a l'etat sauvage OU obtenu
  par synthese. C'est le comportement du moteur precedent, conserve
  pour rester coherent (le mecanisme de "personnalite" exact du jeu
  n'est pas modelise dans le detail).
- La synthese a 4 monstres (grands-parents) n'est PAS re-optimisee
  talent par talent dans cette version : l'espece intermediaire reste
  "libre" comme avant, sans propagation fine des talents a travers les
  grands-parents. Limite connue, assumee explicitement.
- Le "cout" d'un noeud = nombre de syntheses necessaires pour
  l'obtenir (recursif) ; une capture sauvage coute 0.
- Pour limiter l'explosion combinatoire (un talent peut avoir plusieurs
  recettes alternatives, et il peut y avoir plusieurs talents a
  repartir sur 2 parents en meme temps), le solveur limite le nombre
  de recettes de talent explorees par talent ET le nombre total
  d'appels recursifs (garde-fou anti-explosion). Au-dela, il retourne
  la meilleure solution trouvee jusque-la (peut ne pas etre l'optimum
  absolu dans les cas les plus complexes, mais reste une solution
  valide).
"""

from synthese_core import (
    is_capturable,
    is_family_placeholder,
    rank_meets_minimum,
    get_talent_recipes,
    talent_exists_anywhere,
    resolve_talent_chain,
    simplify_chain,
    get_egg_source_label,
    capture_difficulty,
)

MAX_DEPTH = 16
MAX_TALENT_RECIPES_PER_TALENT = 2   # limite l'explosion combinatoire
MAX_CALLS = 1500000                  # garde-fou : arrete la recherche au-dela (~3-5s)


# ---------------------------------------------------------------------------
# COUT A 2 DIMENSIONS : (nombre_de_syntheses, difficulte_cumulee)
# ---------------------------------------------------------------------------
# Le "cout" d'un noeud n'est plus un simple entier (nombre de syntheses),
# mais un TUPLE (nb_syntheses, difficulte). Python compare les tuples
# lexicographiquement : le nombre de syntheses reste le critere principal
# (un arbre plus court gagne toujours), mais A NOMBRE DE SYNTHESES EGAL,
# celui utilisant des monstres plus FACILES A OBTENIR (rang bas, zone peu
# avancee) l'emporte. Ca evite par exemple qu'un Slime "Metal" (rang
# eleve, zone tardive, notoirement difficile a capturer en pratique meme
# si techniquement "capturable") ne soit prefere a un Gluant de base
# quand les deux menent au meme resultat en autant d'etapes.

def _wild_cost(db, monster, reachable):
    """Cout d'une feuille obtenue par capture (ou oeuf special) : 0
    synthese, plus la difficulte reelle d'obtention de CE monstre."""
    return (0, capture_difficulty(db, monster, reachable))


def _combine_cost(cost1, cost2):
    """Cout d'un noeud resultant de la combinaison de 2 parents : 1
    synthese de plus, difficultes cumulees."""
    return (1 + cost1[0] + cost2[0], cost1[1] + cost2[1])


class _SearchBudget:
    """Compteur partage entre tous les appels recursifs d'une resolution,
    pour eviter qu'une combinatoire pathologique ne bloque le serveur."""
    __slots__ = ("calls", "exhausted", "limit")

    def __init__(self, limit=None):
        self.calls = 0
        self.exhausted = False
        self.limit = limit if limit is not None else MAX_CALLS

    def tick(self):
        self.calls += 1
        if self.calls > self.limit:
            self.exhausted = True
        return not self.exhausted

    def should_stop_early(self):
        """Passe en mode 'satisficing' (accepter la premiere solution
        valide trouvee plutot que de continuer a chercher mieux) une
        fois qu'une bonne partie du budget est deja consommee. Evite
        qu'un arbre genealogique tres profond (beaucoup de niveaux et
        de recettes alternatives) n'epuise tout le budget a essayer
        d'optimiser au lieu de trouver ne serait-ce QU'UNE solution."""
        return self.calls > self.limit * 0.4


GREEDY_BRANCH_DEPTH_LIMIT = 5  # au-dela de cette profondeur, un seul choix par talent (evite l'explosion)


def _assign_talents(db, remaining, idx=0, req1=None, req2=None, transitions=None, greedy=None, depth=0):
    """Genere (backtracking) les repartitions possibles d'un ensemble de
    talents 'remaining' entre les 2 parents d'une synthese, selon la
    regle de deblocage propre a chaque talent (points / simple /
    feuille).

    MODE GLOUTON : quand PLUSIEURS talents doivent etre repartis EN
    MEME TEMPS (typiquement les 3 talents demandes a la racine), le
    produit cartesien des alternatives par talent explose bien au-dela
    de ce qui est exploitable, D'AUTANT PLUS que cette repartition se
    reproduit a CHAQUE niveau de l'arbre d'especes (profondeur 8-15
    niveaux courante). Dans ce cas :
    - pres de la racine (profondeur < GREEDY_BRANCH_DEPTH_LIMIT), on
      garde 2 choix par talent (un peu de marge si le premier choix
      mene a une impasse plus bas) ;
    - au-dela, un seul choix deterministe par talent (sinon la
      combinatoire profondeur x branchement explose de facon
      ingerable). Quand un seul talent est en jeu (cas frequent en
      profondeur, ou l'optimisation du cout compte le plus), toutes les
      alternatives restent explorees normalement, quelle que soit la
      profondeur."""
    remaining = list(remaining)
    if req1 is None:
        req1, req2, transitions = set(), set(), []
    if greedy is None:
        greedy = len(remaining) > 1

    if idx >= len(remaining):
        yield set(req1), set(req2), list(transitions)
        return

    talent_id = remaining[idx]
    recipes = get_talent_recipes(db, talent_id)[:MAX_TALENT_RECIPES_PER_TALENT]

    feuille_branches = [({talent_id}, set(), None), (set(), {talent_id}, None)]

    recipe_branches = []
    for recipe in recipes:
        if recipe["category"] == "points":
            prereq = recipe["combo"][0]
            transition = {"category": "points", "result_id": talent_id, "prereq_ids": [prereq]}
            recipe_branches.append(({prereq}, {prereq}, transition))
        else:
            a, b = recipe["combo"]
            transition = {"category": "simple", "result_id": talent_id, "prereq_ids": [a, b]}
            recipe_branches.append(({a}, {b}, transition))
            recipe_branches.append(({b}, {a}, transition))

    # PRIORITE DYNAMIQUE :
    # - Si ce talent existe NATIVEMENT quelque part dans le jeu (ou n'a
    #   aucune recette de synthese connue), la propagation "un seul
    #   parent le porte" (nativement ou via sa propre chaine) a de
    #   bonnes chances d'aboutir rapidement -> on la tente EN PREMIER.
    #   Un talent, une fois obtenu, n'est jamais perdu : il se transmet
    #   a chaque synthese ulterieure tant qu'un parent le porte, donc
    #   cette route garantit une solution des que le talent existe
    #   quelque part.
    # - Si ce talent n'existe QUE via une recette de synthese de talent
    #   (ex: un palier de Booster au-dela du niveau I, jamais natif chez
    #   aucune espece), la route "feuille" est un cul-de-sac qui ne mene
    #   jamais nulle part (aucune espece ne le porte jamais nativement,
    #   la recursion tourne en rond) -> on privilegie directement la
    #   vraie recette de synthese de talent, seule route viable.
    if not recipes or talent_exists_anywhere(db, talent_id):
        branches = feuille_branches + recipe_branches
    else:
        branches = recipe_branches + feuille_branches

    if greedy:
        branches = branches[:2] if depth < GREEDY_BRANCH_DEPTH_LIMIT else branches[:1]

    for add1, add2, transition in branches:
        new_req1 = set(req1) | add1
        new_req2 = set(req2) | add2
        new_transitions = list(transitions)
        if transition:
            new_transitions.append(transition)
        yield from _assign_talents(db, remaining, idx + 1, new_req1, new_req2, new_transitions, greedy, depth)


def _chain_to_solver_node(db, chain_node, collected=None):
    """Convertit un noeud de chaine de talent INDEPENDANTE (deja
    simplifiee a un seul chemin par simplify_chain, cf.
    synthese_core.resolve_talent_chain) vers le format de noeud unifie
    utilise par solve_monster, pour un affichage et une greffe
    homogenes dans l'arbre principal.

    Si 'collected' (dict) est fourni, ENREGISTRE au passage chaque
    sous-noeud converti, indexe par son propre talent_id - ce qui
    permet de recuperer gratuitement des arbres greffables pour TOUS
    les talents INTERMEDIAIRES de la chaine (pas seulement le talent
    final demande), cf. build_intermediate_talent_trees.

    Renvoie None si la chaine est en impasse (aucune solution)."""
    talent_id = chain_node["talent_id"]

    if chain_node["wild_candidates"]:
        candidate = chain_node["wild_candidates"][0]
        monster = db.monster_by_name.get(candidate["monster_name"].strip().lower())
        monster_id = monster["MonsterId"] if monster else None
        node = {
            "kind": "wild",
            "monster_id": monster_id,
            "name": candidate["monster_name"],
            "capture_locations": candidate["locations"],
            "native_talents": db.talent_ids_by_monster.get(monster_id, {talent_id}),
            "required_talents": {talent_id},
            "transitions": [],
            "parent1": None,
            "parent2": None,
            "recommended_level": db.recommended_level({talent_id}),
            "cost": (0, capture_difficulty(db, monster, None) if monster else 0.0),
            "grafted_talent": True,
        }
        if collected is not None:
            collected[talent_id] = node
        return node

    if chain_node["options"]:
        option = chain_node["options"][0]
        if option["category"] == "points":
            slot = option["slots"][0]
            child1 = _chain_to_solver_node(db, slot, collected)
            child2 = _chain_to_solver_node(db, slot, collected)
            if not child1 or not child2:
                return None
            transition = {"category": "points", "result_id": talent_id, "prereq_ids": [slot["talent_id"]]}
        else:
            child1 = _chain_to_solver_node(db, option["slots"][0], collected)
            child2 = _chain_to_solver_node(db, option["slots"][1], collected)
            if not child1 or not child2:
                return None
            transition = {
                "category": "simple",
                "result_id": talent_id,
                "prereq_ids": [option["slots"][0]["talent_id"], option["slots"][1]["talent_id"]],
            }
        node = {
            "kind": "synth",
            "monster_id": None,
            "name": f"Porteur de {db.talent_by_id[talent_id]['Name']}",
            "capture_locations": [],
            "native_talents": set(),
            "required_talents": {talent_id},
            "transitions": [transition],
            "parent1": child1,
            "parent2": child2,
            "recommended_level": option.get("recommended_level"),
            "cost": _combine_cost(child1["cost"], child2["cost"]),
            "grafted_talent": True,
        }
        if collected is not None:
            collected[talent_id] = node
        return node

    return None


def build_intermediate_talent_trees(db, talent_ids, reachable, excluded_wild_ids=None):
    """Construit, pour CHAQUE talent de 'talent_ids' (typiquement les 3
    talents finaux demandes), un arbre intermediaire independant du
    monstre final (la maniere la moins couteuse d'obtenir ce talent sur
    N'IMPORTE QUELLE espece) - ET, gratuitement au passage, un arbre
    pour CHAQUE talent INTERMEDIAIRE rencontre dans ces chaines (ex:
    pour Hair Splitter, on obtient aussi Freezer Burner, Air Fryer,
    Spicy/Soggy/Blowy Slasher...). Cette couverture etendue est ce qui
    permet a la greffe de s'appliquer meme quand le talent final
    lui-meme n'a pas de porteur sauvage direct, mais que ses
    PREREQUIS, eux, en ont un.

    'excluded_wild_ids' est propage a resolve_talent_chain pour ne
    jamais proposer un monstre decoche comme porteur sauvage racine
    d'un arbre intermediaire.

    Renvoie {talent_id: noeud_convertit} - seuls les talents pour
    lesquels une solution existe sont presents dans le resultat."""
    trees = {}
    for talent_id in talent_ids:
        if talent_id in trees:
            continue  # deja couvert par la conversion d'une chaine precedente
        chain = resolve_talent_chain(db, talent_id, reachable, excluded_wild_ids=excluded_wild_ids)
        simplify_chain(chain)
        _chain_to_solver_node(db, chain, collected=trees)
    return trees


def solve_monster(db, species_id, required_talents, reachable, budget=None, cache=None, _depth=0, _visited=None, intermediate_trees=None, excluded_wild_ids=None):
    """Coeur du moteur : trouve la maniere la MOINS COUTEUSE d'obtenir un
    individu de l'espece 'species_id' qui porte TOUS les talents de
    'required_talents' (frozenset de TalentId).

    Renvoie un noeud (dict) ou None si infaisable avec les donnees et la
    zone actuelles.

    'excluded_wild_ids' (frozenset de MonsterId, optionnel) : monstres
    decoches par le joueur dans la liste "Monstres disponibles dans la
    nature" - jamais proposes comme individu capture directement (cf.
    section "EXCLUSION DE MONSTRES SAUVAGES" en tete de fichier).

    Noeud renvoye :
        {
            "kind": "wild" | "synth" | "unresolved",
            "monster_id":, "name":,
            "capture_locations": [...],           # zones si capturable
            "native_talents": set(TalentId),      # talents natifs de l'espece
            "required_talents": set(TalentId),    # ce que CE noeud doit transporter
            "transitions": [...],                 # syntheses de talent declenchees ICI
            "parent1": <noeud> | None,
            "parent2": <noeud> | None,
            "recommended_level": int | None,
            "cost": int,                          # nombre de syntheses necessaires
        }
    """
    if budget is None:
        budget = _SearchBudget()
    if cache is None:
        cache = {}
    if _visited is None:
        _visited = set()
    if excluded_wild_ids is None:
        excluded_wild_ids = frozenset()

    required_talents = frozenset(required_talents)
    key = (species_id, required_talents)
    if key in cache:
        return cache[key]

    if _depth > MAX_DEPTH or key in _visited or not budget.tick():
        return None

    monster = db.monster_by_id.get(species_id)
    if monster is None:
        return None

    native = db.talent_ids_by_monster.get(species_id, set())
    display_name = monster["FrenchName"] or monster["Name"]

    # --- Option 1 : capture sauvage (cout 0), si elle suffit a couvrir
    #     tous les talents requis - SAUF si ce monstre a ete decoche de
    #     la liste "Monstres disponibles dans la nature" -------------
    if not is_family_placeholder(monster) and species_id not in excluded_wild_ids:
        locations = is_capturable(db, species_id, reachable)
        egg_label = None
        if not locations and not db.synth_by_result.get(species_id):
            # Aucune capture ET aucune recette de synthese connue :
            # si ce monstre possede un EggTypeId, il est obtenu
            # EXCLUSIVEMENT via eclosion d'un oeuf special (mecanisme
            # confirme pour plusieurs monstres du jeu, ex: Robin 'ood).
            egg_label = get_egg_source_label(monster)
        if (locations or egg_label) and required_talents <= native:
            node = {
                "kind": "wild",
                "monster_id": species_id,
                "name": display_name,
                "capture_locations": locations if locations else [egg_label],
                "native_talents": native,
                "required_talents": set(required_talents),
                "transitions": [],
                "parent1": None,
                "parent2": None,
                "recommended_level": db.recommended_level(required_talents) if required_talents else None,
                "cost": _wild_cost(db, monster, reachable),
            }
            cache[key] = node
            return node

    visited_next = _visited | {key}

    # --- Option 2 : "ingredient libre" (placeholder famille/rang) : on
    #     essaie chaque espece reelle de la famille (et du rang, sauf
    #     rang "Any"), et on garde la moins couteuse. C'est un OR sur
    #     toutes les especes candidates, chacune resolue normalement. --
    if is_family_placeholder(monster):
        family_id = monster["FamilyId"]
        rank_id = monster["RankId"]
        rank_is_any = db.rank_by_id.get(rank_id, {}).get("Identifier") == "any"
        candidate_ids = {
            m["MonsterId"] for m in db.monsters
            if m["FamilyId"] == family_id
            and not is_family_placeholder(m)
            and rank_meets_minimum(m["RankId"], rank_id, rank_is_any)
        }
        best = None

        # --- Greffe : si un arbre intermediaire independant a deja ete
        #     construit pour LE talent demande ici (cas frequent : un seul
        #     talent par emplacement), et que son espece racine appartient
        #     bien a cette famille/rang, on peut l'inserer directement
        #     (deja calcule, quasi gratuit) au lieu de re-chercher parmi
        #     tous les candidats. --------------------------------------
        if intermediate_trees and len(required_talents) == 1:
            only_talent = next(iter(required_talents))
            grafted = intermediate_trees.get(only_talent)
            if grafted and grafted.get("monster_id") in candidate_ids:
                best = grafted

        for cand_id in candidate_ids:
            if not budget.tick():
                break
            if best is not None and budget.should_stop_early():
                break
            sub = solve_monster(db, cand_id, required_talents, reachable, budget, cache, _depth + 1, visited_next, intermediate_trees, excluded_wild_ids)
            if sub and (best is None or sub["cost"] < best["cost"]):
                best = sub

        if best is not None:
            # Copie legere (ne PAS muter l'objet partage du cache/de
            # intermediate_trees) pour marquer ce noeud comme issu d'un
            # emplacement "libre" (placeholder famille/rang) - utile
            # pour la strategie de secours "arbres intermediaires
            # greffes" (decompose_and_graft) qui a besoin de retrouver
            # ces emplacements pour y inserer un talent apres coup.
            best = dict(best)
            best["is_free_slot"] = True
            best["free_family_id"] = family_id
            best["free_rank_id"] = rank_id
            best["free_rank_is_any"] = rank_is_any
            cache[key] = best
        return best

    # --- Option 3 : synthese (recettes a 2 parents fixes OU a 4 monstres
    #     via grands-parents) ---------------------------------------
    remaining = required_talents - native
    recipes = db.synth_by_result.get(species_id, [])
    best = None

    for recipe in recipes:
        if budget.exhausted:
            break
        if best is not None and budget.should_stop_early():
            break
        p1s, p2s = recipe["MonsterParent1Id"], recipe["MonsterParent2Id"]

        if p1s and p2s:
            # --- cas standard : 2 parents fixes -----------------------
            for req1, req2, transitions in _assign_talents(db, remaining, depth=_depth):
                if not budget.tick():
                    break
                if best is not None and budget.should_stop_early():
                    break
                sub1 = solve_monster(db, p1s, frozenset(req1), reachable, budget, cache, _depth + 1, visited_next, intermediate_trees, excluded_wild_ids)
                if not sub1:
                    continue
                sub2 = solve_monster(db, p2s, frozenset(req2), reachable, budget, cache, _depth + 1, visited_next, intermediate_trees, excluded_wild_ids)
                if not sub2:
                    continue
                cost = _combine_cost(sub1["cost"], sub2["cost"])
                if best is None or cost < best["cost"]:
                    best = {
                        "kind": "synth",
                        "monster_id": species_id,
                        "name": display_name,
                        "capture_locations": is_capturable(db, species_id, reachable),
                        "native_talents": native,
                        "required_talents": set(required_talents),
                        "transitions": transitions,
                        "parent1": sub1,
                        "parent2": sub2,
                        "recommended_level": db.recommended_level(remaining) if remaining else None,
                        "cost": cost,
                    }
            continue

        # --- cas synthese a 4 monstres (grands-parents) ----------------
        # GrandParent1A + GrandParent1B -> fusion intermediaire 1
        # GrandParent2A + GrandParent2B -> fusion intermediaire 2
        # fusion1 + fusion2 -> resultat. L'espece de chaque fusion
        # intermediaire n'est PAS fixee dans les donnees (le jeu la
        # determine differemment) ; ce noeud represente donc juste "une
        # fusion qui transporte les talents requis", peu importe
        # l'espece exacte obtenue.
        gp1a, gp1b = recipe["MonsterGrandParent1AId"], recipe["MonsterGrandParent1BId"]
        gp2a, gp2b = recipe["MonsterGrandParent2AId"], recipe["MonsterGrandParent2BId"]
        if not (gp1a and gp1b and gp2a and gp2b):
            continue  # donnee incomplete/inattendue, on ignore cette recette

        for req1, req2, transitions in _assign_talents(db, remaining, depth=_depth):
            if not budget.tick():
                break
            if best is not None and budget.should_stop_early():
                break
            inter1 = _solve_intermediate_pair(db, gp1a, gp1b, frozenset(req1), reachable, budget, cache, _depth + 1, visited_next, intermediate_trees, excluded_wild_ids)
            if not inter1:
                continue
            inter2 = _solve_intermediate_pair(db, gp2a, gp2b, frozenset(req2), reachable, budget, cache, _depth + 1, visited_next, intermediate_trees, excluded_wild_ids)
            if not inter2:
                continue
            cost = _combine_cost(inter1["cost"], inter2["cost"])
            if best is None or cost < best["cost"]:
                best = {
                    "kind": "synth",
                    "monster_id": species_id,
                    "name": display_name,
                    "capture_locations": is_capturable(db, species_id, reachable),
                    "native_talents": native,
                    "required_talents": set(required_talents),
                    "transitions": transitions,
                    "parent1": inter1,
                    "parent2": inter2,
                    "recommended_level": db.recommended_level(remaining) if remaining else None,
                    "cost": cost,
                }

    if best is not None:
        cache[key] = best
    return best


def _solve_intermediate_pair(db, gp_a, gp_b, required_talents, reachable, budget, cache, depth, visited, intermediate_trees, excluded_wild_ids=None):
    """Resout la fusion de 2 grands-parents dans une synthese a 4
    monstres. L'espece resultante intermediaire n'est PAS fixee dans
    les donnees brutes (le jeu la determine par d'autres mecanismes non
    modelises ici) : ce noeud represente donc uniquement "une fusion
    qui transporte les talents requis", sans espece precise ni talents
    natifs propres. Utilise une cle de cache dediee pour ne pas entrer
    en collision avec le cache des especes normales."""
    if budget.exhausted or depth > MAX_DEPTH:
        return None

    cache_key = ("__intermediate__", gp_a, gp_b, frozenset(required_talents))
    if cache_key in cache:
        return cache[cache_key]

    best = None
    for req1, req2, transitions in _assign_talents(db, required_talents, depth=depth):
        if not budget.tick():
            break
        if best is not None and budget.should_stop_early():
            break
        sub1 = solve_monster(db, gp_a, frozenset(req1), reachable, budget, cache, depth + 1, visited, intermediate_trees, excluded_wild_ids)
        if not sub1:
            continue
        sub2 = solve_monster(db, gp_b, frozenset(req2), reachable, budget, cache, depth + 1, visited, intermediate_trees, excluded_wild_ids)
        if not sub2:
            continue
        cost = _combine_cost(sub1["cost"], sub2["cost"])
        if best is None or cost < best["cost"]:
            best = {
                "kind": "intermediate",
                "monster_id": None,
                "name": "Fusion intermédiaire (espèce variable)",
                "capture_locations": [],
                "native_talents": set(),
                "required_talents": set(required_talents),
                "transitions": transitions,
                "parent1": sub1,
                "parent2": sub2,
                "recommended_level": db.recommended_level(required_talents) if required_talents else None,
                "cost": cost,
            }

    if best is not None:
        cache[cache_key] = best
    return best


def solve(db, target_monster_id, target_talent_names, reachable, max_calls=None, excluded_wild_ids=None):
    """Point d'entree public. Resout simultanement le monstre final ET
    les talents demandes (un seul arbre unifie, pas un arbre par
    objectif).

    Avant de lancer la recherche principale, construit un arbre
    INTERMEDIAIRE independant pour chaque talent demande (la maniere la
    moins couteuse d'obtenir ce talent sur N'IMPORTE QUELLE espece), qui
    sera introduit ("greffe") dans l'arbre principal partout ou un
    ingredient libre de la bonne famille/rang s'y prete - cf.
    build_intermediate_talent_trees et la section "ARBRES
    INTERMEDIAIRES" en tete de ce fichier.

    'max_calls' permet de brider le budget de recherche pour CET appel
    precis (utilise par app.py pour une premiere tentative rapide avant
    de basculer sur la strategie de secours decompose_and_graft si elle
    echoue - cf. section "STRATEGIE DE SECOURS" plus haut).

    'excluded_wild_ids' (optionnel) : ensemble des MonsterId decoches
    par le joueur dans la liste "Monstres disponibles dans la nature",
    jamais utilises comme individu capture directement (cf. section
    "EXCLUSION DE MONSTRES SAUVAGES" en tete de fichier).

    Renvoie (root_node_ou_None, final_talent_ids, noms_talents_inconnus,
    budget_exhausted). 'budget_exhausted' est True si la recherche a du
    s'arreter par manque de budget SANS avoir prouve l'infaisabilite -
    utile pour distinguer un cas VRAIMENT impossible (aucune solution
    n'existe dans les donnees) d'un cas OU la recherche est simplement
    trop complexe pour etre entierement exploree dans le temps imparti
    (ex: plusieurs talents exigeants a la fois sur un monstre a la
    genealogie tres profonde).
    """
    if excluded_wild_ids is None:
        excluded_wild_ids = frozenset()

    final_talent_ids = set()
    unknown_names = []
    for name in target_talent_names:
        name = (name or "").strip()
        if not name:
            continue
        talent = db.talent_by_name.get(name.lower())
        if talent:
            final_talent_ids.add(talent["TalentId"])
        else:
            unknown_names.append(name)

    # Court-circuit rapide et HONNETE : si TOUS les talents demandes
    # n'ont AUCUNE source connue dans les donnees (ni natif quelque
    # part, ni aucune chaine de synthese de talent n'y menant), c'est
    # une impossibilite PROUVEE - inutile de lancer la recherche
    # couteuse. En revanche, si SEULEMENT CERTAINS talents sont
    # impossibles (mais pas tous), on NE bloque PAS ici : le flux
    # normal (recherche rapide puis decomposition) doit pouvoir
    # continuer et proposer une solution pour les talents qui ONT une
    # chance, le(s) talent(s) impossible(s) finissant naturellement
    # dans la liste des "non assignes" (cf. decompose_and_graft) plutot
    # que de bloquer TOUTE la demande a cause d'un seul talent absent
    # des donnees.
    if final_talent_ids:
        native_to_target = db.talent_ids_by_monster.get(target_monster_id, set())
        all_impossible = True
        for talent_id in final_talent_ids:
            if talent_id in native_to_target:
                # Deja natif au monstre CIBLE lui-meme (ex: le talent
                # signature "Zoma" est natif au monstre "Zoma") : pas
                # besoin d'une chaine de construction independante.
                all_impossible = False
                break
            # Condition d'impossibilite PROUVEE (prudente) : le talent
            # n'est natif chez AUCUN monstre reel du jeu, ET aucune
            # recette de synthese de talent ne permet de l'obtenir.
            if talent_exists_anywhere(db, talent_id) or get_talent_recipes(db, talent_id):
                all_impossible = False
                break
        if all_impossible:
            return None, final_talent_ids, unknown_names, False

    intermediate_trees = build_intermediate_talent_trees(db, final_talent_ids, reachable, excluded_wild_ids)

    budget = _SearchBudget(limit=max_calls)
    root = solve_monster(db, target_monster_id, frozenset(final_talent_ids), reachable, budget, intermediate_trees=intermediate_trees, excluded_wild_ids=excluded_wild_ids)

    return root, final_talent_ids, unknown_names, budget.exhausted


# ---------------------------------------------------------------------------
# 7. STRATEGIE DE SECOURS : decomposition en arbres intermediaires
# ---------------------------------------------------------------------------
#
# Quand la recherche unifiee (solve_monster avec TOUS les talents a la
# fois) devient trop complexe - typiquement 2+ talents exigeants sur un
# monstre a la genealogie tres profonde - le nombre de combinaisons a
# explorer peut depasser ce qui est raisonnable pour une reponse web
# rapide, sans que ca signifie qu'aucune solution n'existe.
#
# Dans ce cas, on bascule sur une strategie plus simple et beaucoup
# moins couteuse en calcul : DECOMPOSER le probleme.
#   1) Resoudre l'ARBRE DE L'ESPECE SEULE (sans aucun talent) - rapide,
#      quasi toujours instantane meme pour une genealogie profonde,
#      puisqu'il n'y a pas de talent a faire transiter.
#   2) Construire, pour CHAQUE talent demande, un arbre INDEPENDANT
#      (n'importe quelle espece) - deja fait par
#      build_intermediate_talent_trees.
#   3) INTRODUIRE (greffer) chacun de ces arbres a la place d'un
#      ingredient "libre" (placeholder de famille/rang) de l'arbre
#      d'espece, chaque fois que la famille/rang correspond.
#
# Cette approche est moins couteuse car elle evite totalement la
# combinatoire de repartition simultanee de plusieurs talents entre les
# 2 parents A CHAQUE niveau de l'arbre (qui est la source de
# l'explosion) : chaque talent est resolu une fois, independamment, une
# bonne fois pour toutes. En contrepartie, la solution obtenue peut
# etre legerement moins optimisee (plus de syntheses au total) que ce
# qu'une recherche exhaustive aurait pu trouver - c'est le compromis
# assume pour garantir une reponse rapide et fiable.

def collect_free_slots(node, acc=None):
    """Parcourt (recursif) un arbre deja resolu et collecte les
    REFERENCES (memes objets, pas des copies) de tous les noeuds marques
    comme issus d'un emplacement 'libre' (placeholder de famille/rang),
    dans l'ordre d'apparition. Utilise par decompose_and_graft pour
    trouver ou inserer les talents demandes."""
    if acc is None:
        acc = []
    if node.get("is_free_slot"):
        acc.append(node)
    for parent_key in ("parent1", "parent2"):
        child = node.get(parent_key)
        if child:
            collect_free_slots(child, acc)
    return acc


def build_species_only_tree(db, target_species, reachable, excluded_wild_ids=None):
    """Resout l'arbre de l'espece SEULE, sans aucune contrainte de
    talent. Beaucoup plus rapide/leger que la resolution unifiee car il
    n'y a pas de combinatoire de repartition de talents a explorer."""
    budget = _SearchBudget()
    return solve_monster(db, target_species, frozenset(), reachable, budget, excluded_wild_ids=excluded_wild_ids)


FAMILY_SCOPE_MAX_CANDIDATES = 20         # nb max d'especes candidates essayees par talent/famille
FAMILY_SCOPE_MAX_CALLS_PER_CANDIDATE = 150_000  # budget dedie et borne par candidat


def solve_family_scoped(db, family_id, rank_id, rank_is_any, talent_id, reachable, cache=None, excluded_wild_ids=None):
    """DIVIDE & CONQUER : recherche FOCALISEE (un seul talent, une seule
    famille/rang a la fois) parmi les especes REELLES de cette
    famille/rang, capable de porter 'talent_id' - via sa PROPRE
    genealogie, potentiellement synthetisee (contrairement a
    build_intermediate_talent_trees qui est purement species-agnostique
    et ne peut donc pas garantir que le porteur trouve appartient a la
    bonne famille).

    Beaucoup moins couteux que la recherche globale unifiee car
    circonscrit a UN SEUL talent, et le budget est bride PAR CANDIDAT
    (un candidat recalcitrant n'empeche pas d'essayer les suivants).
    S'arrete au PREMIER succes trouve (privilegie la rapidite/fiabilite
    sur l'optimalite absolue, coherent avec l'esprit "diviser pour
    reduire la complexite").

    'cache' (dict optionnel, partage entre plusieurs appels) evite de
    refaire la meme recherche si le meme (famille, rang, talent)
    revient a plusieurs endroits de l'arbre.

    'excluded_wild_ids' est propage a chaque resolution de candidat
    (cf. section "EXCLUSION DE MONSTRES SAUVAGES" en tete de fichier)."""
    cache_key = (family_id, rank_id, rank_is_any, talent_id)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    candidates = [
        m for m in db.monsters
        if m["FamilyId"] == family_id
        and not is_family_placeholder(m)
        and rank_meets_minimum(m["RankId"], rank_id, rank_is_any)
    ]

    # Priorite aux candidats porteurs NATIFS du talent (cout 0 si
    # capturables) avant d'essayer les autres, dont la construction
    # peut necessiter sa propre synthese - garantit de trouver la
    # solution la plus simple en premier quand elle existe (ex: un
    # monstre sauvage qui connait deja nativement le talent).
    native_ids = set(db.monsters_by_talent.get(talent_id, []))
    native_candidates = [m for m in candidates if m["MonsterId"] in native_ids]
    other_candidates = [m for m in candidates if m["MonsterId"] not in native_ids]

    # Parmi les candidats natifs (cout 0 si capturables), essaie d'abord
    # les plus FACILES A OBTENIR (rang bas, zone peu avancee) - sinon le
    # premier trouve dans l'ordre naturel des donnees pourrait etre un
    # monstre difficile (ex: Slime "Metal", rang eleve/zone tardive)
    # alors qu'un candidat bien plus simple existe dans la meme famille.
    native_candidates.sort(key=lambda m: capture_difficulty(db, m, reachable))

    ordered_candidates = (native_candidates + other_candidates)[:FAMILY_SCOPE_MAX_CANDIDATES]

    result = None
    for cand in ordered_candidates:
        budget = _SearchBudget(limit=FAMILY_SCOPE_MAX_CALLS_PER_CANDIDATE)
        sub = solve_monster(db, cand["MonsterId"], frozenset({talent_id}), reachable, budget, excluded_wild_ids=excluded_wild_ids)
        if sub:
            result = sub
            break  # premier succes : on s'arrete (rapidite avant optimalite)

    if cache is not None:
        cache[cache_key] = result
    return result


def decompose_and_graft(db, target_species, final_talent_ids, reachable, excluded_wild_ids=None):
    """Strategie de secours (cf. section 7 ci-dessus) : resout l'espece
    seule, puis introduit independamment chaque talent demande a la
    place d'un ingredient libre compatible (meme famille, et meme rang
    sauf rang 'Any'), en 2 passes :

    PASSE 1 (rapide) : talents SIMPLES dont la racine de construction
    est directement un individu sauvage (ex: Zap Ward) - reutilise les
    arbres intermediaires species-agnostiques deja disponibles, cout
    quasi nul.

    PASSE 2 (DIVIDE & CONQUER, pour les talents COMPLEXES restants,
    ex: Attack Booster IV, Hair Splitter) : pour chaque emplacement
    libre encore vacant, recherche FOCALISEE (solve_family_scoped) -
    UN SEUL talent, UNE SEULE famille/rang a la fois - parmi les
    especes reelles de cette famille, capable de porter ce talent via
    sa PROPRE genealogie (potentiellement synthetisee). Beaucoup moins
    couteux que la recherche globale car la combinatoire de plusieurs
    talents simultanes sur TOUTE la genealogie ne se produit jamais :
    chaque talent est resolu independamment, un emplacement a la fois.

    'excluded_wild_ids' est propage a chaque etape (arbre de l'espece
    seule, arbres intermediaires, recherche focalisee) - cf. section
    "EXCLUSION DE MONSTRES SAUVAGES" en tete de fichier.

    Renvoie (species_tree_ou_None, talents_assignes, talents_non_assignes).
    - species_tree est None si meme l'espece seule est infaisable avec
      les donnees/zone actuelles (cas rarissime).
    - talents_assignes : ceux deja natifs a la racine OU greffes avec
      succes (passe 1 ou 2) quelque part dans l'arbre.
    - talents_non_assignes : ceux pour lesquels aucun emplacement libre
      de famille/rang compatible n'existe DU TOUT dans cette
      genealogie precise (limite structurelle, pas un manque de temps).
    """
    species_tree = build_species_only_tree(db, target_species, reachable, excluded_wild_ids)
    if species_tree is None:
        return None, set(), set(final_talent_ids)

    native_root = db.talent_ids_by_monster.get(target_species, set())
    already_native = {t for t in final_talent_ids if t in native_root}
    remaining = [t for t in final_talent_ids if t not in native_root]

    if not remaining:
        return species_tree, set(already_native), set()

    free_slots = collect_free_slots(species_tree)
    assigned = set(already_native)

    # --- PASSE 1 : talents simples (racine sauvage directe) ----------
    intermediate_trees = build_intermediate_talent_trees(db, set(remaining), reachable, excluded_wild_ids)
    for slot in free_slots:
        if slot.get("is_free_slot") is not True:
            continue  # deja utilise par une greffe precedente
        if not remaining:
            break
        for talent_id in list(remaining):
            graft = intermediate_trees.get(talent_id)
            if not graft or not graft.get("monster_id"):
                continue
            root_monster = db.monster_by_id.get(graft["monster_id"])
            if not root_monster:
                continue
            same_family = root_monster["FamilyId"] == slot["free_family_id"]
            same_rank = rank_meets_minimum(root_monster["RankId"], slot["free_rank_id"], slot["free_rank_is_any"])
            if same_family and same_rank:
                slot.clear()
                slot.update(graft)
                assigned.add(talent_id)
                remaining.remove(talent_id)
                break

    # --- PASSE 2 : divide & conquer pour les talents complexes restants
    if remaining:
        family_scope_cache = {}
        for slot in free_slots:
            if slot.get("is_free_slot") is not True:
                continue
            if not remaining:
                break
            fam = slot["free_family_id"]
            rank = slot["free_rank_id"]
            is_any = slot["free_rank_is_any"]
            for talent_id in list(remaining):
                solved = solve_family_scoped(db, fam, rank, is_any, talent_id, reachable, family_scope_cache, excluded_wild_ids)
                if solved:
                    slot.clear()
                    slot.update(solved)
                    assigned.add(talent_id)
                    remaining.remove(talent_id)
                    break

    unassigned = set(remaining)
    return species_tree, assigned, unassigned
