"""
view_methods.py — la repartition des surveillants dans les salles.

Ce fichier portait aussi six fonctions d'affichage — par enseignant, par
salle, par jour, le detail des responsables, un ancien tableau de qualite.
Aucune n'etait atteignable : l'application affiche ses vues par
`PlanningApp.switch_view`, qui appelle ses PROPRES methodes. Les seules
fonctions qui menaient ici etaient quatre `*_wrapper` que rien n'appelait.

Elles ne dormaient pas tranquillement. Elles ne pouvaient meme pas s'executer :
`_t` y etait utilise sans etre importe — dans quatre d'entre elles — et
`app.populate_flat_view()` n'existe sur aucune classe. Mesure en appelant les
trois que l'application reliait encore : les trois levent immediatement. Six
cent cinquante lignes qui imitaient du code vivant — exactement le piege que ce
projet documente ailleurs.
"""
import random

from genetic_algorithm import is_valid_teacher


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
