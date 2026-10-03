# -*- coding: utf-8 -*-
"""
cadre_test.py — le minimum pour ecrire et lancer des tests.

Il vit dans son propre module pour une raison precise : un fichier lance
directement s'appelle `__main__`, et un second fichier qui l'importe par son
nom en obtient une DEUXIEME copie, avec sa propre liste de tests. Les tests
d'interface s'enregistraient ainsi dans une liste que personne ne lisait, et
la suite annoncait tranquillement « 18 tests » en en ignorant dix.
"""
import json
import os
import sqlite3


_resultats = []


def verifie(nom):
    """Decorateur : un test est une fonction qui leve si quelque chose cloche."""
    def deco(fn):
        _resultats.append((nom, fn))
        return fn
    return deco


def egal(obtenu, attendu, quoi):
    if obtenu != attendu:
        raise AssertionError("%s : obtenu %r, attendu %r" % (quoi, obtenu, attendu))


def vrai(condition, quoi):
    if not condition:
        raise AssertionError(quoi)


def planning_enregistre():
    """Le dernier planning enregistre, ou None.

    Le depot ne contient aucune donnee personnelle, donc aucune base. Mais le
    simple fait de lancer l'application en CREE une, vide : tester l'existence
    du fichier ne suffit pas, et c'est ce qui faisait tomber trois tests de
    parcours sur `fetchone()` qui rend None. Un seul predicat repond donc a la
    vraie question — y a-t-il un planning a lire ?
    """
    if not os.path.exists('planning_history.db'):
        return None
    try:
        c = sqlite3.connect('planning_history.db')
        ligne = c.execute('select planning_data from planning_history '
                          'order by id desc limit 1').fetchone()
        c.close()
    except sqlite3.Error:
        return None
    return json.loads(ligne[0]) if ligne else None


def donnees_reelles_presentes():
    """Vrai si un planning reel est disponible.

    Les tests doivent tourner sans lui : ils retombent sur un jeu synthetique,
    et ceux qui portent sur des faits propres a la session reelle se declarent
    sautes plutot que d'echouer.
    """
    return planning_enregistre() is not None


def donnees():
    """Les vraies donnees de la derniere generation enregistree."""
    p = planning_enregistre()
    if p is None:
        return _donnees_de_secours()
    return p['teachers'], [(s, d) for s, d in p['slots']], p['best']


_SECOURS = None


def _donnees_de_secours():
    """Un jeu fabrique, avec un planning valide, quand la base est absente."""
    global _SECOURS
    if _SECOURS is None:
        import random
        import genetic_algorithm as G
        import jeu_synthetique as J
        fiches, creneaux = J.fabriquer(jours=4, enseignants=45, salles_max=4, graine=1)
        random.seed(1)
        best, _, _ = G.run_ga_optimized(creneaux, fiches, None, profil='rapide')
        _SECOURS = (fiches, creneaux, best)
    return _SECOURS


class ConfigTemporaire:
    """Isole les fichiers de configuration le temps d'un test."""
    FICHIERS = ('parametres.json', 'regles.json')

    def __enter__(self):
        self.sauves = {}
        for f in self.FICHIERS:
            if os.path.exists(f):
                self.sauves[f] = open(f, encoding='utf-8').read()
                os.remove(f)
        return self

    def __exit__(self, *a):
        for f in self.FICHIERS:
            if os.path.exists(f):
                os.remove(f)
            if f in self.sauves:
                open(f, 'w', encoding='utf-8').write(self.sauves[f])
        import genetic_algorithm as G
        G.recharger_regles()
        return False




def resultats():
    """La liste des tests enregistres, dans l'ordre de declaration."""
    return list(_resultats)
