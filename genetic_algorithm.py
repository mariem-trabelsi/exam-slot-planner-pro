"""
Module contenant l'algorithme génétique pour l'optimisation du planning
"""
import random
import numpy as np
from datetime import datetime

SESSION_ORDER = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}
SESSION_TIMES = {"S1": "08:30", "S2": "10:30", "S3": "12:30", "S4": "14:30"}


def is_valid_teacher(t):
    """Vérifie si un enseignant est valide (pas NaN)"""
    if t is None:
        return False
    t_str = str(t).strip()
    return t_str and t_str.lower() != 'nan'


def get_teacher_slots(assignment, teacher):
    """Récupère les créneaux assignés à un enseignant avec tri"""
    slots = []
    for slot in assignment:
        if teacher in assignment[slot]:
            parsed = parse_datetime(slot)
            if parsed[0]:
                date, order = parsed
                slots.append((date, order, slot))
    return sorted(slots)




def index_par_enseignant(assignment, teachers):
    """Les creneaux de chaque surveillant, en UN seul parcours du planning.

    Auparavant `get_teacher_slots` rebalayait tout le planning pour chaque
    enseignant, et deux fonctions le faisaient chacune de leur cote : le cout
    d'une evaluation etait en enseignants x creneaux la ou il suffit d'un
    passage sur les affectations.

    Les doublons a l'interieur d'un creneau sont ecartes, comme le faisait
    `get_teacher_slots` : ils sont penalises ailleurs, pas comptes deux fois ici.
    """
    index = {}
    for slot, assignes in assignment.items():
        date, order = parse_datetime(slot)
        if date is None:
            continue
        entree = (date, order, slot)
        for t in set(assignes):
            if t in teachers and teachers[t].get('participe_surveillance', False):
                index.setdefault(t, []).append(entree)
    for creneaux in index.values():
        creneaux.sort()
    return index


def jours_du_surveillant(creneaux):
    """Regroupe par jour. La cle du jour est le debut du libelle de creneau,
    jamais un strftime : la date en vient deja, la reformater est du gaspillage."""
    jours = {}
    for _, order, slot in creneaux:
        jours.setdefault(slot.split()[0], []).append(order)
    return jours


def check_gap_violations(assignment, teachers, slots_dict, index=None):
    """Vérifie les séances creuses dans la même journée"""
    violations = {'one_gap': 0, 'two_gaps': 0}
    if index is None:
        index = index_par_enseignant(assignment, teachers)

    for teacher in teachers:
        if not teachers[teacher].get('participe_surveillance', False):
            continue

        for date_key, sessions in jours_du_surveillant(index.get(teacher, ())).items():
            if len(sessions) < 2:
                continue
            sessions = sorted(set(sessions))
            
            for i in range(len(sessions) - 1):
                gap = sessions[i + 1] - sessions[i]
                if gap == 2:
                    violations['one_gap'] += 1
                elif gap == 3:
                    violations['two_gaps'] += 1
    
    return violations


def dispersion_penalty(teacher_slots):
    """Pénalise les mauvaises répartitions"""
    if len(teacher_slots) < 2:
        return 0
    
    penalty = 0

    days = jours_du_surveillant(teacher_slots)

    # Pénaliser le nombre de jours
    num_days = len(days)
    if num_days > 3:
        penalty -= 30 * (num_days - 3)
    
    # Pénaliser les gaps
    for date_key, sessions in days.items():
        if len(sessions) < 2:
            continue
        sessions = sorted(set(sessions))
        
        for i in range(len(sessions) - 1):
            gap = sessions[i + 1] - sessions[i]
            if gap == 1:
                penalty += 20
            elif gap == 2:
                penalty -= 50
            elif gap == 3:
                penalty -= 100
    
    return penalty


def calculate_grade_equity(counts, teachers):
    """Calcule la variance des charges par grade"""
    grades = set(t.get('grade', '') for t in teachers.values() if t.get('participe_surveillance', False))
    total_variance = 0
    
    for grade in grades:
        if not grade:
            continue
        grade_counts = [counts.get(e, 0) for e in teachers 
                       if teachers[e].get('grade') == grade and teachers[e].get('participe_surveillance', False)]
        if grade_counts and len(grade_counts) > 1:
            variance = np.var(grade_counts)
            total_variance += variance
    
    return total_variance


def calculate_quota_violations(counts, teachers):
    """Calcule les dépassements de quota"""
    total_excess = 0
    violation_count = 0
    
    for teacher_code, count in counts.items():
        if teacher_code not in teachers:
            continue
        teacher = teachers[teacher_code]
        quota = teacher.get('quota', 0)
        
        if count > quota:
            excess = count - quota
            total_excess += excess
            violation_count += 1
    
    return total_excess, violation_count


def table_des_codes(teachers):
    """Code enseignant -> identifiant reel.

    Les creneaux designent leur responsable par un CODE (`enseignant`: '4'),
    alors que les affectations portent des adresses. Sans cette table, la
    comparaison echoue toujours.
    """
    table = {}
    for ident, fiche in teachers.items():
        code = str(fiche.get('code_smartex_ens', '')).strip()
        if code and code.lower() != 'nan':
            table[code] = ident
    return table


def responsable_du_creneau(slot_data, codes):
    """L'identifiant du responsable d'un creneau, ou None."""
    brut = str(slot_data.get('enseignant', '')).strip()
    if not brut or not is_valid_teacher(brut):
        return None
    return codes.get(brut, brut if '@' in brut else None)


def check_responsable_presence(assignment, slots_dict, teachers, codes=None):
    """Verifie la presence des profs responsables.

    Le code comparait un CODE enseignant a des adresses e-mail : il ne trouvait
    jamais personne. Mesure sur le planning retenu du 20/10/2025 :
    present=0, absent=23, soit -2300 points appliques identiquement a tous les
    individus. Une penalite constante ne distingue rien ; la contrainte etait
    donc inoperante, et 19 responsables sur 21 manquaient a leur propre examen
    sans que rien ne le signale.
    """
    if codes is None:
        codes = table_des_codes(teachers)
    present = 0
    absent = 0

    for slot, slot_data in slots_dict.items():
        resp = responsable_du_creneau(slot_data, codes)
        if resp is None:
            continue
        if resp in set(assignment.get(slot, ())):
            present += 1
        else:
            absent += 1

    return present, absent


def _conf_regles():
    """La configuration de l'etablissement, relue a chaud.

    Lue a chaque appel ce serait un acces disque par evaluation ; gardee en
    memoire pour toujours, un changement dans l'ecran d'administration
    n'aurait aucun effet avant un redemarrage. On garde donc une copie, que
    `recharger_regles()` invalide.
    """
    global _REGLES
    if _REGLES is None:
        import regles
        _REGLES = regles.charger()
    return _REGLES


_REGLES = None


def recharger_regles():
    """A appeler quand l'ecran d'administration a enregistre."""
    global _REGLES
    _REGLES = None


def par_salle():
    """Le minimum et le maximum de surveillants par salle, tels que
    l'etablissement les a regles. Ils etaient ecrits en dur, 2 et 4."""
    import regles as R
    conf = _conf_regles()
    return R.valeur(conf, 'R-01') or 2, R.valeur(conf, 'R-02') or 4


def poids(rid, defaut):
    """Le poids d'une regle souple. Zero si elle est ignoree ou rendue dure :
    une regle dure est imposee par la reparation, la compter deux fois
    fausserait la comparaison entre plannings."""
    import regles as R
    conf = _conf_regles().get(rid)
    if conf is None:
        return float(defaut)
    if conf['nature'] != R.SOUPLE:
        return 0.0
    return float(conf['poids'])


def fitness(assignment, teachers, slots_dict, index=None):
    """Fonction de fitness.

    `index` est la table enseignant -> creneaux. Elle est construite ici une
    seule fois et partagee par le controle des seances creuses et le calcul de
    dispersion, qui la reconstruisaient chacun de leur cote, enseignant par
    enseignant.
    """
    score = 0.0
    counts = {}
    if index is None:
        index = index_par_enseignant(assignment, teachers)
    
    # Compter les assignations
    for slot in assignment:
        valid_teachers = [t for t in assignment[slot] if is_valid_teacher(t) and t in teachers]
        unique_assigned = set(valid_teachers)
        slot_data = slots_dict.get(slot, {})
        room_count = slot_data.get('room_count', 1)
        _mn, _mx = par_salle()
        min_needed = _mn * room_count
        max_needed = _mx * room_count
        
        # Contraintes sur le nombre de profs
        if len(unique_assigned) < min_needed:
            score -= poids('R-01', 300) * (min_needed - len(unique_assigned)) ** 2
        elif len(unique_assigned) > max_needed:
            score -= poids('R-02', 500) * (len(unique_assigned) - max_needed) ** 2
        # elif len(unique_assigned) == min_needed:
        #     score += 100
        
        # Pénalité pour doublons
        if len(valid_teachers) != len(unique_assigned):
            score -= poids('R-03', 500) * (len(valid_teachers) - len(unique_assigned))
        
        # Compter pour chaque enseignant
        for e in valid_teachers:
            counts[e] = counts.get(e, 0) + 1
            
            # Pénalité pour indisponibilité
            if slot in teachers[e].get('indispo', []):
                wish_priority = teachers[e].get('wish_priority', {}).get(slot, 1.0)
                score -= poids('R-04', 2000) * wish_priority
    
    # Vérifier dépassements de quota
    total_excess, violation_count = calculate_quota_violations(counts, teachers)
    score -= poids('R-05', 500) * (total_excess ** 2)
    
    # Vérifier présence des profs responsables
    present, absent = check_responsable_presence(assignment, slots_dict, teachers)
    score += poids('R-06', 200) * present
    score -= poids('R-06', 200) / 2 * absent
    
    if absent == 0 and present > 0:
        score += 500
    
    # Pénaliser les séances creuses
    gap_violations = check_gap_violations(assignment, teachers, slots_dict, index)
    score -= poids('R-07', 200) * gap_violations['one_gap']
    score -= poids('R-08', 500) * gap_violations['two_gaps']
    
    if gap_violations['one_gap'] == 0 and gap_violations['two_gaps'] == 0:
        score += 500
    
    # Dispersion pour chaque enseignant
    for teacher_code, t_slots in index.items():
        score += dispersion_penalty(t_slots)
    
    # Équité par grade
    total_variance = calculate_grade_equity(counts, teachers)
    score -= poids('R-09', 400) * total_variance

    # R-12 : l'ecart au-dela d'une surveillance, a grade egal
    charges_grade = {}
    for e, fiche in teachers.items():
        if fiche.get('participe_surveillance'):
            charges_grade.setdefault(fiche.get('grade'), []).append(counts.get(e, 0))
    ecart_total = sum(max(v) - min(v)
                      for v in charges_grade.values() if len(v) > 1)
    score -= poids('R-12', 600) * ecart_total
    
    return score


def generate_population(pop_size, slots, teachers):
    """Génère une population initiale"""
    population = []
    teacher_list = [str(e) for e in teachers
                   if teachers[e].get('participe_surveillance', False) and is_valid_teacher(e)]
    
    for _ in range(pop_size):
        assignment = {}
        sorted_teachers = sorted(teacher_list, 
                               key=lambda t: teachers[t].get('quota', 0), 
                               reverse=True)
        
        for slot, slot_data in slots:
            min_needed = par_salle()[0] * slot_data.get('room_count', 1)
            available = [e for e in sorted_teachers 
                        if slot not in teachers[e].get('indispo', [])]
            
            # Prioriser le prof responsable
            enseignant_responsable = str(slot_data.get('enseignant', '')).strip()
            selected = []
            
            if (enseignant_responsable and 
                is_valid_teacher(enseignant_responsable) and 
                enseignant_responsable in available):
                selected.append(enseignant_responsable)
                available.remove(enseignant_responsable)
            
            if available:
                needed = min(min_needed - len(selected), len(available))
                if needed > 0:
                    selected.extend(random.sample(available, needed))
                
                # Compléter si nécessaire
                while len(selected) < min_needed and available:
                    selected.append(random.choice(available))
                
                max_needed = par_salle()[1] * slot_data.get('room_count', 1)
                assignment[slot] = selected[:max_needed]
            else:
                assignment[slot] = selected if selected else []
        
        population.append(assignment)
    
    return population


def crossover(parent1, parent2):
    """Croisement uniforme"""
    child = {}
    for key in parent1.keys():
        if random.random() < 0.5:
            child[key] = parent1[key][:]
        else:
            child[key] = parent2[key][:]
    return child


def _ajuster_totaux_par_grade(child, teachers, grades, counts, conf):
    """Rend le total de chaque grade divisible par son effectif.

    Sans cela, l'egalite stricte est hors d'atteinte : 44 surveillances pour
    9 enseignants ne se partagent pas egalement, et un echange a l'interieur du
    grade n'y change rien puisqu'il conserve le total du grade. Il faut donc
    deplacer des surveillances ENTRE grades — ce que la souplesse des effectifs
    par creneau permet : chacun accepte de deux a quatre surveillants par salle.

    On vise, pour chaque grade, le multiple de son effectif le plus proche de
    sa charge actuelle, sans depasser le quota du grade. Puis on troque : un
    grade en trop cede une place a un grade qui en manque.
    """
    import regles as R
    dures = {rid for rid, v in conf.items() if v['nature'] == R.DURE}

    def quota(e):
        return teachers[e].get('quota', 0)

    cibles = {}
    for grade, gens in grades.items():
        n = len(gens)
        total = sum(counts.get(e, 0) for e in gens)
        k = max(0, round(total / n)) if n else 0
        plafond = min(quota(e) for e in gens)
        cibles[grade] = min(k, plafond) * n

    for _ in range(300):
        surplus, manque = [], []
        for grade, gens in grades.items():
            ecart = sum(counts.get(e, 0) for e in gens) - cibles[grade]
            if ecart > 0:
                surplus.append(grade)
            elif ecart < 0:
                manque.append(grade)
        if not surplus or not manque:
            break

        echange = False
        for g_plein in surplus:
            for g_vide in manque:
                entrants = sorted(grades[g_vide], key=lambda e: counts.get(e, 0))
                for sortant in sorted(grades[g_plein],
                                      key=lambda e: counts.get(e, 0), reverse=True):
                    creneaux = [s for s, lst in child.items() if sortant in lst]
                    for entrant in entrants:
                        if 'R-05' in dures and counts.get(entrant, 0) >= quota(entrant):
                            continue
                        cible = next(
                            (s for s in creneaux
                             if entrant not in child[s]
                             and s not in (teachers[entrant].get('indispo') or ())),
                            None)
                        if cible is None:
                            continue
                        child[cible][child[cible].index(sortant)] = entrant
                        counts[sortant] -= 1
                        counts[entrant] = counts.get(entrant, 0) + 1
                        echange = True
                        break
                    if echange:
                        break
                if echange:
                    break
            if echange:
                break
        if not echange:
            break


def _equilibrer_par_grade(child, teachers, slots_dict, counts, participants, conf):
    """Ramene l'ecart a une surveillance au plus, a grade egal.

    On echange : le plus charge d'un grade cede un creneau au moins charge du
    MEME grade, pourvu que celui-ci soit disponible et absent du creneau. On
    n'ajoute ni ne retire rien — l'effectif de chaque creneau est inchange, et
    les autres regles obligatoires restent tenues.
    """
    import regles as R
    grades = {}
    for e in participants:
        grades.setdefault(teachers[e].get('grade'), []).append(e)

    _ajuster_totaux_par_grade(child, teachers, grades, counts, conf)

    for _ in range(400):                      # borne : on ne boucle pas sans fin
        bouge = False
        for grade, gens in grades.items():
            if len(gens) < 2:
                continue
            charges = {e: counts.get(e, 0) for e in gens}
            haut = max(charges.values())
            bas = min(charges.values())
            if haut == bas:
                continue
            charges_max = [e for e in gens if charges[e] == haut]
            charges_min = sorted((e for e in gens if charges[e] == bas),
                                 key=lambda e: counts.get(e, 0))
            # On essaie chaque porteur du maximum contre chaque porteur du
            # minimum : se limiter au premier couple laissait l'egalite hors
            # d'atteinte des que l'indisponibilite bloquait un echange.
            for sortant in sorted(charges_max,
                                  key=lambda e: len(teachers[e].get('indispo') or ())):
                creneaux = [s for s, lst in child.items() if sortant in lst]
                for entrant in charges_min:
                    cible = next(
                        (s for s in creneaux
                         if entrant not in child[s]
                         and s not in (teachers[entrant].get('indispo') or ())
                         and not ('R-05' in {rid for rid, v in conf.items()
                                             if v['nature'] == R.DURE}
                                  and counts.get(entrant, 0) >= teachers[entrant].get('quota', 0))),
                        None)
                    if cible is None:
                        continue
                    child[cible][child[cible].index(sortant)] = entrant
                    counts[sortant] -= 1
                    counts[entrant] = counts.get(entrant, 0) + 1
                    bouge = True
                    break
                if bouge:
                    break
        if not bouge:
            break


def mutate_improved(assignment, teachers, slots, slots_dict):
    """Mutation améliorée"""
    mutation_type = random.choice(['swap', 'reassign', 'redistribute', 'remove_overload'])
    teacher_list = [t for t in teachers 
                   if teachers[t].get('participe_surveillance', False) and is_valid_teacher(t)]
    
    if mutation_type == 'swap' and len(assignment) >= 2:
        slot_keys = list(assignment.keys())
        slot1, slot2 = random.sample(slot_keys, 2)
        valid1 = [t for t in assignment[slot1] if t in teacher_list]
        valid2 = [t for t in assignment[slot2] if t in teacher_list]
        
        if valid1 and valid2:
            e1 = random.choice(valid1)
            e2 = random.choice(valid2)
            
            if (slot2 not in teachers[e1].get('indispo', []) and 
                slot1 not in teachers[e2].get('indispo', [])):
                idx1 = assignment[slot1].index(e1)
                idx2 = assignment[slot2].index(e2)
                assignment[slot1][idx1] = e2
                assignment[slot2][idx2] = e1
    
    elif mutation_type in ['reassign', 'remove_overload']:
        counts = {e: sum(1 for slot in assignment if e in assignment[slot]) 
                 for e in teacher_list}
        overloaded = [e for e in counts 
                     if e in teachers and counts[e] > teachers[e].get('quota', 0)]
        underloaded = [e for e in counts 
                      if e in teachers and counts[e] < teachers[e].get('quota', 0)]
        
        if overloaded and underloaded:
            e_over = random.choice(overloaded)
            e_under = random.choice(underloaded)
            slots_with_over = [s for s in assignment if e_over in assignment[s]]
            
            if slots_with_over:
                slot = random.choice(slots_with_over)
                if slot not in teachers[e_under].get('indispo', []):
                    idx = assignment[slot].index(e_over)
                    assignment[slot][idx] = e_under
    
    elif mutation_type == 'redistribute':
        grades = list(set(t.get('grade', '') for t in teachers.values() 
                         if t.get('participe_surveillance', False)))
        
        if grades:
            grade = random.choice(grades)
            grade_teachers = [e for e in teacher_list if teachers[e].get('grade') == grade]
            
            if len(grade_teachers) >= 2:
                counts = {e: sum(1 for slot in assignment if e in assignment[slot]) 
                         for e in grade_teachers}
                most = max(counts, key=counts.get)
                least = min(counts, key=counts.get)
                
                if counts[most] - counts[least] >= 2:
                    slots_with_most = [s for s in assignment if most in assignment[s]]
                    if slots_with_most:
                        slot = random.choice(slots_with_most)
                        if slot not in teachers[least].get('indispo', []):
                            idx = assignment[slot].index(most)
                            assignment[slot][idx] = least
    
    return assignment


def repair_solution(child, teachers, slots_dict, codes=None):
    """Repare une solution.

    Quatre differences avec la version precedente, chacune mesuree :

    - le QUOTA est une limite, plus une preference. On completait en triant par
      charge decroissante sans jamais s'arreter au quota : la reparation creait
      elle-meme 708 depassements sur trente enfants, que la selection devait
      ensuite defaire a coups de penalites. On puise desormais d'abord chez
      ceux qui ont encore du quota, et on ne depasse que s'il n'existe aucun
      autre moyen de doter le creneau — un creneau en sous-effectif est une
      faute plus grave qu'une surveillance de trop.
    - le RESPONSABLE du creneau est place d'office. La contrainte existait dans
      le score mais ne pouvait pas s'appliquer, le controle comparant un code a
      des adresses.
    - la TRONCATURE retire les plus charges, et jamais le responsable, au lieu
      de couper la fin de la liste telle que le hasard l'a laissee.
    - les COMPTES sont tenus a jour au lieu d'etre recomptes a chaque creneau,
      ce qui etait l'essentiel du cout de cette fonction.
    """
    import regles as R
    conf = _conf_regles()
    dures = {rid for rid, v in conf.items() if v['nature'] == R.DURE}

    participants = {t for t in teachers
                    if teachers[t].get('participe_surveillance', False) and is_valid_teacher(t)}
    if codes is None:
        codes = table_des_codes(teachers)

    # un seul comptage, tenu a jour ensuite
    counts = {}
    for assignes in child.values():
        for t in set(assignes):
            if t in participants:
                counts[t] = counts.get(t, 0) + 1

    def quota(t):
        return teachers[t].get('quota', 0)

    for slot in child:
        # nettoyage : doublons et inconnus. L'ensemble des participants ne
        # change pas, donc les comptes restent justes.
        child[slot] = [t for t in dict.fromkeys(child[slot]) if t in participants]

        # R-04 declaree obligatoire : une convocation sur un creneau refuse est
        # RETIREE, pas seulement evitee au remplissage. Une penalite ne peut pas
        # defaire ce que le croisement a introduit.
        if 'R-04' in dures:
            partis = [t for t in child[slot]
                      if slot in (teachers[t].get('indispo') or ())]
            if partis:
                ecartes = set(partis)
                for t in ecartes:
                    counts[t] = counts.get(t, 1) - 1
                child[slot] = [t for t in child[slot] if t not in ecartes]

        data = slots_dict.get(slot, {})
        rooms = data.get('room_count', 1)
        _mn, _mx = par_salle()
        mini, maxi = _mn * rooms, _mx * rooms

        # Le responsable de l'examen surveille son propre examen — sauf s'il a
        # declare ce creneau impossible : une indisponibilite prime, sinon on
        # fabrique une convocation que l'interesse a explicitement refusee.
        resp = responsable_du_creneau(data, codes)
        if conf.get('R-06', {}).get('nature') == R.IGNOREE:
            resp = None
        if resp in participants and slot in (teachers[resp].get('indispo') or ()):
            resp = None
        # Le responsable ne passe pas devant une regle declaree obligatoire :
        # le place sans regarder son quota faisait ressortir un enseignant a 8
        # surveillances pour un quota de 7, R-05 pourtant obligatoire.
        if resp in participants and 'R-05' in dures and counts.get(resp, 0) >= quota(resp):
            resp = None
        if resp in participants and resp not in child[slot]:
            child[slot].append(resp)
            counts[resp] = counts.get(resp, 0) + 1

        if len(child[slot]) < mini:
            deja = set(child[slot])
            libres = [t for t in participants
                      if t not in deja and slot not in (teachers[t].get('indispo') or ())]
            sous_quota = sorted((t for t in libres if counts.get(t, 0) < quota(t)),
                                key=lambda t: counts.get(t, 0))
            au_dela = sorted((t for t in libres if counts.get(t, 0) >= quota(t)),
                             key=lambda t: counts.get(t, 0) - quota(t))
            candidats = sous_quota if 'R-05' in dures else sous_quota + au_dela
            for t in candidats:
                if len(child[slot]) >= mini:
                    break
                child[slot].append(t)
                counts[t] = counts.get(t, 0) + 1

        # Elagage. Un creneau accepte de `mini` a `maxi` surveillants : tant
        # qu'on reste au-dessus de `mini`, retirer quelqu'un qui a depasse son
        # quota ne coute rien et repare un exces herite du croisement, que la
        # version precedente ne defaisait jamais.
        cible = maxi if len(child[slot]) > maxi else mini
        if len(child[slot]) > cible:
            depassent = sorted((t for t in child[slot]
                                if t != resp and counts.get(t, 0) > quota(t)),
                               key=lambda t: counts.get(t, 0) - quota(t), reverse=True)
            retires = set()
            for t in depassent:
                if len(child[slot]) - len(retires) <= cible:
                    break
                retires.add(t)
            # au-dela de `maxi` il faut couper meme sans exces de quota
            if len(child[slot]) - len(retires) > maxi:
                autres = sorted((t for t in child[slot] if t != resp and t not in retires),
                                key=lambda t: counts.get(t, 0), reverse=True)
                for t in autres:
                    if len(child[slot]) - len(retires) <= maxi:
                        break
                    retires.add(t)
            for t in retires:
                counts[t] = counts.get(t, 1) - 1
            child[slot] = [t for t in child[slot] if t not in retires]

        # Echange. Un creneau deja au minimum ne peut rien perdre, mais il peut
        # TROQUER : un enseignant au-dela de son quota contre un disponible qui
        # a encore du sien. La capacite totale des quotas depasse le besoin, un
        # depassement n'est donc jamais fatal — il vient de ce que personne ne
        # remettait en cause les affectations heritees du croisement.
        trop = [t for t in child[slot] if t != resp and counts.get(t, 0) > quota(t)]
        if trop:
            dedans = set(child[slot])
            reserve = sorted((t for t in participants
                              if t not in dedans
                              and counts.get(t, 0) < quota(t)
                              and slot not in (teachers[t].get('indispo') or ())),
                             key=lambda t: counts.get(t, 0))
            trop.sort(key=lambda t: counts.get(t, 0) - quota(t), reverse=True)
            for sortant, entrant in zip(trop, reserve):
                child[slot][child[slot].index(sortant)] = entrant
                counts[sortant] -= 1
                counts[entrant] = counts.get(entrant, 0) + 1

            # Regle obligatoire : ce qui reste en depassement SORT, meme sans
            # remplacant disponible. Le creneau passe alors sous l'effectif
            # minimum, et c'est la verification qui le dira — mieux vaut un
            # manque annonce qu'une regle obligatoire violee en silence.
            if 'R-05' in dures:
                restants = [t for t in child[slot]
                            if t != resp and counts.get(t, 0) > quota(t)]
                for t in restants:
                    counts[t] = counts.get(t, 1) - 1
                if restants:
                    exces = set(restants)
                    child[slot] = [t for t in child[slot] if t not in exces]


    # Egalite de charge a grade egal, quand la regle est declaree obligatoire.
    # Elle vient en dernier : elle ECHANGE sans rien ajouter ni retirer, donc
    # elle ne defait aucune des garanties posees au-dessus.
    if 'R-12' in dures:
        _equilibrer_par_grade(child, teachers, slots_dict, counts, participants, conf)

    return child


_DATES = {}

def parse_datetime(slot_str):
    """Parse un slot au format 'YYYY-MM-DD SESSION' (e.g., '2025-05-13 S2').

    Memoise : le planning ne compte qu'une vingtaine de creneaux distincts,
    mais la fonction etait appelee des centaines de fois par evaluation, et
    strptime est couteux.
    """
    r = _DATES.get(slot_str)
    if r is not None:
        return r
    try:
        date_part, session = slot_str.split()
        r = (datetime.strptime(date_part, '%Y-%m-%d'), SESSION_ORDER.get(session, 0))
    except (ValueError, AttributeError):
        r = (None, 0)
    _DATES[slot_str] = r
    return r

# Deux profils de recherche. Les mesures sont prises sur 23 creneaux et 126
# surveillants, apres l'optimisation du calcul de score et de la reparation :
# une generation coute environ 0,4 s la ou elle en coutait 4.
PROFILS = {
    'rapide': {
        'nom': "Rapide",
        'detail': "Une quinzaine de secondes. Suffisant dans la plupart des cas.",
        'pop_size': 60, 'max_generations': 120, 'stagnation': 40,
    },
    'approfondie': {
        'nom': "Approfondie",
        'detail': "Quelques minutes. A reserver aux sessions difficiles.",
        'pop_size': 200, 'max_generations': 500, 'stagnation': 250,
    },
}
PROFIL_DEFAUT = 'rapide'


def run_ga_optimized(slots, teachers, progress_callback=None, profil=None):
    """
    Algorithme génétique optimisé avec gestion sécurisée du multiprocessing
    """
    reglage = PROFILS.get(profil or PROFIL_DEFAUT, PROFILS[PROFIL_DEFAUT])
    EARLY_STOP_THRESHOLD = 5000
    STAGNATION_LIMIT = reglage['stagnation']
    MIN_IMPROVEMENT = 1.0
    slots_dict = {slot: data for slot, data in slots}
    pop_size = reglage['pop_size']
    max_generations = reglage['max_generations']
    elite_size = int(pop_size * 0.2)
    pop = generate_population(pop_size, slots, teachers)
    echecs = 0
    best_fitness_history = []
    stagnation_counter = 0
    last_significant_improvement_gen = 0
    mutation_rate = 0.25
    for gen in range(max_generations):
        try:
            # Évaluation séquentielle pour éviter problèmes de mémoire
            pop_with_fitness = []
            rates = 0
            for ind in pop:
                try:
                    fitness_score = fitness(ind, teachers, slots_dict)
                    pop_with_fitness.append((ind, fitness_score))
                except Exception as e:
                    # Noter -999999 rend tous les individus equivalents : la
                    # selection ne distingue plus rien et la recherche tourne
                    # a vide en rendant quand meme un planning. Un echec isole
                    # reste tolere, un echec general arrete.
                    rates += 1
                    pop_with_fitness.append((ind, -999999))
            if rates >= len(pop):
                raise RuntimeError(
                    "Aucun planning n'a pu etre evalue (%d echecs). "
                    "Le resultat serait sans valeur." % rates)
            pop_with_fitness.sort(key=lambda x: x[1], reverse=True)
            best_fitness = pop_with_fitness[0][1]
            best_fitness_history.append(best_fitness)
            if best_fitness > EARLY_STOP_THRESHOLD:
                if progress_callback:
                    progress_callback(gen, max_generations, best_fitness,
                                     "🎯 Solution optimale trouvée!", "optimal")
                return pop_with_fitness[0][0], best_fitness_history, "optimal"
            if gen > 0:
                improvement = best_fitness - best_fitness_history[-2]
                if improvement >= MIN_IMPROVEMENT:
                    last_significant_improvement_gen = gen
                    stagnation_counter = 0
                    mutation_rate = max(mutation_rate * 0.8, 0.1)
                else:
                    stagnation_counter += 1
            if gen - last_significant_improvement_gen > STAGNATION_LIMIT:
                if progress_callback:
                    progress_callback(gen, max_generations, best_fitness,
                                     "✅ Convergence atteinte", "stagnated")
                return pop_with_fitness[0][0], best_fitness_history, "stagnated"
            if stagnation_counter < 20:
                mutation_rate = 0.25
            elif stagnation_counter < 50:
                mutation_rate = 0.5
            else:
                mutation_rate = 0.8
            if progress_callback:
                fitness_values = [f for _, f in pop_with_fitness]
                diversity = np.std(fitness_values) if len(fitness_values) > 1 else 0
                status = f"Stag: {stagnation_counter} | Div: {diversity:.1f} | Mut: {mutation_rate:.2f}"
                progress_callback(gen, max_generations, best_fitness, status, "running")
            new_pop = [ind for ind, _ in pop_with_fitness[:elite_size]]
            while len(new_pop) < pop_size:
                tournament_size = 10
                tournament1 = random.sample(pop_with_fitness[:pop_size//2],
                                           min(tournament_size, len(pop_with_fitness)//2))
                p1 = max(tournament1, key=lambda x: x[1])[0]
                tournament2 = random.sample(pop_with_fitness[:pop_size//2],
                                           min(tournament_size, len(pop_with_fitness)//2))
                p2 = max(tournament2, key=lambda x: x[1])[0]
                child = crossover(p1, p2)
                if random.random() < mutation_rate:
                    child = mutate_improved(child, teachers, slots, slots_dict)
                child = repair_solution(child, teachers, slots_dict)
                new_pop.append(child)
            pop = new_pop
        except Exception as e:
            # Une generation qui echoue etait simplement sautee. Un defaut de
            # programmation — un nom mal ecrit, un attribut absent — passait
            # ainsi inapercu : les 500 generations echouaient l'une apres
            # l'autre et la fonction rendait quand meme un planning, bati sur
            # la population initiale. Mesure : un ecart de charge de 8 au lieu
            # de 1, sans le moindre signal. Quelques echecs isoles restent
            # tolerables ; au-dela, on arrete et on le dit.
            echecs += 1
            print("Erreur generation %d : %s" % (gen, e))
            if echecs > max(5, max_generations // 20):
                raise RuntimeError(
                    "La recherche a echoue %d fois de suite (%s). "
                    "Le planning serait inexploitable." % (echecs, e))
            continue
    # Le meilleur SCORE n'est pas forcement un planning conforme. La reparation
    # fait tenir les regles obligatoires quand elle le peut, et l'egalite
    # stricte des charges a grade egal ne lui est pas toujours accessible : sur
    # le jeu d'exemple, elle y arrivait une fois sur deux. Or une regle
    # declaree obligatoire passe AVANT le score — c'est tout le contrat.
    # On rend donc le meilleur planning CONFORME de la population finale, et le
    # mieux note seulement si aucun ne l'est. Dans ce cas la verification le
    # declarera non tenue, ce qui reste la bonne reponse : tenue, ou declaree
    # non tenue, jamais violee en silence.
    for candidat, _note in pop_with_fitness[:20]:
        try:
            if planning_conforme(verifier_planning(candidat, teachers, slots_dict)):
                return candidat, best_fitness_history, "max_gen"
        except Exception:
            break
    return pop_with_fitness[0][0], best_fitness_history, "max_gen"

def verifier_planning(assignment, teachers, slots_dict, conf=None):
    """Controle le planning produit, regle par regle.

    Rend une liste de verdicts : identifiant, intitule, nature exigee, nombre
    d'infractions, et le detail des premieres. C'est ce qui permet de dire au
    responsable de scolarite ce que le planning tient, au lieu de lui montrer
    un score que personne ne sait lire — et de REFUSER de presenter comme bon
    un planning qui viole une regle declaree obligatoire.
    """
    import regles as _R
    R = _R
    conf = conf or _conf_regles()
    codes = table_des_codes(teachers)
    index = index_par_enseignant(assignment, teachers)
    from collections import Counter
    comptes = Counter(e for lst in assignment.values() for e in set(lst))

    infractions = {rid: [] for rid in R.PAR_ID}

    for slot, assignes in assignment.items():
        uniques = set(assignes)
        salles = slots_dict.get(slot, {}).get('room_count', 1)
        _mn, _mx = par_salle()
        if len(uniques) < _mn * salles:
            infractions['R-01'].append("%s : %d surveillants pour %d attendus"
                                       % (slot, len(uniques), _mn * salles))
        if len(uniques) > _mx * salles:
            infractions['R-02'].append("%s : %d surveillants pour %d au plus"
                                       % (slot, len(uniques), _mx * salles))
        if len(assignes) != len(uniques):
            infractions['R-03'].append("%s : %d doublon(s)"
                                       % (slot, len(assignes) - len(uniques)))
        for e in uniques:
            if e in teachers and slot in (teachers[e].get('indispo') or ()):
                infractions['R-04'].append("%s convoque le %s, qu'il a refuse" % (e, slot))

    for e, n in comptes.items():
        q = teachers.get(e, {}).get('quota', 0)
        if e in teachers and n > q:
            infractions['R-05'].append("%s : %d surveillances pour un quota de %d" % (e, n, q))

    for slot, data in slots_dict.items():
        resp = responsable_du_creneau(data, codes)
        if resp is not None and resp not in set(assignment.get(slot, ())):
            infractions['R-06'].append("%s : responsable %s absent" % (slot, resp))

    # R-12 : meme charge a grade egal, au sens STRICT — « ils sont cinq au
    # maximum, on ne peut pas en voir un a quatre et un autre du meme grade a
    # cinq ». Le controle ci-dessous exige donc max == min, sans tolerance.
    #
    # Ce n'est pas toujours atteignable : il faut que le total de chaque grade
    # se divise par son effectif, et les indisponibilites comme les effectifs
    # par salle ne le permettent pas toujours. La reparation deplace alors des
    # surveillances ENTRE grades pour s'en approcher (`_ajuster_totaux_par_
    # grade`), puis echange A L'INTERIEUR de chaque grade. Quand elle n'y
    # arrive pas, la regle est declaree non tenue et le grade est nomme — ce
    # qui est le contrat, pas un echec : tenue, ou declaree non tenue.
    par_grade = {}
    for e, fiche in teachers.items():
        if fiche.get('participe_surveillance'):
            par_grade.setdefault(fiche.get('grade'), []).append(comptes.get(e, 0))
    for grade, charges in par_grade.items():
        if len(charges) > 1 and max(charges) != min(charges):
            infractions['R-12'].append(
                "grade %s : de %d a %d surveillances"
                % (grade, min(charges), max(charges)))

    creux = check_gap_violations(assignment, teachers, slots_dict, index)
    infractions['R-07'] = ["%d journee(s) avec une seance creuse" % creux['one_gap']] if creux['one_gap'] else []
    infractions['R-08'] = ["%d journee(s) avec deux seances creuses" % creux['two_gaps']] if creux['two_gaps'] else []

    verdicts = []
    for regle in R.CATALOGUE:
        rid = regle['id']
        nature = conf.get(rid, {}).get('nature', regle['defaut'])
        if nature == R.IGNOREE:
            continue
        liste = infractions.get(rid) or []
        verdicts.append({
            'id': rid, 'nom': _R.intitule(conf, rid), 'nature': nature,
            'infractions': len(liste), 'exemples': liste[:4],
            'tenue': not liste,
        })
    return verdicts


def planning_conforme(verdicts):
    """Vrai si aucune regle DECLAREE OBLIGATOIRE n'est violee."""
    import regles as R
    return all(v['tenue'] for v in verdicts if v['nature'] == R.DURE)
