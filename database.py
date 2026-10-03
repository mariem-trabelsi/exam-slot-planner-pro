from constants import police as _police
import sqlite3
import json
from datetime import datetime
from tkinter import messagebox
import customtkinter as ctk
from tkinter import ttk
def _poser_fenetre(fenetre, parent):
    """Place une fenetre secondaire et la rend fermable au clavier.

    Elles s'ouvraient n'importe ou a l'ecran, parfois derriere la fenetre
    principale, et seul un clic sur la croix les fermait.
    """
    fenetre.transient(parent)
    fenetre.withdraw()
    fenetre.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - fenetre.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - fenetre.winfo_height()) // 3
    fenetre.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
    fenetre.deiconify()
    fenetre.update()
    fenetre.bind('<Escape>', lambda e: fenetre.destroy())
    fenetre.after(80, fenetre.focus_force)


class DatabaseManager:
    def __init__(self, db_path='planning_history.db'):
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """Initialise la base de données SQLite"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Créer la table si elle n'existe pas
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS planning_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                planning_data TEXT NOT NULL,
                teacher_count INTEGER,
                slot_count INTEGER,
                notes TEXT
            )
        ''')
        self.conn.commit()
    
    def save_planning_to_history(self, planning_data, notes=""):
        """Sauvegarde le planning actuel dans l'historique"""
        try:
            # Calculer les statistiques
            teacher_count = len(set().union(*planning_data['best'].values()))
            slot_count = len(planning_data['best'])
            
            # Insérer dans la base de données
            self.cursor.execute('''
                INSERT INTO planning_history 
                (timestamp, planning_data, teacher_count, slot_count, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                json.dumps(planning_data),
                teacher_count,
                slot_count,
                notes
            ))
            
            self.conn.commit()
            history_id = self.cursor.lastrowid
            return True, history_id
            
        except Exception as e:
            return False, str(e)
    
    def get_all_history_records(self):
        """Récupère tous les enregistrements d'historique"""
        try:
            self.cursor.execute('''
                SELECT id, timestamp, teacher_count, 
                    slot_count, notes
                FROM planning_history 
                ORDER BY timestamp DESC
            ''')
            return True, self.cursor.fetchall()
        except Exception as e:
            return False, str(e)
    
    def get_planning_by_id(self, planning_id):
        """Récupère un planning spécifique par son ID"""
        try:
            self.cursor.execute('SELECT planning_data FROM planning_history WHERE id = ?', (planning_id,))
            result = self.cursor.fetchone()
            if result:
                return True, json.loads(result[0])
            else:
                return False, "Planning non trouvé"
        except Exception as e:
            return False, str(e)
    
    def delete_history_record(self, planning_id):
        """Supprime un enregistrement d'historique"""
        try:
            self.cursor.execute('DELETE FROM planning_history WHERE id = ?', (planning_id,))
            self.conn.commit()
            return True, "Suppression réussie"
        except Exception as e:
            return False, str(e)
    
    def count_constraint_violations(self, planning_data):
        """Compte le nombre de violations de contraintes"""
        violations = 0
        best = planning_data['best']
        teachers = planning_data['teachers']
        room_assignments = planning_data.get('room_assignments', {})
        
        if not best:
            return violations
        
        # Vérifier les quotas
        teacher_assignments = {}
        for slot in best:
            for teacher in best[slot]:
                if teacher not in teacher_assignments:
                    teacher_assignments[teacher] = 0
                teacher_assignments[teacher] += 1
        
        for teacher, count in teacher_assignments.items():
            if teacher in teachers and count > teachers[teacher]['quota']:
                violations += 1
        
        # Vérifier les salles surchargées
        for slot in room_assignments:
            for room, teachers_list in room_assignments[slot].items():
                if len(teachers_list) > 4:  # Maximum 4 profs par salle
                    violations += 1
                if len(teachers_list) < 2:  # Minimum 2 profs par salle
                    violations += 1
        
        return violations
    
    def close_connection(self):
        """Ferme la connexion à la base de données"""
        if self.conn:
            self.conn.close()

    # Méthodes d'interface utilisateur pour l'historique
    def prompt_save_current_planning(self, main_app):
        """Demande à l'utilisateur de sauvegarder le planning actuel"""
        if not main_app.best:
            main_app.show_error_message("❌ Erreur", "Aucun planning à sauvegarder!")
            return
        
        # Créer une fenêtre de dialogue pour les notes
        save_window = ctk.CTkToplevel(main_app)
        save_window.title("💾 Sauvegarder le planning")
        save_window.geometry("500x300")
        save_window.transient(main_app)
        save_window.grab_set()
        
        ctk.CTkLabel(save_window,
                    text="Ajouter une note pour ce planning:",
                    font=(_police(), 16, "bold")).pack(pady=20)
        
        notes_entry = ctk.CTkTextbox(save_window, width=400, height=100)
        notes_entry.pack(pady=10)
        notes_entry.insert("1.0", f"Planning généré le {datetime.now().strftime('%d/%m/%Y')}")
        
        def save_with_notes():
            notes = notes_entry.get("1.0", "end-1c").strip()
            self._save_planning_with_ui(main_app, notes)
            save_window.destroy()
        
        ctk.CTkButton(save_window, text="💾 Sauvegarder",
                    font=(_police(), 14, "bold"),
                    fg_color=main_app.colors['success'],
                    hover_color=main_app.adjust_color(main_app.colors['success'], -20),
                    height=45,
                    command=save_with_notes,
                    width=200).pack(pady=20)
    
    def _save_planning_with_ui(self, main_app, notes=""):
        """Sauvegarde le planning avec interface utilisateur"""
        if not main_app.best:
            main_app.show_error_message("❌ Erreur", "Aucun planning à sauvegarder!")
            return False
        
        try:
            # Préparer les données pour la sauvegarde
            planning_data = {
                'best': main_app.best,
                'teachers': main_app.teachers,
                'slots': main_app.slots,
                'room_assignments': main_app.room_assignments,
                'prof_resp_list': main_app.prof_resp_list
            }
            
            # Utiliser le DatabaseManager pour sauvegarder
            success, result = self.save_planning_to_history(planning_data, notes)
            
            if success:
                history_id = result
                main_app.show_success_message("✅ Sauvegarde réussie", 
                    f"Planning sauvegardé dans l'historique (ID: {history_id})")
                return True
            else:
                main_app.show_error_message("❌ Erreur", f"Erreur lors de la sauvegarde:\n{result}")
                return False
            
        except Exception as e:
            main_app.show_error_message("❌ Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")
            return False
    
    def show_history(self, main_app):
        """Affiche l'historique des plannings"""
        try:
            success, history_records = self.get_all_history_records()
            
            if not success:
                main_app.show_error_message("❌ Erreur", f"Erreur lors du chargement de l'historique:\n{history_records}")
                return
                
            if not history_records:
                main_app.show_error_message("📊 Historique vide", 
                    "Aucun planning sauvegardé dans l'historique.\nGénérez et sauvegardez d'abord un planning.")
                return
            
            # Créer une fenêtre pour afficher l'historique
            # Une seule fenetre d'historique a la fois. Rien ne l'empechait
            # d'etre ouverte plusieurs fois : fermer celle du dessus decouvrait
            # la suivante, identique, et le bouton Fermer avait l'air casse.
            ancienne = getattr(main_app, '_fenetre_historique', None)
            if ancienne is not None and ancienne.winfo_exists():
                ancienne.lift()
                ancienne.focus_force()
                return

            history_window = ctk.CTkToplevel(main_app)
            main_app._fenetre_historique = history_window
            history_window.title("Historique des plannings")
            history_window.geometry("1000x700")
            history_window.configure(fg_color=main_app.colors['bg'])
            _poser_fenetre(history_window, main_app)
            
            # Header
            header = ctk.CTkFrame(history_window, fg_color=main_app.colors['card'],
                                corner_radius=16, height=80)
            header.pack(fill='x', padx=20, pady=20)
            header.pack_propagate(False)
            
            ctk.CTkLabel(header, 
                        text="Historique des plannings générés",
                        font=(_police(), 20, "bold"),
                        text_color=main_app.colors['text']).pack(pady=25)
            
            # Treeview pour l'historique
            tree_frame = ctk.CTkFrame(history_window, fg_color='transparent')
            tree_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
            
            # Scrollbars
            tree_scroll_y = ctk.CTkScrollbar(tree_frame)
            tree_scroll_y.pack(side='right', fill='y')
            
            tree_scroll_x = ctk.CTkScrollbar(tree_frame, orientation='horizontal')
            tree_scroll_x.pack(side='bottom', fill='x')
            
            # Configuration du treeview
            history_tree = ttk.Treeview(
                tree_frame,
                columns=("ID", "Date", "Enseignants", "Créneaux", "Notes"),
                show="headings",
                yscrollcommand=tree_scroll_y.set,
                xscrollcommand=tree_scroll_x.set,
                height=15
            )
            
            history_tree.pack(fill='both', expand=True)
            
            tree_scroll_y.configure(command=history_tree.yview)
            tree_scroll_x.configure(command=history_tree.xview)
            
            # Configurer les colonnes
            columns_config = [
                ("ID", 60, "center"),
                ("Date", 150, "center"),
                ("Enseignants", 100, "center"),
                ("Créneaux", 100, "center"),
                ("Notes", 300, "w")
            ]
            
            for col, width, anchor in columns_config:
                history_tree.heading(col, text=col)
                history_tree.column(col, width=width, anchor=anchor)
            
            # Remplir avec les données
            for record in history_records:
                (id, timestamp, teacher_count, slot_count, notes) = record
                
                # Formater la date
                date_obj = datetime.fromisoformat(timestamp)
                formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                
                history_tree.insert("", "end", values=(
                    id, formatted_date, teacher_count, slot_count, notes or ""
                ))
            
            # Frame pour les boutons d'action
            button_frame = ctk.CTkFrame(history_window, fg_color='transparent')
            button_frame.pack(fill='x', padx=20, pady=(0, 20))
            
            ctk.CTkButton(button_frame, text="Charger ce planning",
                        font=(_police(), 13, "bold"),
                        fg_color=main_app.colors['primary'],
                        hover_color=main_app.colors['primary_hover'],
                        height=45,
                        command=lambda: self._load_selected_planning(main_app, history_tree),
                        width=200).pack(side='left', padx=(0, 10))
            
            ctk.CTkButton(button_frame, text="Supprimer",
                        font=(_police(), 13),
                        fg_color=main_app.colors['error'],
                        hover_color=main_app.adjust_color(main_app.colors['error'], -20),
                        height=45,
                        command=lambda: self._delete_selected_history(main_app, history_tree),
                        width=120).pack(side='left', padx=(0, 10))
            
            ctk.CTkButton(button_frame, text="Fermer",
                        font=(_police(), 13),
                        fg_color=main_app.colors['hover'],
                        hover_color=main_app.colors['border'],
                        text_color=main_app.colors['text'],
                        height=45,
                        command=history_window.destroy,
                        width=120).pack(side='right')
            
        except Exception as e:
            main_app.show_error_message("❌ Erreur", f"Erreur lors du chargement de l'historique:\n{str(e)}")
    
    def _load_selected_planning(self, main_app, history_tree):
        """Charge le planning sélectionné depuis l'historique"""
        selected = history_tree.selection()
        if not selected:
            main_app.show_error_message("❌ Erreur", "Veuillez sélectionner un planning dans l'historique")
            return
        
        item = selected[0]
        planning_id = history_tree.item(item, "values")[0]
        
        try:
            success, planning_data = self.get_planning_by_id(planning_id)
            
            if not success:
                main_app.show_error_message("❌ Erreur", f"Erreur lors du chargement:\n{planning_data}")
                return
            
            # Restaurer l'état de l'application
            main_app.best = planning_data['best']
            main_app.teachers = planning_data['teachers']
            main_app.slots = planning_data['slots']
            main_app.room_assignments = planning_data['room_assignments']
            main_app.prof_resp_list = planning_data['prof_resp_list']
            
            # Afficher le planning chargé
            main_app.display_planning_result()
            
            main_app.show_success_message("✅ Chargement réussi", 
                f"Planning chargé depuis l'historique (ID: {planning_id})")
            
        except Exception as e:
            main_app.show_error_message("❌ Erreur", f"Erreur lors du chargement:\n{str(e)}")

    def _delete_selected_history(self, main_app, history_tree):
        """Supprime l'entrée sélectionnée de l'historique"""
        selected = history_tree.selection()
        if not selected:
            main_app.show_error_message("❌ Erreur", "Veuillez sélectionner un planning à supprimer")
            return
        
        item = selected[0]
        planning_id = history_tree.item(item, "values")[0]
        
        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer le planning #{planning_id} ?"):
            try:
                success, message = self.delete_history_record(planning_id)
                if success:
                    history_tree.delete(item)
                    main_app.show_success_message("✅ Suppression réussie", f"Planning #{planning_id} supprimé")
                else:
                    main_app.show_error_message("❌ Erreur", f"Erreur lors de la suppression:\n{message}")
            except Exception as e:
                main_app.show_error_message("❌ Erreur", f"Erreur lors de la suppression:\n{str(e)}")