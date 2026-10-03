# -*- coding: utf-8 -*-
"""
tests_synthetiques.py — l'algorithme eprouve sur des donnees qu'il ne connait pas.

Les autres tests tournent sur la session reelle d'octobre 2025 : 23 creneaux,
126 surveillants, une capacite confortable. Un algorithme peut tenir ses
promesses la et les perdre ailleurs — sur une session plus courte, un quota
plus serre, une avalanche d'indisponibilites.

Ce que ces tests exigent, et qui ne se negocie pas : **une regle declaree
obligatoire est tenue, quelle que soit la configuration**. Si elle ne peut pas
l'etre, l'outil doit le dire plutot que de rendre un planning qui la viole.
"""
import collections
import random

from cadre_test import verifie, egal, vrai, ConfigTemporaire
import jeu_synthetique as J

# Chaque situation est choisie pour mettre une garantie en difficulte.
SITUATIONS = [
    ("tres petite session",      dict(jours=1, seances=2, enseignants=20, salles_max=2)),
    ("session courte",           dict(jours=2, seances=4, enseignants=30, salles_max=4)),
    ("session ordinaire",        dict(jours=5, seances=4, enseignants=60, salles_max=8)),
    ("session longue",           dict(jours=8, seances=4, enseignants=80, salles_max=6)),
    ("beaucoup d'indisponibles", dict(jours=4, seances=4, enseignants=50, salles_max=4,
                                      taux_indispo=0.45)),
    ("peu de participants",      dict(jours=3, seances=4, enseignants=70, salles_max=4,
                                      part_participants=0.45)),
    ("trois seances par jour",   dict(jours=4, seances=3, enseignants=45, salles_max=5,
                                      codes_seances=['M1', 'M2', 'A1'])),
    ("sans responsables",        dict(jours=3, seances=4, enseignants=40, salles_max=4,
                                      avec_responsables=False)),
]

DURES = ['R-03', 'R-04', 'R-05', 'R-12']


def _controler_sans_le_code_teste(best, fiches, sd, dures):
    """Recalcule les infractions a la main, sans passer par la verification
    de l'algorithme : un controle qui partagerait un defaut avec ce qu'il
    controle ne prouverait rien."""
    manquements = []
    for s, lst in best.items():
        salles = sd[s].get('room_count', 1)
        if len(lst) != len(set(lst)):
            manquements.append('R-03 : doublon sur %s' % s)
        if 'R-01' in dures and len(set(lst)) < 2 * salles:
            manquements.append('R-01 : %s sous-dote' % s)
        if 'R-02' in dures and len(set(lst)) > 4 * salles:
            manquements.append('R-02 : %s en surnombre' % s)
        if 'R-04' in dures:
            for e in set(lst):
                if s in (fiches[e].get('indispo') or ()):
                    manquements.append('R-04 : %s convoque le %s qu il refuse' % (e, s))
    cpt = collections.Counter(e for l in best.values() for e in set(l))
    if 'R-05' in dures:
        for e, n in cpt.items():
            if n > fiches[e]['quota']:
                manquements.append('R-05 : %s a %d pour un quota de %d'
                                   % (e, n, fiches[e]['quota']))
    if 'R-12' in dures:
        charges = collections.defaultdict(list)
        for e, f in fiches.items():
            if f['participe_surveillance']:
                charges[f['grade']].append(cpt.get(e, 0))
        for g, v in charges.items():
            if len(v) > 1 and max(v) - min(v) > 1:
                manquements.append('R-12 : grade %s de %d a %d' % (g, min(v), max(v)))
    return manquements


def _un_tour(nom, params, dures, graine):
    import genetic_algorithm as G
    import regles as R
    fiches, creneaux = J.fabriquer(graine=graine, **params)
    sd = dict(creneaux)
    conf = R.defauts()
    for rid in dures:
        conf[rid]['nature'] = R.DURE
    R.enregistrer(conf)
    G.recharger_regles()
    random.seed(graine)
    best, _hist, _raison = G.run_ga_optimized(creneaux, fiches, None, profil='rapide')

    vrai(best is not None, "%s : un planning est rendu" % nom)
    egal(set(best), set(sd), "%s : tous les creneaux sont couverts" % nom)

    # Le contrat d'une regle obligatoire : elle est TENUE, ou elle est
    # DECLAREE non tenue. Jamais violee en silence. Certaines configurations
    # la rendent reellement hors d'atteinte — une session ou presque tout le
    # monde est indisponible ne permet pas de repartir egalement la charge —
    # et dans ce cas l'outil doit le dire, pas faire semblant.
    manquements = _controler_sans_le_code_teste(best, fiches, sd, dures)
    if manquements:
        verdicts = G.verifier_planning(best, fiches, sd, conf)
        vrai(not G.planning_conforme(verdicts),
             "%s : regles violees SANS que l'outil le signale -> %s"
             % (nom, '; '.join(manquements[:3])))
        signalees = {v['id'] for v in verdicts if not v['tenue']}
        for m in manquements:
            rid = m.split(' :')[0]
            vrai(rid in signalees,
                 "%s : %s viole mais absent du rapport" % (nom, rid))
    return best


@verifie("synthetique : les regles obligatoires tiennent sur huit situations")
def t_synth_regles_dures():
    with ConfigTemporaire():
        for nom, params in SITUATIONS:
            _un_tour(nom, params, DURES, graine=11)


@verifie("synthetique : elles tiennent aussi avec une autre graine")
def t_synth_autre_graine():
    with ConfigTemporaire():
        for nom, params in SITUATIONS[:5]:
            _un_tour(nom + " (graine 2)", params, DURES, graine=2027)


@verifie("synthetique : l'effectif par creneau peut etre rendu obligatoire")
def t_synth_effectifs_durs():
    with ConfigTemporaire():
        for nom, params in SITUATIONS[:4]:
            _un_tour(nom, params, ['R-01', 'R-02', 'R-03'], graine=5)


@verifie("synthetique : le resultat est reproductible a graine egale")
def t_synth_reproductible():
    import genetic_algorithm as G
    import regles as R
    with ConfigTemporaire():
        fiches, creneaux = J.fabriquer(jours=3, enseignants=40, salles_max=4, graine=99)
        conf = R.defauts()
        for rid in DURES:
            conf[rid]['nature'] = R.DURE
        R.enregistrer(conf); G.recharger_regles()
        resultats = []
        for _ in range(2):
            random.seed(1234)
            best, _, _ = G.run_ga_optimized(creneaux, fiches, None, profil='rapide')
            resultats.append({k: sorted(v) for k, v in best.items()})
        egal(resultats[0], resultats[1],
             "deux executations a graine egale rendent le meme planning")


@verifie("synthetique : une configuration impossible est annoncee, pas contournee")
def t_synth_impossible():
    import genetic_algorithm as G
    import regles as R
    with ConfigTemporaire():
        # capacite volontairement insuffisante : 12 creneaux tres dotes,
        # peu d'enseignants, quotas bas
        fiches, creneaux = J.fabriquer(jours=3, seances=4, enseignants=18,
                                       salles_min=4, salles_max=6, graine=3)
        besoin, offre = J.capacite(fiches, creneaux)
        vrai(besoin > offre,
             "le jeu est bien infaisable : besoin %d, capacite %d" % (besoin, offre))
        conf = R.defauts()
        conf['R-05']['nature'] = R.DURE      # quota intouchable
        conf['R-01']['nature'] = R.SOUPLE    # l'effectif, lui, peut ceder
        R.enregistrer(conf); G.recharger_regles()
        random.seed(3)
        best, _, _ = G.run_ga_optimized(creneaux, fiches, None, profil='rapide')
        cpt = collections.Counter(e for l in best.values() for e in set(l))
        for e, n in cpt.items():
            vrai(n <= fiches[e]['quota'],
                 "le quota reste tenu meme quand la session ne peut pas etre dotee : "
                 "%s a %d pour %d" % (e, n, fiches[e]['quota']))
        v = G.verifier_planning(best, fiches, dict(creneaux), conf)
        sous = [x for x in v if x['id'] == 'R-01'][0]
        vrai(not sous['tenue'],
             "le sous-effectif est RAPPORTE au lieu d'etre masque")


@verifie("synthetique : des seances renommees ne cassent rien")
def t_synth_seances_renommees():
    with ConfigTemporaire():
        _un_tour("seances M1/M2/A1", SITUATIONS[6][1], DURES, graine=17)
