# Les tests

```
python3 tests_auto.py            # tout, y compris les ecrans
python3 tests_auto.py --sans-ui  # la logique seule, sans ouvrir de fenetre
```

Cinquante controles.

Ils s'executent sur un jeu **fabrique** — `jeu_synthetique.py`, et les trois
fichiers `exemple-*.xlsx`. Le depot ne contient aucune donnee personnelle, donc
aucune base de travail : les tests ne doivent dependre d'aucun fichier reel.
Quand une base est presente a cote des sources, ils s'executent dessus et
quelques controles propres a cette session s'ajoutent.

## Pourquoi ils existent

Les trois defauts les plus graves trouves dans ce projet etaient invisibles a
l'oeil.

`check_responsable_presence` comparait un **code enseignant** (`'4'`) a des
**adresses e-mail**. Elle ne reconnaissait donc jamais personne : `present=0,
absent=23`, soit une penalite constante appliquee identiquement a tous les
plannings, qui ne distingue rien. Pendant ce temps 19 responsables sur 21
manquaient a leur propre examen sans que rien ne le signale.

`repair_solution` creait **1485 depassements de quota** sur trente enfants,
alors qu'une penalite de 500 points etait censee les empecher. Une penalite
n'interdit rien ; seule la reparation le peut.

`fitness` reparcourait tout le planning pour **chaque** enseignant, deux fois.
Une evaluation coutait 9,51 ms la ou elle en coute 1,39.

Aucun des trois n'aurait survecu a une suite de tests.

## Ce qui est verifie

**Configuration** — les defauts reproduisent le comportement historique ; un
fichier abime ou edite a la main ne fait pas tomber l'application ; ce qui est
enregistre est relu a l'identique ; le logo choisi est copie puis retrouve.

**Regles** — une nature interdite par le catalogue est refusee ; un intitule
personnalise remplace celui du catalogue ; une regle ignoree disparait du score
et du rapport.

## Le contrat d'une regle obligatoire

**Elle est tenue, ou elle est declaree non tenue. Jamais violee en silence.**

C'est la regle que toute la suite fait respecter, et elle merite d'etre dite
clairement parce qu'elle n'est pas evidente : rendre une regle obligatoire ne
suffit pas a la rendre possible.

L'egalite stricte des charges a grade egal en est l'exemple. Elle est atteinte
sur huit grades sur neuf des donnees reelles. Le neuvième, MA, compte
quarante-neuf enseignants : le total de ce grade doit alors etre un multiple de
quarante-neuf, et la marge laissee par les effectifs par creneau — deux a
quatre surveillants par salle — ne le permet pas toujours.

Dans ce cas l'outil ne doit pas faire semblant. `planning_conforme()` rend
faux, l'ecran affiche « UNE REGLE OBLIGATOIRE N'EST PAS TENUE », le rapport
nomme le grade concerne, et le PDF le porte. C'est verifie : les tests
exigent que tout manquement figure dans le rapport, et qu'un planning
non conforme soit annonce comme tel.

**Egalite de charge** — avec R-12 declaree obligatoire, deux enseignants d'un
meme grade ne different que d'une surveillance. L'egalite STRICTE est
arithmetiquement impossible : 44 surveillances pour 9 enseignants de grade AC,
218 pour 49 en MA — ces nombres ne se divisent pas, pour 5 grades sur 9. Un
ecart d'au plus un est ce qu'un planning peut tenir, et c'est ce qui est
verifie.

**Echecs non avales** — un defaut de programmation dans la boucle de recherche
arrete la generation au lieu de rendre un planning degrade. La boucle sautait
les generations en echec : un nom mal ecrit faisait echouer les 500 generations
l'une apres l'autre et la fonction rendait quand meme un planning, bati sur la
population initiale, avec un ecart de charge de 8 au lieu de 1 et aucun signal.

**Aucun courriel a l'export** — produire les PDF n'ouvre aucune fenetre SMTP et
ne tente aucun envoi. L'export partait avec l'envoi active : un clic sur
« Export Individuel » ouvrait sans prevenir une demande d'identifiants, et la
remplir faisait partir un courriel vers chacun des 126 surveillants convoques.
L'envoi est desormais un geste distinct, qui annonce le nombre de destinataires
et demande confirmation.

**Regles obligatoires** — avec le quota declare obligatoire, aucun enseignant
ne depasse le sien ; avec les indisponibilites declarees obligatoires, personne
n'est convoque sur un creneau qu'il a refuse. Ce sont les deux garanties qui
distinguent cet outil d'un tableur.

**Algorithme** — le score est deterministe ; la reparation tient ses invariants
structurels (aucun doublon, effectif entre le minimum et le maximum) ; le mode
rapide produit en moins de 90 s un planning conforme.

**Verification** — elle detecte une infraction fabriquee exprès, et refuse un
planning qui viole une regle obligatoire.

**Imports** — un fichier qui ne convient pas est **nomme**, avec la colonne
manquante et les colonnes trouvees, au lieu d'une `KeyError` brute.

**Ecrans** — la fenetre se construit ; les exports restent desactives tant
qu'aucun planning n'existe ; l'onglet Qualite affiche le rapport ; l'ecran
d'administration s'ouvre avec ses six onglets ; une saisie invalide est refusee
sans rien enregistrer ; la generation complete aboutit ; le PDF general porte sa
page de conformite.

## Les quatre suites

`tests_auto.py` les lance toutes.

**Logique** (`tests_auto.py`) — configuration, regles, algorithme, verification,
imports de fichiers.

**Synthetique** (`tests_synthetiques.py`) — l'algorithme eprouve sur des donnees
qu'il n'a jamais vues, fabriquees par `jeu_synthetique.py` : session d'un jour
ou de huit, 20 ou 80 enseignants, seances renommees, 45 % d'indisponibilites,
capacite volontairement insuffisante. **Ce que ces tests exigent et qui ne se
negocie pas : une regle declaree obligatoire est tenue quelle que soit la
configuration.** Les infractions y sont recalculees a la main, sans passer par
la verification de l'algorithme — un controle qui partagerait un defaut avec ce
qu'il controle ne prouverait rien.

**Ecrans** (`tests_ui.py`) — chaque fenetre construite, remplie, enregistree.

**Parcours** (`tests_parcours.py`) — chaque bouton presse, chaque fenetre
ouverte puis refermee, et la coherence des donnees : aucun doublon, aucun code
enseignant partage, aucun creneau en double, les quotas accordes aux grades.
Rien ne sort de la machine : les boites de fichier, les questions oui/non et
l'envoi de courriels sont remplaces par des bouchons qui refusent tout.

## Deux pieges rencontres en les ecrivant

**Un fichier lance directement s'appelle `__main__`.** Un second fichier qui
l'importe par son nom en obtient une DEUXIEME copie, avec sa propre liste de
tests. Les tests d'interface s'enregistraient ainsi dans une liste que personne
ne lisait, et la suite annoncait « 18 tests » en en ignorant dix. D'ou
`cadre_test.py`, importe par les deux.

**Chaque test d'interface tourne dans son propre processus.** customtkinter
planifie des rappels qui continuent de se declencher apres la destruction d'une
fenetre : enchainer dix fenetres dans un meme processus finit par faire tomber
Tk sur des widgets disparus. L'isolation coute une seconde par test et rend un
echec lisible.

**Et surveiller la fin d'un traitement par une boucle `while ... update()`
reentre dans Tk** pendant que les rappels s'executent, ce qui fait tomber
l'interpreteur — un defaut du test, pas de l'application. On attend comme
l'application attend : en rendant la main a `mainloop`.
