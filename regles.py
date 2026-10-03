# -*- coding: utf-8 -*-
"""
regles.py — le catalogue des regles, et ce que l'etablissement en fait.

Chaque etablissement n'a pas les memes usages : certains interdisent
absolument de convoquer un enseignant sur une indisponibilite declaree,
d'autres l'acceptent faute de monde. Le catalogue dit ce qui est verifiable,
la configuration dit ce que l'etablissement exige.

Une regle a trois natures possibles.

  DURE    la reparation l'impose, l'algorithme ne peut pas la violer. Si elle
          rend le probleme impossible, l'outil le DIT au lieu de rendre un
          planning casse.
  SOUPLE  elle vaut des points dans le score. L'algorithme cherche a la
          satisfaire sans y etre tenu.
  IGNOREE elle n'entre dans aucun calcul.

Toutes les natures ne sont pas ouvertes a toutes les regles : on ne peut pas
rendre souple l'interdiction d'inscrire deux fois la meme personne sur un
creneau, ce n'est pas une preference mais une absurdite. Le champ `natures`
dit ce que l'administrateur a le droit de choisir.

Les valeurs par defaut reproduisent EXACTEMENT le comportement actuel, pour
qu'activer la configuration ne change rien tant que personne n'y touche.
"""
import json
import os

DURE, SOUPLE, IGNOREE = 'dure', 'souple', 'ignoree'

FICHIER = 'regles.json'

CATALOGUE = [
    {
        'id': 'R-01', 'nom': "Effectif minimum par salle",
        'detail': "Nombre de surveillants exige par salle, au minimum.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE], 'poids': 300,
        'unite': "points par surveillant manquant, au carre",
        'parametre': {'cle': 'par_salle_min', 'defaut': 2, 'min': 1, 'max': 10,
                      'libelle': "surveillants par salle"},
    },
    {
        'id': 'R-02', 'nom': "Effectif maximum par salle",
        'detail': "Nombre de surveillants admis par salle, au maximum.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE], 'poids': 500,
        'unite': "points par surveillant en trop, au carre",
        'parametre': {'cle': 'par_salle_max', 'defaut': 4, 'min': 1, 'max': 12,
                      'libelle': "surveillants par salle"},
    },
    {
        'id': 'R-03', 'nom': "Pas deux fois la meme personne",
        'detail': "Un enseignant ne figure qu'une fois sur un creneau.",
        'defaut': DURE, 'natures': [DURE], 'poids': 500,
        'unite': "points par doublon",
    },
    {
        'id': 'R-04', 'nom': "Indisponibilites declarees",
        'detail': "Ne pas convoquer quelqu'un sur un creneau qu'il a refuse.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE, IGNOREE], 'poids': 2000,
        'unite': "points par convocation, ponderes par la priorite du souhait",
    },
    {
        'id': 'R-05', 'nom': "Quota par grade",
        'detail': "Le nombre de surveillances d'un enseignant reste dans son quota.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE, IGNOREE], 'poids': 500,
        'unite': "points par surveillance en trop, au carre",
    },
    {
        'id': 'R-06', 'nom': "Responsable present a son examen",
        'detail': "L'enseignant responsable d'une epreuve la surveille.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE, IGNOREE], 'poids': 200,
        'unite': "points par responsable present",
    },
    {
        'id': 'R-07', 'nom': "Pas de seance creuse",
        'detail': "Eviter un trou d'une seance dans la journee d'un surveillant.",
        'defaut': SOUPLE, 'natures': [SOUPLE, IGNOREE], 'poids': 200,
        'unite': "points par trou d'une seance",
    },
    {
        'id': 'R-08', 'nom': "Pas de double seance creuse",
        'detail': "Eviter un trou de deux seances dans la journee.",
        'defaut': SOUPLE, 'natures': [SOUPLE, IGNOREE], 'poids': 500,
        'unite': "points par trou de deux seances",
    },
    {
        'id': 'R-09', 'nom': "Equite entre memes grades",
        'detail': "Repartir la charge equitablement a grade egal.",
        'defaut': SOUPLE, 'natures': [SOUPLE, IGNOREE], 'poids': 400,
        'unite': "points par unite de variance",
    },
    {
        'id': 'R-10', 'nom': "Concentrer sur peu de jours",
        'detail': "Nombre de jours de presence au-dela duquel on penalise.",
        'defaut': SOUPLE, 'natures': [SOUPLE, IGNOREE], 'poids': 30,
        'unite': "points par jour au-dela du seuil",
        'parametre': {'cle': 'jours_max', 'defaut': 3, 'min': 1, 'max': 15,
                      'libelle': "jours de presence"},
    },
    {
        'id': 'R-12', 'nom': "Meme charge a grade egal",
        'detail': "Deux enseignants d'un meme grade font exactement le meme nombre de surveillances.",
        'defaut': SOUPLE, 'natures': [DURE, SOUPLE, IGNOREE], 'poids': 600,
        'unite': "points par unite d'ecart au-dela de un",
    },
    {
        'id': 'R-11', 'nom': "Surveillances consecutives",
        'detail': "Recompenser deux seances qui se suivent dans la journee.",
        'defaut': SOUPLE, 'natures': [SOUPLE, IGNOREE], 'poids': 20,
        'unite': "points par paire consecutive",
    },
]

PAR_ID = {r['id']: r for r in CATALOGUE}


def defauts():
    """La configuration qui reproduit le comportement historique."""
    base = {}
    for r in CATALOGUE:
        entree = {'nature': r['defaut'], 'poids': r['poids']}
        if 'parametre' in r:
            entree['valeur'] = r['parametre']['defaut']
        base[r['id']] = entree
    return base


def valeur(conf, rid):
    """Le nombre reglable d'une regle, ou son defaut.

    « Deux surveillants par salle » etait ecrit en dur dans l'algorithme : un
    etablissement qui en veut trois ne pouvait rien y faire.
    """
    param = PAR_ID[rid].get('parametre')
    if not param:
        return None
    v = (conf.get(rid) or {}).get('valeur')
    if isinstance(v, (int, float)) and param['min'] <= v <= param['max']:
        return int(v)
    return param['defaut']


def charger(chemin=FICHIER):
    """La configuration de l'etablissement, completee par les defauts.

    Une regle absente du fichier prend sa valeur par defaut, et une nature
    interdite par le catalogue est ramenee au defaut : un fichier modifie a la
    main ne doit pas pouvoir mettre l'outil dans un etat impossible.
    """
    conf = defauts()
    if not os.path.exists(chemin):
        return conf
    try:
        with open(chemin, encoding='utf-8') as f:
            lu = json.load(f)
    except (ValueError, OSError):
        return conf
    for rid, valeurs in (lu or {}).items():
        if rid not in PAR_ID or not isinstance(valeurs, dict):
            continue
        nature = valeurs.get('nature')
        if nature in PAR_ID[rid]['natures']:
            conf[rid]['nature'] = nature
        poids = valeurs.get('poids')
        if isinstance(poids, (int, float)) and poids >= 0:
            conf[rid]['poids'] = float(poids)
        # L'etablissement peut renommer une regle dans ses propres mots sans
        # toucher a ce qu'elle verifie : l'identifiant reste la seule reference.
        for champ in ('nom', 'detail'):
            if isinstance(valeurs.get(champ), str) and valeurs[champ].strip():
                conf[rid][champ] = valeurs[champ].strip()
        param = PAR_ID[rid].get('parametre')
        if param:
            v = valeurs.get('valeur')
            if isinstance(v, (int, float)) and param['min'] <= v <= param['max']:
                conf[rid]['valeur'] = int(v)
    return conf


def intitule(conf, rid):
    return (conf.get(rid) or {}).get('nom') or PAR_ID[rid]['nom']


def description(conf, rid):
    return (conf.get(rid) or {}).get('detail') or PAR_ID[rid]['detail']


def enregistrer(conf, chemin=FICHIER):
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)


def dures(conf):
    return {rid for rid, v in conf.items() if v['nature'] == DURE}


def poids(conf, rid):
    """Zero si la regle est ignoree : elle disparait du score sans condition
    dispersee dans le code."""
    v = conf.get(rid)
    if not v or v['nature'] == IGNOREE:
        return 0.0
    return float(v['poids'])
