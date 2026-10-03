# Planification des surveillances d'examens

Un outil qui répartit les enseignants sur les créneaux de surveillance d'une
session d'examens, **en respectant les règles que l'établissement a fixées**, et
qui produit la preuve qu'il les a respectées.

La répartition se fait aujourd'hui au tableur, en deux à trois jours de travail
par session, et elle se conteste. Ici elle prend quinze secondes et sort avec un
rapport de conformité, règle par règle.

## Ce qu'il garantit

Chaque règle est déclarée **obligatoire**, **souhaitable** ou **ignorée**, par
l'établissement, dans l'écran d'administration.

Une règle obligatoire est **imposée**, pas encouragée. La distinction est tout
le produit : une pénalité dans un score n'interdit rien. Mesuré sur une session
réelle de 23 créneaux et 126 surveillants, l'ancienne approche laissait passer
1 485 dépassements de quota que sa propre pénalité était censée empêcher.

Et quand une règle obligatoire ne peut pas être tenue — une session où presque
tout le monde est indisponible ne permet pas de répartir également la charge —
**l'outil le dit** et refuse de présenter le planning comme conforme. Il ne fait
jamais semblant.

## Les douze règles

| | |
|---|---|
| R-01 | Effectif minimum par salle *(nombre réglable)* |
| R-02 | Effectif maximum par salle *(nombre réglable)* |
| R-03 | Jamais deux fois la même personne sur un créneau |
| R-04 | Indisponibilités déclarées respectées |
| R-05 | Quota de surveillances par grade |
| R-06 | L'enseignant responsable surveille son propre examen |
| R-07 | Pas de séance creuse dans la journée |
| R-08 | Pas de double séance creuse |
| R-09 | Équité entre enseignants de même grade |
| R-10 | Concentrer sur peu de jours *(seuil réglable)* |
| R-11 | Surveillances consécutives favorisées |
| R-12 | Même charge à grade égal |

Leur intitulé et leur description se modifient dans vos propres mots. Ce qu'elles
vérifient ne change pas.

## Ce qu'il fait

**Importe** vos trois fichiers Excel : créneaux d'examen, enseignants, souhaits
d'indisponibilité. Un fichier qui ne convient pas est nommé, avec la colonne
manquante et les colonnes trouvées.

**Génère** le planning, en mode rapide (une quinzaine de secondes) ou approfondi.

**Montre** le résultat par créneau, par enseignant, par salle, et son rapport de
conformité.

**Corrige à la main** : transférer un surveillant d'un créneau ou d'une salle à
l'autre, retirer, remplacer.

**Exporte** un PDF par surveillant et un PDF général, celui-ci portant la page de
conformité. **Envoie** les convocations par courriel, après confirmation
nommant le nombre de destinataires.

## S'adapte à votre établissement

Nom et logo, horaires et nombre de séances, grades et quotas, nature de chaque
règle, durée de la recherche, langue de l'interface — français ou anglais. Rien
de tout cela n'est écrit dans le code.

## Installation

**Windows** — télécharger `ExamSlotPlanner.exe` depuis la page
[Releases](../../releases) et double-cliquer. Rien d'autre à installer. La
configuration et l'historique sont écrits dans `%APPDATA%\ExamSlotPlanner`.

**Depuis les sources** — Python 3.10 ou plus récent, et le paquet système
`python3-tk`.

```
sudo apt install python3-tk          # Debian, Ubuntu
pip install -r requirements.txt
python3 main.py
```

## Essayer sans vos données

Trois fichiers d'exemple sont livrés — `exemple-creneaux.xlsx`,
`exemple-enseignants.xlsx`, `exemple-souhaits.xlsx`. Ils ont la structure
attendue des vrais fichiers et ne contiennent que des noms et des adresses
fabriqués. Les importer suffit à générer un planning complet.

```
python3 fabriquer_exemples.py        # pour en refabriquer d'autres
```

## Tests

```
python3 tests_auto.py            # 49 contrôles
python3 tests_auto.py --sans-ui  # la logique seule, sans ouvrir de fenêtre
```

Quatre suites : la logique sur des données réelles, l'algorithme sur des données
synthétiques fabriquées pour le mettre en difficulté, les écrans, et un parcours
qui presse chaque bouton et ouvre chaque fenêtre. Voir [TESTS.md](TESTS.md) —
chaque test y est expliqué par le défaut qu'il aurait attrapé.

## Données personnelles

Les fichiers de travail contiennent des noms, des adresses et des souhaits
d'absence. Ils sont exclus du dépôt et ne doivent jamais y entrer : en Tunisie
ces données relèvent de la loi 2004-63 et de l'INPDP.

## Licence

Tous droits réservés. Le code est publié pour que l'outil puisse être
**évalué** : téléchargé, exécuté, examiné. Toute exploitation en production
demande un accord écrit — voir [LICENSE](LICENSE).

---

© 2026 Meriem Trabelsi
