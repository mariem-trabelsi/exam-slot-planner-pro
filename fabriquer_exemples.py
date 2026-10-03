#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fabriquer_exemples.py — produit les trois fichiers d'exemple.

Ils ont exactement la structure attendue par les imports, avec des noms et des
adresses inventes. Ils servent a essayer l'outil sans donnees reelles, et aux
tests, qui ne doivent dependre d'aucun fichier personnel.

    python3 fabriquer_exemples.py
"""
import pandas as pd

import jeu_synthetique as J

SEANCES = {'S1': ('08:30:00', '10:00:00'), 'S2': ('10:30:00', '12:00:00'),
           'S3': ('12:30:00', '14:00:00'), 'S4': ('14:30:00', '16:00:00')}


def main():
    fiches, creneaux = J.fabriquer(jours=5, seances=4, enseignants=48,
                                   salles_min=1, salles_max=6, graine=2026)

    lignes = []
    for cle, d in creneaux:
        date, seance = cle.split()
        debut, fin = SEANCES.get(seance, ('08:30:00', '10:00:00'))
        for salle in d['room_names']:
            lignes.append({
                'dateExam': '/'.join(reversed(date.split('-'))),
                'h_debut': '30/12/1999 ' + debut,
                'h_fin': '30/12/1999 ' + fin,
                'session': seance,
                'type ex': 'E',
                'semestre': 'SEMESTRE 2',
                'enseignant': d.get('enseignant', ''),
                'cod_salle': salle,
            })
    pd.DataFrame(lignes).to_excel('exemple-creneaux.xlsx', index=False)

    pd.DataFrame([{
        'nom_ens': f['nom'], 'prenom_ens': f['prenom'], 'abrv_ens': f['abrv'],
        'email_ens': f['email'], 'grade_code_ens': f['grade'],
        'code_smartex_ens': f['code_smartex_ens'],
        'participe_surveillance': 'oui' if f['participe_surveillance'] else 'non',
    } for f in fiches.values()]).to_excel('exemple-enseignants.xlsx', index=False)

    # La colonne « Jour » porte le NUMERO du jour d'examen, pas sa date :
    # l'import la lit par `int()` et s'en sert comme index dans la liste des
    # dates triees. Un exemple qui y mettait une date faisait echouer
    # l'import — et c'est le fichier que le lecteur du README essaie en
    # premier.
    jours = sorted({cle.split()[0] for cle, _ in creneaux})
    numero = {d: str(i + 1) for i, d in enumerate(jours)}

    voeux = []
    for e, f in fiches.items():
        for cle in f['indispo']:
            date, seance = cle.split()
            if date not in numero:
                continue
            voeux.append({'Enseignant': f['abrv'], 'Semestre': 'SEMESTRE 2',
                          'Session': 'Principale',
                          'Jour': numero[date],
                          'Séances': seance})
    pd.DataFrame(voeux).to_excel('exemple-souhaits.xlsx', index=False)

    print('exemple-creneaux.xlsx    %4d lignes' % len(lignes))
    print('exemple-enseignants.xlsx %4d lignes' % len(fiches))
    print('exemple-souhaits.xlsx    %4d lignes' % len(voeux))


if __name__ == '__main__':
    main()
