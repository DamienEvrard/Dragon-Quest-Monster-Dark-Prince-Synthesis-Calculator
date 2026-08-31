# Calculateur de synthese - DQM: The Dark Prince (projet_23)

## Changements de cette version (projet_23)

### Cout a 2 dimensions : (nombre de syntheses, difficulte reelle d'obtention)
Le "cout" utilise pour choisir entre plusieurs solutions n'est plus un
simple nombre de syntheses : c'est desormais un TUPLE
`(nb_syntheses, difficulte_cumulee)`. Le nombre de syntheses reste le
critere principal (un arbre plus court gagne toujours), mais A NOMBRE
DE SYNTHESES EGAL, la solution utilisant des monstres plus FACILES A
OBTENIR (rang bas, zone peu avancee dans la progression) l'emporte
desormais sur une solution utilisant des monstres plus difficiles.

**Exemple concret verifie** : pour le talent "Crag Ward" (porte par
plusieurs Limons de la famille Slime), le solveur choisit maintenant
"Monte-gluant" (Slime Knight, rang F, plutot facile) au lieu de
"Gluant de metal" (Metal Slime, rang E, notoirement difficile a
capturer en pratique malgre son faible niveau apparent - point
signale par l'utilisateur). Nouvelle fonction `capture_difficulty()`
dans `synthese_core.py` (rang ordinal du monstre + zone de capture la
plus accessible, avec le rang comme critere dominant).

La recherche "divide & conquer" (`solve_family_scoped`) trie
desormais ses candidats natifs par facilite avant de les essayer (elle
s'arrete toujours au premier succes pour rester rapide, mais ce
premier succes est desormais le plus simple plutot que le premier
trouve dans un ordre arbitraire).

### Reutilisation des talents deja construits
Le systeme de cache (par couple espece+talents, partage a travers tout
l'arbre de recherche) garantit deja qu'un MEME talent, pour la MEME
espece, n'est jamais reconstruit deux fois - toute branche qui a
besoin de la meme combinaison reutilise directement le resultat deja
calcule. Quand 2 especes DIFFERENTES (necessairement distinctes, car
fixees par des recettes differentes du jeu) doivent chacune porter
independamment le meme talent, ce n'est pas une redondance evitable
mais une necessite du mecanisme de synthese lui-meme (chaque parent
doit individuellement porter le talent). Verifie : le temps de
resolution du cas "Zoma" (genealogie tres profonde) est passe de
~0.9s a ~0.2s grace a la combinaison de ce cache et du tri par
difficulte qui reduit l'exploration de branches inutiles.

---

### Correction : pages Compendium/Talents recentrées
Le changement de mise en page de la version precedente (elargissement
de l'arbre) avait par erreur decentre les pages Compendium et Talents
(qui n'ont pas de barre laterale). Corrige : ces 2 pages restent
centrees, seule la page Arbre (avec sa barre laterale) beneficie de
l'elargissement.

### Icone "unknown-thumb.png" pour les monstres non specifiques
Recuperee depuis le repo Sprites. Utilisee partout ou un noeud de
l'arbre represente un monstre dont l'espece n'est pas fixee (fusion
intermediaire a 4 monstres, talent construit independamment) ou dans
le Compendium si un monstre n'a pas d'icone associee.

### Bug important corrige : "Zoma" (et d'autres cas similaires) a tort juges impossibles
Deux bugs distincts corriges :
1. Le "court-circuit rapide" (verification d'impossibilite avant de
   lancer la recherche) ne verifiait pas si un talent demande etait
   deja NATIF au monstre CIBLE lui-meme (ex: le talent signature
   "Zoma" est natif au monstre "Zoma") - il pouvait donc conclure a
   tort a l'impossibilite. Egalement, ce court-circuit utilisait une
   fonction qui ne considere que les porteurs directement CAPTURABLES
   comme source valide, ignorant les porteurs eux-memes synthetisables
   (comme certains boss uniques) - remplace par une verification plus
   prudente (talent natif quelque part OU recette de synthese
   existante).
2. **Nouveau mecanisme "oeuf special"** : 19 monstres du jeu (ex:
   "Robin 'ood", confirme par recherche externe comme obtenu
   EXCLUSIVEMENT par eclosion d'un oeuf special) n'ont ni recette de
   synthese ni capture sauvage dans les donnees CSV, ce qui bloquait
   a tort toute une genealogie qui en dependait (le cas de "Zoma",
   dont la lignee remonte a "Robin 'ood"). Ces monstres sont
   desormais reconnus via leur colonne `EggTypeId` (deja presente
   dans Monster.csv mais non exploitee) et traites comme une source
   valide (cout 0), avec la mention "Œuf spécial (type X)" au lieu
   d'une zone de capture.

### Mention du nombre de syntheses retiree
Sur la page Arbre, le texte "Cette solution necessite X synthese(s)"
a ete retire (seule la mention "recherche simplifiee" subsiste
lorsque la decomposition a ete utilisee).

### Niveau recommande recalcule (plusieurs talents simultanes)
Quand un noeud doit faire evoluer PLUSIEURS talents en meme temps (ex:
2 talents actifs sur le meme parent), le niveau recommande est
desormais base sur la SOMME des seuils de points de chaque talent
(chacun a sa propre barre a remplir, avec le meme pool de points
gagnes par niveau) - au lieu du simple maximum utilise avant, qui
sous-estimait le niveau reellement necessaire.

### Traductions francaises des talents et skills (generees, non officielles)
Aucune base de donnees FR structuree n'a ete trouvee pour les 241
talents et 194 skills (contrairement a Monster.csv qui en avait deja
une). Une colonne `FrenchName` a ete ajoutee et remplie pour les
DEUX fichiers, en s'appuyant sur les conventions de traduction bien
etablies de la serie Dragon Quest (Frizz->Flam, Zap->Eclair,
Sizz->Brasier, etc.) et, pour les talents thematiques propres a ce
jeu (ex: "Charmer", "Grump"), sur une traduction de sens.
**ATTENTION : ce ne sont PAS des traductions officielles verifiees**,
mais ma meilleure estimation en l'absence de source fiable - a
corriger si vous connaissez la vraie version francaise du jeu. Les 2
noms (FR/EN) sont desormais affiches dans le Compendium et la page
Talents, comme deja fait pour les monstres.

---

### Plier/deplier une branche de l'arbre
Chaque noeud qui a une synthese (2 parents) affiche desormais un petit
bouton "−" a droite de sa carte. Cliquer dessus masque toute la suite
de l'arbre a partir de ce noeud (le bouton devient "+"), pour se
concentrer sur une partie de l'arbre ou reduire la longueur visible
d'une genealogie tres profonde. Recliquer sur "+" affiche a nouveau la
suite. Purement visuel (cote client, ne recharge pas la page).

### Arbre de synthese elargi
Les marges laterales de la page ont ete reduites et le container de
l'arbre n'est plus limite a une largeur maximale fixe (1120px avant) :
il occupe desormais tout l'espace disponible a droite de la barre
laterale. L'ecart entre la barre laterale ("Arbres enregistres") et
la zone de l'arbre est desormais IDENTIQUE a l'ecart entre le bord
droit de la page et la zone de l'arbre (24px de chaque cote).

---

### Icones des monstres
Les 526 icones reelles ont ete recuperees depuis le repo
MetalKid/DQM3_Database (dossier `Sprites/`), en utilisant la colonne
`Identifier` de `Monster.csv` (deja au bon format, ex: "abyss-diver"
-> `abyss-diver-thumb.png`). Stockees dans `static/icons/`. Affichees :
- a gauche du nom de chaque monstre dans l'arbre de synthese ;
- a gauche du nom dans le tableau du Compendium.
Les 70 "placeholders" de famille/rang (ex: "Slime Family (G)") n'ont
pas d'icone dediee dans le jeu (normal, ce ne sont pas des especes
precises) ; un petit encadre en pointilles s'affiche a la place.

### Detail complet des talents dans le Compendium
Cliquer sur un talent (principal ou secondaire) dans le Compendium
ouvre desormais la MEME fenetre de detail complet que sur la page
Talents : skills/bonus avec points requis, prerequis de synthese
eventuels, et ce que ce talent permet de debloquer - au lieu de
seulement la liste des skills comme avant.

### Mise en page de l'arbre de synthese
La liste des arbres enregistres est deplacee a GAUCHE de l'ecran (au
lieu de la droite), pour laisser toute la largeur disponible a droite
a l'arbre de synthese lui-meme, souvent tres large avec des
genealogies profondes.

---

### Recette manquante corrigee : Woosh Virtuoso
Recherche menee sur Game8.co et Dragon Quest Wiki (dragon-quest.org) :
confirmation par 2 sources independantes que "Woosh Virtuoso" suit
exactement le meme mecanisme que ses 8 talents freres (Crag/Bang/Frizz/
Zam/Crack/Sizz/Zap/Splash Virtuoso) : il s'obtient en synthetisant 2
monstres ayant chacun maximise "Woosh Afficionado". Cette recette
etait tout simplement ABSENTE de `TalentSynthesis.csv` /
`TalentSynthesisTalent.csv` (verifie : c'etait le SEUL des 9 talents
"Virtuoso" a n'avoir aucune recette dans les donnees, une vraie
anomalie isolee, pas un pattern general). Corrige en ajoutant la ligne
manquante (Woosh Virtuoso <- Woosh Afficionado, categorie "points"),
en suivant exactement le meme format que les recettes freres deja
presentes.

**Impact concret verifie** : "Perfect Speller" (qui necessite
Polariser, qui necessite lui-meme Woosh Virtuoso dans toutes ses
variantes) est passe de "structurellement impossible" a "constructible
en 7 etapes". Le cas teste "Krystalinda + Wisdom Booster IV + Perfect
Speller + Blowhard" se resout desormais integralement (0.93s, 77
syntheses), la ou Perfect Speller etait auparavant rapporte comme
"bloque par Woosh Virtuoso, sans aucune source connue".

### Limite identifiee et documentee (pas de correction possible)
Recherche menee sur "Hard Warder", "Holy Warder", "Sparkling Warder"
(egalement signales comme sans aucune source dans nos donnees) :
confirme (Dragon Quest Wiki) que ces talents s'obtiennent
UNIQUEMENT via un parchemin achete en boutique (chez Fizzy, les
week-ends) ou via eclosion d'oeufs "arc-en-ciel" - PAS via capture
sauvage classique ni synthese de monstres. Ce mecanisme d'acquisition
(parchemins/oeufs speciaux) n'est represente par AUCUNE des tables CSV
utilisees (Monster.csv, MonsterTalent.csv, TalentSynthesis.csv). Il
n'y a donc pas de correction de donnees pertinente a apporter pour ces
3 talents avec le schema actuel - ils resteront signales comme "sans
source connue", ce qui est fidele a la realite de nos donnees (memes
si en pratique ils sont bien obtenables en jeu par un autre moyen).

### Portee de cette mise a jour (transparence)
Une verification EXHAUSTIVE de toutes les donnees du jeu (plus de 600
monstres, 241 talents, des centaines de recettes) via recherche web
est une tache tres vaste, longue, et risquee si elle n'est pas menee
avec une source structuree fiable (risque d'erreurs de saisie
manuelle). Cette mise a jour se concentre sur les anomalies
CONCRETEMENT DETECTEES par le solveur (talents rapportes comme "sans
aucune source" alors qu'ils devraient en avoir une), verifiees
individuellement par recherche croisee sur au moins une source fiable
avant modification. D'autres anomalies peuvent exister ailleurs dans
les donnees ; n'hesitez pas a signaler tout autre cas suspect
rencontre pour verification et correction ciblee.

---

### Persistance maximale avant d'abandonner (sur demande explicite)
Le flux de resolution pousse desormais la recherche BEAUCOUP plus loin
avant de proposer un resultat partiel. Concretement, quand la
decomposition rapide ne parvient pas a placer TOUS les talents
demandes, le systeme distingue :
- les talents qui restent **theoriquement constructibles** (leur
  chaine independante de l'espece a un cout fini) mais que la
  decomposition simplifiee n'a pas reussi a placer dans cette
  genealogie precise ;
- les talents **veritablement impossibles** (aucune chaine de
  construction n'existe dans les donnees, quelle que soit l'espece).

Si au moins un talent reste theoriquement constructible, une RECHERCHE
COMPLETE a budget tres eleve (15 millions d'appels, jusqu'a plusieurs
dizaines de secondes si necessaire) est tentee avant d'abandonner -
quel que soit le cout en temps, conformement a la demande explicite.
Ce n'est que si meme cette recherche etendue echoue que le resultat
partiel de la decomposition est propose, avec un message precis.

### Message d'erreur precis : identification du talent bloquant
Nouvelle fonction `find_blocking_talent()` (dans `synthese_core.py`) :
pour un talent structurellement impossible, identifie PRECISEMENT quel
talent-prerequis, plus bas dans sa chaine de construction, n'a
strictement aucune source (ni capture, ni recette de synthese) et
bloque donc tout. Exemple concret verifie : "Perfect Speller" est
desormais signale comme "bloqué par « Woosh Virtuoso », sans aucune
source connue" plutot qu'un simple "aucune solution" generique - ce
dernier talent n'a effectivement aucune donnee dans MonsterTalent.csv
ni TalentSynthesis.csv, c'est une vraie lacune des donnees sources
(pas un bug du solveur).

### Bug de mutation corrige
`simplify_chain()` modifie sa chaine en place (elle "elague" les
options non retenues). Un appel a `find_blocking_talent()` sur une
chaine deja passee par `simplify_chain()` donnait un resultat errone
(le talent racine lui-meme, plutot que le vrai talent bloquant en
profondeur). Corrige en utilisant systematiquement une chaine fraiche
(non mutee) pour cette analyse.

---

**Le rang indique dans un ingredient "libre" (ex: "Slime Family (G)")
est un MINIMUM requis, pas une correspondance exacte** (merci pour la
clarification !). Un monstre de rang plus FORT que celui demande
convient tout aussi bien (ex: un monstre de rang A convient pour un
emplacement qui demande au moins G, puisque A est plus fort que G).
Les RankId 1 a 9 sont ordonnes du plus faible (1=G) au plus fort
(9=X) ; le rang special "Any" (10) n'impose aucune contrainte.

Nouvelle fonction centralisee `rank_meets_minimum()` dans
`synthese_core.py`, utilisee partout ou cette comparaison intervient
(recherche de candidats pour un emplacement libre, greffe simple,
recherche divide & conquer). Egalement priorise, dans la recherche
focalisee (`solve_family_scoped`), les candidats qui possedent deja
NATIVEMENT le talent avant les autres, pour trouver la solution la
plus simple en premier.

**Exemple concret verifie** : pour Mékanotoké + Attack Booster IV +
Hair Splitter + Multidisciplinarian, le Général Mac Léo (famille
Demon, rang A) est desormais correctement identifie comme porteur
valide de Multidisciplinarian pour un emplacement qui ne demandait
qu'un rang minimum G - la recherche complete des 3 talents reussit
maintenant en moins d'une seconde (contre un echec partiel
auparavant).

---

### Vrai divide & conquer (talents complexes maintenant greffables)
La decomposition (etape 2 du flux hybride) ne gerait auparavant que
les talents SIMPLES (racine de construction directement sauvage, ex:
Zap Ward). Elle gere desormais aussi les talents COMPLEXES (ex: Attack
Booster IV, qui necessite sa propre chaine de syntheses) grace a une
nouvelle PASSE 2, `solve_family_scoped` : pour chaque emplacement libre
restant, une recherche FOCALISEE (un seul talent, une seule
famille/rang a la fois, budget dedie et borne par espece candidate)
cherche parmi les especes reelles de cette famille laquelle peut
porter ce talent via SA PROPRE genealogie. Beaucoup moins couteux que
la recherche globale car la combinatoire de plusieurs talents
simultanes ne se produit jamais dans cette passe.

**Plus jamais de "recherche trop longue" sans avoir essaye cette
strategie** : le flux ne renonce desormais que si (a) la decomposition
en 2 passes a ete tentee et n'a rien pu assigner du tout, ET (b) la
recherche complete (dernier recours, budget maximal) a aussi echoue.
Si la decomposition reussit ne serait-ce que partiellement, ce
resultat est propose plutot qu'un message d'echec.

### Message honnete affine (2 categories de talents non integres)
Quand un talent ne peut pas etre place dans l'arbre :
- ⚠️ **"aucun emplacement compatible trouve"** : le talent A une
  chaine de construction connue (verifiee independamment de
  l'espece), mais aucun emplacement libre de la bonne famille/rang
  n'existe dans CETTE genealogie precise - il reste constructible
  separement.
- ❌ **"aucune source connue"** : le talent n'a strictement AUCUNE
  chaine de construction dans les donnees actuelles (ni capture
  native, ni recette de synthese), meme en ignorant toute contrainte
  d'espece - cas veritablement hors de portee, pas juste un probleme
  de temps de recherche.

### Detection instantanee des cas vraiment impossibles
Avant de lancer toute recherche couteuse, verifie maintenant si TOUS
les talents demandes ont ne serait-ce qu'une chance theorique
(independante de l'espece). Si oui pour au moins un, la recherche
normale se poursuit. Si aucun des talents demandes n'a de chance,
retour instantane (auparavant, meme un talent totalement absent des
donnees comme "Woosh Virtuoso" pouvait epuiser tout le budget de
recherche avant de conclure a l'echec - corrige, desormais instantane).

### Flux simplifie (gain de temps)
Le "dernier recours" (recherche complete a budget maximal) n'est plus
systematiquement tente apres un succes partiel de la decomposition :
s'il elle a deja place au moins un talent, ce resultat est utilise
directement (rapide) plutot que de perdre plusieurs secondes
supplementaires sur une recherche complete qui, ayant deja echoue a
l'etape rapide, a peu de chances d'apporter mieux.

---

### Strategie hybride en 3 etapes (reduit la complexite automatiquement)
Le solveur essaie maintenant, dans l'ordre :

1. **Recherche rapide** (budget reduit, ~300 000 appels) : couvre la
   grande majorite des demandes (0-3 talents simples), quasi
   instantanee.
2. **Decomposition en arbres intermediaires** (si l'etape 1 echoue par
   manque de budget) : resout l'arbre de l'ESPECE SEULE (rapide, sans
   aucune combinatoire de talents), puis introduit chaque talent
   demande INDEPENDAMMENT a la place d'un ingredient libre compatible
   (meme famille, et meme rang sauf rang "Any") - `decompose_and_graft`
   dans `solver.py`. Beaucoup moins couteuse en calcul que la
   recherche unifiee complete. Utilisee des qu'elle parvient a placer
   TOUS les talents demandes.
3. **Recherche complete** (budget maximal, dernier recours) : si la
   decomposition ne suffit pas (ex: talent complexe necessitant sa
   propre sous-arborescence, sans assez d'emplacements libres
   compatibles dans cette genealogie precise), retente une recherche
   exhaustive avec le budget complet (~1.5M appels, jusqu'a quelques
   secondes). Si meme la decomposition partielle a reussi a placer une
   PARTIE des talents alors que la recherche complete echoue, cette
   solution partielle est proposee plutot que rien, avec les talents
   non places clairement indiques et un lien vers leur construction
   independante.

Resultat concret observe : un cas a 3 talents qui prenait ~2s avec
l'ancien moteur (recherche complete systematique) descend a ~0.2s avec
cette strategie, car la recherche rapide de l'etape 1 suffit dans la
majorite des cas.

### Limite structurelle honnete (a savoir)
La decomposition (etape 2) ne peut greffer que des talents dont la
racine de construction est directement un individu SAUVAGE (ex: Zap
Ward, porte nativement par Gluant). Un talent COMPLEXE dont la
construction necessite sa propre synthese (ex: Attack Booster IV, Hair
Splitter) ne peut pas etre greffe comme un simple remplacement d'UN
ingredient libre : sa construction implique elle-meme plusieurs
individus combines a travers plusieurs syntheses, ce qui necessiterait
plusieurs emplacements libres compatibles simultanement dans la
genealogie du monstre cible - rarement disponible dans les faits.
Quand ce cas se presente, le systeme retombe sur l'etape 3 (recherche
complete), qui reste le seul moyen de trouver ces solutions plus
complexes, avec le cout en temps que cela implique.

---

### Corrections de bugs importants (merci pour le signalement !)
- **Bug de cache critique corrige** : le cache de resolution
  (species+talents -> solution) memorisait aussi les ECHECS, mais
  certains de ces echecs etaient des FAUX NEGATIFS causes par la
  protection anti-cycle (`_visited`), qui ne devrait etre valable que
  pour le CHEMIN d'appel en cours, pas pour toute recherche future
  avec la meme cle. Une branche parfaitement valide pouvait donc etre
  bloquee a tort par un echec mis en cache dans un contexte totalement
  different. Desormais, seuls les SUCCES sont mis en cache. C'etait la
  cause principale du bug "Krystalinda impossible" alors qu'une
  solution existe bien.
- **Synthese a 4 monstres (grands-parents) enfin geree par le nouveau
  solveur** : le moteur ignorait purement et simplement (`continue`)
  les recettes utilisant des grands-parents au lieu de 2 parents
  fixes, ce qui faisait echouer TOUTE la recherche des qu'un tel
  maillon apparaissait dans la genealogie (frequent). Implemente via
  `_solve_intermediate_pair` : la fusion de 2 grands-parents est
  resolue comme une espece "libre" (non fixee dans les donnees) qui
  transporte les talents requis, exactement comme le reste du moteur.
- **Couverture etendue de la greffe** : `build_intermediate_talent_trees`
  construit desormais un arbre pour TOUS les talents INTERMEDIAIRES
  d'une chaine (pas seulement le talent final demande) - ex: pour
  "Hair Splitter", on obtient gratuitement aussi des arbres pour
  Freezer Burner, Air Fryer, et les Slashers qui les composent,
  augmentant enormement les occasions de greffe reussie.

### Limite honnete assumee (a lire)
Pour un tres petit nombre de cas extremes (plusieurs talents exigeants
combines - notamment un talent "a points" a plusieurs paliers comme
Attack Booster IV - sur un monstre a la genealogie tres profonde comme
Overkilling Machine/Mékanotoké), le nombre de combinaisons a explorer
devient enorme (plusieurs millions), et le solveur peut s'arreter
avant d'avoir trouve OU exclu une solution, par souci de temps de
reponse raisonnable pour une app web (~3-5 secondes maximum). Dans ce
cas, le message est maintenant honnete : "la recherche est trop
complexe... cela ne veut pas dire que c'est impossible", plutot que
d'affirmer categoriquement l'echec. La suggestion : demander moins de
talents a la fois (1 ou 2), la recherche est alors quasi instantanee
dans l'immense majorite des cas.

### Nouvelles donnees integrees
`Monster.csv`, `MonsterTalent.csv` (considerablement enrichi : 943
lignes contre 737 avant) et `Talent.csv` mis a jour avec les fichiers
fournis. Note : la colonne `IsPrimary` utilise maintenant `TRUE`/`FALSE`
(majuscules) au lieu de `True`/`False` - le code a ete adapte pour
etre insensible a la casse sur ce champ.

---

## Changements de projet_13 (arbres intermediaires greffes)
Cette lignee repart de projet_11 comme base (n'inclut donc pas la
correction "insensible aux accents" qui avait ete faite dans projet_12
-- a redemander si besoin).

- **Arbres intermediaires greffes** : en complement de la resolution
  unifiee, le solveur construit desormais aussi, pour chaque talent
  demande, un arbre INDEPENDANT du monstre final (la maniere la moins
  couteuse d'obtenir ce talent sur n'importe quelle espece -
  `build_intermediate_talent_trees` dans `solver.py`, qui reutilise le
  resolveur de chaine independant deja present dans
  `synthese_core.py`). Cet arbre est ensuite "introduit" (greffe) dans
  l'arbre principal partout ou un ingredient libre (placeholder de
  famille/rang) de la bonne famille/rang s'y prete, SI c'est moins
  couteux que la recherche classique a cet endroit. Un noeud greffe
  est marque par le badge 🔀 "arbre intermediaire greffé" dans
  l'interface.

---

Interface web uniquement (Flask). La version ligne de commande a ete
retiree du projet : seule l'app web est maintenue desormais.

## Installation

```
pip install -r requirements.txt
```

## Lancer l'application

```
python3 app.py
```
Puis ouvre **http://127.0.0.1:5000**

### 3 onglets

- **Arbre de synthèse** : formulaire (monstre + 3 talents souhaités +
  dernière zone explorée). Le moteur (`solver.py`) résout **en un seul
  arbre unifié** le monstre final ET les talents demandés simultanément
  (recherche récursive avec mémoïsation, minimisant le nombre total de
  synthèses). Chaque nœud affiche :
  - 📍 la zone de capture (pour un monstre sauvage),
  - 🏆 les talents finaux demandés portés à ce nœud,
  - 🔧 les talents intermédiaires nécessaires (paliers de construction,
    ex: Attack Booster II en route vers IV),
  - 🎓 le niveau recommandé pour la synthèse,
  - un bandeau entre les 2 parents indiquant quelle synthèse de talent
    se déclenche à cette étape.
  - **Suivi de progression** : clique sur un monstre de l'arbre pour le
    marquer comme validé (✅ vert). Clique sur "💾 Enregistrer cet
    arbre" une seule fois : après ça, chaque validation/dévalidation
    est sauvegardée automatiquement (dans le navigateur, via
    localStorage — rien n'est envoyé sur internet). La liste des
    arbres enregistrés apparaît à droite, avec bouton "Charger" et
    "Supprimer".

- **Compendium** : tous les monstres, filtrables par nom (FR/EN),
  famille, rang, localisation, talent. Distingue talent principal
  (natif) et talents secondaires (apprenables). Clique sur un talent
  pour voir les skills qu'il contient.

- **Talents** : tous les talents, filtrables par nom ou par skill
  contenu. Clique sur un talent pour voir son contenu (skills/bonus +
  points requis), ses prérequis éventuels (s'il résulte d'une synthèse
  de talents) et ce qu'il permet de débloquer.

## Structure du projet

```
app.py                  -> interface web (Flask), routes + rendu HTML
solver.py                -> moteur de resolution unifie (monstre + talents)
synthese_core.py          -> chargement des CSV, structures de donnees, helpers
templates/                 -> base.html, index.html, compendium.html, talents.html
static/                    -> style.css, tree.js, compendium.js, talents.js
requirements.txt
data/*.csv                 -> donnees du jeu (repo MetalKid/DQM3_Database + SkillPointLevel.csv fourni)
```

## Moteur de resolution (solver.py)

Le probleme resolu : "construire un arbre de synthese qui permet
d'obtenir simultanement le monstre final ET les talents demandes, en
minimisant le nombre de syntheses."

Un noeud de l'arbre = `(espece, ensemble de talents qu'il doit
transporter)`. Deux occurrences de la meme espece avec des talents
differents sont deux etats differents (cle de memoisation :
`(monsterId, frozenset(talents_requis))`).

Regles de deblocage des talents utilisees par le solveur :
- **Talent a points** (Booster I->II->III->IV, Aficionado->Virtuoso) :
  les DEUX parents doivent porter le palier immediatement inferieur.
- **Talent simple a 2 prerequis** (ex: Hair Splitter) : un parent
  porte le premier prerequis, l'autre porte le second.
- **Talent "feuille"** (aucune recette de synthese de talent connue) :
  un seul des deux parents doit le porter (nativement, ou via sa
  propre chaine).

Hypotheses / simplifications assumees :
- Un individu a toujours acces aux talents natifs de son espece
  (MonsterTalent.csv), qu'il soit capture ou synthetise.
- La synthese a 4 monstres (grands-parents) n'est pas re-optimisee
  talent par talent : l'espece intermediaire reste "libre".
- Le cout = nombre de syntheses ; une capture sauvage coute 0.
- Recherche plafonnee (profondeur max, nombre d'appels max) pour eviter
  une explosion combinatoire ; au-dela, le moteur garde la meilleure
  solution trouvee jusque-la (peut ne pas etre l'optimum absolu dans
  les cas les plus complexes).
- Le niveau recommande est calcule a partir de `SkillPointLevel.csv`
  (colonne "Total"), en supposant que les points des DEUX parents se
  combinent pour atteindre le seuil requis.

## Limites connues

- Les monstres "Famille (X)" (placeholders generiques, ex: "Slime
  Family (G)") ne sont pas de vrais monstres ; le solveur essaie
  chaque espece reelle de la meme famille/rang et garde la moins
  couteuse, mais ne garantit pas le choix optimal absolu dans tous les
  cas.
- Sauvegarde des arbres : stockee dans le navigateur (localStorage),
  donc propre a cet ordinateur/navigateur. Pas de compte, pas de
  synchronisation entre appareils.
