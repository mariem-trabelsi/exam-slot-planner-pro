# -*- coding: utf-8 -*-
"""
traductions.py — les textes de l'interface, dans la langue choisie.

Le choix de langue existait dans les parametres mais n'avait aucun effet :
on selectionnait English, rien ne changeait. Les textes sont desormais passes
par `t()`, qui rend la version anglaise quand elle existe et le francais
sinon — une chaine non encore traduite reste donc lisible au lieu de
disparaitre.

L'arabe a ete retire du choix : tkinter ne lie pas les lettres arabes et
n'inverse pas le sens de lecture. Le seul mot arabe de l'interface s'affichait
deja a l'envers, lettres detachees. Le proposer aurait promis une langue que
l'outil ne sait pas ecrire.
"""

EN = {
    # fenetre et en-tete
    "Gestion des créneaux de surveillance": "Exam invigilation planner",
    "Gestion des Créneaux de Surveillance": "Exam invigilation planner",
    "Système de planification des examens": "Exam scheduling system",
    "📄 Export Individuel": "📄 Individual export",
    "📄 Export Général": "📄 Full export",
    "Envoyer par e-mail": "Send by e-mail",

    # barre laterale
    "📁 Chargement des fichiers": "📁 Load your files",
    "Charger Créneaux": "Load exam slots",
    "Charger Enseignants": "Load teachers",
    "Charger Vœux": "Load availability",
    "Administration": "Administration",
    "Génération du Planning": "Planning generation",
    "Générer Planning": "Generate planning",
    "Historique du Planning": "Planning history",
    "Voir Historique": "View history",
    "Sauvegarder Historique": "Save to history",

    # vue de donnees
    "Données": "Data",
    "Planning": "Planning",
    "Par Enseignant": "By teacher",
    "Par Salle": "By room",
    "Qualité": "Compliance",
    "Rechercher enseignant": "Search teacher",
    "Rechercher jour": "Search day",

    # menu
    "Fichier": "File",
    "Parametres...": "Settings...",
    "Quitter": "Quit",

    # messages
    "Fermer": "Close",
    "Aucun planning": "No planning yet",
    "Generez d'abord un planning.": "Generate a planning first.",
    "Donnees manquantes": "Missing data",
    "Chargez d'abord les creneaux et les enseignants.":
        "Load the exam slots and the teachers first.",
    "Fichier inattendu": "Unexpected file",
    "Planning genere": "Planning generated",
    "La generation a echoue": "Generation failed",
    "Recherche du meilleur planning": "Searching for the best planning",
    "Preparation...": "Preparing...",
    "Generation du planning": "Generating the planning",
    "Deja ouverte": "Already open",
    "Affichage impossible": "Cannot display",

    # ecran d'administration
    "Parametres": "Settings",
    "Etablissement": "Institution",
    "Seances": "Sessions",
    "Quotas": "Quotas",
    "Regles": "Rules",
    "Generation": "Generation",
    "Langue": "Language",
    "Enregistrer": "Save",
    "Annuler": "Cancel",
    "Retirer": "Remove",
    "Nom de l'etablissement": "Institution name",
    "Il apparait en tete de l'application et sur les exports.":
        "Shown in the application header and on exports.",
    "Logo": "Logo",
    "Choisir une image...": "Choose an image...",
    "Revenir au logo par defaut": "Back to the default logo",
    "Logo par defaut": "Default logo",
    "Aucun logo": "No logo",
    "Horaires des seances": "Session times",
    "Le code est celui qui figure dans vos fichiers de creneaux.":
        "Use the same codes as in your exam slot files.",
    "Ajouter une seance": "Add a session",
    "Code": "Code",
    "Debut": "Start",
    "Fin": "End",
    "Surveillances par grade": "Invigilations per rank",
    "Ajouter un grade": "Add a rank",
    "Grade": "Rank",
    "Surveillances": "Invigilations",
    "surveillances": "invigilations",
    "Ce que le planning doit respecter": "What the planning must respect",
    "Duree de la recherche": "Search effort",
    "Une recherche plus longue explore davantage de plannings.":
        "A longer search explores more plannings.",
    "Rapide": "Quick",
    "Approfondie": "Thorough",
    "Langue de l'interface": "Interface language",
    "Obligatoire": "Mandatory",
    "Souhaitable": "Preferred",
    "Ignoree": "Ignored",

    # champs de recherche
    "🔍 Rechercher enseignant...": "🔍 Search a teacher...",
    "🔍 Rechercher jour...": "🔍 Search a day...",
    "🔍 Rechercher salle...": "🔍 Search a room...",

    # en-tetes du tableau
    "📅 Date": "📅 Date",
    "📅 Date Examen": "📅 Exam date",
    "🕐 Session": "🕐 Session",
    "⏰ Heure": "⏰ Time",
    "👥 Nb": "👥 Count",
    "Nombre": "Count",
    "Enseignants": "Teachers",
    "👨‍🏫 Enseignants Assignés": "👨‍🏫 Assigned teachers",
    "Enseignants Assignés": "Assigned teachers",
    "Sessions": "Sessions",
    "Enseignant": "Teacher",
    "Présent": "Present",
    "Salle": "Room",
    "enseignants au total": "teachers in total",
    "sessions": "sessions",

    # jours de la semaine
    "Lundi": "Monday", "Mardi": "Tuesday", "Mercredi": "Wednesday",
    "Jeudi": "Thursday", "Vendredi": "Friday", "Samedi": "Saturday",
    "Dimanche": "Sunday",

    # ecran d'accueil
    "Etape": "Step",
    "A faire": "To do",
    "Charger les créneaux d'examen": "Load the exam slots",
    "Charger la liste des enseignants": "Load the teacher list",
    "Charger les souhaits d'indisponibilité": "Load the availability wishes",
    "Générer le planning": "Generate the planning",
    "Les règles que le planning doit respecter se règlent dans Administration.":
        "The rules the planning must respect are set in Administration.",

    # fenetre de generation
    "Generation du planning": "Generating the planning",
    "Recherche du meilleur planning": "Searching for the best planning",
    "Mode %s": "%s mode",
    "Preparation...": "Preparing...",
    "Generation %d sur %d": "Generation %d of %d",
    "%d s ecoulees%s": "%d s elapsed%s",
    "   ·   score %s": "   ·   score %s",
    "Mode %s, %d generations, %d secondes.": "%s mode, %d generations, %d seconds.",
    "Une quinzaine de secondes. Suffisant dans la plupart des cas.":
        "About fifteen seconds. Enough in most cases.",
    "Quelques minutes. A reserver aux sessions difficiles.":
        "A few minutes. For difficult sessions only.",

    # resume de conformite
    "%d règles sur %d sont tenues.": "%d rules out of %d are met.",
    "ATTENTION — une regle declaree obligatoire n'est pas tenue.":
        "WARNING — a mandatory rule is not met.",
    "obligatoire": "mandatory",
    "souhaitable": "preferred",

    # rapport de conformite
    "Règle": "Rule",
    "Exigence": "Requirement",
    "Verdict": "Verdict",
    "Detail": "Detail",
    "BILAN": "SUMMARY",
    "A CORRIGER": "TO FIX",
    "TENUES": "MET",
    "Conforme a toutes les regles obligatoires": "Meets every mandatory rule",
    "UNE REGLE OBLIGATOIRE N'EST PAS TENUE": "A MANDATORY RULE IS NOT MET",
    "Tenue": "Met",

    # La page de conformite du PDF general.
    "Rapport de conformité": "Compliance report",
    "Règle": "Rule",
    "Détail des infractions": "Breaches in detail",
    "%d règles sur %d sont tenues.": "%d rules out of %d are met.",
    "Le planning respecte toutes les règles déclarées obligatoires.":
        "The planning meets every rule declared mandatory.",
    "ATTENTION : une règle déclarée obligatoire n'est pas tenue.":
        "WARNING: a rule declared mandatory is not met.",
    "infraction": "breach",
    "infractions": "breaches",

    # Les douze regles du catalogue. L'etablissement peut reecrire chaque
    # intitule dans ses propres mots ; ce sont les libelles livres qui sont
    # traduits ici, et un intitule personnalise passe tel quel.
    "Effectif minimum par salle": "Minimum invigilators per room",
    "Nombre de surveillants exige par salle, au minimum.":
        "How many invigilators each room requires, at least.",
    "Effectif maximum par salle": "Maximum invigilators per room",
    "Nombre de surveillants admis par salle, au maximum.":
        "How many invigilators each room allows, at most.",
    "Pas deux fois la meme personne": "Never the same person twice",
    "Un enseignant ne figure qu'une fois sur un creneau.":
        "A teacher appears once per slot.",
    "Indisponibilites declarees": "Declared unavailability",
    "Ne pas convoquer quelqu'un sur un creneau qu'il a refuse.":
        "Never assign anyone to a slot they declined.",
    "Quota par grade": "Quota per grade",
    "Le nombre de surveillances d'un enseignant reste dans son quota.":
        "A teacher's number of duties stays within their quota.",
    "Responsable present a son examen": "Examiner present at their own exam",
    "L'enseignant responsable d'une epreuve la surveille.":
        "The teacher responsible for an exam invigilates it.",
    "Pas de seance creuse": "No idle session",
    "Eviter un trou d'une seance dans la journee d'un surveillant.":
        "Avoid a one-session gap in an invigilator's day.",
    "Pas de double seance creuse": "No double idle session",
    "Eviter un trou de deux seances dans la journee.":
        "Avoid a two-session gap in the day.",
    "Equite entre memes grades": "Fairness within a grade",
    "Repartir la charge equitablement a grade egal.":
        "Spread the load evenly among equals.",
    "Concentrer sur peu de jours": "Concentrate on few days",
    "Nombre de jours de presence au-dela duquel on penalise.":
        "Number of days on site beyond which a penalty applies.",
    "Surveillances consecutives": "Consecutive duties",
    "Recompenser deux seances qui se suivent dans la journee.":
        "Reward two sessions that follow one another.",
    "Meme charge a grade egal": "Equal load within a grade",
    "Deux enseignants d'un meme grade font exactement le meme nombre de surveillances.":
        "Two teachers of the same grade do exactly the same number of duties.",
}

_LANGUE = 'fr'


def definir_langue(code):
    global _LANGUE
    _LANGUE = code if code in ('fr', 'en') else 'fr'


def langue():
    return _LANGUE


def charger_depuis_parametres():
    import parametres as P
    definir_langue(P.charger().get('langue', 'fr'))


def jour(nom_anglais):
    """Le nom du jour dans la langue courante.

    `DAY_NAMES_FR` traduit l'anglais de `strftime` vers le francais. En anglais,
    c'est le nom d'origine qu'il faut rendre, pas sa traduction.
    """
    if _LANGUE == 'en':
        return nom_anglais
    from constants import DAY_NAMES_FR
    return DAY_NAMES_FR.get(nom_anglais, nom_anglais)


def t(texte):
    """Le texte dans la langue courante, le francais a defaut.

    Un pictogramme en tete est conserve et seul le texte qui suit est traduit :
    « 📅 Planning » n'a pas besoin de sa propre entree a cote de « Planning ».
    """
    if _LANGUE != 'en' or not texte:
        return texte
    direct = EN.get(texte)
    if direct is not None:
        return direct
    tete, sep, reste = texte.partition(' ')
    if sep and tete and not tete[0].isalnum() and reste in EN:
        return tete + ' ' + EN[reste]
    return texte
