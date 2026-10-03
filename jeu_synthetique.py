# -*- coding: utf-8 -*-
"""
jeu_synthetique.py — fabrique des donnees d'examen, a la demande.

Tous les tests existants tournaient sur les memes 23 creneaux et 126
surveillants. Un algorithme peut tres bien tenir ses promesses sur un jeu de
donnees et les perdre sur un autre : une session plus courte, un quota plus
serre, beaucoup d'indisponibilites. Ce module fabrique ces situations.

Tout est deterministe : la meme graine rend exactement les memes donnees, pour
qu'un echec se rejoue a l'identique.
"""
import random

GRADES_TYPES = {
    'PR': 4, 'MC': 4, 'MA': 7, 'AS': 8, 'PES': 9, 'V': 4,
}

PRENOMS = ['Amel', 'Sami', 'Nadia', 'Karim', 'Leila', 'Mehdi', 'Sonia', 'Anis',
           'Rim', 'Walid', 'Ines', 'Hatem', 'Olfa', 'Nizar', 'Dorra', 'Slim']
NOMS = ['Ben Ali', 'Trabelsi', 'Gharbi', 'Mejri', 'Hamdi', 'Bouazizi', 'Khelifi',
        'Jlassi', 'Saidi', 'Ayari', 'Chaabane', 'Zouari', 'Mansouri', 'Abidi']


def fabriquer(jours=5, seances=4, enseignants=60, salles_min=1, salles_max=8,
              taux_indispo=0.15, part_participants=0.9, graine=1,
              codes_seances=None, avec_responsables=True):
    """Rend (enseignants, creneaux) au format attendu par l'algorithme.

    `taux_indispo` est la proportion de creneaux qu'un enseignant refuse en
    moyenne. Au-dela de 0,5 le probleme devient difficile, et c'est voulu :
    c'est la que les garanties se verifient.
    """
    rng = random.Random(graine)
    codes = codes_seances or ['S%d' % (i + 1) for i in range(seances)]

    cles = []
    for j in range(jours):
        date = '2026-05-%02d' % (4 + j)
        for code in codes:
            cles.append('%s %s' % (date, code))

    fiches = {}
    for i in range(enseignants):
        grade = rng.choice(list(GRADES_TYPES))
        ident = 'ens%03d@exemple.tn' % i
        fiches[ident] = {
            'nom': rng.choice(NOMS), 'prenom': rng.choice(PRENOMS),
            'abrv': 'E%03d' % i, 'email': ident, 'grade': grade,
            'quota': GRADES_TYPES[grade],
            'indispo': [], 'wish_priority': {},
            'participe_surveillance': rng.random() < part_participants,
            'code_smartex_ens': str(i),
        }

    participants = [e for e, f in fiches.items() if f['participe_surveillance']]
    for e in participants:
        for cle in cles:
            if rng.random() < taux_indispo:
                fiches[e]['indispo'].append(cle)
                fiches[e]['wish_priority'][cle] = rng.choice([1.0, 1.0, 2.0])

    creneaux = []
    for cle in cles:
        salles = rng.randint(salles_min, salles_max)
        donnees = {
            'room_count': salles,
            'room_names': ['S%03d' % (rng.randint(1, 60)) for _ in range(salles)],
            'session': cle.split()[1],
        }
        if avec_responsables:
            # un responsable qui participe ET qui est disponible ce jour-la,
            # sinon la regle serait impossible a tenir par construction
            libres = [e for e in participants if cle not in fiches[e]['indispo']]
            if libres:
                donnees['enseignant'] = fiches[rng.choice(libres)]['code_smartex_ens']
        creneaux.append((cle, donnees))
    return fiches, creneaux


def capacite(fiches, creneaux):
    """Ce que le jeu exige et ce qu'il peut fournir."""
    besoin = sum(2 * d.get('room_count', 1) for _, d in creneaux)
    offre = sum(f['quota'] for f in fiches.values() if f['participe_surveillance'])
    return besoin, offre
