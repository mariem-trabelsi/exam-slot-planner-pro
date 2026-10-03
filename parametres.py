# -*- coding: utf-8 -*-
"""
parametres.py — ce que l'etablissement regle lui-meme.

Trois choses etaient ecrites en dur et empechaient l'outil de servir ailleurs
que la ou il est ne : les horaires des seances, le nom et le logo de
l'etablissement, et la langue. Elles vivent desormais dans un fichier que
l'ecran de parametres ecrit, et les valeurs par defaut reproduisent le
comportement d'origine.

Les regles, elles, ont leur propre module (`regles.py`) : elles sont assez
nombreuses pour meriter leur catalogue.
"""
import json
import os
import re

FICHIER = 'parametres.json'
LOGO_DEFAUT = os.path.join('assets', 'logo-defaut.png')

# Deux langues seulement. L'arabe a ete retire : tkinter ne lie pas les lettres
# arabes et n'inverse pas le sens de lecture, le mot « العربية » s'affichait
# « ةيبرعلا ». Le proposer aurait promis une langue que l'outil ne sait pas
# ecrire ; l'ajouter demanderait arabic-reshaper et python-bidi pour les PDF,
# et une mise en page miroir que tkinter ne fait pas.
LANGUES = {'fr': 'Francais', 'en': 'English'}

# Les quatre seances historiques. Une seance ajoutee prend la suite de la liste.
SEANCES_DEFAUT = [
    {'code': 'S1', 'debut': '08:30', 'fin': '10:00'},
    {'code': 'S2', 'debut': '10:30', 'fin': '12:00'},
    {'code': 'S3', 'debut': '12:30', 'fin': '14:00'},
    {'code': 'S4', 'debut': '14:30', 'fin': '16:00'},
]

# Six teintes, reprises cycliquement si l'etablissement declare plus de seances.
TEINTES = [
    ('#E3F2FD', '#1976D2'), ('#E8F5E9', '#388E3C'),
    ('#FFF3E0', '#F57C00'), ('#F3E5F5', '#7B1FA2'),
    ('#E0F7FA', '#00796B'), ('#FCE4EC', '#C2185B'),
]

_HEURE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def defauts():
    return {
        'etablissement': '',
        'logo': '',
        'langue': 'fr',
        'seances': [dict(s) for s in SEANCES_DEFAUT],
        'generation': 'rapide',
        'quotas': {},          # grade -> nombre de surveillances ; vide = ceux du code
    }


def _seance_valide(s):
    return (isinstance(s, dict)
            and isinstance(s.get('code'), str) and s['code'].strip()
            and _HEURE.match(str(s.get('debut', '')))
            and _HEURE.match(str(s.get('fin', ''))))


def charger(chemin=FICHIER):
    """La configuration, completee et nettoyee.

    Une valeur invalide est remplacee par son defaut plutot que de faire
    tomber l'application au demarrage : le fichier peut avoir ete edite a la
    main, et un planning qui refuse de s'ouvrir est pire qu'un horaire faux.
    """
    conf = defauts()
    if not os.path.exists(chemin):
        return conf
    try:
        with open(chemin, encoding='utf-8') as f:
            lu = json.load(f)
    except (ValueError, OSError):
        return conf
    if not isinstance(lu, dict):
        return conf
    for cle in ('etablissement', 'logo'):
        if isinstance(lu.get(cle), str):
            conf[cle] = lu[cle].strip()
    if lu.get('langue') in LANGUES:
        conf['langue'] = lu['langue']
    if lu.get('generation') in ('rapide', 'approfondie'):
        conf['generation'] = lu['generation']
    q = lu.get('quotas')
    if isinstance(q, dict):
        conf['quotas'] = {str(g).strip().upper(): int(v) for g, v in q.items()
                          if str(g).strip() and isinstance(v, (int, float)) and 0 <= v <= 99}
    seances = [s for s in (lu.get('seances') or []) if _seance_valide(s)]
    if seances:
        vues, propres = set(), []
        for s in seances:                      # un code en double casserait
            code = s['code'].strip().upper()   # la correspondance creneau/seance
            if code in vues:
                continue
            vues.add(code)
            propres.append({'code': code, 'debut': s['debut'], 'fin': s['fin']})
        propres.sort(key=lambda s: s['debut'])
        conf['seances'] = propres
    return conf


def enregistrer(conf, chemin=FICHIER):
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)


def horaires(conf):
    """{'S1': '08:30', ...} — ce que le reste du code appelle SESSION_TIMES."""
    return {s['code']: s['debut'] for s in conf['seances']}


def ordre(conf):
    """{'S1': 1, ...} — l'ordre chronologique, deduit des horaires."""
    return {s['code']: i + 1 for i, s in enumerate(conf['seances'])}


def couleurs(conf):
    """{'s1': (fond, texte), ...} — en minuscules, comme l'attend l'affichage."""
    return {s['code'].lower(): TEINTES[i % len(TEINTES)]
            for i, s in enumerate(conf['seances'])}


def chemin_logo(conf):
    """Le logo de l'etablissement, ou celui par defaut, ou rien."""
    for c in (conf.get('logo'), LOGO_DEFAUT):
        if c and os.path.exists(c):
            return c
    return None
