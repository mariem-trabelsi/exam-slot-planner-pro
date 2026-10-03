#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests_auto.py — ce que l'application doit tenir, verifie automatiquement.

Les trois defauts les plus graves trouves dans ce projet etaient invisibles a
l'oeil : le controle du responsable comparait un code a des adresses et ne
reconnaissait jamais personne, la reparation creait des depassements de quota
qu'elle etait censee empecher, et le calcul du score reparcourait tout le
planning pour chaque enseignant. Aucun n'aurait survecu a une suite de tests.

Usage :  python3 tests_auto.py           (tout)
         python3 tests_auto.py --sans-ui (sans ouvrir de fenetre)
"""
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback

ICI = os.path.dirname(os.path.abspath(__file__))
os.chdir(ICI)
sys.path.insert(0, ICI)

from cadre_test import (verifie, egal, vrai, donnees, ConfigTemporaire,
                        resultats, donnees_reelles_presentes)


# ───────────────────────────────────────────────────────── configuration

@verifie("parametres : les defauts reproduisent le comportement historique")
def t_param_defauts():
    import parametres as P
    from constants import SESSION_TIMES
    with ConfigTemporaire():
        c = P.charger()
        egal(P.horaires(c), dict(SESSION_TIMES), "horaires par defaut")
        egal(c['langue'], 'fr', "langue par defaut")
        egal(c['generation'], 'rapide', "mode par defaut")


@verifie("parametres : un fichier abime ne fait pas tomber l'application")
def t_param_abime():
    import parametres as P
    f = tempfile.mktemp(suffix='.json')
    open(f, 'w').write('{ ceci n est pas du JSON')
    egal(P.charger(f)['langue'], 'fr', "repli sur les defauts")
    json.dump({'langue': 'klingon', 'seances': [{'code': 'S1', 'debut': '99:99', 'fin': 'x'}],
               'quotas': {'PR': 500}}, open(f, 'w'))
    c = P.charger(f)
    egal(c['langue'], 'fr', "langue inconnue refusee")
    vrai(len(c['seances']) == 4, "horaire invalide refuse, defauts conserves")
    egal(c['quotas'], {}, "quota aberrant refuse")
    os.remove(f)


@verifie("parametres : ce qui est enregistre est relu a l'identique")
def t_param_aller_retour():
    import parametres as P
    with ConfigTemporaire():
        c = P.defauts()
        c['etablissement'] = "Faculte des Sciences de Bizerte"
        c['langue'] = 'en'
        c['generation'] = 'approfondie'
        c['quotas'] = {'PR': 6, 'MA': 9}
        c['seances'] = [{'code': 'M1', 'debut': '08:00', 'fin': '09:30'},
                        {'code': 'M2', 'debut': '09:45', 'fin': '11:15'}]
        P.enregistrer(c)
        r = P.charger()
        egal(r['etablissement'], c['etablissement'], "nom conserve")
        egal(r['langue'], 'en', "langue conservee")
        egal(r['generation'], 'approfondie', "mode conserve")
        egal(r['quotas'], {'PR': 6, 'MA': 9}, "quotas conserves")
        egal(P.horaires(r), {'M1': '08:00', 'M2': '09:45'}, "seances conservees")
        egal(P.ordre(r), {'M1': 1, 'M2': 2}, "ordre deduit des horaires")


@verifie("logo : le fichier choisi est copie et retrouve")
def t_logo():
    import parametres as P
    with ConfigTemporaire():
        src = tempfile.mktemp(suffix='.png')
        shutil.copyfile(P.LOGO_DEFAUT, src)
        cible = os.path.join('assets', 'logo-test.png')
        shutil.copyfile(src, cible)
        c = P.defauts(); c['logo'] = cible
        P.enregistrer(c)
        egal(P.chemin_logo(P.charger()), cible, "logo retrouve apres relecture")
        os.remove(cible); os.remove(src)
        egal(P.chemin_logo(P.charger()), P.LOGO_DEFAUT, "repli sur le logo par defaut")


@verifie("regles : les defauts et le refus d'une nature interdite")
def t_regles_defauts():
    import regles as R
    with ConfigTemporaire():
        c = R.charger()
        egal(len(c), len(R.CATALOGUE), "toutes les regles presentes")
        egal(c['R-03']['nature'], R.DURE, "R-03 dure par defaut")
        R.enregistrer({'R-03': {'nature': R.SOUPLE, 'poids': 1},
                       'R-05': {'nature': R.DURE, 'poids': 500}})
        c = R.charger()
        egal(c['R-03']['nature'], R.DURE, "nature interdite ramenee au defaut")
        egal(c['R-05']['nature'], R.DURE, "nature autorisee conservee")


@verifie("regles : un intitule personnalise remplace celui du catalogue")
def t_regles_intitule():
    import regles as R
    with ConfigTemporaire():
        R.enregistrer({'R-06': {'nature': R.SOUPLE, 'poids': 200,
                                'nom': "Le responsable surveille son epreuve"}})
        c = R.charger()
        egal(R.intitule(c, 'R-06'), "Le responsable surveille son epreuve", "intitule repris")
        egal(R.intitule(c, 'R-01'), R.PAR_ID['R-01']['nom'], "intitule du catalogue sinon")


# ─────────────────────────────────────────────────────────── algorithme

@verifie("score : deterministe sur une meme entree")
def t_score_deterministe():
    import genetic_algorithm as G
    with ConfigTemporaire():
        t, s, best = donnees()
        sd = dict(s)
        valeurs = {G.fitness(best, t, sd) for _ in range(5)}
        egal(len(valeurs), 1, "cinq evaluations, une seule valeur")


@verifie("reparation : les invariants structurels sont tenus")
def t_reparation_invariants():
    import genetic_algorithm as G, random
    with ConfigTemporaire():
        t, s, _ = donnees()
        sd = dict(s)
        random.seed(4)
        pop = G.generate_population(12, s, t)
        for i in range(0, 12, 2):
            r = G.repair_solution(G.crossover(pop[i], pop[i + 1]), t, sd)
            for slot, lst in r.items():
                salles = sd.get(slot, {}).get('room_count', 1)
                egal(len(lst), len(set(lst)), "aucun doublon sur %s" % slot)
                vrai(len(lst) >= 2 * salles, "effectif minimum sur %s" % slot)
                vrai(len(lst) <= 4 * salles, "effectif maximum sur %s" % slot)


@verifie("regle dure : le quota n'est jamais depasse quand il est obligatoire")
def t_quota_dur():
    import genetic_algorithm as G, regles as R, random
    from collections import Counter
    with ConfigTemporaire():
        t, s, _ = donnees()
        sd = dict(s)
        c = R.defauts(); c['R-05']['nature'] = R.DURE
        R.enregistrer(c); G.recharger_regles()
        random.seed(11)
        pop = G.generate_population(12, s, t)
        for i in range(0, 12, 2):
            r = G.repair_solution(G.crossover(pop[i], pop[i + 1]), t, sd)
            cnt = Counter(e for l in r.values() for e in set(l))
            for e, n in cnt.items():
                vrai(n <= t[e].get('quota', 0),
                     "%s a %d surveillances pour un quota de %d" % (e, n, t[e].get('quota', 0)))


@verifie("regle dure : aucune convocation sur une indisponibilite declaree")
def t_indispo_dur():
    import genetic_algorithm as G, regles as R, random
    with ConfigTemporaire():
        t, s, _ = donnees()
        sd = dict(s)
        c = R.defauts(); c['R-04']['nature'] = R.DURE
        R.enregistrer(c); G.recharger_regles()
        random.seed(12)
        pop = G.generate_population(12, s, t)
        for i in range(0, 12, 2):
            r = G.repair_solution(G.crossover(pop[i], pop[i + 1]), t, sd)
            for slot, lst in r.items():
                for e in set(lst):
                    vrai(slot not in (t[e].get('indispo') or ()),
                         "%s convoque le %s qu'il a refuse" % (e, slot))


@verifie("regle ignoree : elle disparait du score et du rapport")
def t_regle_ignoree():
    import genetic_algorithm as G, regles as R
    with ConfigTemporaire():
        t, s, best = donnees()
        sd = dict(s)
        avant = G.fitness(best, t, sd)
        c = R.defauts(); c['R-06']['nature'] = R.IGNOREE
        R.enregistrer(c); G.recharger_regles()
        apres = G.fitness(best, t, sd)
        vrai(avant != apres, "le score change quand une regle sort du calcul")
        v = G.verifier_planning(best, t, sd)
        vrai(all(x['id'] != 'R-06' for x in v), "la regle ignoree sort du rapport")


@verifie("responsable : le controle reconnait un code enseignant")
def t_responsable():
    if not donnees_reelles_presentes():
        return        # faits propres a la session reelle
    import genetic_algorithm as G
    with ConfigTemporaire():
        t, s, best = donnees()
        sd = dict(s)
        codes = G.table_des_codes(t)
        vrai(len(codes) > 100, "la table des codes est peuplee")
        presents, absents = G.check_responsable_presence(best, sd, t, codes)
        vrai(presents + absents > 0, "des responsables sont identifies")
        vrai(presents + absents == 21,
             "21 creneaux ont un responsable identifiable, obtenu %d" % (presents + absents))


@verifie("regle dure : meme charge a grade egal, a une surveillance pres")
def t_egalite_grade():
    import genetic_algorithm as G, regles as R, random, collections
    with ConfigTemporaire():
        t, s, _ = donnees()
        sd = dict(s)
        c = R.defauts(); c['R-12']['nature'] = R.DURE
        R.enregistrer(c); G.recharger_regles()
        random.seed(7)
        best, _, _ = G.run_ga_optimized(s, t, None, profil='rapide')
        cpt = collections.Counter(e for l in best.values() for e in set(l))
        par_grade = collections.defaultdict(list)
        for e, f in t.items():
            if f.get('participe_surveillance'):
                par_grade[f.get('grade')].append(cpt.get(e, 0))
        inegaux = [(g, min(v), max(v)) for g, v in par_grade.items()
                   if len(v) > 1 and min(v) != max(v)]
        v = G.verifier_planning(best, t, sd, c)

        # Le contrat : l'egalite stricte est TENUE, ou elle est DECLAREE non
        # tenue. Sur certains jeux elle est hors d'atteinte — le grade MA
        # compte 49 enseignants, et la marge laissee par les effectifs par
        # creneau ne permet pas toujours un total divisible par 49. L'outil
        # doit alors le dire, et refuser de presenter le planning comme
        # conforme.
        if inegaux:
            vrai(not G.planning_conforme(v),
                 "charges inegales non signalees : %s" % inegaux[:2])
            r12 = [x for x in v if x['id'] == 'R-12'][0]
            vrai(not r12['tenue'], "R-12 doit figurer parmi les manquements")
        else:
            vrai(G.planning_conforme(v), "le planning respecte les regles obligatoires")


@verifie("algorithme : des echecs repetes arretent la recherche au lieu de la degrader")
def t_echecs_non_avales():
    import genetic_algorithm as G
    with ConfigTemporaire():
        t, s, _ = donnees()
        garde = G.fitness
        G.fitness = lambda *a, **k: (_ for _ in ()).throw(NameError("defaut simule"))
        try:
            souleve = False
            try:
                G.run_ga_optimized(s, t, None, profil='rapide')
            except RuntimeError:
                souleve = True
            vrai(souleve, "la recherche s'arrete au lieu de rendre un planning degrade")
        finally:
            G.fitness = garde


@verifie("verification : elle detecte une infraction fabriquee")
def t_verification_detecte():
    if not donnees_reelles_presentes():
        return        # faits propres a la session reelle
    import genetic_algorithm as G, regles as R
    with ConfigTemporaire():
        t, s, best = donnees()
        sd = dict(s)
        v = G.verifier_planning(best, t, sd)
        # Le planning enregistre en octobre 2025 a ete produit avant que ces
        # deux regles existent : le responsable n'etait pas reconnu, et la
        # charge egale a grade egal n'etait pas exigee. Les deux manquements
        # sont donc attendus, et c'est leur detection que ce test verifie.
        egal(sorted(x['id'] for x in v if not x['tenue']), ['R-06', 'R-12'],
             "les deux manquements connus du planning enregistre")

        # on fabrique une violation d'indisponibilite
        casse = {k: list(val) for k, val in best.items()}
        slot = next(sl for sl in casse)
        victime = next(e for e in t if slot in (t[e].get('indispo') or ()))
        casse[slot].append(victime)
        v2 = G.verifier_planning(casse, t, sd)
        r4 = [x for x in v2 if x['id'] == 'R-04'][0]
        vrai(not r4['tenue'], "l'infraction fabriquee est detectee")
        vrai(r4['exemples'], "elle est nommee dans le rapport")


@verifie("interface : le glyphe qui fait tomber Tk n'est nulle part")
def t_glyphe_fatal():
    """U+1F4BE ne doit reapparaitre dans aucun libelle.

    Mesure dans l'application reelle : un bouton portant ce caractere, cree
    apres l'ouverture de la fenetre et avec une police explicite, fait tomber
    l'interpreteur en erreur de segmentation — 3 fois sur 3. Sans lui, 3
    reussites sur 3 ; avec la police par defaut, 3 reussites sur 3. Les autres
    pictogrammes du logiciel passent tous.

    C'etait le bouton « Sauvegarder Historique » : en production, un clic
    faisait disparaitre l'application. Un controle de source vaut mieux qu'un
    test d'interface ici, puisque le defaut TUE le processus au lieu de lever.
    """
    import glob
    fautifs = []
    for f in sorted(glob.glob('*.py')):
        for n, ligne in enumerate(io.open(f, encoding='utf-8'), 1):
            if '\U0001F4BE' in ligne and not ligne.lstrip().startswith('#'):
                fautifs.append('%s:%d' % (f, n))
    egal(fautifs, [], "U+1F4BE est revenu dans le code")


@verifie("conformite : un planning violant une regle dure est refuse")
def t_conformite():
    """Le verdict suit la NATURE de la regle, pas le nombre d'infractions.

    Le test fabrique lui-meme son infraction au lieu de compter sur un defaut
    du jeu de donnees : il doit dire la meme chose sur les donnees reelles et
    sur le jeu synthetique. L'infraction est un ECHANGE — le responsable d'un
    creneau cede sa place a un collegue disponible — pour ne toucher qu'a R-06
    et laisser intacts l'effectif par salle (R-01, R-02) et les quotas (R-05).
    """
    import genetic_algorithm as G, regles as R
    with ConfigTemporaire():
        t, s, best = donnees()
        sd = dict(s)
        codes = G.table_des_codes(t)
        casse = None
        for slot, data in sd.items():
            resp = G.responsable_du_creneau(data, codes)
            presents = list(best.get(slot, ()))
            if resp is None or resp not in presents:
                continue
            remplacant = next(
                (e for e, f in t.items()
                 if e not in presents and f.get('participe_surveillance')
                 and slot not in (f.get('indispo') or ())), None)
            if remplacant is None:
                continue
            casse = {k: list(val) for k, val in best.items()}
            casse[slot] = [remplacant if e == resp else e for e in presents]
            break
        vrai(casse is not None, "un creneau se prete a l'echange fabrique")

        # Le test porte sur R-06 SEULE : on relache tout ce qui peut l'etre,
        # sinon une autre regle obligatoire — l'egalite des charges, par
        # exemple — refuserait le planning et l'on ne saurait plus laquelle
        # a parle.
        c = R.defauts()
        for rid, entree in c.items():
            if rid != 'R-06' and R.SOUPLE in R.PAR_ID[rid]['natures']:
                entree['nature'] = R.SOUPLE
        c['R-06']['nature'] = R.DURE
        R.enregistrer(c); G.recharger_regles()
        v = G.verifier_planning(casse, t, sd)
        r6 = [x for x in v if x['id'] == 'R-06'][0]
        vrai(not r6['tenue'], "l'absence du responsable est detectee")
        vrai(not G.planning_conforme(v),
             "R-06 obligatoire et infraction : le planning doit etre refuse")

        c['R-06']['nature'] = R.SOUPLE
        R.enregistrer(c); G.recharger_regles()
        v = G.verifier_planning(casse, t, sd)
        r6 = [x for x in v if x['id'] == 'R-06'][0]
        vrai(not r6['tenue'], "la meme infraction est toujours rapportee")
        vrai(G.planning_conforme(v),
             "en souhaitable, elle ne refuse plus le planning")


@verifie("generation : le mode rapide produit un planning exploitable")
def t_generation():
    import genetic_algorithm as G
    with ConfigTemporaire():
        t, s, _ = donnees()
        sd = dict(s)
        t0 = time.time()
        best, hist, raison = G.run_ga_optimized(s, t, None, profil='rapide')
        duree = time.time() - t0
        vrai(best, "un planning est rendu")
        egal(set(best), set(sd), "tous les creneaux sont couverts")
        vrai(duree < 90, "mode rapide en moins de 90 s, obtenu %.0f s" % duree)
        v = G.verifier_planning(best, t, sd)
        vrai(G.planning_conforme(v), "le planning respecte les regles obligatoires")


@verifie("profils : l'approfondi explore davantage que le rapide")
def t_profils():
    import genetic_algorithm as G
    vrai(G.PROFILS['approfondie']['pop_size'] > G.PROFILS['rapide']['pop_size'],
         "population plus large en approfondi")
    vrai(G.PROFILS['approfondie']['max_generations'] > G.PROFILS['rapide']['max_generations'],
         "plus de generations en approfondi")


# ──────────────────────────────────────────────────────────── fichiers

@verifie("import : un fichier de creneaux valide est accepte")
def t_import_creneaux():
    import pandas as pd
    f = 'exemple-creneaux.xlsx'
    vrai(os.path.exists(f),
         "le fichier d'exemple est present (python3 fabriquer_exemples.py)")
    df = pd.read_excel(f, engine='openpyxl')
    for col in ('dateExam', 'h_debut', 'h_fin', 'cod_salle'):
        vrai(col in df.columns, "colonne %s presente" % col)


@verifie("import : un fichier qui ne convient pas est nomme, pas une KeyError")
def t_import_mauvais_fichier():
    import pandas as pd
    import main
    df = pd.read_excel('exemple-enseignants.xlsx')
    msg = main.PlanningApp.verifier_colonnes(df, 'creneaux', 'exemple-enseignants.xlsx')
    vrai(msg, "un fichier d'enseignants est refuse comme fichier de creneaux")
    vrai('dateExam' in msg, "la colonne manquante est nommee")
    vrai('nom_ens' in msg, "les colonnes trouvees sont listees")
    egal(main.PlanningApp.verifier_colonnes(
        pd.read_excel('exemple-enseignants.xlsx'), 'enseignants', 'x'),
        None, "le bon fichier passe")


def _lancer_ui_isole(noms):
    """Chaque test d'interface tourne dans SON processus.

    customtkinter planifie des rappels (`check_dpi_scaling`, redessins) qui
    continuent de se declencher apres la destruction d'une fenetre : enchainer
    dix fenetres dans un meme processus finit par faire tomber Tk sur des
    widgets disparus. L'isolation coute une seconde par test et rend le
    resultat lisible — un echec est un echec, pas une contamination.
    """
    import subprocess
    sorties = []
    for nom, fonction in noms:
        module = 'tests_parcours' if (fonction.startswith('t_parcours_')
                                      or fonction.startswith('t_donnees_')) else 'tests_ui'
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "import %s as m\n"
            "m.%s()\n" % (ICI, module, fonction)
        )
        r = subprocess.run([sys.executable, '-c', code], cwd=ICI,
                           capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            sorties.append((nom, None, ''))
        else:
            derniere = [l for l in (r.stderr or '').strip().split('\n') if l.strip()]
            sorties.append((nom, derniere[-1] if derniere else 'code %d' % r.returncode,
                            r.stderr))
    return sorties


if __name__ == '__main__':
    sans_ui = '--sans-ui' in sys.argv
    echecs = []
    # Les tests synthetiques eprouvent l'algorithme sur des donnees qu'il ne
    # connait pas. Ils n'ouvrent aucune fenetre, donc ils tournent toujours.
    import tests_synthetiques                      # noqa: F401
    tests = resultats()
    larg = 62
    for nom, fn in tests:
        try:
            fn()
            print('  ok      %s' % nom)
        except Exception as e:
            echecs.append((nom, e, traceback.format_exc()))
            print('  ECHEC   %-*s  %s' % (larg, nom, e))

    total = len(tests)
    if not sans_ui:
        import tests_ui
        import tests_parcours
        ui = [(n.replace('t_ui_', '').replace('_', ' '), n)
              for n in dir(tests_ui) if n.startswith('t_ui_')]
        ui += [(n.replace('t_', '').replace('_', ' '), n)
               for n in dir(tests_parcours)
               if n.startswith('t_parcours_') or n.startswith('t_donnees_')]
        print()
        for nom, souci, detail in _lancer_ui_isole(ui):
            total += 1
            court = nom.strip().split('\n')[0][:62]
            if souci is None:
                print('  ok      %s' % court)
            else:
                echecs.append((court, souci, detail))
                print('  ECHEC   %-*s  %s' % (larg, court, souci))

    print('\n%d tests, %d echec(s)' % (total, len(echecs)))
    for nom, e, tb in echecs:
        print('\n--- %s ---\n%s' % (nom, tb))
    sys.exit(1 if echecs else 0)
