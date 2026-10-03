# -*- coding: utf-8 -*-
"""
ecran_parametres.py — l'ecran ou l'etablissement regle l'outil.

Quatre choses y sont reglees, qui etaient jusqu'ici ecrites dans le code :
l'identite de l'etablissement, les horaires des seances, la nature de chaque
regle, et la langue. Rien n'y est applique a l'aveugle : les horaires sont
valides avant d'etre ecrits, et une nature interdite par le catalogue n'est
pas proposee.
"""
import os
import shutil
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from traductions import t as _t

import parametres as P
import regles as R

NATURES = {R.DURE: "Obligatoire", R.SOUPLE: "Souhaitable", R.IGNOREE: "Ignoree"}
EXPLICATION = {
    R.DURE: "Le planning ne peut pas la violer. S'il devient impossible, l'outil le dit.",
    R.SOUPLE: "L'algorithme cherche a la satisfaire, sans y etre tenu.",
    R.IGNOREE: "Elle n'entre dans aucun calcul.",
}


class FenetreParametres(ctk.CTkToplevel):
    def __init__(self, parent, au_retour=None):
        super().__init__(parent)
        self.title("Parametres")
        self.geometry("860x660")
        self.au_retour = au_retour
        self.conf = P.charger()
        self.regles = R.charger()
        self.lignes_seances = []
        self.choix_regles = {}

        self.transient(parent)
        self._construire()
        self.after(220, self.lift)

    # ---------------------------------------------------------------- bati
    def _construire(self):
        onglets = ctk.CTkTabview(self, width=820, height=560)
        onglets.pack(fill='both', expand=True, padx=16, pady=(16, 8))
        self._etablissement(onglets.add(_t("Etablissement")))
        self._seances(onglets.add(_t("Seances")))
        self._quotas(onglets.add(_t("Quotas")))
        self._regles(onglets.add(_t("Regles")))
        self._generation(onglets.add(_t("Generation")))
        self._langue(onglets.add(_t("Langue")))

        pied = ctk.CTkFrame(self, fg_color='transparent')
        pied.pack(fill='x', padx=16, pady=(0, 14))
        self.message = ctk.CTkLabel(pied, text="", text_color='#B91C1C', anchor='w')
        self.message.pack(side='left')
        ctk.CTkButton(pied, text=_t("Annuler"), width=110, fg_color='#6B7280',
                      command=self.destroy).pack(side='right', padx=(8, 0))
        ctk.CTkButton(pied, text=_t("Enregistrer"), width=140,
                      command=self._enregistrer).pack(side='right')

    # -------------------------------------------------------- etablissement
    def _etablissement(self, onglet):
        ctk.CTkLabel(onglet, text=_t("Nom de l'etablissement"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 4))
        self.champ_nom = ctk.CTkEntry(onglet, width=520,
                                      placeholder_text="Faculte des Sciences de ...")
        self.champ_nom.pack(anchor='w', padx=20)
        self.champ_nom.insert(0, self.conf['etablissement'])
        ctk.CTkLabel(onglet, text=_t("Il apparait en tete de l'application et sur les exports."),
                     text_color='#6B7280').pack(anchor='w', padx=20, pady=(4, 20))

        ctk.CTkLabel(onglet, text=_t("Logo"), font=("DejaVu Sans", 13, "bold")).pack(
            anchor='w', padx=20, pady=(0, 6))
        rang = ctk.CTkFrame(onglet, fg_color='transparent')
        rang.pack(anchor='w', padx=20)
        self.apercu = ctk.CTkLabel(rang, text="", width=96, height=96)
        self.apercu.pack(side='left')
        colonne = ctk.CTkFrame(rang, fg_color='transparent')
        colonne.pack(side='left', padx=16)
        ctk.CTkButton(colonne, text=_t("Choisir une image..."), width=190,
                      command=self._choisir_logo).pack(anchor='w')
        ctk.CTkButton(colonne, text=_t("Revenir au logo par defaut"), width=190,
                      fg_color='#6B7280', command=self._logo_defaut).pack(anchor='w', pady=(8, 0))
        self.etiquette_logo = ctk.CTkLabel(onglet, text="", text_color='#6B7280')
        self.etiquette_logo.pack(anchor='w', padx=20, pady=(10, 0))
        self._rafraichir_logo()

    def _rafraichir_logo(self):
        chemin = P.chemin_logo(self.conf)
        self.etiquette_logo.configure(
            text=("Logo par defaut" if chemin == P.LOGO_DEFAUT
                  else (os.path.basename(chemin) if chemin else "Aucun logo")))
        if not chemin:
            self.apercu.configure(image=None, text="—")
            return
        try:
            from PIL import Image
            img = Image.open(chemin)
            self.apercu.configure(image=ctk.CTkImage(img, size=(88, 88)), text="")
        except Exception:
            self.apercu.configure(image=None, text="?")

    def _choisir_logo(self):
        f = filedialog.askopenfilename(
            parent=self, title="Logo de l'etablissement",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if not f:
            return
        # On COPIE dans le projet : un logo pris sur une cle USB disparaitrait
        # au prochain demarrage, et l'ecran afficherait un cadre vide.
        os.makedirs('assets', exist_ok=True)
        cible = os.path.join('assets', 'logo-etablissement' + os.path.splitext(f)[1].lower())
        try:
            if os.path.abspath(f) != os.path.abspath(cible):
                shutil.copyfile(f, cible)
            self.conf['logo'] = cible
            self._rafraichir_logo()
        except OSError as e:
            self.message.configure(text="Logo non copie : %s" % e)

    def _logo_defaut(self):
        self.conf['logo'] = ''
        self._rafraichir_logo()

    # -------------------------------------------------------------- seances
    def _seances(self, onglet):
        ctk.CTkLabel(onglet, text=_t("Horaires des seances"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 2))
        ctk.CTkLabel(onglet, text=_t("Le code est celui qui figure dans vos fichiers de creneaux."),
                     text_color='#6B7280').pack(anchor='w', padx=20, pady=(0, 10))
        self.boite_seances = ctk.CTkScrollableFrame(onglet, height=300)
        self.boite_seances.pack(fill='both', expand=True, padx=20)
        entete = ctk.CTkFrame(self.boite_seances, fg_color='transparent')
        entete.pack(fill='x', pady=(0, 4))
        for titre, l in (("Code", 90), ("Debut", 110), ("Fin", 110)):
            ctk.CTkLabel(entete, text=titre, width=l, anchor='w',
                         text_color='#6B7280').pack(side='left', padx=4)
        for s in self.conf['seances']:
            self._ligne_seance(s)
        ctk.CTkButton(onglet, text=_t("Ajouter une seance"), width=190,
                      command=lambda: self._ligne_seance(
                          {'code': '', 'debut': '08:00', 'fin': '09:30'})
                      ).pack(anchor='w', padx=20, pady=12)

    def _ligne_seance(self, s):
        rang = ctk.CTkFrame(self.boite_seances, fg_color='transparent')
        rang.pack(fill='x', pady=2)
        code = ctk.CTkEntry(rang, width=90); code.insert(0, s['code'])
        debut = ctk.CTkEntry(rang, width=110, placeholder_text="08:30"); debut.insert(0, s['debut'])
        fin = ctk.CTkEntry(rang, width=110, placeholder_text="10:00"); fin.insert(0, s['fin'])
        for w in (code, debut, fin):
            w.pack(side='left', padx=4)
        entree = {'code': code, 'debut': debut, 'fin': fin, 'rang': rang}
        ctk.CTkButton(rang, text=_t("Retirer"), width=80, fg_color='#9CA3AF',
                      command=lambda: self._retirer_seance(entree)).pack(side='left', padx=8)
        self.lignes_seances.append(entree)

    def _retirer_seance(self, entree):
        entree['rang'].destroy()
        self.lignes_seances.remove(entree)

    # --------------------------------------------------------------- quotas
    def _quotas(self, onglet):
        from constants import GRADE_QUOTAS
        ctk.CTkLabel(onglet, text=_t("Surveillances par grade"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 2))
        ctk.CTkLabel(onglet,
                     text="Le nombre maximum de surveillances d'un enseignant, selon son grade.\n"
                          "Le code du grade est celui qui figure dans votre fichier enseignants.",
                     text_color='#6B7280', justify='left').pack(anchor='w', padx=20, pady=(0, 10))

        self.boite_quotas = ctk.CTkScrollableFrame(onglet, height=300)
        self.boite_quotas.pack(fill='both', expand=True, padx=20)
        entete = ctk.CTkFrame(self.boite_quotas, fg_color='transparent')
        entete.pack(fill='x', pady=(0, 4))
        for titre, l in (("Grade", 110), ("Surveillances", 110)):
            ctk.CTkLabel(entete, text=titre, width=l, anchor='w',
                         text_color='#6B7280').pack(side='left', padx=4)

        self.lignes_quotas = []
        valeurs = dict(GRADE_QUOTAS)
        valeurs.update(self.conf.get('quotas') or {})
        for grade in sorted(valeurs):
            self._ligne_quota(grade, valeurs[grade])
        ctk.CTkButton(onglet, text=_t("Ajouter un grade"), width=190,
                      command=lambda: self._ligne_quota('', 4)).pack(
                          anchor='w', padx=20, pady=12)

    def _ligne_quota(self, grade, valeur):
        rang = ctk.CTkFrame(self.boite_quotas, fg_color='transparent')
        rang.pack(fill='x', pady=2)
        code = ctk.CTkEntry(rang, width=110, placeholder_text="PR")
        code.insert(0, grade)
        nombre = ctk.CTkEntry(rang, width=110)
        nombre.insert(0, str(valeur))
        code.pack(side='left', padx=4)
        nombre.pack(side='left', padx=4)
        ctk.CTkLabel(rang, text=_t("surveillances"), text_color='#6B7280').pack(side='left', padx=6)
        entree = {'code': code, 'nombre': nombre, 'rang': rang}
        ctk.CTkButton(rang, text=_t("Retirer"), width=80, fg_color='#9CA3AF',
                      command=lambda: self._retirer_quota(entree)).pack(side='left', padx=8)
        self.lignes_quotas.append(entree)

    def _retirer_quota(self, entree):
        entree['rang'].destroy()
        self.lignes_quotas.remove(entree)

    # ----------------------------------------------------------- generation
    def _generation(self, onglet):
        import genetic_algorithm as G
        ctk.CTkLabel(onglet, text=_t("Duree de la recherche"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 2))
        ctk.CTkLabel(onglet, text=_t("Une recherche plus longue explore davantage de plannings."),
                     text_color='#6B7280').pack(anchor='w', padx=20, pady=(0, 14))
        self.choix_generation = tk.StringVar(
            value=self.conf.get('generation', G.PROFIL_DEFAUT))
        for cle in ('rapide', 'approfondie'):
            prof = G.PROFILS[cle]
            carte = ctk.CTkFrame(onglet)
            carte.pack(fill='x', padx=20, pady=6)
            ctk.CTkRadioButton(carte, text=prof['nom'], value=cle,
                               variable=self.choix_generation,
                               font=("DejaVu Sans", 13, "bold")).pack(
                                   anchor='w', padx=14, pady=(12, 2))
            ctk.CTkLabel(carte, text=prof['detail'], text_color='#6B7280',
                         anchor='w').pack(fill='x', padx=38, pady=(0, 6))
            ctk.CTkLabel(carte, text="%d plannings explores en parallele, %d tours"
                                     % (prof['pop_size'], prof['max_generations']),
                         text_color='#9CA3AF', anchor='w').pack(fill='x', padx=38, pady=(0, 12))

    # --------------------------------------------------------------- regles
    def _regles(self, onglet):
        ctk.CTkLabel(onglet, text=_t("Ce que le planning doit respecter"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 2))
        ctk.CTkLabel(onglet,
                     text="Obligatoire : le planning ne peut pas la violer.  "
                          "Souhaitable : l'algorithme y tend sans y etre tenu.  "
                          "Ignoree : elle sort de tous les calculs.\n"
                          "L'intitule et la description se modifient ; ce que la regle "
                          "verifie, lui, ne change pas.",
                     text_color='#6B7280').pack(anchor='w', padx=20, pady=(0, 10))
        boite = ctk.CTkScrollableFrame(onglet, height=380)
        boite.pack(fill='both', expand=True, padx=20, pady=(0, 14))
        for regle in R.CATALOGUE:
            self._ligne_regle(boite, regle)

    def _ligne_regle(self, parent, regle):
        """Une regle : son intitule, sa description, ce qu'on en exige, et le
        nombre qu'elle porte quand elle en porte un.

        « Deux surveillants par salle » etait ecrit dans l'algorithme : un
        etablissement qui en veut trois n'avait aucun moyen de le dire. Les
        regles qui reposent sur un nombre l'exposent desormais dans une case.
        """
        rid = regle['id']
        carte = ctk.CTkFrame(parent)
        carte.pack(fill='x', pady=4)

        haut = ctk.CTkFrame(carte, fg_color='transparent')
        haut.pack(fill='x', padx=12, pady=(10, 2))
        ctk.CTkLabel(haut, text=rid, font=("DejaVu Sans", 11, "bold"),
                     text_color='#9CA3AF', width=48, anchor='w').pack(side='left')
        nom = ctk.CTkEntry(haut, width=320, font=("DejaVu Sans", 12, "bold"))
        # En anglais, l'intitule LIVRE s'affiche traduit ; un intitule que
        # l'etablissement a ecrit lui-meme passe tel quel, il n'a pas d'entree.
        nom.insert(0, _t(R.intitule(self.regles, rid)))
        nom.pack(side='left')
        menu = ctk.CTkOptionMenu(haut, values=[NATURES[n] for n in regle['natures']],
                                 width=150)
        menu.set(NATURES[self.regles[rid]['nature']])
        menu.pack(side='right')

        detail = ctk.CTkEntry(carte, font=("DejaVu Sans", 11))
        detail.insert(0, _t(R.description(self.regles, rid)))
        detail.pack(fill='x', padx=(72, 12), pady=(2, 6))

        champ_valeur = None
        param = regle.get('parametre')
        if param:
            rang = ctk.CTkFrame(carte, fg_color='transparent')
            rang.pack(fill='x', padx=(72, 12), pady=(0, 10))
            champ_valeur = ctk.CTkEntry(rang, width=64, justify='center',
                                        font=("DejaVu Sans", 13, "bold"))
            champ_valeur.insert(0, str(R.valeur(self.regles, rid)))
            champ_valeur.pack(side='left')
            ctk.CTkLabel(rang, text=param['libelle'],
                         text_color='#5B6472').pack(side='left', padx=8)
            ctk.CTkLabel(rang, text="(de %d a %d)" % (param['min'], param['max']),
                         text_color='#A7AEBB').pack(side='left')
        else:
            ctk.CTkFrame(carte, height=4, fg_color='transparent').pack()

        self.choix_regles[rid] = {'menu': menu, 'nom': nom, 'detail': detail,
                                  'valeur': champ_valeur}

    # ---------------------------------------------------------------- bati

    # -------------------------------------------------------- etablissement




    # -------------------------------------------------------------- seances



    # --------------------------------------------------------------- quotas



    # ----------------------------------------------------------- generation

    # --------------------------------------------------------------- regles


    # --------------------------------------------------------------- langue
    def _langue(self, onglet):
        ctk.CTkLabel(onglet, text=_t("Langue de l'interface"),
                     font=("DejaVu Sans", 13, "bold")).pack(anchor='w', padx=20, pady=(18, 6))
        self.choix_langue = ctk.CTkOptionMenu(
            onglet, values=list(P.LANGUES.values()), width=220)
        self.choix_langue.set(P.LANGUES[self.conf['langue']])
        self.choix_langue.pack(anchor='w', padx=20)

    # ----------------------------------------------------------- validation
    def _enregistrer(self):
        seances, vus = [], set()
        for e in self.lignes_seances:
            code = e['code'].get().strip().upper()
            debut, fin = e['debut'].get().strip(), e['fin'].get().strip()
            if not code:
                continue
            if not (P._HEURE.match(debut) and P._HEURE.match(fin)):
                return self._refus("Seance %s : l'heure doit s'ecrire HH:MM." % code)
            if debut >= fin:
                return self._refus("Seance %s : la fin precede le debut." % code)
            if code in vus:
                return self._refus("Le code %s apparait deux fois." % code)
            vus.add(code)
            seances.append({'code': code, 'debut': debut, 'fin': fin})
        if not seances:
            return self._refus("Il faut au moins une seance.")
        seances.sort(key=lambda s: s['debut'])

        inverse = {v: k for k, v in NATURES.items()}
        regles = {}
        for rid, widgets in self.choix_regles.items():
            # Un champ laisse tel qu'il s'affiche n'est pas une
            # personnalisation : en anglais il contient la TRADUCTION du
            # libelle livre, et l'enregistrer figerait l'anglais dans la
            # configuration — l'outil repasse en francais et garde l'anglais.
            catalogue = R.PAR_ID[rid]
            nom_saisi = widgets['nom'].get().strip()
            detail_saisi = widgets['detail'].get().strip()
            entree = {
                'nature': inverse[widgets['menu'].get()],
                'poids': self.regles[rid]['poids'],      # inchange, invisible
                'nom': '' if nom_saisi == _t(catalogue['nom']) else nom_saisi,
                'detail': ('' if detail_saisi == _t(catalogue['detail'])
                           else detail_saisi),
            }
            champ = widgets.get('valeur')
            if champ is not None:
                param = R.PAR_ID[rid]['parametre']
                brut = champ.get().strip()
                if not brut.isdigit() or not (param['min'] <= int(brut) <= param['max']):
                    return self._refus(
                        "%s : un entier entre %d et %d."
                        % (rid, param['min'], param['max']))
                entree['valeur'] = int(brut)
            regles[rid] = entree

        quotas, vus_grades = {}, set()
        for e in self.lignes_quotas:
            grade = e['code'].get().strip().upper()
            brut = e['nombre'].get().strip()
            if not grade:
                continue
            if grade in vus_grades:
                return self._refus("Le grade %s apparait deux fois." % grade)
            if not brut.isdigit() or not (0 <= int(brut) <= 99):
                return self._refus("Grade %s : un entier entre 0 et 99." % grade)
            vus_grades.add(grade)
            quotas[grade] = int(brut)
        if not quotas:
            return self._refus("Il faut au moins un grade.")

        self.conf['quotas'] = quotas
        self.conf['generation'] = self.choix_generation.get()
        self.conf['etablissement'] = self.champ_nom.get().strip()
        self.conf['seances'] = seances
        self.conf['langue'] = {v: k for k, v in P.LANGUES.items()}[self.choix_langue.get()]
        P.enregistrer(self.conf)
        R.enregistrer(regles)

        # On ferme AVANT de prevenir l'appelant, et on le previent au tour
        # d'evenements suivant. Changer de langue rebatit la fenetre
        # principale : le faire pendant que cette fenetre-ci est encore posee
        # dessus detruisait des widgets sous les rappels en cours et faisait
        # tomber l'interpreteur.
        parent, rappel = self.master, self.au_retour
        self.grab_release()
        self.destroy()
        if rappel:
            parent.after(60, rappel)

    def _refus(self, texte):
        self.message.configure(text=texte)
