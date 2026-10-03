from constants import police as _police
import numpy as np
from datetime import datetime
import random
from collections import defaultdict
from genetic_algorithm import (
    is_valid_teacher, get_teacher_slots, check_gap_violations,
    calculate_quota_violations, fitness, SESSION_TIMES, SESSION_ORDER
)


def get_teacher_display_name(teacher_code, teachers):
    """Retourne le nom complet du prof"""
    if teacher_code not in teachers:
        return teacher_code
    t = teachers[teacher_code]
    return f"{t.get('prenom', '')} {t.get('nom', '')}".strip() or teacher_code


def assign_teachers_to_rooms(app):
    """Assigne les enseignants aux salles avec noms corrects"""
    app.room_assignments = {}
    slots_dict = {slot: data for slot, data in app.slots}
    
    for slot in app.best:
        teachers = [t for t in app.best[slot] if is_valid_teacher(t)]
        app.room_assignments[slot] = {}
        
        slot_data = slots_dict.get(slot, {})
        room_names = slot_data.get('room_names', [])
        room_count = slot_data.get('room_count', 1)
        
        if not room_names:
            room_names = [f"{i+1}" for i in range(room_count)]
        
        if not teachers:
            for room in room_names:
                app.room_assignments[slot][room] = []
            continue
        
        total_teachers = len(teachers)
        teachers_per_room = [0] * len(room_names)
        
        if total_teachers < 2 * len(room_names):
            for i in range(total_teachers):
                teachers_per_room[i % len(room_names)] += 1
        else:
            teachers_per_room = [2] * len(room_names)
            remaining = total_teachers - 2 * len(room_names)
            room_indices = list(range(len(room_names)))
            random.shuffle(room_indices)
            
            for i in room_indices:
                while teachers_per_room[i] < 4 and remaining > 0:
                    teachers_per_room[i] += 1
                    remaining -= 1
        
        random.shuffle(teachers)
        idx = 0
        for i, room in enumerate(room_names):
            num = teachers_per_room[i]
            app.room_assignments[slot][room] = teachers[idx:idx + num]
            idx += num


def check_prof_responsable_presence_simple(app):
    """
    - Reprendre TOUS les slots du fichier slots.xlsx (app.slots)
    - Pour chaque slot: si le prof responsable code smart est dans app.best = PRESENT
    - Sinon = ABSENT
    """
    results = []
    
    # Parcourir TOUTES les repartitions du fichier original (app.prof_resp_list)
    for resp in app.prof_resp_list:
        prof_resp_code = resp['prof_code']
        
        # Skip si pas de prof responsable defini
        if not prof_resp_code or not is_valid_teacher(prof_resp_code):
            continue
        
        # VERIFICATION SIMPLE: le prof est-il dans la liste des surveillants pour ce slot exact?
        valid_teachers = [t for t in app.best.get(resp['slot'], []) if is_valid_teacher(t)]
        is_present = prof_resp_code in valid_teachers
        
        nom_prof = get_teacher_display_name(prof_resp_code, app.teachers)
        email = app.teachers.get(prof_resp_code, {}).get('email', '')
        
        results.append({
            'prof_code': prof_resp_code,
            'nom': nom_prof,
            'email': email,
            'jour': resp['jour'],
            'session': resp['session'],
            'slot': resp['slot'],
            'present': is_present,
            'date_exam': resp['date_exam'],
            'h_debut': resp['h_debut'],
            'h_fin': resp['h_fin'],
            'type_ex': resp['type_ex'],
            'semestre': resp['semestre'],
            'cod_salle': resp['cod_salle']
        })
    
    return results

def show_prof_responsable_details(app):
    """Vue moderne et simplifiée des profs responsables"""
    if not app.best:
        app.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
        return
    
    # Import the check function (adjust the import based on your file structure)
    prof_resp_results = check_prof_responsable_presence_simple(app)
    
    if not prof_resp_results:
        app.show_error_message("⚠️ Info", "Aucun prof responsable défini dans les créneaux")
        return
    
    from datetime import datetime
    from collections import defaultdict
    
    app.tree.delete(*app.tree.get_children())
    app.tree["columns"] = ("Date", "Sessions", "Enseignant", "Présent")
    
    # Configure columns with modern styling
    cols = {
        "Date": {"width": 250, "text": _t("Date Examen"), "anchor": "w"},
        "Sessions": {"width": 350, "text": _t("Sessions"), "anchor": "w"},
        "Enseignant": {"width": 300, "text": _t("Enseignant Responsable"), "anchor": "w"},
        "Présent": {"width": 150, "text": _t("Statut"), "anchor": "center"}
    }
    
    for col, config in cols.items():
        app.tree.heading(col, text=config["text"])
        app.tree.column(col, width=config["width"], anchor=config["anchor"])
    
    # Group results by date and teacher
    grouped_data = defaultdict(lambda: defaultdict(list))
    
    for result in prof_resp_results:
        date_exam = result['date_exam']
        teacher_code = result.get('cod_ens', '')
        
        # Get teacher name from code
        teacher_name = result.get('nom', f"#{teacher_code}")
        if teacher_code and str(teacher_code) in app.teachers:
            teacher_name = get_teacher_display_name(teacher_code,app.teachers)
            
        grouped_data[date_exam][teacher_name].append({
            'session': result.get('session', ''),
            'h_debut': result.get('h_debut', ''),
            'salle': result.get('cod_salle', ''),
            'present': result.get('present', False)
        })
    
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
    
    # Insert grouped data
    total_entries = 0
    presents_count = 0
    absents_count = 0
    
    for date_str in sorted(grouped_data.keys()):
        # Format date with day name
        try:
            date_obj = datetime.strptime(date_str, '%d/%m/%Y')
            day_name = DAY_NAMES_FR.get(date_obj.strftime('%A'), '')
            formatted_date = f"{day_name} {date_str}"
        except:
            formatted_date = date_str
        
        # Create parent for this date
        date_parent = app.tree.insert("", "end", 
                                      values=(f"📅 {formatted_date}", "", "", ""),
                                      tags=('date_group',),
                                      open=True)
        
        for teacher_name in sorted(grouped_data[date_str].keys()):
            sessions_list = grouped_data[date_str][teacher_name]
            
            # Format sessions info
            sessions_info = []
            all_present = True
            any_absent = False
            
            for session_data in sorted(sessions_list, key=lambda x: x['h_debut']):
                session = session_data['session']
                time = session_data['h_debut'][:5] if len(session_data['h_debut']) >= 5 else session_data['h_debut']
                salle = session_data['salle']
                present = session_data['present']
                
                if present:
                    presents_count += 1
                else:
                    absents_count += 1
                    all_present = False
                    any_absent = True
                
                total_entries += 1
                
                # Format: "S1 (08:30) - Salle A101"
                session_text = f"{session} ({time})"
                if salle:
                    session_text += f" - Salle {salle}"
                sessions_info.append(session_text)
            
            sessions_display = " | ".join(sessions_info)
            
            # Determine status
            if all_present:
                status = "✅ Présent"
                tag = "present"
            elif any_absent:
                status = "❌ Absent"
                tag = "absent"
            else:
                status = "⚠️ Inconnu"
                tag = "warning"
            
            # Insert teacher row as child of date
            app.tree.insert(date_parent, "end",
                           values=("", sessions_display, teacher_name, status),
                           tags=(tag,))
    
    # Configure tag colors
    app.tree.tag_configure("date_group", background="#E5E7EB", 
                           font=(_police(), 11, "bold"))
    app.tree.tag_configure("present", background="#D1FAE5", foreground="#065F46")
    app.tree.tag_configure("absent", background="#FEE2E2", foreground="#991B1B")
    app.tree.tag_configure("warning", background="#FEF3C7", foreground="#92400E")
    
    # Calculate statistics
    taux_presence = (presents_count / total_entries * 100) if total_entries > 0 else 0
    taux_absence = (absents_count / total_entries * 100) if total_entries > 0 else 0
    
    # Update summary if exists
    if hasattr(app, 'summary_label'):
        summary_text = (f"📊 Total: {total_entries} créneaux | "
                       f"✅ {presents_count} présents ({taux_presence:.1f}%) | "
                       f"❌ {absents_count} absents ({taux_absence:.1f}%)")
        app.summary_label.configure(text=summary_text)




def show_by_teacher(app):
    """Affiche la vue par enseignant avec nom et mail, filtrée par nom si spécifié"""
    if not app.best:
        from tkinter import messagebox
        messagebox.showerror("Erreur", "Generez le planning d'abord!")
        return
    
    teacher_slots = {teacher: [] for teacher in app.teachers}
    
    for slot in app.best:
        valid_teachers = [t for t in app.best[slot] if is_valid_teacher(t)]
        for teacher in valid_teachers:
            if teacher in teacher_slots:
                teacher_slots[teacher].append(slot)
    
    data = []
    for teacher in sorted(app.teachers.keys()):
        t_data = app.teachers[teacher]
        if not t_data.get('participe_surveillance', False):
            continue
        
        num_gardes = len(teacher_slots[teacher])
        violated_wishes = [slot for slot in teacher_slots[teacher]
                          if slot in t_data.get('indispo', [])]
        voeux_status = ("VIOLE" if violated_wishes else
                       "Acceptés" if t_data.get('indispo') else "Aucun")
        tag = ("voeux_violes" if violated_wishes else 
               "voeux_ok")
        
        quota = t_data.get('quota', 0)
        if num_gardes > quota:
            tag = "over_quota"
        elif num_gardes == 0:
            tag = "unassigned"
        elif num_gardes == quota:
            tag = "quota_respected"
        
        nom_complet = f"{t_data.get('prenom', '')} {t_data.get('nom', '')}".strip()
        email = t_data.get('email', '')
        
        # Ajouter un indicateur de succès (✓) si le quota est respecté
        assigne_display = f"{num_gardes} ✓" if num_gardes == quota and num_gardes > 0 else str(num_gardes)
        
        # Filtrer par nom si app.current_filter est non vide
        if app.current_filter and app.current_filter.lower() not in nom_complet.lower():
            continue
        
        data.append((
            teacher,
            nom_complet,
            email,
            t_data.get('grade', ''),
            quota,
            assigne_display,
            ", ".join(sorted(teacher_slots[teacher])) if teacher_slots[teacher] else "Non assigne",
            voeux_status
        ))
    
    app.view_data = data
    app.tree.delete(*app.tree.get_children())
    #app.tree["columns"] = ("Code", "Nom", "Email", "Grade", "Quota",
     #                     "Assigne", "Creneaux", "Statut des vœux")
    app.tree["columns"] = ("Email", "Nom", "Grade", "Quota",
                          "Assigne", "Creneaux", "Statut des vœux")
    
    
    cols = {
        #"Code": 60,
        "Email": 200,
        "Nom": 150,
        
        "Grade": 60,
        "Quota": 60,
        "Assigne": 80,
        "Creneaux": 250,
        "Statut des vœux": 100
    }
    
    for col, width in cols.items():
        app.tree.heading(col, text=col)
        app.tree.column(col, width=width)
    
    app.populate_flat_view()
    
    app.tree.tag_configure("over_quota", background="#ffcccc")
    app.tree.tag_configure("unassigned", background="#ffffcc")
    app.tree.tag_configure("voeux_violes", background="#ff9999")
    app.tree.tag_configure("voeux_ok", background="#ccffcc")
    app.tree.tag_configure("quota_respected", background="#ccffcc")
    
    app.current_view = "teacher"
    app.view_type_label.config(text="Vue actuelle: Par Enseignant")
    app.configure_action_buttons()









def show_by_day_calendar(app):
    """Affiche la vue calendrier par jour avec salles reelles"""
    if not app.best:
        from tkinter import messagebox
        messagebox.showerror("Erreur", "Generez le planning d'abord!")
        return
    
    if not hasattr(app, 'room_assignments') or not app.room_assignments:
        assign_teachers_to_rooms(app)
    
    app.tree.delete(*app.tree.get_children())
    app.tree["columns"] = ("Session/Salle", "Enseignants")
    app.tree.heading("Session/Salle", text=_t("Session / Salle"))
    app.tree.heading("Enseignants", text=_t("Enseignants"))
    app.tree.column("Session/Salle", width=250)
    app.tree.column("Enseignants", width=800)
    
    days_data = {}
    for slot in sorted(app.best.keys()):
        try:
            date_str, session = slot.split()
            if date_str not in days_data:
                days_data[date_str] = {s: {} for s in ["S1", "S2", "S3", "S4"]}
            
            for room, teachers in app.room_assignments[slot].items():
                valid_teachers = [t for t in teachers if is_valid_teacher(t)]
                teacher_names = [get_teacher_display_name(t, app.teachers) for t in valid_teachers]
                days_data[date_str][session][room] = teacher_names
        except:
            continue
    
    hide_rooms = app.hide_rooms_var.get()
    for date_str in sorted(days_data.keys()):
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_display = date_obj.strftime('%d/%m/%Y (%A)')
        except:
            continue
        
        day_iid = None
        for session in ["S1", "S2", "S3", "S4"]:
            session_display = f"{session} ({SESSION_TIMES[session]})"
            session_iid = None
            
            if hide_rooms:
                all_teachers = []
                for room_teachers in days_data[date_str][session].values():
                    all_teachers.extend(room_teachers)
                
                teachers_str = ", ".join(sorted(set(all_teachers))) if all_teachers else "-"
                
                if app.current_filter.lower() in teachers_str.lower() or not app.current_filter:
                    if not day_iid:
                        day_iid = app.tree.insert("", "end", values=(date_display, ""),
                                                 open=True, tags=("day_header",))
                    session_iid = app.tree.insert(day_iid, "end", values=(session_display, teachers_str),
                                                 open=True, tags=("session_header",))
            else:
                for room in sorted(days_data[date_str][session].keys()):
                    teachers = days_data[date_str][session][room]
                    teachers_str = ", ".join(sorted(teachers)) if teachers else "-"
                    room_display = f"Salle {room}"
                    search_text = (room_display + " " + teachers_str).lower()
                    
                    if app.current_filter.lower() in search_text or not app.current_filter:
                        if not day_iid:
                            day_iid = app.tree.insert("", "end", values=(date_display, ""),
                                                     open=True, tags=("day_header",))
                        if not session_iid:
                            session_iid = app.tree.insert(day_iid, "end",
                                                         values=(session_display, ""),
                                                         open=True, tags=("session_header",))
                        app.tree.insert(session_iid, "end", values=(room_display, teachers_str),
                                       tags=("room_item",))
    
    app.tree.tag_configure("day_header", font=("Arial", 14, "bold"), background="#e3f2fd")
    app.tree.tag_configure("session_header", font=("Arial", 12, "bold"), background="#f0f8ff")
    app.tree.tag_configure("room_item", font=("Arial", 10))
    
    app.current_view = "calendar"
    app.view_type_label.config(text="Vue actuelle: Calendrier par Jour")
    app.configure_action_buttons()


def show_by_room(app):
    """Affiche la vue par salle avec noms reels"""
    if not app.best:
        from tkinter import messagebox
        messagebox.showerror("Erreur", "Generez le planning d'abord!")
        return
    
    if not hasattr(app, 'room_assignments') or not app.room_assignments:
        assign_teachers_to_rooms(app)
    
    app.tree.delete(*app.tree.get_children())
    app.tree["columns"] = ("Creneau", "Salle", "Nb_Profs", "Enseignants")
    app.tree.heading("Creneau", text=_t("Creneau"))
    app.tree.heading("Salle", text=_t("Salle"))
    app.tree.heading("Nb_Profs", text=_t("Nb Profs"))
    app.tree.heading("Enseignants", text=_t("Enseignants"))
    app.tree.column("Creneau", width=200)
    app.tree.column("Salle", width=100)
    app.tree.column("Nb_Profs", width=100)
    app.tree.column("Enseignants", width=600)
    
    data = []
    for slot in sorted(app.best.keys()):
        for room in sorted(app.room_assignments[slot].keys()):
            teachers = app.room_assignments[slot][room]
            valid_teachers = [t for t in teachers if is_valid_teacher(t)]
            teacher_names = [get_teacher_display_name(t, app.teachers) for t in valid_teachers]
            nb = len(valid_teachers)
            tag = "optimal" if nb == 2 else "acceptable" if nb <= 4 else "problem"
            data.append((slot, room, nb, ", ".join(sorted(teacher_names)), tag))
    
    app.view_data = data
    app.populate_flat_view()
    
    app.tree.tag_configure("optimal", background="#e6ce81")
    app.tree.tag_configure("acceptable", background="#ffffcc")
    app.tree.tag_configure("problem", background="#e98484")
    
    app.current_view = "room"
    app.view_type_label.config(text="Vue actuelle: Par Salle")
    app.configure_action_buttons()

def show_planning_quality_with_prof_resp(app):
    """Affiche la qualité du planning avec UI moderne et améliorée"""
    if not app.best:
        app.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
        return
    
    app.tree.delete(*app.tree.get_children())
    app.tree["columns"] = ("Métrique", "Valeur", "Statut", "Détails")
    
    # Configure columns
    cols = {
        "Métrique": {"width": 300, "anchor": "w"},
        "Valeur": {"width": 120, "anchor": "center"},
        "Statut": {"width": 150, "anchor": "center"},
        "Détails": {"width": 350, "anchor": "w"}
    }
    
    for col, config in cols.items():
        app.tree.heading(col, text=col)
        app.tree.column(col, width=config["width"], anchor=config["anchor"])
    
    # Calculate metrics
    counts = defaultdict(int)
    for slot in app.best:
        for teacher in app.best[slot]:
            counts[teacher] += 1
    
    # Unassigned teachers
    assigned_teachers = set(counts.keys())
    eligible_teachers = {t for t, data in app.teachers.items() 
                        if data.get('participe_surveillance', False)}
    unassigned_teachers = eligible_teachers - assigned_teachers
    
    # Quota violations
    total_excess = 0
    quota_violations_count = 0
    over_quota_list = []
    
    for teacher, count in counts.items():
        quota = app.teachers[teacher].get('quota', 0)
        if count > quota:
            excess = count - quota
            total_excess += excess
            quota_violations_count += 1
            teacher_name = f"{app.teachers[teacher].get('prenom', '')} {app.teachers[teacher].get('nom', '')}"
            over_quota_list.append(f"{teacher_name} (+{excess})")
    
    # Constraint violations
    violations = {
        'min_profs': 0,
        'max_profs': 0,
        'duplicates': 0,
        'voeux_violes': 0,
        'voeux_prioritaires_violes': 0
    }
    
    # Check each slot
    for slot in app.best:
        teachers_in_slot = app.best[slot]
        unique_teachers = len(set(teachers_in_slot))
        
        # Get room count for this slot
        room_count = 1  # Default
        if hasattr(app, 'room_assignments') and slot in app.room_assignments:
            room_count = len(app.room_assignments[slot])
        
        min_needed = 2 * room_count
        max_needed = 4 * room_count
        
        if unique_teachers < min_needed:
            violations['min_profs'] += (min_needed - unique_teachers)
        if unique_teachers > max_needed:
            violations['max_profs'] += (unique_teachers - max_needed)
        if len(teachers_in_slot) != unique_teachers:
            violations['duplicates'] += (len(teachers_in_slot) - unique_teachers)
        
        # Check unavailability
        for teacher in teachers_in_slot:
            teacher_str = str(teacher)
            if teacher_str in app.teachers:
                indispo = app.teachers[teacher_str].get('indispo', [])
                if slot in indispo:
                    violations['voeux_violes'] += 1
    
    # Teacher distribution by days
    teacher_days = defaultdict(set)
    for slot in app.best:
        date = slot.split()[0]
        for teacher in app.best[slot]:
            teacher_days[teacher].add(date)
    
    day_distribution = defaultdict(int)
    for teacher, days in teacher_days.items():
        day_distribution[len(days)] += 1
    
    # Total exam days
    total_exam_days = len(set(slot.split()[0] for slot in app.best))
    
    # Grade equity
    grade_stats = {}
    for grade in set(t.get('grade', '') for t in app.teachers.values() 
                    if t.get('participe_surveillance', False) and t.get('grade')):
        grade_counts = [counts.get(e, 0) for e in app.teachers
                       if app.teachers[e].get('grade') == grade 
                       and app.teachers[e].get('participe_surveillance', False)]
        if grade_counts:
            grade_stats[grade] = {
                'min': min(grade_counts),
                'max': max(grade_counts),
                'avg': np.mean(grade_counts),
                'std': np.std(grade_counts)
            }
    
    # Calculate global score (simplified)
    global_score = 0
    global_score -= violations['min_profs'] * 100
    global_score -= violations['max_profs'] * 50
    global_score -= violations['duplicates'] * 75
    global_score -= violations['voeux_violes'] * 20
    global_score -= total_excess * 30
    global_score -= len(unassigned_teachers) * 40
    
    # Build tree data
    def insert_section(title, tag="header"):
        """Insert a section header"""
        parent = app.tree.insert("", "end", values=(title, "", "", ""), 
                                 tags=(tag,), open=True)
        return parent
    
    def insert_metric(parent, metric, value, status, details="", tag=""):
        """Insert a metric row"""
        app.tree.insert(parent, "end", values=(metric, value, status, details), 
                        tags=(tag,))
    
    # === SCORE GLOBAL ===
    quality = "✅ Excellent" if global_score > -100 else "🟡 Acceptable" if global_score > -500 else "⚠️ À améliorer"
    quality_tag = "optimal" if global_score > -100 else "acceptable" if global_score > -500 else "problem"
    
    parent = insert_section("📊 SCORE GLOBAL")
    insert_metric(parent, "Score de qualité", f"{global_score:.0f}", quality, "", quality_tag)
    
    # === CONTRAINTES RIGIDES ===
    parent = insert_section("🔒 CONTRAINTES RIGIDES")
    
    # Min profs
    status = "✅ OK" if violations['min_profs'] == 0 else f"❌ {violations['min_profs']} violation(s)"
    tag = "optimal" if violations['min_profs'] == 0 else "problem"
    insert_metric(parent, "Minimum 2 profs/salle", violations['min_profs'], status, "", tag)
    
    # Max profs
    status = "✅ OK" if violations['max_profs'] == 0 else f"⚠️ {violations['max_profs']} violation(s)"
    tag = "optimal" if violations['max_profs'] == 0 else "problem"
    insert_metric(parent, "Maximum 4 profs/salle", violations['max_profs'], status, "", tag)
    
    # Duplicates
    status = "✅ OK" if violations['duplicates'] == 0 else f"❌ {violations['duplicates']} doublon(s)"
    tag = "optimal" if violations['duplicates'] == 0 else "problem"
    insert_metric(parent, "Doublons", violations['duplicates'], status, "", tag)
    
    # Quota violations
    status = "✅ OK" if total_excess == 0 else f"⚠️ {quota_violations_count} enseignant(s)"
    tag = "optimal" if total_excess == 0 else "problem"
    details = ", ".join(over_quota_list[:3]) if over_quota_list else ""
    if len(over_quota_list) > 3:
        details += f" ... (+{len(over_quota_list)-3})"
    insert_metric(parent, "Dépassements de quota", total_excess, status, details, tag)
    
    # Unassigned teachers
    status = "✅ Tous assignés" if not unassigned_teachers else f"⚠️ {len(unassigned_teachers)} non assigné(s)"
    tag = "optimal" if not unassigned_teachers else "acceptable"
    insert_metric(parent, "Enseignants non assignés", len(unassigned_teachers), status, "", tag)
    
    # === VOEUX ===
    parent = insert_section("🎯 RESPECT DES VOEUX")
    
    status = "✅ Aucune violation" if violations['voeux_violes'] == 0 else f"⚠️ {violations['voeux_violes']} violation(s)"
    tag = "optimal" if violations['voeux_violes'] == 0 else "acceptable"
    insert_metric(parent, "Indisponibilités violées", violations['voeux_violes'], status, "", tag)
    
    # === DISTRIBUTION PAR JOURS ===
    parent = insert_section("📅 RÉPARTITION PAR JOURS")
    
    insert_metric(parent, "Jours d'examen totaux", total_exam_days, "", "", "")
    
    for num_days in sorted(day_distribution.keys()):
        count = day_distribution[num_days]
        label = f"Enseignants sur {num_days} jour(s)"
        tag = "acceptable" if num_days <= 3 else "problem" if num_days >= 5 else ""
        insert_metric(parent, label, count, f"{count} enseignant(s)", "", tag)
    
    # === ÉQUITÉ PAR GRADE ===
    parent = insert_section("⚖️ ÉQUITÉ PAR GRADE")
    
    for grade in sorted(grade_stats.keys()):
        stats = grade_stats[grade]
        equity_status = "✅ Excellent" if stats['std'] < 1.0 else "🟡 Acceptable" if stats['std'] < 2.0 else "⚠️ À améliorer"
        tag = "optimal" if stats['std'] < 1.0 else "acceptable" if stats['std'] < 2.0 else ""
        
        value = f"Min:{stats['min']} Max:{stats['max']}"
        details = f"Moyenne: {stats['avg']:.1f}, Écart-type: {stats['std']:.2f}"
        insert_metric(parent, f"Grade {grade}", value, equity_status, details, tag)
    
    # === STATISTIQUES GÉNÉRALES ===
    parent = insert_section("📈 STATISTIQUES GÉNÉRALES")
    
    total_slots = len(app.best)
    total_assignments = sum(len(teachers) for teachers in app.best.values())
    avg_teachers_per_slot = total_assignments / total_slots if total_slots > 0 else 0
    
    insert_metric(parent, "Créneaux totaux", total_slots, "", "", "")
    insert_metric(parent, "Assignations totales", total_assignments, "", "", "")
    insert_metric(parent, "Moyenne profs/créneau", f"{avg_teachers_per_slot:.1f}", "", "", "")
    insert_metric(parent, "Enseignants participants", len(eligible_teachers), "", "", "")
    insert_metric(parent, "Enseignants assignés", len(assigned_teachers), 
                 f"{len(assigned_teachers)}/{len(eligible_teachers)}", "", "")
    
    # Update summary if exists
    if hasattr(app, 'summary_label'):
        summary_text = f"📊 Score: {global_score:.0f} | "
        summary_text += f"❌ {violations['min_profs'] + violations['max_profs']} violations | "
        summary_text += f"⚠️ {len(unassigned_teachers)} non assignés | "
        summary_text += f"✅ {len(assigned_teachers)}/{len(eligible_teachers)} enseignants"
        app.summary_label.configure(text=summary_text)








