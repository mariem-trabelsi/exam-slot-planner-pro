import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

# CustomTkinter dessine les coins arrondis avec les glyphes d'une police
# dediee. Sur ce Tk, ce rendu fait tomber l'interpreteur en erreur de
# segmentation — mesure : create_aa_circle -> tkinter.create_text -> segfault,
# de maniere reproductible des que le rayon sort des valeurs deja dessinees.
# Le dessin par formes geometriques donne le meme resultat sans passer par la
# police. J'avais ecarte cette piste ce matin : mes mesures etaient alors
# faussees par des instances restees ouvertes en arriere-plan.
try:
    from customtkinter.windows.widgets.core_rendering.draw_engine import DrawEngine
    DrawEngine.preferred_drawing_method = 'circle_shapes'
except ImportError:
    pass
from traductions import t as _t
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from genetic_algorithm import run_ga_optimized, is_valid_teacher, SESSION_TIMES
from view_methods import (
    show_by_teacher, show_by_day_calendar, show_by_room,
    show_prof_responsable_details, assign_teachers_to_rooms
)
from export_methods import ExportMethods
from database import DatabaseManager

# Import des constantes
from constants import police as _police
from constants import (
    GRADE_QUOTAS, SESSION_TIMES, SESSION_ORDER, SESSION_COLORS, 
    COLORS
)

class PlanningApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(_t("Gestion des créneaux de surveillance"))
        self.geometry("1500x950")
        #self.configure(fg_color="#FAFAFA")
        self.configure(fg_color=COLORS['bg'])

        self.colors = COLORS
        # La langue est etablie AVANT la construction : les libelles sont poses
        # une fois pour toutes a la creation de chaque widget.
        import traductions as _tr
        _tr.charger_depuis_parametres()

        # Initialiser la base de données
        self.db_manager = DatabaseManager()
        
        # Thème moderne
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # La palette vient de constants.py et de nulle part ailleurs. Elle y
        # etait lue, puis aussitot ecrasee par un dictionnaire ecrit ici :
        # modifier la palette centrale n'avait aucun effet.
        self.colors = dict(COLORS)

        self.drag_data = {"item": None, "teacher": None, "source_slot": None}
        self.selected_teacher = None
        self.context_menu = None
        self.selected_teacher_for_transfer = None

        self.slots = []
        self.prof_resp_list = []
        self.teachers = {}
        self.best = None
        self.best_fitness_history = []
        self.day_to_date = {}
        self.room_assignments = {}
        self.room_names = {}
        self.quota_window = None
        self.quota_entries = {}
        self.current_view = "default"
        self.data_loaded = {
            'slots': False,
            'teachers': False,
            'wishes': False
        }
        self.view_data = []
        self.action_frame = None
        self.search_entry = None
        self.current_filter = ""
        self.data_buttons = {}
        
        self.create_ui()
    
    def create_ui(self):
        # Main container with subtle shadow effect
        main_container = ctk.CTkFrame(self, fg_color='transparent')
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Content area with cards
        content = ctk.CTkFrame(main_container, fg_color='transparent')
        content.pack(fill='both', expand=True, pady=(20, 0))
        
        # Left sidebar for actions
        self.create_app_sidebar(content)
        
        # Main content area
        self.main_content = ctk.CTkFrame(content, fg_color='transparent')
        self.main_content.pack(side='left', fill='both', expand=True, padx=(20, 0))
        
        # Data view area
        self.create_data_view()
        self.afficher_etat_vide()

        # L'en-tete est construit EN DERNIER, puis remonte visuellement.
        # Mesure : construit en premier, il fait tomber l'interpreteur en
        # erreur de segmentation 8 fois sur 8 ; construit apres la barre
        # laterale et la vue de donnees, il passe 5 fois sur 5. L'ordre est
        # le seul facteur — meme code, memes widgets.
        self.create_app_header(main_container, avant=content)

        # Pied de page
        self.create_app_footer(main_container)

        # Barre de menu
        self.creer_menu()

    def create_app_header(self, parent, avant=None):
        header = ctk.CTkFrame(parent, fg_color=self.colors['card'],
                             corner_radius=14, height=96)
        header.pack(fill='x', pady=(0, 0), **({'before': avant} if avant is not None else {}))
        header.pack_propagate(False)
        
        # Logo and title
        logo_container = ctk.CTkFrame(header, fg_color='transparent')
        logo_container.pack(side='left', padx=30, pady=20)
        
        # Logo simplifié sans image
        logo = ctk.CTkFrame(logo_container, fg_color=self.colors['primary'],
                           width=52, height=52, corner_radius=13)
        logo.pack(side='left')
        logo.pack_propagate(False)
        
        # Le logo de l'etablissement, s'il en a choisi un. Il etait enregistre
        # dans les parametres mais ne s'affichait nulle part : on le choisissait,
        # rien ne changeait, et on en concluait qu'il n'avait pas ete pris.
        self._image_logo = None
        import parametres as _p
        chemin = _p.chemin_logo(_p.charger())
        if chemin:
            try:
                from PIL import Image
                self._image_logo = ctk.CTkImage(Image.open(chemin).convert('RGBA'),
                                                size=(40, 40))
            except Exception:
                self._image_logo = None
        if self._image_logo is not None:
            self._etiquette_logo = ctk.CTkLabel(logo, image=self._image_logo, text="")
        else:
            self._etiquette_logo = ctk.CTkLabel(logo, text="📊", font=(_police(), 24),
                                                text_color="white")
        self._etiquette_logo.place(relx=0.5, rely=0.5, anchor='center')
        
        title_container = ctk.CTkFrame(logo_container, fg_color='transparent')
        title_container.pack(side='left', padx=(16, 0))
        
        ctk.CTkLabel(title_container,
                    text=_t("Gestion des Créneaux de Surveillance"),
                    font=(_police(), 13),
                    text_color=self.colors['text_secondary']).pack(anchor='w')
        
        from parametres import charger as _conf
        etablissement = _conf()['etablissement']
        # Le nom de l'etablissement passe devant : c'est lui qui identifie le
        # document qu'on imprime et la personne qui l'edite. La mention
        # generique, elle, reste discrete.
        self._libelle_etablissement = ctk.CTkLabel(
            title_container,
            text=etablissement or _t("Système de planification des examens"),
            font=(_police(), 16, "bold") if etablissement else (_police(), 13),
            text_color=self.colors['text'] if etablissement
            else self.colors['text_secondary'])
        self._libelle_etablissement.pack(anchor='w')
        
        # Action buttons (RIGHT)
        buttons_container = ctk.CTkFrame(header, fg_color='transparent')
        buttons_container.pack(side='right', padx=30, pady=20)
        
        # Export individual PDF button
        export_btn = self.btn_export_individuel = ctk.CTkButton(
            buttons_container,
            state='disabled',
            text=_t("📄 Export Individuel"),
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.colors['text_secondary'],
            hover_color=self.colors['text_secondary_light'],
            command=lambda: self.export_teachers_to_pdf()
        )
        export_btn.pack(side='left', padx=5)
        
        # Export general PDF button
        export_general_btn = self.btn_export_general = ctk.CTkButton(
            buttons_container,
            state='disabled',
            text=_t("📄 Export Général"),
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.colors['text_secondary'],  
            hover_color=self.colors['text_secondary_light'],
            command=lambda: self.export_general_pdf()
        )
        export_general_btn.pack(side='left', padx=5)

        # L'envoi des convocations, visible plutot que cache dans un menu.
        # Teinte distincte : c'est le seul geste de cet ecran qui sort de la
        # machine et qui ne se reprend pas.
        self.btn_envoi = ctk.CTkButton(
            buttons_container,
            state='disabled',
            text=_t("Envoyer par e-mail"),
            width=160,
            height=40,
            corner_radius=10,
            fg_color=self.colors['text'],
            hover_color=self.adjust_color(self.colors['text'], 25),
            # Encre sur orange : le blanc par defaut de customtkinter ne
            # contraste pas assez avec cette teinte, le libelle etait a peine
            # lisible.
            text_color='#FFFFFF',
            command=self.envoyer_convocations
        )
        self.btn_envoi.pack(side='left', padx=5)

    def creer_menu(self):
        """La barre de menu : l'acces aux parametres, sans ajouter de widget
        dans la mise en page."""
        barre = tk.Menu(self)
        fichier = tk.Menu(barre, tearoff=0)
        fichier.add_command(label=_t("Parametres..."), command=self.ouvrir_parametres)

        fichier.add_separator()
        fichier.add_command(label=_t("Quitter"), command=self.destroy)
        barre.add_cascade(label=_t("Fichier"), menu=fichier)
        self.config(menu=barre)

    def ouvrir_parametres(self):
        """Ouvre l'ecran des parametres, et recharge ce qui en depend."""
        from ecran_parametres import FenetreParametres
        FenetreParametres(self, au_retour=self.appliquer_parametres)

    def appliquer_parametres(self):
        """Reprend les horaires et l'identite apres un enregistrement.

        Les seances sont relues a chaud ; l'identite demande en revanche un
        redemarrage, car le bandeau est construit une fois pour toutes.
        """
        import parametres as _p
        import genetic_algorithm as _ga
        conf = _p.charger()
        SESSION_TIMES.clear(); SESSION_TIMES.update(_p.horaires(conf))
        SESSION_ORDER.clear(); SESSION_ORDER.update(_p.ordre(conf))
        SESSION_COLORS.clear(); SESSION_COLORS.update(_p.couleurs(conf))
        _ga.SESSION_TIMES.clear(); _ga.SESSION_TIMES.update(_p.horaires(conf))
        _ga.SESSION_ORDER.clear(); _ga.SESSION_ORDER.update(_p.ordre(conf))
        _ga._DATES.clear()   # les creneaux deja analyses portent l'ancien ordre
        _ga.recharger_regles()

        # Les quotas sont appliques en deux temps : la table des grades, puis
        # le quota porte par chaque enseignant deja charge. Sans le second,
        # changer un quota n'aurait d'effet qu'au prochain import du fichier
        # enseignants — et l'ecran annoncerait un reglage qui ne s'applique pas.
        # Le logo et le nom sont repris a chaud : ils demandaient un
        # redemarrage, ce qui donnait l'impression qu'ils n'avaient pas ete
        # enregistres.
        self.rafraichir_identite(conf)

        quotas = conf.get('quotas') or {}
        if quotas:
            GRADE_QUOTAS.clear()
            GRADE_QUOTAS.update(quotas)
            for fiche in (self.teachers or {}).values():
                fiche['quota'] = GRADE_QUOTAS.get(fiche.get('grade'), 2)
        self.show_success_message(
            "Parametres enregistres",
            self._message_parametres(conf))

    def rafraichir_identite(self, conf):
        """Reprend le logo et le nom de l'etablissement sans redemarrage."""
        import parametres as _p
        libelle = getattr(self, '_libelle_etablissement', None)
        if libelle is not None and libelle.winfo_exists():
            nom = conf.get('etablissement') or ''
            libelle.configure(
                text=nom or _t("Système de planification des examens"),
                font=(_police(), 16, "bold") if nom else (_police(), 13),
                text_color=self.colors['text'] if nom else self.colors['text_secondary'])

        pastille = getattr(self, '_etiquette_logo', None)
        if pastille is None or not pastille.winfo_exists():
            return
        chemin = _p.chemin_logo(conf)
        if chemin:
            try:
                from PIL import Image
                self._image_logo = ctk.CTkImage(Image.open(chemin).convert('RGBA'),
                                                size=(40, 40))
                pastille.configure(image=self._image_logo, text="")
                return
            except Exception:
                pass
        pastille.configure(image=None, text="📊")

    def _message_parametres(self, conf):
        """Ce qui vient d'etre applique, et ce qui attend le prochain demarrage.

        Le nom et le logo sont repris a chaud. La langue, elle, est posee a la
        creation de chaque widget : la rebattre a chaud detruisait des widgets
        sous les rappels en cours et faisait tomber l'interpreteur. On prefere
        le dire que le risquer.
        """
        import traductions as _tr
        base = _t("Les horaires, les quotas, les regles, le nom et le logo "
                  "sont pris en compte.")
        if conf.get('langue') != _tr.langue():
            return base + "\n\n" + _t("La langue s'appliquera au prochain demarrage.")
        return base

    def afficher_etat_vide(self):
        """Dit quoi faire, tant qu'il n'y a rien a montrer.

        La zone centrale s'ouvrait sur un grand rectangle blanc, sans un mot.
        Quelqu'un qui decouvre l'outil n'a aucun moyen de savoir par ou
        commencer, ni dans quel ordre.
        """
        if self.best:
            return
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ("etape", "quoi")
        self.tree["show"] = "headings"
        self.tree.heading("etape", text=_t("Etape"))
        self.tree.heading("quoi", text=_t("A faire"))
        self.tree.column("etape", width=90, anchor="center", stretch=False)
        self.tree.column("quoi", width=760, anchor="w")
        self.tree.tag_configure('fait', foreground='#047857')
        self.tree.tag_configure('reste', foreground='#6B7280')

        etapes = [
            ('slots', _t("Charger les créneaux d'examen")),
            ('teachers', _t("Charger la liste des enseignants")),
            ('wishes', _t("Charger les souhaits d'indisponibilité")),
        ]
        for n, (cle, texte) in enumerate(etapes, start=1):
            fait = self.data_loaded.get(cle, False)
            self.tree.insert('', 'end', values=("%d" % n, texte),
                             tags=('fait' if fait else 'reste'))
        pret = all(self.data_loaded.get(c, False) for c, _ in etapes[:2])
        self.tree.insert('', 'end', values=("4", _t("Générer le planning")),
                         tags=('reste' if not pret else 'fait'))
        self.tree.insert('', 'end', values=("", ""))
        self.tree.insert('', 'end', values=(
            "", _t("Les règles que le planning doit respecter se règlent dans Administration.")),
            tags=('reste'))

    def create_app_footer(self, parent):
        """Pied de page."""
        from datetime import datetime as _dt
        pied = tk.Frame(parent, bg=self.colors['bg'], height=26,
                        highlightthickness=0, bd=0)
        pied.pack(fill='x', pady=(10, 0))
        pied.pack_propagate(False)
        tk.Label(pied, text="© %d Meriem Trabelsi" % _dt.now().year,
                 bg=self.colors['bg'], fg=self.colors['text_secondary'],
                 font=('DejaVu Sans', 9)).pack(side='right', padx=6)

    def create_section(self, parent, title, top_padding):
        title = _t(title)        # idem pour les intitules de section
        ctk.CTkLabel(
            parent,
            text=title.upper(),
            font=(_police(), 10, "bold"),
            text_color=self.colors['text_secondary_light'],
            anchor='w'
        ).pack(fill='x', padx=20, pady=(top_padding, 10))
        
    def create_modern_button(self, parent, text, icon, command, color, large=False, data_key=None):
        text = _t(text)          # traduit ici : tous les boutons y passent
        height = 46 if large else 40
        font_size = 15 if large else 13
        
        # Add status indicator if this is a data loading button
        status_icon = ""
        btn_color = color
        if data_key:
            status_icon = "   ✓" if self.data_loaded.get(data_key, False) else ""
        
        btn = ctk.CTkButton(
            parent,
            text=f"{icon}  {text}{status_icon}",
            font=(_police(), font_size, "bold" if large else "normal"),
            fg_color=color,
            hover_color=self.adjust_color(color, -20),
            text_color='white',
            height=height,
            corner_radius=8,
            command=command,
            anchor='w'
        )
        btn.pack(fill='x', padx=20, pady=(0, 10))
        
        # Store button reference if it's a data button
        if data_key:
            self.data_buttons[data_key] = btn
        
        return btn

    def create_app_sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, fg_color=self.colors['card'],
                              corner_radius=14, width=300)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        
        # Section: Chargement des données
        self.create_section(sidebar, "📁 Chargement des fichiers", 30)
        
        # Charger un fichier n'est ni un danger ni une erreur : le rouge
        # d'origine faisait d'un ecran au repos un ecran en alerte. Gris tant
        # que le fichier manque, vert une fois charge — la couleur dit l'etat,
        # pas la gravite.
        self.create_modern_button(
            sidebar, "Charger Créneaux", "📊",
            self.load_slots, self.colors['text_secondary'], data_key='slots'
        )
        self.create_modern_button(
            sidebar, "Charger Enseignants", "👥",
            self.load_teachers, self.colors['text_secondary'], data_key='teachers'
        )
        self.create_modern_button(
            sidebar, "Charger Vœux", "💭",
            self.load_wishes, self.colors['text_secondary'], data_key='wishes'
        )
        self.create_modern_button(
            sidebar, "Administration", "⚙️",
            self.ouvrir_parametres, self.colors['primary']
        )

        
        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=self.colors['border']).pack(
            fill='x', padx=20, pady=20
        )
        
        # Section: Génération
        self.create_section(sidebar, "🧬 Génération du Planning", 0)
        
        self.create_modern_button(
            sidebar, "Générer Planning", "▶️",
            self.generate_planning, self.colors['success'], large=True
        )
        
        # Section: Historique
        self.create_section(sidebar, "🧬 Historique du Planning", 0)

        self.create_modern_button(
            sidebar, "Voir Historique", "▶️",
            lambda: self.db_manager.show_history(self),
            self.colors['text_secondary'], large=True
        )
        
        self.create_modern_button(
            sidebar, "Sauvegarder Historique", "💾", 
            lambda: self.db_manager.prompt_save_current_planning(self),
            self.colors['text_secondary'], large=False
        )
        
        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=self.colors['border']).pack(
            fill='x', padx=20, pady=20
        )

    def create_data_view(self):
        view_frame = ctk.CTkFrame(self.main_content, fg_color=self.colors['card'],
                                corner_radius=16)
        view_frame.pack(fill='both', expand=True)
        
        # Header with view switcher buttons
        header_container = ctk.CTkFrame(view_frame, fg_color='transparent', height=70)
        header_container.pack(fill='x', padx=25, pady=(20, 10))
        header_container.pack_propagate(False)
        
        # Title
        ctk.CTkLabel(header_container, 
                    text=_t("📋 Données"),
                    font=(_police(), 18, "bold"),
                    text_color=self.colors['text']).pack(side='left')
        
        # View switcher buttons (center)
        view_buttons_frame = ctk.CTkFrame(header_container, fg_color='transparent')
        view_buttons_frame.pack(side='left', padx=50)
        
        # Planning view button
        self.planning_view_btn = ctk.CTkButton(
            view_buttons_frame,
            text=_t("Planning"),
            width=80,
            height=40,
            corner_radius=10,
            text_color="black",
            fg_color=self.colors['primary'] if self.current_view == 'planning' else 'transparent',
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['primary'],
            command=lambda: self.switch_view('planning')
        )
        self.planning_view_btn.pack(side='left', padx=5)
        
        # Teacher view button
        self.teacher_view_btn = ctk.CTkButton(
            view_buttons_frame,
            text=_t("Par Enseignant"),
            width=100,
            height=40,
            corner_radius=10,
            text_color="black",
            fg_color=self.colors['primary'] if self.current_view == 'teacher' else 'transparent',
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['primary'],
            command=lambda: self.switch_view('teacher')
        )
        self.teacher_view_btn.pack(side='left', padx=5)
        
        # Room view button
        self.room_view_btn = ctk.CTkButton(
            view_buttons_frame,
            text=_t("Par Salle"),
            width=100,
            height=40,
            corner_radius=10,
            text_color="black",
            fg_color=self.colors['primary'] if self.current_view == 'room' else 'transparent',
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['primary'],
            command=lambda: self.switch_view('room')
        )
        self.room_view_btn.pack(side='left', padx=5)
        
        self.quality_btn = ctk.CTkButton(
            view_buttons_frame,
            text=_t("Qualité"),
            width=100,
            height=40,
            corner_radius=10,
            text_color="black",
            fg_color=self.colors['success'] if self.current_view == 'quality' else 'transparent',
            hover_color=self.colors['hover'],
            border_width=2,
            border_color=self.colors['success'],
            command=lambda: self.switch_view('quality')
        )
        self.quality_btn.pack(side='left', padx=5)
        
        # Search inputs (right side)
        self.search_frame = ctk.CTkFrame(header_container, fg_color='transparent')
        self.search_frame.pack(side='right')
        
        # Teacher search
        self.teacher_search = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=_t("🔍 Rechercher enseignant..."),
            width=150,
            height=40,
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        self.teacher_search.pack(side='left', padx=5)
        self.teacher_search.bind('<KeyRelease>', lambda e: self.filter_by_teacher())
        
        # Day search
        self.day_search = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=_t("🔍 Rechercher jour..."),
            width=150,
            height=40,
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        self.day_search.pack(side='left', padx=5)
        self.day_search.bind('<KeyRelease>', lambda e: self.filter_by_date())
        
        # Room search
        self.room_search = ctk.CTkEntry(
            self.search_frame,
            placeholder_text=_t("🔍 Rechercher salle..."),
            width=150,
            height=40,
            corner_radius=10,
            border_width=1,
            border_color=self.colors['border']
        )
        
        # Treeview with modern styling
        tree_container = ctk.CTkFrame(view_frame, fg_color='transparent')
        tree_container.pack(fill='both', expand=True, padx=25, pady=(0, 25))
        
        # Scrollbars
        tree_scroll_y = ctk.CTkScrollbar(tree_container)
        tree_scroll_y.pack(side='right', fill='y', padx=(5, 0))
        
        tree_scroll_x = ctk.CTkScrollbar(tree_container, orientation='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x', pady=(5, 0))
        
        # Style configuration for treeview
        # Le tableau occupe les trois quarts de l'ecran : c'est lui qui
        # donne son allure a l'application. Laisse au theme « clam » par
        # defaut, il portait des bordures grises, des en-tetes en relief et
        # des lignes serrees — l'aspect d'un outil des annees deux mille.
        style = ttk.Style()
        style.theme_use('clam')
        police = _police()

        style.configure("Modern.Treeview",
                        background=self.colors['card'],
                        foreground=self.colors['text'],
                        fieldbackground=self.colors['card'],
                        borderwidth=0,
                        relief='flat',
                        font=(police, 11),
                        rowheight=34)

        style.configure("Modern.Treeview.Heading",
                        background=self.colors['card'],
                        foreground=self.colors['text_secondary'],
                        borderwidth=0,
                        relief='flat',
                        padding=(10, 12),
                        font=(police, 10, "bold"))

        # Les bordures internes de « clam » se retirent par la carte de mise
        # en page, pas par une option : sans cela chaque cellule garde son
        # trait grave.
        style.layout("Modern.Treeview", [
            ('Modern.Treeview.treearea', {'sticky': 'nswe'})])

        style.map('Modern.Treeview',
                  background=[('selected', self.colors['primary'])],
                  foreground=[('selected', '#FFFFFF')])
        style.map('Modern.Treeview.Heading',
                  background=[('active', self.colors['hover'])],
                  relief=[('active', 'flat'), ('pressed', 'flat')])

        style.configure("Vertical.TScrollbar",
                        background=self.colors['border'],
                        troughcolor=self.colors['card'],
                        borderwidth=0, arrowsize=12)
        style.configure("Horizontal.TScrollbar",
                        background=self.colors['border'],
                        troughcolor=self.colors['card'],
                        borderwidth=0, arrowsize=12)

        self.tree = ttk.Treeview(
            tree_container,
            columns=("Col1", "Col2"),
            show="headings",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
            style="Modern.Treeview"
        )
        self.tree.pack(fill='both', expand=True)
        
        tree_scroll_y.configure(command=self.tree.yview)
        tree_scroll_x.configure(command=self.tree.xview)
        
        # Configure tags for colors
        self.tree.tag_configure("over_quota", background="#FEE2E2")
        self.tree.tag_configure("unassigned", background="#FEF3C7")
        self.tree.tag_configure("optimal", background="#D1FAE5")
        self.tree.tag_configure("acceptable", background="#FEF3C7")
        self.tree.tag_configure("problem", background="#FEE2E2")
        self.tree.tag_configure("optimal_light", background=self.adjust_color("#D1FAE5", 30))
        self.tree.tag_configure("acceptable_light", background=self.adjust_color("#FEF3C7", 30))
        self.tree.tag_configure("problem_light", background=self.adjust_color("#FEE2E2", 30))
        self.tree.tag_configure("header", background=self.colors['hover'], 
                            font=(_police(), 11, "bold"))
        self.tree.tag_configure("ok", background="#D1FAE5")
        self.tree.tag_configure("error", background="#FEE2E2")
        
        # Session colors for planning view
        self.tree.tag_configure('session_s1', background='#E3F2FD')
        self.tree.tag_configure('session_s2', background='#E8F5E9')
        self.tree.tag_configure('session_s3', background='#FFF3E0')
        self.tree.tag_configure('session_s4', background='#F3E5F5')
        self.tree.tag_configure('date_group', background='#D1D5DB', font=('TkDefaultFont', 10, 'bold'))
        self.tree.tag_configure('separator', background='#BDBDBD')
        
        # Update search visibility based on current view
        self.update_search_visibility()

    def switch_view(self, view_type):
        """Switch between different view types"""
        self.current_view = view_type
        
        # Update button styles
        self.planning_view_btn.configure(
            fg_color=self.colors['primary'] if view_type == 'planning' else 'transparent'
        )
        self.teacher_view_btn.configure(
            fg_color=self.colors['primary'] if view_type == 'teacher' else 'transparent'
        )
        self.room_view_btn.configure(
            fg_color=self.colors['primary'] if view_type == 'room' else 'transparent'
        )
        self.quality_btn.configure(
            fg_color=self.colors['success'] if view_type == 'quality' else 'transparent'
        )

        # Update search field visibility
        self.update_search_visibility()
        
        # Clear search fields
        self.teacher_search.delete(0, 'end')
        self.day_search.delete(0, 'end')
        if hasattr(self, 'room_search'):
            self.room_search.delete(0, 'end')
        
        # Display the appropriate view
        if view_type == 'planning':
            self.display_planning_result()
        elif view_type == 'teacher':
            self.show_by_teacher()
        elif view_type == 'room':
            self.show_by_room()
        elif view_type == 'quality':
            # Le rapport de conformite, pas l'ancien tableau de metriques.
            # Celui-ci annoncait « Score de qualite : 0 », un nombre qui ne dit
            # rien a personne, a cote de compteurs tous a zero sans qu'on sache
            # si c'etait une bonne ou une mauvaise nouvelle.
            self.afficher_conformite()

    def _remontrer(self, champ, texte):
        """Reaffiche un champ de recherche avec son texte d'aide.

        CustomTkinter ne redessine pas le placeholder apres un `pack_forget`
        suivi d'un `pack` : le champ revenait vide, sans rien pour dire ce
        qu'on y cherche.
        """
        champ.pack(side='left', padx=5)
        if not champ.get():
            champ.configure(placeholder_text=_t(texte))
            try:
                champ._activate_placeholder()
            except Exception:
                pass

    def update_search_visibility(self):
        """Show/hide search fields based on current view"""
        if hasattr(self, 'room_search'):
            self.room_search.pack_forget()
        
        if self.current_view == 'planning':
            self._remontrer(self.teacher_search, "🔍 Rechercher enseignant...")
            self._remontrer(self.day_search, "🔍 Rechercher jour...")
        elif self.current_view == 'teacher':
            self._remontrer(self.teacher_search, "🔍 Rechercher enseignant...")
            self.day_search.pack_forget()
        elif self.current_view == 'room':
            self.teacher_search.pack_forget()
            self.day_search.pack_forget()
            self._remontrer(self.room_search, "🔍 Rechercher salle...")
        elif self.current_view == "quality":
            self.day_search.pack_forget()
            self.room_search.pack_forget()
            self.teacher_search.pack_forget()

    def filter_by_teacher(self):
        """Filter the current view by teacher name/code"""
        search_term = self.teacher_search.get().lower().strip()
        
        if not search_term:
            self.switch_view(self.current_view)
            return
        
        all_items = self.tree.get_children()
        
        for item in all_items:
            values = self.tree.item(item, 'values')
            
            match = False
            for value in values:
                if search_term in str(value).lower():
                    match = True
                    break
            
            if match:
                self.tree.reattach(item, '', self.tree.index(item))
            else:
                self.tree.detach(item)
            
            children = self.tree.get_children(item)
            for child in children:
                child_values = self.tree.item(child, 'values')
                child_match = False
                for value in child_values:
                    if search_term in str(value).lower():
                        child_match = True
                        break
                
                if child_match:
                    self.tree.reattach(item, '', self.tree.index(item))
                    self.tree.item(item, open=True)

    def filter_by_date(self):
        """Filter planning view by date"""
        if self.current_view != 'planning':
            return
        
        search_term = self.day_search.get().lower().strip()
        
        if not search_term:
            self.display_planning_result()
            return
        
        all_items = self.tree.get_children()
        
        for item in all_items:
            values = self.tree.item(item, 'values')
            
            if values and search_term in str(values[0]).lower():
                self.tree.reattach(item, '', self.tree.index(item))
                self.tree.item(item, open=True)
            else:
                self.tree.detach(item)

    def adjust_color(self, hex_color, adjustment):
        """Darken or lighten a color"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, min(255, r + adjustment))
        g = max(0, min(255, g + adjustment))
        b = max(0, min(255, b + adjustment))
        return f'#{r:02x}{g:02x}{b:02x}'

    def update_button_status(self, data_key, text, icon):
        """Update button appearance when data is loaded"""
        if data_key in self.data_buttons:
            btn = self.data_buttons[data_key]
            status_icon = "   ✓" if self.data_loaded[data_key] else ""
            # `text` arrive ici dans sa forme d'origine : sans _t, le bouton
            # repassait en francais au moment ou le fichier etait charge.
            btn.configure(text=f"{icon}  {_t(text)}{status_icon}")
            btn.configure(fg_color=self.colors['success'])
            btn.configure(hover_color=self.adjust_color(self.colors['success'], -20))

    # ========== DATA LOADING METHODS ==========
    
    # Les trois imports attendent des colonnes precises. Sans controle, un
    # fichier pris par erreur dans la boite de dialogue — elle les montre tous —
    # sort une KeyError brute : l'ecran affichait « 'dateExam' », ce qui ne dit
    # ni ce qui manque ni quel fichier il fallait choisir.
    COLONNES_ATTENDUES = {
        'creneaux': ['dateExam', 'h_debut', 'h_fin', 'cod_salle'],
        'enseignants': ['nom_ens', 'prenom_ens', 'email_ens', 'grade_code_ens'],
        'voeux': ['Enseignant', 'Jour'],
    }

    @classmethod
    def verifier_colonnes(cls, df, genre, fichier):
        """Rend None si le fichier convient, sinon un message pour l'ecran."""
        attendues = cls.COLONNES_ATTENDUES[genre]
        manquantes = [c for c in attendues if c not in df.columns]
        if not manquantes:
            return None
        import os as _os
        return (
            "Ce fichier ne ressemble pas a un fichier de %s.\n\n"
            "Fichier choisi : %s\n\n"
            "Colonne%s manquante%s : %s\n\n"
            "Colonnes trouvees : %s"
        ) % (genre, _os.path.basename(fichier),
             's' if len(manquantes) > 1 else '', 's' if len(manquantes) > 1 else '',
             ', '.join(manquantes), ', '.join(str(c) for c in df.columns))

    def load_slots(self):
        file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if file:
            try:
                engine = 'openpyxl' if file.endswith('.xlsx') else 'xlrd'
                df = pd.read_excel(file, engine=engine)

                souci = self.verifier_colonnes(df, 'creneaux', file)
                if souci:
                    self.show_error_message("Fichier inattendu", souci)
                    return
               
                print(f"Colonnes disponibles: {df.columns.tolist()}")
               
                df['dateExam'] = pd.to_datetime(df['dateExam'], format='%d/%m/%Y', dayfirst=True)
                df['h_debut_time'] = df['h_debut'].str.extract(r'(\d{2}:\d{2}:\d{2})', expand=False)
                df['h_fin_time'] = df['h_fin'].str.extract(r'(\d{2}:\d{2}:\d{2})', expand=False)
               
                df['h_debut'] = pd.to_datetime(df['dateExam'].astype(str) + ' ' + df['h_debut_time'],
                                             format='%Y-%m-%d %H:%M:%S', errors='coerce')
                df['h_fin'] = pd.to_datetime(df['dateExam'].astype(str) + ' ' + df['h_fin_time'],
                                           format='%Y-%m-%d %H:%M:%S', errors='coerce')
               
                SESSION_TIMES_REV = {v: k for k, v in SESSION_TIMES.items()}
                df['session'] = df['h_debut'].dt.strftime('%H:%M').map(lambda x: SESSION_TIMES_REV.get(x, 'S1'))
                df['slot'] = df.apply(lambda row: f"{row['dateExam'].strftime('%Y-%m-%d')} {row['session']}", axis=1)
               
                # Remove duplicates
                df = df.drop_duplicates(subset=['slot', 'cod_salle'], keep='first')
               
                # Trouver la colonne prof responsable
                prof_col = None
                if 'smart_ens_code' in df.columns:
                    prof_col = 'smart_ens_code'
                elif 'enseignant' in df.columns:
                    prof_col = 'enseignant'
                else:
                    for col in df.columns:
                        if 'ens' in col.lower() or 'prof' in col.lower():
                            prof_col = col
                            break
               
                total_repartitions = len(df)
               
                # Collecter TOUTES les repartitions profs responsables
                self.prof_resp_list = []
                profs_responsables_count = 0
                if prof_col:
                    for _, row in df.iterrows():
                        if pd.notna(row[prof_col]):
                            prof_val = row[prof_col]
                            if isinstance(prof_val, float):
                                prof_code = str(int(prof_val))
                            else:
                                prof_code = str(prof_val).strip()
                            if is_valid_teacher(prof_code):
                                profs_responsables_count += 1
                                self.prof_resp_list.append({
                                    'prof_code': prof_code,
                                    'slot': row['slot'],
                                    'date_exam': row['dateExam'].strftime('%d/%m/%Y'),
                                    'h_debut': row['h_debut_time'],
                                    'h_fin': row['h_fin_time'],
                                    'type_ex': row.get('type ex', ''),
                                    'semestre': row.get('semestre', ''),
                                    'cod_salle': row['cod_salle'],
                                    'session': row['session'],
                                    'jour': row['dateExam'].strftime('%a %d/%m/%Y')
                                })
               
                # Grouper par slot et conserver TOUTES les salles par slot
                self.slots = []
                self.room_names = {}
               
                grouped = df.groupby('slot')
               
                for slot, group in grouped:
                    enseignant = ''
                    if prof_col:
                        prof_values = group[prof_col].dropna()
                        if len(prof_values) > 0:
                            prof_val = prof_values.iloc[0]
                            if isinstance(prof_val, float):
                                enseignant = str(int(prof_val))
                            else:
                                enseignant = str(prof_val)
                   
                    rooms = sorted(group['cod_salle'].unique().tolist())
                    room_count = len(rooms)
                   
                    self.slots.append((slot, {
                        'room_count': room_count,
                        'enseignant': enseignant,
                        'session': group['session'].iloc[0],
                        'room_names': rooms
                    }))
                   
                    if slot not in self.room_names:
                        self.room_names[slot] = {}
                    for room in rooms:
                        self.room_names[slot][room] = room
                   
                    self.room_assignments[slot] = {room: [] for room in rooms}
               
                unique_dates = sorted(df['dateExam'].unique())
                self.day_to_date = {str(i+1): d.strftime('%Y-%m-%d') for i, d in enumerate(unique_dates)}
                self.data_loaded['slots'] = True
                self.update_button_status('slots', "Charger Créneaux", "📊")
                self.show_success_message("✅ Succès",f"Fichier charge avec succès!\n\n"
                    f"Total lignes : {total_repartitions}\n"
                    f"Créneaux : {len(self.slots)}","400x250")

            except Exception as e:
                self.show_error_message("❌ Erreur", f"Erreur lors du chargement des créneaux:\n{str(e)}")


    def load_teachers(self):
        file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if file:
            try:
                engine = 'openpyxl' if file.endswith('.xlsx') else 'xlrd'
                df = pd.read_excel(file, engine=engine)

                souci = self.verifier_colonnes(df, 'enseignants', file)
                if souci:
                    self.show_error_message("Fichier inattendu", souci)
                    return
            
                required_columns = ['email_ens']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    self.show_error_message(
                        "❌ Erreur",
                        f"Le fichier Excel ne contient pas la colonne requise : {', '.join(missing_columns)}"
                    )
                    return
                self.teachers = {}
                counter = 0
            
                for index, row in df.iterrows():
                    participe = row.get('participe_surveillance', False) in [1, '1', True, 'true', 'True']
                
                    email = row.get('email_ens', '')
                    if not email or email in self.teachers:
                        code = f"TEACHER_{index}_{counter}"
                        counter += 1
                    else:
                        code = email
                
                    self.teachers[code] = {
                        'nom': row.get('nom_ens', ''),
                        'prenom': row.get('prenom_ens', ''),
                        'abrv': row.get('abrv_ens', ''),
                        'email': email,
                        'grade': row.get('grade_code_ens', ''),
                        'quota': GRADE_QUOTAS.get(row.get('grade_code_ens', ''), 2),  # Utilisez GRADE_QUOTAS
                        'indispo': [],
                        'wish_priority': {},
                        'participe_surveillance': participe,
                        'code_smartex_ens': str(int(row['code_smartex_ens'])) if 'code_smartex_ens' in row and not pd.isna(row['code_smartex_ens']) else ''
                    }
            
                participating = sum(1 for t in self.teachers.values() if t['participe_surveillance'])
                self.data_loaded['teachers'] = True
                self.update_button_status('teachers', "Charger Enseignants", "👥")
                self.show_success_message("✅ Succès", 
                    f"{len(self.teachers)} enseignants chargés\n({participating} participent à la surveillance)")
            except Exception as e:
                self.show_error_message("❌ Erreur", f"Erreur lors du chargement des enseignants:\n{str(e)}")

    def load_wishes(self):
        file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if file:
            if not self.day_to_date:
                self.show_error_message("❌ Erreur", "Chargez d'abord les créneaux!")
                return
            try:
                engine = 'openpyxl' if file.endswith('.xlsx') else 'xlrd'
                df = pd.read_excel(file, engine=engine)

                souci = self.verifier_colonnes(df, 'voeux', file)
                if souci:
                    self.show_error_message("Fichier inattendu", souci)
                    return
                df = df.drop_duplicates(subset=['Enseignant', 'Jour', 'Séances'], keep='first')  

                if 'ordre_arrivee' in df.columns or 'timestamp' in df.columns:
                    sort_col = 'ordre_arrivee' if 'ordre_arrivee' in df.columns else 'timestamp'
                    df = df.sort_values(sort_col)
            
                loaded_count = 0
                affected_abrvs = set()

                for idx, row in df.iterrows():
                    ens_abrv = str(row.get('Enseignant', '')).strip()

                    if not ens_abrv:
                        continue
                
                    # Trouver la clé de l'enseignant par abréviation
                    teacher_key = next((k for k, v in self.teachers.items() if v.get('abrv', '') == ens_abrv), None)
                    if not teacher_key:
                        continue  # Pas d'enseignant correspondant
                
                    if 'wish_priority' not in self.teachers[teacher_key]:
                        self.teachers[teacher_key]['wish_priority'] = {}
                
                    # Gérer les jours (assumer un seul jour par ligne)
                    jour_str = str(int(row['Jour'])) if pd.notna(row.get('Jour')) else None
                
                    # Gérer les séances (peut être multiples, séparées par virgule)
                    seance_str = str(row.get('Séances', '')).strip()
                    seances = [s.strip() for s in seance_str.split(',') if s.strip()]
                
                    if jour_str and seances:
                        date = self.day_to_date.get(jour_str)
                        if date:
                            for seance in seances:
                                slot = f"{date} {seance}"
                                if slot not in self.teachers[teacher_key]['indispo']:
                                    self.teachers[teacher_key]['indispo'].append(slot)
                                    priority = 2.0 - (idx / max(len(df), 1))
                                    self.teachers[teacher_key]['wish_priority'][slot] = priority
                                    loaded_count += 1
                            affected_abrvs.add(ens_abrv)
            
                # messagebox.showinfo("Succes",
                #                   f"{loaded_count} voeux chargés pour {len(affected_abrvs)} enseignants\n"
                #                   f"Priorités appliquées (premiers arrivés mieux protégés)")
                self.data_loaded['wishes'] = True
                self.update_button_status('wishes', "Charger Voeux", "💭")
                self.show_success_message("✅ Succès",
                        f"Voeux chargés: {loaded_count} indisponibilités\npour {len(affected_abrvs)} enseignants")
            except Exception as e:
                self.show_error_message("❌ Erreur", f"Erreur lors du chargement des voeux:\n{str(e)}")
    def configure_quotas(self):
        """Ouvre la fenêtre de configuration des quotas"""
        if self.quota_window and self.quota_window.winfo_exists():
            self.quota_window.lift()
            return
        
        self.quota_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(self.quota_window)
        self.quota_window.title("⚙️ Configuration des Quotas")
        self.quota_window.geometry("450x550")
        self.quota_window.configure(fg_color=self.colors['bg'])
        
        # Header
        header = ctk.CTkFrame(self.quota_window, fg_color=self.colors['card'],
                             corner_radius=12, height=80)
        header.pack(fill='x', padx=20, pady=20)
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, 
                    text="Configuration des Quotas par Grade",
                    font=(_police(), 18, "bold"),
                    text_color=self.colors['text']).pack(pady=25)
        
        # Scrollable frame for quotas
        scroll_frame = ctk.CTkScrollableFrame(self.quota_window, 
                                             fg_color=self.colors['card'],
                                             corner_radius=12)
        scroll_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        for grade in sorted(GRADE_QUOTAS.keys()):
            quota_card = ctk.CTkFrame(scroll_frame, fg_color=self.colors['hover'],
                                     corner_radius=10)
            quota_card.pack(fill='x', pady=5, padx=10)
            
            ctk.CTkLabel(quota_card, text=f"{grade}:", 
                        font=(_police(), 13, "bold"),
                        text_color=self.colors['text'],
                        width=80, anchor='w').pack(side='left', padx=15, pady=12)
            
            entry = ctk.CTkEntry(quota_card, width=100, height=35,
                                corner_radius=8,
                                border_width=1,
                                border_color=self.colors['border'])
            entry.insert(0, str(GRADE_QUOTAS[grade]))
            entry.pack(side='right', padx=15, pady=12)
            self.quota_entries[grade] = entry
        
        # Buttons
        button_frame = ctk.CTkFrame(self.quota_window, fg_color='transparent')
        button_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        ctk.CTkButton(button_frame, text="💾 Sauvegarder",
                     font=(_police(), 13, "bold"),
                     fg_color=self.colors['success'],
                     hover_color=self.adjust_color(self.colors['success'], -20),
                     height=45,
                     corner_radius=10,
                     command=self.save_quotas).pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ctk.CTkButton(button_frame, text="❌ Annuler",
                     font=(_police(), 13),
                     fg_color=self.colors['hover'],
                     hover_color=self.colors['border'],
                     text_color=self.colors['text'],
                     height=45,
                     corner_radius=10,
                     command=self.quota_window.destroy).pack(side='left', fill='x', expand=True)
        self.montrer_fenetre(self.quota_window)

    def save_quotas(self):
        """Sauvegarde les quotas configurés"""
        try:
            for grade, entry in self.quota_entries.items():
                quota = int(entry.get())
                if quota < 0:
                    raise ValueError(f"Quota négatif pour {grade}")
                GRADE_QUOTAS[grade] = quota
            
            for teacher in self.teachers:
                self.teachers[teacher]['quota'] = GRADE_QUOTAS.get(self.teachers[teacher]['grade'], 2)
            
            self.show_success_message("✅ Succès", "Quotas mis à jour avec succès!")
            if self.quota_window:
                self.quota_window.destroy()
        except ValueError as e:
            self.show_error_message("❌ Erreur", 
                f"Valeur invalide: {str(e)}\nLes quotas doivent être des nombres positifs.")

    def generate_planning(self):
        """Lance la generation, dans un fil separe.

        Elle tournait dans le fil principal : la fenetre de progression etait
        donc creee puis jamais peinte avant le premier retour de l'algorithme,
        et restait grise et vide a l'ecran. L'interface etait figee pendant
        toute la recherche — impossible de deplacer la fenetre, et le systeme
        la signalait comme ne repondant plus.

        Le calcul est desormais confie a un fil, et l'affichage est rafraichi
        par le fil principal, seul autorise a toucher aux widgets.
        """
        import threading
        import genetic_algorithm as _ga
        import parametres as _p

        if not self.slots or not self.teachers:
            self.show_error_message(
                "Donnees manquantes",
                "Chargez d'abord les creneaux et les enseignants.")
            return

        profil = _p.charger().get('generation', _ga.PROFIL_DEFAUT)
        reglage = _ga.PROFILS[profil]

        fen = ctk.CTkToplevel(self)
        fen.title(_t("Generation du planning"))
        fen.geometry("560x300")
        fen.resizable(False, False)
        fen.configure(fg_color=self.colors['bg'])
        fen.transient(self)
        fen.protocol("WM_DELETE_WINDOW", lambda: None)   # on ne ferme pas en cours

        carte = ctk.CTkFrame(fen, fg_color=self.colors['card'], corner_radius=14)
        carte.pack(fill='both', expand=True, padx=20, pady=20)
        ctk.CTkLabel(carte, text=_t("Recherche du meilleur planning"),
                     font=("DejaVu Sans", 16, "bold"),
                     text_color=self.colors['text']).pack(pady=(26, 4))
        ctk.CTkLabel(carte, text=_t("Mode %s") % _t(reglage['nom']).lower() + " — " + _t(reglage['detail']),
                     font=("DejaVu Sans", 11),
                     text_color=self.colors['text_secondary'],
                     wraplength=440).pack()

        barre = ctk.CTkProgressBar(carte, width=430, height=10, corner_radius=5,
                                   progress_color=self.colors['primary'])
        barre.set(0)
        barre.pack(pady=(24, 10))
        etiquette = ctk.CTkLabel(carte, text=_t("Preparation..."),
                                 font=("DejaVu Sans", 12, "bold"),
                                 text_color=self.colors['text'])
        etiquette.pack()
        detail = ctk.CTkLabel(carte, text="", font=("DejaVu Sans", 11),
                              text_color=self.colors['text_secondary'])
        detail.pack(pady=(6, 20))

        fen.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - fen.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - fen.winfo_height()) // 3
        fen.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        fen.grab_set()
        fen.update()          # peinte AVANT que le calcul commence

        import time
        depart = time.time()
        etat = {'gen': 0, 'total': reglage['max_generations'], 'score': None,
                'fini': False, 'resultat': None, 'erreur': None}

        def avancement(gen, total, score, _info, _etat):
            etat['gen'], etat['total'], etat['score'] = gen + 1, total, score

        def calculer():
            try:
                etat['resultat'] = _ga.run_ga_optimized(
                    self.slots, self.teachers, avancement, profil=profil)
            except Exception as e:            # remonte au fil principal
                etat['erreur'] = e
            finally:
                etat['fini'] = True

        fil = threading.Thread(target=calculer, daemon=True)
        fil.start()

        def rafraichir():
            ecoule = int(time.time() - depart)
            if not etat['fini']:
                barre.set(min(1.0, etat['gen'] / max(etat['total'], 1)))
                etiquette.configure(text=_t("Generation %d sur %d")
                                         % (etat['gen'], etat['total']))
                detail.configure(text=_t("%d s ecoulees%s") % (
                    ecoule,
                    "" if etat['score'] is None else _t("   ·   score %s") % format(int(etat['score']), ',d').replace(',', ' ')))
                fen.after(150, rafraichir)
                return
            fen.grab_release()
            fen.destroy()
            if etat['erreur'] is not None:
                self.show_error_message(_t("La generation a echoue"), str(etat['erreur']))
                return
            self.best, self.best_fitness_history, _raison = etat['resultat']
            self.activer_exports()
            self.display_planning_result_with_edit()
            self.show_success_message(
                _t("Planning genere"),
                _t("Mode %s, %d generations, %d secondes.") % (
                    _t(reglage['nom']).lower(), etat['gen'], ecoule)
                + "\n\n" + self.resume_conformite())

        fen.after(150, rafraichir)

    def activer_exports(self):
        """Les exports ne s'ouvrent qu'une fois un planning produit.

        Ils etaient cliquables des le demarrage et repondaient « Veuillez
        generer le planning d'abord ». Un bouton qui ne sert a rien ne doit
        pas se laisser cliquer : la personne apprend l'ordre des operations en
        voyant le bouton s'allumer, pas en lisant un refus.
        """
        for nom in ('btn_export_individuel', 'btn_export_general', 'btn_envoi'):
            bouton = getattr(self, nom, None)
            if bouton is not None:
                bouton.configure(state='normal')

    def resume_conformite(self):
        """Le verdict du planning, regle par regle.

        Un planning qui sort avec sa preuve vaut mieux qu'un score que
        personne ne sait lire : c'est ce qu'un responsable de scolarite doit
        pouvoir montrer a ses collegues quand on conteste une convocation.
        """
        import genetic_algorithm as _ga
        import regles as _R
        if not self.best:
            return ""
        verdicts = _ga.verifier_planning(self.best, self.teachers, dict(self.slots))
        self._verdicts = verdicts

        tenues = [v for v in verdicts if v['tenue']]
        manquees = [v for v in verdicts if not v['tenue']]
        lignes = []
        if not _ga.planning_conforme(verdicts):
            lignes.append(_t("ATTENTION — une regle declaree obligatoire n'est pas tenue."))
            lignes.append("")
        lignes.append(_t("%d regles sur %d sont tenues.") % (len(tenues), len(verdicts)))
        for v in manquees:
            etiquette = _t("obligatoire") if v['nature'] == _R.DURE else _t("souhaitable")
            lignes.append("")
            lignes.append("%s %s (%s) : %d infraction%s"
                          % (v['id'], _t(v['nom']), etiquette, v['infractions'],
                             's' if v['infractions'] > 1 else ''))
            for ex in v['exemples'][:2]:
                lignes.append("   · %s" % ex)
        return "\n".join(lignes)



























    def afficher_conformite(self):
        """Le verdict du planning, ce qui manque d'abord.

        L'ordre du catalogue n'est pas celui de la lecture : on parcourt ce
        tableau pour savoir ce qui ne va pas, pas pour reciter les douze
        regles. Les manquements remontent donc en tete, les obligatoires avant
        les souhaitables, et ce qui est tenu se replie en fin de liste.
        """
        import genetic_algorithm as _ga
        import regles as _R
        if not self.best:
            self.show_error_message(
                _t("Aucun planning"), _t("Generez d'abord un planning."))
            return

        verdicts = _ga.verifier_planning(self.best, self.teachers, dict(self.slots))
        self._verdicts = verdicts
        conforme = _ga.planning_conforme(verdicts)
        tenues = [v for v in verdicts if v['tenue']]
        manquees = sorted((v for v in verdicts if not v['tenue']),
                          key=lambda v: (v['nature'] != _R.DURE, -v['infractions']))

        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ("regle", "exigence", "verdict", "detail")
        self.tree["show"] = "headings"
        for col, titre, largeur, ancre in (
                ("regle", "Regle", 300, "w"), ("exigence", "Exigence", 120, "center"),
                ("verdict", "Verdict", 140, "center"), ("detail", "Detail", 460, "w")):
            self.tree.heading(col, text=_t(titre))
            self.tree.column(col, width=largeur, anchor=ancre, stretch=(col == "detail"))

        self.tree.tag_configure('tenue', foreground='#047857')
        self.tree.tag_configure('souple', foreground='#B45309')
        self.tree.tag_configure('dure', foreground='#B91C1C')
        self.tree.tag_configure('titre', font=('DejaVu Sans', 10, 'bold'))
        self.tree.tag_configure('exemple', foreground='#6B7280')

        self.tree.insert('', 'end', values=(
            _t("BILAN"), "",
            "%d / %d" % (len(tenues), len(verdicts)),
            _t("Conforme a toutes les regles obligatoires") if conforme
            else _t("UNE REGLE OBLIGATOIRE N'EST PAS TENUE")),
            tags=('titre') if conforme else ('titre', 'dure'))

        if manquees:
            self.tree.insert('', 'end', values=("", "", "", ""))
            self.tree.insert('', 'end',
                             values=(_t("A CORRIGER"), "", "", ""), tags=('titre'))
            for v in manquees:
                dure = v['nature'] == _R.DURE
                self.tree.insert('', 'end', values=(
                    "%s  %s" % (v['id'], _t(v['nom'])),
                    _t("Obligatoire") if dure else _t("Souhaitable"),
                    "%d" % v['infractions'],
                    v['exemples'][0] if v['exemples'] else ""),
                    tags=('dure' if dure else 'souple'))
                for ex in v['exemples'][1:4]:
                    self.tree.insert('', 'end', values=("", "", "", ex), tags=('exemple'))

        if tenues:
            self.tree.insert('', 'end', values=("", "", "", ""))
            self.tree.insert('', 'end', values=(_t("TENUES"), "", "", ""), tags=('titre'))
            for v in tenues:
                self.tree.insert('', 'end', values=(
                    "%s  %s" % (v['id'], _t(v['nom'])),
                    _t("Obligatoire") if v['nature'] == _R.DURE else _t("Souhaitable"),
                    _t("Tenue"), ""), tags=('tenue'))

        self.current_view = "quality"
        self.update_search_visibility()

    def display_planning_result(self):
        """Affiche le planning généré dans le treeview"""
        if not self.best:
            return
        
        # Clear existing data
        self.tree.delete(*self.tree.get_children())
        
        # Configure columns with better structure
        self.tree["columns"] = ("Date", "Session", "Heure", "Nombre", "Enseignants")
        
        # Configure column headings
        self.tree.heading("Date", text=_t("Date"))
        self.tree.heading("Session", text=_t("Session"))
        self.tree.heading("Heure", text=_t("⏰ Heure"))
        self.tree.heading("Nombre", text=_t("Nb"))
        self.tree.heading("Enseignants", text=_t("Enseignants Assignés"))
        
        # Configure column widths
        self.tree.column("Date", width=180, anchor="w", stretch=False, minwidth=180)
        self.tree.column("Session", width=80, anchor="center", stretch=False, minwidth=80)
        self.tree.column("Heure", width=80, anchor="center", stretch=False, minwidth=80)
        self.tree.column("Nombre", width=60, anchor="center", stretch=False, minwidth=60)
        self.tree.column("Enseignants", width=600, anchor="w", stretch=False, minwidth=600)
        
        # Session times mapping
        SESSION_TIMES_DISPLAY = {
            's1': '08:30',
            's2': '10:30',
            's3': '12:30',
            's4': '14:30'
        }
        
        # Day names in French
        DAY_NAMES_FR = {
            'Monday': 'Lundi',
            'Tuesday': 'Mardi',
            'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi',
            'Friday': 'Vendredi',
            'Saturday': 'Samedi',
            'Sunday': 'Dimanche'
        }
        
        # Organize data by date
        from collections import defaultdict
        planning_by_date = defaultdict(list)
        max_teacher_text_length = 0
        
        for slot in sorted(self.best.keys()):
            try:
                parts = slot.split()
                date_str = parts[0]
                session = parts[1].lower()
                
                teachers_assigned = self.best[slot]
                teacher_count = len(teachers_assigned)
                
                teacher_display = []
                for teacher_code in teachers_assigned:
                    teacher_code_str = str(teacher_code)
                    if hasattr(self, 'teachers') and teacher_code_str in self.teachers:
                        teacher_info = self.teachers[teacher_code_str]
                        nom = teacher_info.get('nom', '')
                        prenom = teacher_info.get('prenom', '')
                        if nom and prenom:
                            teacher_display.append(f"{prenom} {nom} (#{teacher_code})")
                        else:
                            teacher_display.append(f"#{teacher_code}")
                    else:
                        teacher_display.append(f"#{teacher_code}")
                
                time = SESSION_TIMES_DISPLAY.get(session, "N/A")
                
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
                    formatted_date = f"{day_name} {date_obj.strftime('%d/%m/%Y')}"
                except:
                    formatted_date = date_str
                
                planning_by_date[date_str].append({
                    'date': formatted_date,
                    'session': session.upper(),
                    'time': time,
                    'count': teacher_count,
                    'teachers': ", ".join(teacher_display),
                    'color': SESSION_COLORS.get(session, '#FFFFFF')[0]
                })
                
                teacher_text = ", ".join(teacher_display)
                if len(teacher_text) > max_teacher_text_length:
                    max_teacher_text_length = len(teacher_text)
            except Exception as e:
                teachers_assigned = [str(teacher) for teacher in self.best[slot]]
                self.tree.insert("", "end", values=(slot, "", "", len(teachers_assigned), ", ".join(teachers_assigned)))
        
        # Insert data with collapsible date groups
        for date_str in sorted(planning_by_date.keys()):
            sessions = planning_by_date[date_str]
            sessions.sort(key=lambda x: x['session'])
            
            total_teachers_day = sum(s['count'] for s in sessions)
            num_sessions = len(sessions)
            
            date_label = sessions[0]['date']
            parent = self.tree.insert(
                "", "end",
                values=(
                    f"📅 {date_label}",
                    f"{num_sessions} sessions",
                    "",
                    total_teachers_day,
                    f"{total_teachers_day} enseignants au total"
                ),
                tags=('date_group'),
                open=True
            )
            
            for session_data in sessions:
                session_tag = f"session_{session_data['session'].lower()}"
                
                self.tree.insert(
                    parent, "end",
                    values=(
                        "",
                        session_data['session'],
                        session_data['time'],
                        session_data['count'],
                        session_data['teachers']
                    ),
                    tags=(session_tag)
                )
        
        # Configure session colors
        self.tree.tag_configure('session_s1', background='#E3F2FD')
        self.tree.tag_configure('session_s2', background='#E8F5E9')
        self.tree.tag_configure('session_s3', background='#FFF3E0')
        self.tree.tag_configure('session_s4', background='#F3E5F5')
        self.tree.tag_configure('date_group', background='#D1D5DB', font=('TkDefaultFont', 10, 'bold'))
        
        calculated_width = min(max(max_teacher_text_length * 8, 600), 4000)
        self.tree.column("Enseignants", width=calculated_width, stretch=False)
        
        assign_teachers_to_rooms(self)
        self.setup_edit_mode()

    def display_planning_result_with_edit(self):
        """Affiche le planning avec possibilité d'édition"""
        if not self.best:
            return
        self.display_planning_result()
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-Button-1>", self.on_double_click)
        self.create_context_menu()

    def create_context_menu(self):
        """Crée le menu contextuel pour supprimer/déplacer un enseignant"""
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="🗑️ Supprimer cet enseignant", 
                                    command=self.delete_selected_teacher)
        self.context_menu.add_command(label="↔️ Déplacer vers...", 
                                    command=self.show_move_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Annuler", command=lambda: None)

    def show_context_menu(self, event):
        """Affiche le menu contextuel sur clic droit"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        values = self.tree.item(item, "values")
        if values and values[1]:
            self.selected_teacher = {
                'item': item,
                'slot': f"{values[0].split()[-1] if values[0] else ''} {values[1].lower()}",
                'teachers_text': values[4]
            }
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def setup_edit_mode(self):
        """Active le mode édition sur le treeview"""
        self.tree.bind("<Double-Button-1>", self.on_double_click)

    def on_double_click(self, event):
        """Gère le double-clic pour éditer la liste des enseignants"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if self.current_view != "planning":
            return
        values = self.tree.item(item, "values")
        if values and values[1]:
            parent = self.tree.parent(item)
            if parent:
                parent_values = self.tree.item(parent, "values")
                date_text = parent_values[0] if parent_values else ""
                self.open_teacher_editor(item, values, date_text)
            else:
                self.open_teacher_editor(item, values, "")

    def open_teacher_editor(self, item, values, parent_date_text):
        """Ouvre une fenêtre pour éditer la liste des enseignants d'une session"""
        editor_window = ctk.CTkToplevel(self)
        editor_window.title(_t("Editer les enseignants"))
        self.preparer_fenetre(editor_window, 800, 600)
        
        session = values[1]
        time = values[2]
        slot_key = None
        
        for sk in self.best.keys():
            parts = sk.split()
            if len(parts) >= 2:
                sk_date = parts[0]
                sk_session = parts[1].lower()
                if sk_session == session.lower():
                    try:
                        from datetime import datetime
                        date_obj = datetime.strptime(sk_date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d/%m/%Y')
                        if formatted_date in parent_date_text:
                            slot_key = sk
                            break
                    except:
                        continue
        
        header = ctk.CTkFrame(editor_window, fg_color="#1976D2", corner_radius=10)
        header.pack(fill="x", padx=20, pady=20)
        
        display_text = f"📅 {slot_key if slot_key else 'Session inconnue'}"
        ctk.CTkLabel(header, 
                    text=display_text,
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color="white").pack(pady=15)
        
        ctk.CTkLabel(editor_window,
                    text="Gérez les enseignants de cette session",
                    font=ctk.CTkFont(size=13)).pack(pady=10)
        
        list_frame = ctk.CTkFrame(editor_window, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        teachers_scroll = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        teachers_scroll.pack(fill="both", expand=True)
        
        if not slot_key:
            ctk.CTkLabel(teachers_scroll,
                        text=_t("Session introuvable"),
                        font=ctk.CTkFont(size=14),
                        text_color=self.colors['error']).pack(pady=50)
            self.montrer_fenetre(editor_window)
            return
        
        if slot_key and slot_key in self.best:
            teacher_codes = list(self.best[slot_key])
            
            if not teacher_codes:
                ctk.CTkLabel(teachers_scroll,
                            text="Aucun enseignant assigné",
                            font=ctk.CTkFont(size=14),
                            text_color="gray").pack(pady=50)
            
            for teacher_code in teacher_codes:
                teacher_frame = ctk.CTkFrame(teachers_scroll, 
                                            fg_color="#f0f0f0",
                                            corner_radius=10,
                                            border_width=2,
                                            border_color="#e0e0e0")
                teacher_frame.pack(fill="x", pady=8, padx=5)
                
                teacher_code_str = str(teacher_code)
                if teacher_code_str in self.teachers:
                    teacher_info = self.teachers[teacher_code_str]
                    nom = teacher_info.get('nom', '')
                    prenom = teacher_info.get('prenom', '')
                    grade = teacher_info.get('grade', '')
                    display_text = f"#{teacher_code} - {prenom} {nom} ({grade})"
                else:
                    display_text = f"#{teacher_code}"
                
                info_frame = ctk.CTkFrame(teacher_frame, fg_color="transparent")
                info_frame.pack(side="left", fill="x", expand=True, padx=15, pady=12)
                
                ctk.CTkLabel(info_frame,
                            text=display_text,
                            font=ctk.CTkFont(size=13, weight="bold"),
                            anchor="w").pack(side="left")
                
                buttons_frame = ctk.CTkFrame(teacher_frame, fg_color="transparent")
                buttons_frame.pack(side="right", padx=10, pady=8)
                
                transfer_btn = ctk.CTkButton(buttons_frame,
                                            text="↔️ Transférer",
                                            width=120,
                                            height=35,
                                            fg_color="#3B82F6",
                                            hover_color="#2563EB",
                                            font=ctk.CTkFont(size=12, weight="bold"),
                                            command=lambda tc=teacher_code, sk=slot_key, ew=editor_window: 
                                                self.show_transfer_destinations(tc, sk, ew))
                transfer_btn.pack(side="left", padx=5)
                
                delete_btn = ctk.CTkButton(buttons_frame,
                                        text="🗑️ Supprimer",
                                        width=120,
                                        height=35,
                                        fg_color="#EF4444",
                                        hover_color="#DC2626",
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        command=lambda tc=teacher_code, sk=slot_key, ew=editor_window: 
                                            self.remove_teacher_from_slot(tc, sk, ew))
                delete_btn.pack(side="left", padx=5)
        
        bottom_frame = ctk.CTkFrame(editor_window, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=20)
        
        close_btn = ctk.CTkButton(bottom_frame,
                                text="✅ Fermer",
                                command=editor_window.destroy,
                                width=200,
                                height=45,
                                font=ctk.CTkFont(size=14, weight="bold"),
                                fg_color="#10B981",
                                hover_color="#059669")
        close_btn.pack()
        self.montrer_fenetre(editor_window)

    def show_transfer_destinations(self, teacher_code, source_slot, editor_window):
        """Affiche la liste des sessions de destination pour transférer un enseignant"""
        self.selected_teacher_for_transfer = {
            'teacher_code': teacher_code,
            'source_slot': source_slot
        }
        
        dest_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(dest_window)
        dest_window.title("↔️ Sélectionner la destination")
        dest_window.geometry("700x600")
        dest_window.transient(editor_window)
        
        header = ctk.CTkFrame(dest_window, fg_color="#3B82F6", corner_radius=10)
        header.pack(fill="x", padx=20, pady=20)
        
        teacher_code_str = str(teacher_code)
        if teacher_code_str in self.teachers:
            teacher_info = self.teachers[teacher_code_str]
            teacher_name = f"{teacher_info.get('prenom', '')} {teacher_info.get('nom', '')}"
        else:
            teacher_name = f"Enseignant #{teacher_code}"
        
        ctk.CTkLabel(header,
                    text=f"Transférer: {teacher_name}",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color="white").pack(pady=15)
        
        ctk.CTkLabel(dest_window,
                    text="Sélectionnez la session de destination :",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 20))
        
        dest_scroll = ctk.CTkScrollableFrame(dest_window, fg_color="transparent")
        dest_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        from collections import defaultdict
        slots_by_date = defaultdict(list)
        
        for slot_key in sorted(self.best.keys()):
            if slot_key != source_slot:
                try:
                    parts = slot_key.split()
                    date = parts[0]
                    session = parts[1]
                    slots_by_date[date].append((slot_key, session))
                except:
                    continue
        
        for date in sorted(slots_by_date.keys()):
            date_frame = ctk.CTkFrame(dest_scroll, fg_color="#E5E7EB", corner_radius=8)
            date_frame.pack(fill="x", pady=(10, 5))
            
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_names_fr = {
                    'Monday': 'Lundi', 'Tuesday': 'Mardi', 'Wednesday': 'Mercredi',
                    'Thursday': 'Jeudi', 'Friday': 'Vendredi', 'Saturday': 'Samedi', 'Sunday': 'Dimanche'
                }
                day_name = day_names_fr.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
                formatted_date = f"{day_name} {date_obj.strftime('%d/%m/%Y')}"
            except:
                formatted_date = date
            
            ctk.CTkLabel(date_frame,
                        text=f"📅 {formatted_date}",
                        font=ctk.CTkFont(size=13, weight="bold"),
                        text_color="#374151").pack(pady=8, padx=15)
            
            sessions_frame = ctk.CTkFrame(dest_scroll, fg_color="transparent")
            sessions_frame.pack(fill="x", pady=(0, 5), padx=10)
            
            SESSION_TIMES_DISPLAY = {'s1': '08:30', 's2': '10:30', 's3': '12:30', 's4': '14:30'}
            
            for slot_key, session in sorted(slots_by_date[date], key=lambda x: x[1]):
                session_btn = ctk.CTkButton(
                    sessions_frame,
                    text=f"{session.upper()} - {SESSION_TIMES_DISPLAY.get(session.lower(), '')} ({len(self.best[slot_key])} enseignants)",
                    command=lambda sk=slot_key, dw=dest_window, ew=editor_window: 
                        self.show_room_selection(sk, dw, ew),
                    height=40,
                    font=ctk.CTkFont(size=13),
                    fg_color="#FFFFFF",
                    text_color="#1F2937",
                    hover_color="#F3F4F6",
                    border_width=2,
                    border_color="#D1D5DB"
                )
                session_btn.pack(fill="x", pady=3)
        
        cancel_btn = ctk.CTkButton(dest_window,
                                text="❌ Annuler",
                                command=dest_window.destroy,
                                width=200,
                                height=45,
                                font=ctk.CTkFont(size=14, weight="bold"),
                                fg_color="#6B7280",
                                hover_color="#4B5563")
        cancel_btn.pack(pady=20)
        self.montrer_fenetre(dest_window)

    def show_room_selection(self, dest_slot, dest_window, editor_window):
        """Affiche les salles disponibles pour la session de destination"""
        if not self.selected_teacher_for_transfer:
            return
        
        teacher_code = self.selected_teacher_for_transfer['teacher_code']
        
        room_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(room_window)
        room_window.title("🏫 Sélectionner la salle")
        room_window.geometry("600x500")
        room_window.transient(dest_window)
        
        header = ctk.CTkFrame(room_window, fg_color="#10B981", corner_radius=10)
        header.pack(fill="x", padx=20, pady=20)
        
        teacher_code_str = str(teacher_code)
        if teacher_code_str in self.teachers:
            teacher_info = self.teachers[teacher_code_str]
            teacher_name = f"{teacher_info.get('prenom', '')} {teacher_info.get('nom', '')}"
        else:
            teacher_name = f"Enseignant #{teacher_code}"
        
        try:
            parts = dest_slot.split()
            date_str = parts[0]
            session = parts[1].upper()
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
            slot_display = f"{formatted_date} - {session}"
        except:
            slot_display = dest_slot
        
        ctk.CTkLabel(header,
                    text=f"Destination: {slot_display}",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color="white").pack(pady=15)
        
        ctk.CTkLabel(room_window,
                    text=f"Sélectionnez une salle pour {teacher_name} :",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 20))
        
        rooms_scroll = ctk.CTkScrollableFrame(room_window, fg_color="transparent")
        rooms_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        if hasattr(self, 'room_assignments') and dest_slot in self.room_assignments:
            rooms = self.room_assignments[dest_slot]
            
            if not rooms:
                ctk.CTkLabel(rooms_scroll,
                            text="❌ Aucune salle disponible pour cette session",
                            font=ctk.CTkFont(size=14),
                            text_color="red").pack(pady=50)
            else:
                for room_name, teachers_in_room in sorted(rooms.items()):
                    room_frame = ctk.CTkFrame(rooms_scroll, 
                                            fg_color="#F9FAFB",
                                            corner_radius=10,
                                            border_width=2,
                                            border_color="#E5E7EB")
                    room_frame.pack(fill="x", pady=8)
                    
                    info_section = ctk.CTkFrame(room_frame, fg_color="transparent")
                    info_section.pack(fill="x", padx=15, pady=10)
                    
                    header_frame = ctk.CTkFrame(info_section, fg_color="transparent")
                    header_frame.pack(fill="x")
                    
                    ctk.CTkLabel(header_frame,
                                text=f"🏫 {room_name}",
                                font=ctk.CTkFont(size=15, weight="bold"),
                                text_color="#1F2937").pack(side="left")
                    
                    count_badge = ctk.CTkFrame(header_frame, 
                                            fg_color="#3B82F6" if len(teachers_in_room) == 2 
                                            else "#10B981" if len(teachers_in_room) < 4 
                                            else "#EF4444",
                                            corner_radius=12)
                    count_badge.pack(side="right")
                    
                    ctk.CTkLabel(count_badge,
                                text=f"{len(teachers_in_room)} profs",
                                font=ctk.CTkFont(size=11, weight="bold"),
                                text_color="white").pack(padx=10, pady=4)
                    
                    if teachers_in_room:
                        teachers_text = ctk.CTkTextbox(info_section, 
                                                    height=80,
                                                    fg_color="#FFFFFF",
                                                    corner_radius=8,
                                                    border_width=1,
                                                    border_color="#E5E7EB")
                        teachers_text.pack(fill="x", pady=(8, 0))
                        
                        teacher_names = []
                        for t_code in teachers_in_room:
                            t_code_str = str(t_code)
                            if t_code_str in self.teachers:
                                t_info = self.teachers[t_code_str]
                                name = f"• {t_info.get('prenom', '')} {t_info.get('nom', '')} ({t_info.get('grade', '')})"
                            else:
                                name = f"• Enseignant #{t_code}"
                            teacher_names.append(name)
                        
                        teachers_text.insert("1.0", "\n".join(teacher_names))
                        teachers_text.configure(state="disabled")
                    
                    select_btn = ctk.CTkButton(room_frame,
                                            text="✅ Sélectionner cette salle",
                                            command=lambda r=room_name: 
                                                self.transfer_teacher_to_room(dest_slot, r, room_window, dest_window, editor_window),
                                            height=40,
                                            font=ctk.CTkFont(size=13, weight="bold"),
                                            fg_color="#10B981",
                                            hover_color="#059669")
                    select_btn.pack(fill="x", padx=15, pady=(5, 10))
        else:
            ctk.CTkLabel(rooms_scroll,
                        text="❌ Aucune information de salle disponible",
                        font=ctk.CTkFont(size=14),
                        text_color="red").pack(pady=50)
        
        cancel_btn = ctk.CTkButton(room_window,
                                text="⬅️ Retour",
                                command=room_window.destroy,
                                width=200,
                                height=45,
                                font=ctk.CTkFont(size=14, weight="bold"),
                                fg_color="#6B7280",
                                hover_color="#4B5563")
        cancel_btn.pack(pady=20)
        self.montrer_fenetre(room_window)

    def transfer_teacher_to_room(self, dest_slot, dest_room, room_window, dest_window, editor_window):
        """Transfère l'enseignant vers la salle sélectionnée"""
        if not self.selected_teacher_for_transfer:
            return
        
        teacher_code = self.selected_teacher_for_transfer['teacher_code']
        source_slot = self.selected_teacher_for_transfer['source_slot']
        
        if source_slot in self.best and teacher_code in self.best[source_slot]:
            self.best[source_slot].remove(teacher_code)
            
            if hasattr(self, 'room_assignments') and source_slot in self.room_assignments:
                for room, teachers in self.room_assignments[source_slot].items():
                    if teacher_code in teachers:
                        teachers.remove(teacher_code)
                        break
            
            if dest_slot in self.best:
                self.best[dest_slot].append(teacher_code)
            else:
                self.best[dest_slot] = [teacher_code]
            
            if hasattr(self, 'room_assignments'):
                if dest_slot not in self.room_assignments:
                    self.room_assignments[dest_slot] = {}
                if dest_room not in self.room_assignments[dest_slot]:
                    self.room_assignments[dest_slot][dest_room] = []
                
                self.room_assignments[dest_slot][dest_room].append(teacher_code)
            
            teacher_code_str = str(teacher_code)
            if teacher_code_str in self.teachers:
                teacher_info = self.teachers[teacher_code_str]
                teacher_name = f"{teacher_info.get('prenom', '')} {teacher_info.get('nom', '')}"
            else:
                teacher_name = f"#{teacher_code}"
            
            self.show_success_message("✅ Transfert réussi",
                f"{teacher_name} transféré vers {dest_slot} - Salle {dest_room}")
            
            self.display_planning_result()
            
            room_window.destroy()
            dest_window.destroy()
            editor_window.destroy()
        else:
            self.show_error_message("❌ Erreur",
                "Enseignant non trouvé dans le créneau source")
        
        self.selected_teacher_for_transfer = None

    def remove_teacher_from_slot(self, teacher_code, slot_key, editor_window=None):
        """Supprime un enseignant d'un créneau"""
        if slot_key in self.best:
            if teacher_code in self.best[slot_key]:
                self.best[slot_key].remove(teacher_code)
                
                self.show_success_message("✅ Suppression réussie", 
                    f"Enseignant #{teacher_code} supprimé du créneau")
                
                self.display_planning_result()
                
                if editor_window:
                    editor_window.destroy()
            else:
                self.show_error_message("❌ Erreur", 
                    "Enseignant non trouvé dans ce créneau")

    def delete_selected_teacher(self):
        """Supprime l'enseignant sélectionné via le menu contextuel"""
        if not self.selected_teacher:
            return
        
        slot_key = self.selected_teacher['slot']
        teachers_text = self.selected_teacher['teachers_text']
        
        delete_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(delete_window)
        delete_window.title("🗑️ Supprimer un enseignant")
        delete_window.geometry("500x400")
        
        ctk.CTkLabel(delete_window,
                    text="Sélectionnez l'enseignant à supprimer :",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)
        
        teachers_frame = ctk.CTkScrollableFrame(delete_window)
        teachers_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        if slot_key in self.best:
            for teacher_code in self.best[slot_key]:
                teacher_code_str = str(teacher_code)
                if teacher_code_str in self.teachers:
                    teacher_info = self.teachers[teacher_code_str]
                    display_text = f"#{teacher_code} - {teacher_info.get('prenom', '')} {teacher_info.get('nom', '')}"
                else:
                    display_text = f"#{teacher_code}"
                
                btn = ctk.CTkButton(teachers_frame,
                                text=display_text,
                                command=lambda tc=teacher_code: [
                                    self.remove_teacher_from_slot(tc, slot_key),
                                    delete_window.destroy()
                                ])
                btn.pack(fill='x', pady=5)
        self.montrer_fenetre(delete_window)

    def show_move_dialog(self):
        """Affiche le dialogue pour déplacer un enseignant vers une autre session"""
        if not self.selected_teacher:
            return
        
        move_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(move_window)
        move_window.title("↔️ Déplacer un enseignant")
        move_window.geometry("600x500")
        
        ctk.CTkLabel(move_window,
                    text="Sélectionnez la session de destination :",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)
        
        slots_frame = ctk.CTkScrollableFrame(move_window)
        slots_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        source_slot = self.selected_teacher['slot']
        
        for slot_key in sorted(self.best.keys()):
            if slot_key != source_slot:
                slot_btn = ctk.CTkButton(slots_frame,
                                        text=slot_key,
                                        command=lambda sk=slot_key: 
                                            self.select_teacher_and_move(source_slot, sk, move_window))
                slot_btn.pack(fill='x', pady=5)
        self.montrer_fenetre(move_window)

    def select_teacher_and_move(self, source_slot, dest_slot, move_window):
        """Sélectionne l'enseignant à déplacer et effectue le déplacement"""
        move_window.destroy()
        
        select_window = ctk.CTkToplevel(self)
        self.preparer_fenetre(select_window)
        select_window.title("Sélectionner l'enseignant")
        select_window.geometry("500x400")
        
        ctk.CTkLabel(select_window,
                    text=f"Déplacer vers: {dest_slot}",
                    font=ctk.CTkFont(size=12)).pack(pady=10)
        
        ctk.CTkLabel(select_window,
                    text="Sélectionnez l'enseignant à déplacer :",
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        teachers_frame = ctk.CTkScrollableFrame(select_window)
        teachers_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        if source_slot in self.best:
            for teacher_code in self.best[source_slot]:
                teacher_code_str = str(teacher_code)
                if teacher_code_str in self.teachers:
                    teacher_info = self.teachers[teacher_code_str]
                    display_text = f"#{teacher_code} - {teacher_info.get('prenom', '')} {teacher_info.get('nom', '')}"
                else:
                    display_text = f"#{teacher_code}"
                
                btn = ctk.CTkButton(teachers_frame,
                                text=display_text,
                                command=lambda tc=teacher_code: [
                                    self.move_teacher(tc, source_slot, dest_slot),
                                    select_window.destroy()
                                ])
                btn.pack(fill='x', pady=5)
        self.montrer_fenetre(select_window)

    def move_teacher(self, teacher_code, source_slot, dest_slot):
        """Déplace un enseignant d'un créneau à un autre"""
        if source_slot in self.best and dest_slot in self.best:
            if teacher_code in self.best[source_slot]:
                self.best[source_slot].remove(teacher_code)
                self.best[dest_slot].append(teacher_code)
                
                self.show_success_message("✅ Succès",
                    f"Enseignant #{teacher_code} déplacé vers {dest_slot}")
                
                self.display_planning_result()
            else:
                self.show_error_message("❌ Erreur",
                    "Enseignant non trouvé dans le créneau source")

    def show_by_teacher(self):
        """Vue par enseignant avec email comme identifiant"""
        if not self.best:
            self.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
            return
        
        from collections import defaultdict
        self.tree.delete(*self.tree.get_children())
        
        self.tree["columns"] = ("Email", "Nom", "Grade", "Stats", "Statut", "Détails")
        
        cols = {
            "Email": {"width": 200, "text": _t("Email"), "anchor": "w"},
            "Nom": {"width": 200, "text": _t("Nom Complet"), "anchor": "w"},
            "Grade": {"width": 100, "text": _t("Grade"), "anchor": "center"},
            "Stats": {"width": 150, "text": _t("Quota/Assigné"), "anchor": "center"},
            "Statut": {"width": 120, "text": _t("Statut"), "anchor": "center"},
            "Détails": {"width": 400, "text": _t("Créneaux (cliquer pour développer)"), "anchor": "w"}
        }
        
        for col, config in cols.items():
            self.tree.heading(col, text=config["text"])
            self.tree.column(col, width=config["width"], anchor=config["anchor"])
        
        teacher_slots = defaultdict(list)
        for slot in self.best:
            for teacher in self.best[slot]:
                teacher_slots[teacher].append(slot)
        
        DAY_NAMES_FR = {
            'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mer',
            'Thursday': 'Jeu', 'Friday': 'Ven', 'Saturday': 'Sam', 'Sunday': 'Dim'
        }
        
        def format_slots_summary(slots):
            if not slots:
                return "Aucun créneau"
            
            slots_by_date = defaultdict(list)
            for slot in sorted(slots):
                try:
                    parts = slot.split()
                    date_str = parts[0]
                    session = parts[1].upper()
                    slots_by_date[date_str].append(session)
                except:
                    continue
            
            summary_parts = []
            for date_str in sorted(slots_by_date.keys()):
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), '')
                    date_short = date_obj.strftime('%d/%m')
                    sessions = sorted(slots_by_date[date_str])
                    summary_parts.append(f"{day_name} {date_short}: {', '.join(sessions)}")
                except:
                    summary_parts.append(f"{date_str}: {', '.join(sorted(slots_by_date[date_str]))}")
            
            if len(summary_parts) > 2:
                visible = " | ".join(summary_parts[:2])
                remaining = len(summary_parts) - 2
                return f"{visible} ... (+{remaining} dates)"
            else:
                return " | ".join(summary_parts)
        
        for teacher in sorted(teacher_slots.keys()):
            if teacher_slots[teacher]:
                data = self.teachers[teacher]
                num_gardes = len(teacher_slots[teacher])
                quota = data['quota']
                
                if num_gardes > quota:
                    status = "⚠️ Dépassé"
                    tag = "over_quota"
                elif num_gardes == quota:
                    status = "✅ Complet"
                    tag = "optimal"
                else:
                    status = "🟢 OK"
                    tag = "acceptable"
                
                full_name = f"{data['prenom']} {data['nom']}"
                stats = f"{num_gardes}/{quota}"
                slots_summary = format_slots_summary(teacher_slots[teacher])
                
                parent = self.tree.insert("", "end", values=(
                    teacher,
                    full_name,
                    data['grade'],
                    stats,
                    status,
                    slots_summary
                ), tags=(tag), open=False)
                
                for slot in sorted(teacher_slots[teacher]):
                    try:
                        parts = slot.split()
                        date_str = parts[0]
                        session = parts[1].upper()
                        
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
                        formatted_date = f"{day_name} {date_obj.strftime('%d/%m/%Y')}"
                        
                        session_times = {'S1': '08:30', 'S2': '10:30', 'S3': '12:30', 'S4': '14:30'}
                        time = session_times.get(session, "N/A")
                        
                        self.tree.insert(parent, "end", values=(
                            "",
                            formatted_date,
                            session,
                            time,
                            "📅 Créneau",
                            ""
                        ), tags=(tag))
                    except:
                        self.tree.insert(parent, "end", values=(
                            "", slot, "", "", "", ""
                        ))
                
                if data['indispo']:
                    unavail_summary = format_slots_summary(data['indispo'])
                    self.tree.insert(parent, "end", values=(
                        "", "🚫 Indisponibilités", "", "", "", unavail_summary
                    ), tags=("separator"))
        
        if teacher_slots:
            self.tree.insert("", "end", values=(
                "━━━━", "━━━━━━━━━━━━━━━━━━━━━", "━━━━", "━━━━━━━━", "━━━━━━━", "━━━━━━━━━━━━━━━━━━━━━"
            ), tags=("separator"))
        
        assigned_teachers = set().union(*self.best.values())
        available_teachers = {t for t in self.teachers 
                            if self.teachers[t]['participe_surveillance'] 
                            and t not in assigned_teachers}
        
        for teacher in sorted(available_teachers):
            data = self.teachers[teacher]
            full_name = f"{data['prenom']} {data['nom']}"
            
            parent = self.tree.insert("", "end", values=(
                teacher,
                full_name,
                data['grade'],
                f"0/{data['quota']}",
                "⚠️ Non assigné",
                "Aucun créneau assigné"
            ), tags=("unassigned"), open=False)
            
            if data['indispo']:
                unavail_summary = format_slots_summary(data['indispo'])
                self.tree.insert(parent, "end", values=(
                    "", "🚫 Indisponibilités", "", "", "", unavail_summary
                ), tags=("separator"))

    def show_by_room(self):
        """Vue par salle avec structure collapsible améliorée"""
        if not self.best:
            self.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
            return
        
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = ("Salle", "Stats", "Statut", "Détails")
        
        cols = {
            "Salle": {"width": 150, "text": _t("Salle"), "anchor": "center"},
            "Stats": {"width": 150, "text": _t("Créneaux"), "anchor": "center"},
            "Statut": {"width": 120, "text": _t("Statut"), "anchor": "center"},
            "Détails": {"width": 500, "text": _t("Résumé (cliquer pour développer)"), "anchor": "w"}
        }
        
        for col, config in cols.items():
            self.tree.heading(col, text=config["text"])
            self.tree.column(col, width=config["width"], anchor=config["anchor"])
        
        room_data = defaultdict(list)
        
        for slot in sorted(self.best.keys()):
            if slot in self.room_assignments:
                for room, teachers in self.room_assignments[slot].items():
                    room_data[room].append({
                        'slot': slot,
                        'teachers': teachers,
                        'nb_profs': len(teachers)
                    })
        
        DAY_NAMES_FR = {
            'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mer',
            'Thursday': 'Jeu', 'Friday': 'Ven', 'Saturday': 'Sam', 'Sunday': 'Dim'
        }
        
        def create_room_summary(assignments):
            total_slots = len(assignments)
            avg_profs = sum(a['nb_profs'] for a in assignments) / total_slots if total_slots > 0 else 0
            
            preview = []
            for assign in assignments[:2]:
                try:
                    parts = assign['slot'].split()
                    date_str = parts[0]
                    session = parts[1].upper()
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), '')
                    date_short = date_obj.strftime('%d/%m')
                    preview.append(f"{day_name} {date_short} {session}")
                except:
                    preview.append(assign['slot'])
            
            summary = " | ".join(preview)
            if total_slots > 2:
                summary += f" ... (+{total_slots - 2})"
            
            return summary
        
        for room in sorted(room_data.keys()):
            assignments = room_data[room]
            total_slots = len(assignments)
            
            total_profs = sum(a['nb_profs'] for a in assignments)
            problem_count = sum(1 for a in assignments if a['nb_profs'] > 4)
            optimal_count = sum(1 for a in assignments if a['nb_profs'] == 2)
            
            if problem_count > 0:
                status = f"⚠️ {problem_count} problème(s)"
                tag = "problem"
            elif optimal_count == total_slots:
                status = "✅ Optimal"
                tag = "optimal"
            else:
                status = "🟢 OK"
                tag = "acceptable"
            
            stats = f"{total_slots} créneaux"
            summary = create_room_summary(assignments)
            
            parent = self.tree.insert("", "end", values=(
                room,
                stats,
                status,
                summary
            ), tags=(tag), open=False)
            
            for assign in sorted(assignments, key=lambda x: x['slot']):
                try:
                    parts = assign['slot'].split()
                    date_str = parts[0]
                    session = parts[1].upper()
                    
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
                    formatted_date = f"{day_name} {date_obj.strftime('%d/%m/%Y')}"
                    
                    session_times = {'S1': '08:30', 'S2': '10:30', 'S3': '12:30', 'S4': '14:30'}
                    time = session_times.get(session, "N/A")
                    
                    nb_profs = assign['nb_profs']
                    teachers_list = []
                    for teacher_code in sorted(assign['teachers']):
                        teacher_code_str = str(teacher_code)
                        if hasattr(self, 'teachers') and teacher_code_str in self.teachers:
                            teacher_info = self.teachers[teacher_code_str]
                            nom = teacher_info.get('nom', '')
                            prenom = teacher_info.get('prenom', '')
                            if nom and prenom:
                                teachers_list.append(f"{prenom} {nom}")
                            else:
                                teachers_list.append(f"#{teacher_code}")
                        else:
                            teachers_list.append(f"#{teacher_code}")
                    
                    teachers_display = ", ".join(teachers_list)
                    
                    if nb_profs > 4:
                        child_tag = "problem_light"
                        status_icon = "⚠️"
                    elif nb_profs == 2:
                        child_tag = "optimal_light"
                        status_icon = "✅"
                    else:
                        child_tag = "acceptable_light"
                        status_icon = "🟢"
                    
                    self.tree.insert(parent, "end", values=(
                        f"{formatted_date} - {session} ({time})",
                        f"{nb_profs} profs {status_icon}",
                        "",
                        teachers_display
                    ), tags=(child_tag))
                    
                except Exception as e:
                    self.tree.insert(parent, "end", values=(
                        assign['slot'],
                        f"{assign['nb_profs']} profs",
                        "",
                        ", ".join(sorted(assign['teachers']))
                    ))

    def export_csv(self):
        """Exporte le planning en CSV"""
        if not self.best:
            self.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
            return
        
        file = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file:
            try:
                data = []
                for slot in sorted(self.best.keys()):
                    teachers_str = ", ".join([str(t) for t in self.best[slot]])
                    data.append({"Créneau": slot, "Enseignants": teachers_str})
                
                df = pd.DataFrame(data)
                df.to_csv(file, index=False, encoding='utf-8-sig')
                self.show_success_message("✅ Succès", f"Planning exporté vers:\n{file}")
            except Exception as e:
                self.show_error_message("❌ Erreur", f"Erreur lors de l'export CSV:\n{str(e)}")


    def export_teachers_to_pdf(self):
        '''Exporte les PDFs individuels pour chaque enseignant'''
        from export_methods import ExportMethods
        # Exporter n'envoie RIEN. L'envoi partait avec l'export : cliquer
        # « Export Individuel » ouvrait sans prevenir une fenetre demandant une
        # adresse et un mot de passe, et la remplir faisait partir 126
        # convocations. Produire des PDF et ecrire a 126 personnes sont deux
        # decisions, et la seconde ne se reprend pas.
        ExportMethods.export_teachers_to_pdf(self, send_emails=False)

    def envoyer_convocations(self):
        """Envoie les convocations par courriel, apres confirmation nominative."""
        from tkinter import messagebox as _mb
        if not self.best:
            self.show_error_message("Aucun planning", "Generez d'abord un planning.")
            return
        destinataires = {e for l in self.best.values() for e in set(l)
                         if (self.teachers.get(e) or {}).get('email')}
        if not destinataires:
            self.show_error_message(
                "Aucune adresse",
                "Aucun surveillant convoque n'a d'adresse e-mail renseignee.")
            return
        if not _mb.askyesno(
                "Envoyer les convocations",
                "Un courriel va partir vers %d enseignants.\n\n"
                "Cette action ne peut pas etre annulee. Continuer ?" % len(destinataires),
                parent=self, default='no', icon='warning'):
            return
        ExportMethods.export_teachers_to_pdf(self, send_emails=True)

    def export_general_pdf(self):
        '''Exporte le PDF général du planning'''
        from export_methods import ExportMethods
        ExportMethods.export_general_pdf(self)

    def show_by_teacher_wrapper(self):
        try:
            show_by_teacher(self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur affichage:\n{str(e)}")

    def show_by_day_calendar_wrapper(self):
        try:
            show_by_day_calendar(self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur affichage:\n{str(e)}")

    def show_by_room_wrapper(self):
        try:
            show_by_room(self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur affichage:\n{str(e)}")

    def show_planning_quality_wrapper(self):
        """L'onglet Qualite montre le rapport de conformite.

        Il affichait des metriques — un score, des compteurs. Un responsable de
        scolarite n'a pas besoin de savoir qu'un planning vaut 1366 points : il
        a besoin de pouvoir dire, devant un collegue qui conteste sa
        convocation, quelle regle a ete tenue et laquelle ne l'a pas ete.
        """
        try:
            self.afficher_conformite()
        except Exception as e:
            self.show_error_message("Affichage impossible", str(e))

    def show_prof_responsable_wrapper(self):
        try:
            show_prof_responsable_details(self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur affichage:\n{str(e)}")

    def preparer_fenetre(self, fenetre, largeur=None, hauteur=None):
        """Prepare une fenetre secondaire : cachee le temps d'etre batie.

        Posee a l'ecran avant d'avoir recu son contenu, une fenetre
        customtkinter s'affiche vide ou en rectangle noir — c'est ce que
        faisait l'editeur d'enseignants. On la retire, on la bat, on la
        remontre centree sur la fenetre principale.
        """
        fenetre.withdraw()
        fenetre.transient(self)
        if largeur and hauteur:
            fenetre.geometry("%dx%d" % (largeur, hauteur))
        fenetre.bind('<Escape>', lambda e: fenetre.destroy())
        return fenetre

    def montrer_fenetre(self, fenetre, modale=True):
        """Centre, affiche et, si besoin, verrouille la fenetre une fois batie."""
        fenetre.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - fenetre.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - fenetre.winfo_height()) // 4
        fenetre.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        fenetre.deiconify()
        fenetre.update()
        if modale:
            fenetre.grab_set()
        fenetre.after(60, fenetre.focus_force)

    def _boite(self, titre, message, teinte, signe):
        """Une boite de message lisible, et qu'on peut fermer.

        L'icone etait posee dans la police « Segoe UI Emoji », qui n'existe pas
        hors de Windows : il ne restait a l'ecran qu'un rectangle de couleur
        vide. Et aucune des deux boites n'avait de bouton — il fallait viser la
        croix de la fenetre.
        """
        w = ctk.CTkToplevel(self)
        w.title(titre)
        w.geometry("460x250")
        w.resizable(False, False)
        w.configure(fg_color=self.colors['bg'])
        w.transient(self)

        carte = ctk.CTkFrame(w, fg_color=self.colors['card'], corner_radius=12)
        carte.pack(fill='both', expand=True, padx=18, pady=18)

        tete = ctk.CTkFrame(carte, fg_color='transparent')
        tete.pack(fill='x', padx=22, pady=(22, 10))
        ctk.CTkLabel(tete, text=signe, font=("DejaVu Sans", 26, "bold"),
                     text_color=teinte, width=40).pack(side='left')
        # Un titre generique repete sous la barre de fenetre n'apprend rien :
        # dans ce cas la premiere ligne du message tient lieu d'intitule.
        lignes = [l for l in message.split("\n") if l.strip()]
        generique = titre.strip().lower() in ("erreur", "termine", "succes", "succès")
        intitule = lignes[0] if (generique and lignes) else titre
        corps = "\n".join(lignes[1:] if (generique and lignes) else lignes)

        ctk.CTkLabel(tete, text=intitule, font=("DejaVu Sans", 14, "bold"),
                     text_color=self.colors['text'], anchor='w',
                     wraplength=330, justify='left').pack(side='left', padx=(10, 0))

        if corps:
            ctk.CTkLabel(carte, text=corps, font=("DejaVu Sans", 12),
                         text_color=self.colors['text_secondary'], justify='left',
                         wraplength=380, anchor='w').pack(
                             fill='x', padx=22, pady=(0, 10))

        ctk.CTkButton(carte, text=_t("Fermer"), width=110, command=w.destroy).pack(
            side='bottom', pady=(0, 20))

        # La fenetre est RETIREE le temps d'etre batie, puis remontree une fois
        # peinte. Creee a la suite immediate de la destruction d'une autre
        # fenetre, elle s'affichait en rectangle noir : Tk la posait a l'ecran
        # avant d'avoir dessine son contenu.
        w.withdraw()
        w.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - w.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - w.winfo_height()) // 3
        w.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        w.deiconify()
        w.update()
        w.grab_set()
        w.bind('<Return>', lambda e: w.destroy())
        w.bind('<Escape>', lambda e: w.destroy())
        w.after(60, w.focus_force)
        return w

    def show_success_message(self, title, message, window_size="400x200"):
        return self._boite(title.lstrip("✅ ").strip() or "Termine",
                           message, self.colors['success'], "\u2713")

    def show_error_message(self, title, message):
        return self._boite(title.lstrip("❌ ").strip() or "Erreur",
                           message, self.colors['error'], "\u2715")

    def __del__(self):
        """Destructeur pour fermer la connexion à la base de données"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close_connection()

VERROU_IMPOSSIBLE = object()   # sentinelle : on n'a pas pu verrouiller, on passe


def installer_dossier_de_travail():
    """Place le dossier courant la ou l'application a le droit d'ecrire.

    Tout le code designe ses fichiers par un nom relatif — `parametres.json`,
    `regles.json`, `planning_history.db`, `assets/`, `exports/`. Lance depuis
    les sources, le dossier courant est celui du projet et tout va bien.

    Dans un executable produit par PyInstaller, deux choses changent : les
    fichiers livres avec l'application vivent dans un dossier temporaire
    (`sys._MEIPASS`) efface a la fermeture, et le dossier courant est celui
    d'ou le raccourci a ete lance — souvent `C:\Windows\System32`, ou
    l'ecriture est refusee. La configuration serait donc perdue a chaque
    fermeture, et le logo livre introuvable.

    On se place donc dans un dossier par utilisateur, et on y recopie une
    seule fois ce qui est livre en lecture seule.
    """
    if not getattr(sys, 'frozen', False):
        return
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    travail = os.path.join(base, 'ExamSlotPlanner')
    os.makedirs(travail, exist_ok=True)
    livre = os.path.join(getattr(sys, '_MEIPASS', ''), 'assets')
    if os.path.isdir(livre):
        import shutil
        cible = os.path.join(travail, 'assets')
        os.makedirs(cible, exist_ok=True)
        for nom in os.listdir(livre):
            dst = os.path.join(cible, nom)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(livre, nom), dst)
    os.chdir(travail)


def instance_unique():
    """Refuse un second lancement.

    Mesure : lancer l'application une seconde fois pendant que la premiere
    tourne fait tomber la seconde en erreur de segmentation, 3 fois sur 3,
    alors qu'un lancement seul reussit 10 fois sur 10. Les deux instances
    partagent le meme fichier de base et la meme reconstruction du cache de
    polices que customtkinter declenche a l'import.

    Un refus clair vaut mieux qu'un plantage : la personne croirait
    l'application cassee alors qu'elle est deja ouverte.
    """
    import tempfile
    # os.getuid() n'existe pas sous Windows, et le lire hors du try faisait
    # tomber le lancement en AttributeError avant meme la fenetre.
    qui = getattr(os, 'getuid', None)
    qui = qui() if qui else (os.environ.get('USERNAME') or 'poste')
    chemin = os.path.join(tempfile.gettempdir(),
                          'exam-slot-planner-%s.lock' % qui)
    try:
        verrou = open(chemin, 'w')
    except OSError:
        return VERROU_IMPOSSIBLE   # on ne sait pas verrouiller : on laisse passer
    pose = None
    try:
        import fcntl
        pose = lambda: fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        try:
            import msvcrt
            pose = lambda: msvcrt.locking(verrou.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            pass
    if pose is None:
        # Ni fcntl ni msvcrt : plutot laisser passer que refuser a tort. Un
        # `except ImportError: return None` refusait TOUT lancement sous
        # Windows, ou fcntl n'existe pas.
        return verrou
    try:
        pose()
    except OSError:
        verrou.close()
        return None                # une instance tourne deja
    try:
        verrou.write(str(os.getpid())); verrou.flush()
    except OSError:
        pass
    return verrou                  # garde le fichier ouvert : le verrou tient


def main():
    """Lance l'application.

    L'ecran de connexion a ete retire : l'outil tourne sur le poste de la
    personne qui etablit le planning, il ne sert pas plusieurs utilisateurs et
    ne garde aucune donnee personnelle au-dela du fichier de travail. Une
    authentification locale n'y protegeait rien, et c'est elle qui portait le
    logo de l'etablissement, ce qui empechait l'outil de servir ailleurs.
    """
    installer_dossier_de_travail()
    verrou = instance_unique()
    if verrou is None:
        racine = tk.Tk(); racine.withdraw()
        messagebox.showwarning(
            "Deja ouverte",
            "L'application est deja ouverte.\n\n"
            "Basculez vers sa fenetre plutot que d'en lancer une seconde.")
        racine.destroy()
        return
    PlanningApp().mainloop()


if __name__ == "__main__":
    main()
