# -*- coding: utf-8 -*-
"""
tests_ui.py — les ecrans, pilotes sans souris.

Ils ouvrent de vraies fenetres sur le display courant et les manipulent par
leurs widgets. C'est plus lent que les tests de logique, mais c'est le seul
moyen d'attraper ce qui se casse entre l'ecran et le modele : un bouton qui
n'enregistre pas, un rappel jamais appele, une fenetre qui ne s'ouvre pas.
"""
import json
import os
import shutil
import sqlite3
import time

from cadre_test import verifie, egal, vrai, donnees, ConfigTemporaire


def _app():
    import main
    a = main.PlanningApp()
    a.update()
    a.show_success_message = lambda t, m, **k: a.__dict__.setdefault('_msgs', []).append(('ok', t, m))
    a.show_error_message = lambda t, m: a.__dict__.setdefault('_msgs', []).append(('err', t, m))
    return a


def _charger_donnees(a):
    t, s, best = donnees()
    a.teachers, a.slots, a.best = t, s, best
    return a


@verifie("ui : la fenetre principale se construit")
def t_ui_fenetre():
    a = _app()
    try:
        vrai(a.tree is not None, "le tableau existe")
        vrai(hasattr(a, 'btn_export_individuel'), "les boutons d'export existent")
        egal(str(a.btn_export_individuel.cget('state')), 'disabled',
             "les exports sont desactives sans planning")
    finally:
        a.destroy()


@verifie("ui : les exports s'activent une fois le planning produit")
def t_ui_exports():
    a = _charger_donnees(_app())
    try:
        a.activer_exports(); a.update()
        egal(str(a.btn_export_individuel.cget('state')), 'normal', "export individuel actif")
        egal(str(a.btn_export_general.cget('state')), 'normal', "export general actif")
    finally:
        a.destroy()


@verifie("ui : l'onglet Qualite affiche le rapport de conformite")
def t_ui_conformite():
    # sous ConfigTemporaire : sans elle, le test dependait de la langue
    # laissee dans parametres.json par une execution precedente, et cherchait
    # « BILAN » dans une interface passee en anglais.
    with ConfigTemporaire():
        a = _charger_donnees(_app())
        try:
            a.afficher_conformite(); a.update()
            lignes = a.tree.get_children()
            vrai(len(lignes) >= 12,
                 "une ligne par regle au moins, obtenu %d" % len(lignes))
            premiere = [str(x) for x in a.tree.item(lignes[0])['values']]
            vrai(premiere[0] == 'BILAN', "le bilan est en tete, obtenu %r" % premiere[0])
            textes = ' '.join(' '.join(str(x) for x in a.tree.item(i)['values'])
                              for i in lignes)
            vrai('R-06' in textes, "les regles sont nommees par leur identifiant")
            vrai('A CORRIGER' in textes, "les manquements sont regroupes en tete")
        finally:
            a.destroy()


@verifie("ui : l'ecran d'administration s'ouvre avec ses six onglets")
def t_ui_admin():
    a = _app()
    try:
        from ecran_parametres import FenetreParametres
        w = FenetreParametres(a); a.update(); w.update()
        import regles as R
        # on compare au catalogue, pas a un nombre ecrit en dur : ajouter une
        # regle ne doit pas faire echouer un test qui ne la concerne pas
        egal(len(w.choix_regles), len(R.CATALOGUE), "toutes les regles du catalogue")
        egal(len(w.lignes_seances), 4, "quatre seances")
        vrai(len(w.lignes_quotas) >= 10, "les grades sont listes")
        vrai(w.choix_generation.get() in ('rapide', 'approfondie'), "mode de generation")
        w.destroy()
    finally:
        a.destroy()


@verifie("ui : la langue choisie est bien enregistree")
def t_ui_langue():
    import parametres as P
    with ConfigTemporaire():
        a = _app()
        try:
            from ecran_parametres import FenetreParametres
            w = FenetreParametres(a, au_retour=a.appliquer_parametres)
            a.update()
            w.choix_langue.set('English')
            w._enregistrer(); a.update()
            a.after(200, a.quit); a.mainloop()
            egal(P.charger()['langue'], 'en', "la langue est enregistree")
            vrai(a.__dict__.get('_msgs'), "l'utilisateur recoit une confirmation")
        finally:
            a.destroy()


@verifie("ui : le logo choisi est enregistre et relu")
def t_ui_logo():
    import parametres as P
    with ConfigTemporaire():
        a = _app()
        try:
            from ecran_parametres import FenetreParametres
            w = FenetreParametres(a, au_retour=a.appliquer_parametres)
            a.update()
            source = os.path.join(os.path.dirname(P.LOGO_DEFAUT), 'logo-source-test.png')
            shutil.copyfile(P.LOGO_DEFAUT, source)
            import tkinter.filedialog as fd
            garde = fd.askopenfilename
            fd.askopenfilename = lambda **k: source
            try:
                w._choisir_logo()
            finally:
                fd.askopenfilename = garde
            vrai(w.conf['logo'], "un logo est retenu dans l'ecran")
            w._enregistrer(); a.update()
            relu = P.charger()
            vrai(relu['logo'], "le logo est present apres relecture")
            vrai(os.path.exists(relu['logo']), "le fichier existe : %s" % relu['logo'])
            egal(P.chemin_logo(relu), relu['logo'], "c'est bien lui qui sera affiche")
            for f in (source, relu['logo']):
                if os.path.exists(f) and 'defaut' not in f:
                    os.remove(f)
        finally:
            a.destroy()


@verifie("ui : les quotas modifies s'appliquent aux enseignants charges")
def t_ui_quotas():
    with ConfigTemporaire():
        a = _charger_donnees(_app())
        try:
            from constants import GRADE_QUOTAS
            from ecran_parametres import FenetreParametres
            w = FenetreParametres(a, au_retour=a.appliquer_parametres)
            a.update()
            grade = w.lignes_quotas[0]['code'].get()
            w.lignes_quotas[0]['nombre'].delete(0, 'end')
            w.lignes_quotas[0]['nombre'].insert(0, '13')
            w._enregistrer(); a.update()
            a.after(250, a.quit); a.mainloop()   # le rappel est differe d'un tour
            egal(GRADE_QUOTAS.get(grade), 13, "la table des grades est a jour")
            portes = {f['quota'] for f in a.teachers.values() if f.get('grade') == grade}
            vrai(portes in ({13}, set()), "les enseignants de ce grade portent 13")
        finally:
            a.destroy()


@verifie("ui : une saisie invalide est refusee sans rien enregistrer")
def t_ui_refus():
    import parametres as P
    with ConfigTemporaire():
        a = _app()
        try:
            from ecran_parametres import FenetreParametres
            w = FenetreParametres(a, au_retour=a.appliquer_parametres)
            a.update()
            w.lignes_seances[0]['debut'].delete(0, 'end')
            w.lignes_seances[0]['debut'].insert(0, '25:00')
            w._enregistrer(); a.update()
            vrai(w.winfo_exists(), "la fenetre reste ouverte")
            vrai(w.message.cget('text'), "un motif de refus est affiche")
            vrai(not os.path.exists(P.FICHIER), "rien n'a ete enregistre")
        finally:
            try:
                w.destroy()
            except Exception:
                pass
            a.destroy()


@verifie("ui : la generation complete aboutit et rend un planning conforme")
def t_ui_generation():
    """La generation de bout en bout, sous la vraie boucle d'evenements.

    Surveiller la fin par une boucle `while ... update()` reentre dans Tk
    pendant que les rappels `after` s'executent, et fait tomber l'interpreteur
    — un defaut du test, pas de l'application. On attend donc comme
    l'application attend : en rendant la main a `mainloop`.
    """
    import genetic_algorithm as G
    with ConfigTemporaire():
        a = _app()
        etat = {}
        try:
            t, s, _ = donnees()
            a.teachers, a.slots = t, s

            def surveiller():
                if a.best:
                    etat['fini'] = True
                    a.quit()
                elif time.time() - etat['depart'] > 150:
                    etat['expire'] = True
                    a.quit()
                else:
                    a.after(200, surveiller)

            etat['depart'] = time.time()
            a.after(100, a.generate_planning)
            a.after(300, surveiller)
            a.mainloop()

            vrai(not etat.get('expire'), "la generation aboutit en moins de 150 s")
            vrai(a.best, "un planning est produit")
            egal(set(a.best), set(dict(s)), "tous les creneaux sont couverts")
            v = G.verifier_planning(a.best, t, dict(s))
            vrai(G.planning_conforme(v), "il respecte les regles obligatoires")
            vrai(any(m[0] == 'ok' for m in a.__dict__.get('_msgs', [])),
                 "un message de fin est affiche")
            egal(str(a.btn_export_individuel.cget('state')), 'normal',
                 "les exports sont actifs apres generation")
        finally:
            a.destroy()


@verifie("ui : generer sans donnees previent au lieu de planter")
def t_ui_generation_sans_donnees():
    a = _app()
    try:
        a.slots, a.teachers = [], {}
        a.generate_planning(); a.update()
        msgs = a.__dict__.get('_msgs', [])
        vrai(any(m[0] == 'err' for m in msgs), "un message d'erreur est affiche")
        vrai(not a.best, "aucun planning fabrique")
    finally:
        a.destroy()


@verifie("ui : le logo choisi apparait dans l'en-tete")
def t_ui_logo_affiche():
    import parametres as P
    with ConfigTemporaire():
        a = _app()
        try:
            vrai(a._image_logo is not None,
                 "le logo par defaut est affiche quand aucun n'est choisi")
        finally:
            a.destroy()
        # sans aucun logo disponible, l'en-tete retombe sur le pictogramme
        garde = P.chemin_logo
        P.chemin_logo = lambda c: None
        try:
            b = _app()
            vrai(b._image_logo is None, "repli sur le pictogramme")
            b.destroy()
        finally:
            P.chemin_logo = garde


def _tous_les_textes(widget, sortie=None):
    sortie = [] if sortie is None else sortie
    try:
        v = widget.cget('text')
        if v:
            sortie.append(str(v))
    except Exception:
        pass
    for enfant in widget.winfo_children():
        _tous_les_textes(enfant, sortie)
    return sortie


@verifie("ui : l'interface demarre dans la langue enregistree")
def t_ui_langue_demarrage():
    import parametres as P
    with ConfigTemporaire():
        c = P.defauts(); c['langue'] = 'en'; P.enregistrer(c)
        a = _app()
        try:
            textes = ' '.join(_tous_les_textes(a))
            vrai('Load exam slots' in textes, "les boutons sont en anglais")
            vrai('Charger Créneaux' not in textes, "plus de francais dans la barre")
        finally:
            a.destroy()


@verifie("ui : le choix de langue est enregistre et annonce")
def t_ui_langue_bascule():
    import parametres as P
    with ConfigTemporaire():
        a = _app()
        try:
            from ecran_parametres import FenetreParametres
            w = FenetreParametres(a, au_retour=a.appliquer_parametres)
            a.update()
            w.choix_langue.set('English')
            w._enregistrer(); a.update()
            a.after(250, a.quit); a.mainloop()
            egal(P.charger()['langue'], 'en', "le choix est enregistre")
            messages = ' '.join(str(m[2]) for m in a.__dict__.get('_msgs', []))
            vrai('langue' in messages.lower(),
                 "l'application annonce que la langue s'appliquera au redemarrage")
        finally:
            a.destroy()


@verifie("ui : le PDF general porte le rapport de conformite")
def t_ui_export_pdf():
    import glob
    import subprocess
    with ConfigTemporaire():
        a = _charger_donnees(_app())
        try:
            dossier = 'exports'
            avant = set(glob.glob(os.path.join(dossier, 'Planning_General_*.pdf')))
            a.export_general_pdf()
            a.update()
            produits = set(glob.glob(os.path.join(dossier, 'Planning_General_*.pdf'))) - avant
            vrai(produits, "un PDF est produit")
            pdf = produits.pop()
            vrai(os.path.getsize(pdf) > 3000, "le PDF n'est pas vide")
            texte = subprocess.run(['pdftotext', pdf, '-'], capture_output=True,
                                   text=True).stdout
            vrai('Rapport de conformité' in texte, "la page de conformite est presente")
            vrai('R-06' in texte, "les regles y sont nommees")
            vrai('règles sur' in texte, "le bilan y figure")
            os.remove(pdf)
        finally:
            a.destroy()


@verifie("ui : exporter n'envoie aucun courriel")
def t_ui_export_sans_envoi():
    """Le filet de securite : produire des PDF ne doit jamais ecrire a personne.

    L'export partait avec `send_emails=True` : il ouvrait sans prevenir une
    fenetre de configuration SMTP, et la remplir faisait partir un courriel
    vers chacun des 126 surveillants convoques.
    """
    import glob
    import export_methods as EM
    with ConfigTemporaire():
        a = _charger_donnees(_app())
        touche = {'dialogue': 0, 'envoi': 0}

        class DialogueInterdit:
            def __init__(self, *a, **k):
                touche['dialogue'] += 1

            def show(self):
                return None

        class EnvoiInterdit:
            def __init__(self, *a, **k):
                touche['envoi'] += 1

            def send_bulk_emails(self, *a, **k):
                touche['envoi'] += 1
                return 0, []

        gardes = (EM.EmailConfigDialog, EM.EmailSender)
        EM.EmailConfigDialog, EM.EmailSender = DialogueInterdit, EnvoiInterdit
        try:
            for f in glob.glob('exports/*.pdf'):
                if 'General' not in f:
                    os.remove(f)
            a.export_teachers_to_pdf()
            a.update()
            egal(touche['dialogue'], 0, "aucune fenetre de configuration SMTP ouverte")
            egal(touche['envoi'], 0, "aucun envoi tente")
            produits = [f for f in glob.glob('exports/*.pdf') if 'General' not in f]
            vrai(produits, "les PDF individuels sont pourtant bien produits")
        finally:
            EM.EmailConfigDialog, EM.EmailSender = gardes
            a.destroy()


@verifie("ui : l'envoi demande confirmation et nomme le nombre de destinataires")
def t_ui_envoi_confirme():
    import export_methods as EM
    import tkinter.messagebox as mb
    with ConfigTemporaire():
        a = _charger_donnees(_app())
        vu = {}
        envoye = {'n': 0}

        def faux_askyesno(titre, message, **k):
            vu['message'] = message
            return False                      # on refuse : rien ne doit partir

        garde_mb, garde_ex = mb.askyesno, EM.ExportMethods.export_teachers_to_pdf
        mb.askyesno = faux_askyesno
        EM.ExportMethods.export_teachers_to_pdf = staticmethod(
            lambda *a, **k: envoye.__setitem__('n', envoye['n'] + 1))
        try:
            a.envoyer_convocations()
            a.update()
            vrai('message' in vu, "une confirmation est demandee")
            vrai(any(ch.isdigit() for ch in vu['message']),
                 "le nombre de destinataires est annonce : %r" % vu['message'][:80])
            egal(envoye['n'], 0, "refuser la confirmation n'envoie rien")
        finally:
            mb.askyesno = garde_mb
            EM.ExportMethods.export_teachers_to_pdf = garde_ex
            a.destroy()
