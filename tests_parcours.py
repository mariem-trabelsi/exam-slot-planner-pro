# -*- coding: utf-8 -*-
"""
tests_parcours.py — chaque bouton presse, chaque fenetre ouverte.

Les tests precedents verifient ce que l'application CALCULE. Celui-ci verifie
qu'elle ne tombe pas : il parcourt l'arbre des widgets, actionne tout ce qui
est actionnable, ouvre chaque fenetre secondaire et la referme.

Rien ne sort de la machine : les boites de dialogue de fichier, les questions
oui/non et l'envoi de courriels sont remplaces par des bouchons qui refusent
tout. Un test qui enverrait vraiment un courriel ou effacerait vraiment un
historique ne serait pas un test.
"""
import customtkinter as ctk

from cadre_test import (verifie, egal, vrai, donnees, ConfigTemporaire,
                        planning_enregistre)


class Bouchons:
    """Neutralise tout ce qui sort de l'application, le temps d'un parcours."""

    def __enter__(self):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        import export_methods as EM
        self.gardes = {
            'open': fd.askopenfilename, 'save': fd.asksaveasfilename,
            'dir': fd.askdirectory, 'yesno': mb.askyesno, 'ok': mb.showinfo,
            'err': mb.showerror, 'warn': mb.showwarning,
            'dialogue': EM.EmailConfigDialog, 'envoi': EM.EmailSender,
        }
        self.appels = []
        fd.askopenfilename = lambda **k: self._note('ouvrir-fichier', '')
        fd.asksaveasfilename = lambda **k: self._note('enregistrer-fichier', '')
        fd.askdirectory = lambda **k: self._note('choisir-dossier', '')
        mb.askyesno = lambda *a, **k: self._note('question', False)
        mb.showinfo = lambda *a, **k: self._note('info', None)
        mb.showerror = lambda *a, **k: self._note('erreur', None)
        mb.showwarning = lambda *a, **k: self._note('alerte', None)

        essai = self

        class DialogueInterdit:
            def __init__(self, *a, **k):
                essai.appels.append('SMTP-dialogue')

            def show(self):
                return None

        class EnvoiInterdit:
            def __init__(self, *a, **k):
                essai.appels.append('SMTP-envoi')

            def send_bulk_emails(self, *a, **k):
                essai.appels.append('SMTP-envoi')
                return 0, []

        EM.EmailConfigDialog = DialogueInterdit
        EM.EmailSender = EnvoiInterdit
        return self

    def _note(self, quoi, retour):
        self.appels.append(quoi)
        return retour

    def __exit__(self, *a):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        import export_methods as EM
        fd.askopenfilename = self.gardes['open']
        fd.asksaveasfilename = self.gardes['save']
        fd.askdirectory = self.gardes['dir']
        mb.askyesno = self.gardes['yesno']
        mb.showinfo = self.gardes['ok']
        mb.showerror = self.gardes['err']
        mb.showwarning = self.gardes['warn']
        EM.EmailConfigDialog = self.gardes['dialogue']
        EM.EmailSender = self.gardes['envoi']
        return False


def _salles_depuis(a):
    """Repartit les surveillants dans les salles, comme le fait l'import."""
    from view_methods import assign_teachers_to_rooms
    assign_teachers_to_rooms(a)
    return a.room_assignments


def _responsables_depuis(slots):
    """Les lignes « prof responsable » que l'import des creneaux produit."""
    import datetime
    import genetic_algorithm as G
    lignes = []
    for cle, d in slots:
        resp = str(d.get('enseignant', '') or '').strip()
        if not resp or not G.is_valid_teacher(resp):
            continue
        date, seance = cle.split()
        jour = datetime.datetime.strptime(date, '%Y-%m-%d')
        debut = G.SESSION_TIMES.get(seance, '08:30')
        h = int(debut[:2]) + 1
        for salle in (d.get('room_names') or ['S001']):
            lignes.append({
                'prof_code': resp, 'slot': cle,
                'date_exam': jour.strftime('%d/%m/%Y'),
                'h_debut': debut + ':00', 'h_fin': '%02d:%s:00' % (h, debut[3:]),
                'type_ex': 'E', 'semestre': 'SEMESTRE 2',
                'cod_salle': salle, 'session': seance,
                'jour': jour.strftime('%a %d/%m/%Y'),
            })
    return lignes


def _app(avec_planning=False):
    import main
    a = main.PlanningApp()
    a.update()
    a._msgs = []
    a.show_success_message = lambda t, m, **k: a._msgs.append(('ok', t, m))
    a.show_error_message = lambda t, m: a._msgs.append(('err', t, m))
    if avec_planning:
        t, s, best = donnees()
        a.teachers, a.slots, a.best = t, s, best
        p = planning_enregistre()
        if p is not None:
            a.room_assignments = p.get('room_assignments') or {}
            a.prof_resp_list = p.get('prof_resp_list') or []
        else:
            # Pas de base de travail : on reconstruit ce que l'import aurait
            # pose. Les ecrans et les exports lisent ces deux structures, et
            # les laisser vides ne testerait plus qu'un affichage vide.
            a.room_assignments = _salles_depuis(a)
            a.prof_resp_list = _responsables_depuis(s)
        a.data_loaded = {'slots': True, 'teachers': True, 'wishes': True}
        a.activer_exports()
        a.update()
    return a


def _boutons(widget, trouves=None):
    trouves = [] if trouves is None else trouves
    if isinstance(widget, ctk.CTkButton):
        trouves.append(widget)
    for enfant in widget.winfo_children():
        _boutons(enfant, trouves)
    return trouves


def _parcourir(a, sauter=()):
    """Presse chaque bouton actionnable et rend les incidents rencontres."""
    incidents = []
    for bouton in _boutons(a):
        try:
            libelle = str(bouton.cget('text'))
        except Exception:
            continue
        if str(bouton.cget('state')) == 'disabled':
            continue
        if any(mot.lower() in libelle.lower() for mot in sauter):
            continue
        try:
            bouton.invoke()
            a.update()
        except Exception as e:
            incidents.append('%s -> %s: %s' % (libelle, type(e).__name__, e))
        # on referme ce qui s'est ouvert, pour continuer le parcours
        for f in list(a.winfo_children()):
            if isinstance(f, ctk.CTkToplevel):
                try:
                    f.grab_release()
                    f.destroy()
                except Exception:
                    pass
        a.update()
    return incidents


@verifie("parcours : tous les boutons de l'ecran d'accueil, sans planning")
def t_parcours_accueil():
    with ConfigTemporaire(), Bouchons() as b:
        a = _app()
        try:
            incidents = _parcourir(a)
            vrai(not incidents, "incidents : %s" % '; '.join(incidents[:3]))
            vrai('SMTP-envoi' not in b.appels, "aucun envoi tente")
            vrai('SMTP-dialogue' not in b.appels, "aucune demande d'identifiants")
        finally:
            a.destroy()


@verifie("parcours : tous les boutons avec un planning charge")
def t_parcours_avec_planning():
    with ConfigTemporaire(), Bouchons() as b:
        a = _app(avec_planning=True)
        try:
            # on saute l'envoi, teste separement, et la suppression d'historique
            incidents = _parcourir(a, sauter=('supprimer',))
            vrai(not incidents, "incidents : %s" % '; '.join(incidents[:3]))
            vrai('SMTP-envoi' not in b.appels,
                 "aucun envoi : la confirmation est refusee par le bouchon")
        finally:
            a.destroy()


@verifie("parcours : chaque vue de donnees s'affiche sans incident")
def t_parcours_vues():
    with ConfigTemporaire(), Bouchons():
        a = _app(avec_planning=True)
        try:
            for vue in ('planning', 'teacher', 'room', 'quality'):
                try:
                    a.switch_view(vue)
                    a.update()
                except Exception as e:
                    vrai(False, "vue %s : %s: %s" % (vue, type(e).__name__, e))
                vrai(a.tree.get_children() or vue == 'planning',
                     "la vue %s affiche quelque chose" % vue)
        finally:
            a.destroy()


@verifie("parcours : chaque fenetre secondaire s'ouvre et se ferme")
def t_parcours_fenetres():
    with ConfigTemporaire(), Bouchons():
        a = _app(avec_planning=True)
        # L'historique ne s'ouvre que s'il a quelque chose a montrer : sans
        # ligne enregistree il annonce « historique vide », ce qui est juste.
        # On enregistre donc le planning courant d'abord — le test couvre du
        # meme coup l'ecriture en base — et on retire la ligne a la sortie,
        # sinon la suite suivante prendrait ce planning d'essai pour les
        # donnees de l'etablissement.
        _ok, ligne = a.db_manager.save_planning_to_history(
            {'best': {k: list(v) for k, v in a.best.items()},
             'teachers': a.teachers,
             'slots': [list(x) for x in a.slots],
             'room_assignments': a.room_assignments,
             'prof_resp_list': a.prof_resp_list},
            notes='essai automatique')
        try:
            from ecran_parametres import FenetreParametres
            ouvertures = [
                ("administration", lambda: FenetreParametres(a)),
                ("historique", lambda: a.db_manager.show_history(a)),
                ("message de succes", lambda: a._boite("Essai", "Corps.", '#10B981', '✓')),
                ("message d'erreur", lambda: a._boite("Essai", "Corps.", '#EF4444', '✕')),
            ]
            for nom, ouvrir in ouvertures:
                avant = len([w for w in a.winfo_children() if isinstance(w, ctk.CTkToplevel)])
                try:
                    ouvrir()
                    a.update()
                except Exception as e:
                    vrai(False, "%s : %s: %s" % (nom, type(e).__name__, e))
                fenetres = [w for w in a.winfo_children() if isinstance(w, ctk.CTkToplevel)]
                vrai(len(fenetres) > avant, "%s s'ouvre" % nom)
                for f in fenetres:
                    f.grab_release()
                    f.destroy()
                a.update()
                reste = [w for w in a.winfo_children()
                         if isinstance(w, ctk.CTkToplevel) and w.winfo_exists()]
                egal(len(reste), 0, "%s se referme entierement" % nom)
        finally:
            if _ok:
                try:
                    a.db_manager.cursor.execute(
                        'delete from planning_history where id = ?', (ligne,))
                    a.db_manager.conn.commit()
                except Exception:
                    pass
            a.destroy()


@verifie("donnees : le planning enregistre ne contient aucun doublon")
def t_donnees_doublons():
    t, s, best = donnees()
    sd = dict(s)
    for slot, lst in best.items():
        egal(len(lst), len(set(lst)), "doublon sur %s" % slot)
    egal(len(sd), len(set(sd)), "aucun creneau en double")
    for e in {x for l in best.values() for x in l}:
        vrai(e in t, "le surveillant %s existe dans le fichier enseignants" % e)


@verifie("donnees : les fiches enseignants sont coherentes")
def t_donnees_fiches():
    from constants import GRADE_QUOTAS
    t, _, _ = donnees()
    codes = {}
    for e, f in t.items():
        vrai(f.get('email'), "%s a une adresse" % e)
        vrai(isinstance(f.get('quota'), int) and f['quota'] >= 0,
             "%s a un quota entier positif" % e)
        if f.get('grade') in GRADE_QUOTAS:
            egal(f['quota'], GRADE_QUOTAS[f['grade']],
                 "le quota de %s suit son grade" % e)
        code = str(f.get('code_smartex_ens', '')).strip()
        if code:
            vrai(code not in codes,
                 "le code %s est partage par %s et %s" % (code, codes.get(code), e))
            codes[code] = e


@verifie("donnees : les creneaux sont bien formes")
def t_donnees_creneaux():
    import re
    _, s, _ = donnees()
    vus = set()
    for cle, d in s:
        vrai(re.match(r'^\d{4}-\d{2}-\d{2} \w+$', cle),
             "le creneau %r suit le format attendu" % cle)
        vrai(cle not in vus, "le creneau %s apparait deux fois" % cle)
        vus.add(cle)
        vrai(isinstance(d.get('room_count'), int) and d['room_count'] > 0,
             "%s declare un nombre de salles valide" % cle)
