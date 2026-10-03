# constants.py
"""
Constantes et configurations de l'application
"""

# Etablissement affiche dans l'en-tete et sur les exports.
# L'outil ne vise aucun etablissement en particulier : changez cette ligne,
# ou laissez-la vide pour n'afficher que le titre.
ETABLISSEMENT = ""

# Configuration des quotas par grade
GRADE_QUOTAS = {
    "PR": 4, "MA": 7, "V": 4, "PTC": 9, "AC": 9,
    "VA": 4, "AS": 8, "EX": 3, "MC": 4, "PES": 9
}

# Mappings des sessions
SESSION_TIMES = {
    "S1": "08:30",
    "S2": "10:30",
    "S3": "12:30",
    "S4": "14:30"
}

SESSION_ORDER = {
    "S1": 1,
    "S2": 2,
    "S3": 3,
    "S4": 4
}

SESSION_COLORS = {
    's1': ('#E3F2FD', '#1976D2'),  # Blue
    's2': ('#E8F5E9', '#388E3C'),  # Green
    's3': ('#FFF3E0', '#F57C00'),  # Orange
    's4': ('#F3E5F5', '#7B1FA2')   # Purple
}

# Noms des jours en français
DAY_NAMES_FR = {
    'Monday': 'Lundi',
    'Tuesday': 'Mardi',
    'Wednesday': 'Mercredi',
    'Thursday': 'Jeudi',
    'Friday': 'Vendredi',
    'Saturday': 'Samedi',
    'Sunday': 'Dimanche'
}

def _police_disponible():
    """La premiere police de la liste reellement installee.

    Tout le code demandait « Segoe UI », une police Windows. Sous Linux elle
    n'existe pas : Tk en substituait une au hasard, et l'application n'avait
    pas la meme allure d'une machine a l'autre. On choisit donc explicitement,
    en descendant une liste jusqu'a trouver.
    """
    candidates = ("Segoe UI", "Inter", "Carlito", "Noto Sans", "Ubuntu",
                  "Liberation Sans", "DejaVu Sans", "TkDefaultFont")
    try:
        import tkinter.font as _tf
        familles = set(_tf.families())
        for nom in candidates:
            if nom in familles:
                return nom
    except Exception:
        pass
    return "TkDefaultFont"


# Police système, resolue au premier acces (il faut une fenetre Tk ouverte)
SYSTEM_FONT = "Segoe UI"


def police():
    global SYSTEM_FONT
    if SYSTEM_FONT == "Segoe UI":
        SYSTEM_FONT = _police_disponible()
    return SYSTEM_FONT

# Palette. Un seul accent, des neutres qui se suivent, et des couleurs de
# statut reservees au statut. Elle etait auparavant redefinie dans main.py,
# si bien que la modifier ici n'avait aucun effet.
COLORS = {
    # accent, un seul
    'primary': '#2B59C3',
    'primary_hover': '#1F47A6',

    # statut, et rien d'autre
    'success': '#0E9F6E',
    'success_light': '#A7E8CE',
    'warning': '#D97706',
    'error': '#DC2626',

    # neutres, du plus clair au plus fonce
    'bg': '#F1F3F7',
    'card': '#FFFFFF',
    'sidebar': '#FAFBFD',
    'hover': '#F3F5F9',
    'border': '#E2E6ED',
    'test': '#E9ECF2',
    'text_secondary_light': '#A7AEBB',
    'text_secondary': '#5B6472',
    'text': '#10151F',
}

# Noms des jours en français
DAY_NAMES_FR = {
    'Monday': 'Lundi',
    'Tuesday': 'Mardi',
    'Wednesday': 'Mercredi',
    'Thursday': 'Jeudi',
    'Friday': 'Vendredi',
    'Saturday': 'Samedi',
    'Sunday': 'Dimanche'
}



# Police système, resolue au premier acces (il faut une fenetre Tk ouverte)
SYSTEM_FONT = "Segoe UI"



# Palette de couleurs moderne
COLORS = {
    'primary': '#2563EB',
    'primary_hover': '#1D4ED8',
    'success': '#10B981',
    'success_light': "#5AE6B7",
    'warning': '#F59E0B',
    'error': '#EF4444',
    'bg': '#EDF0F5',
    'card': '#FFFFFF',
    'sidebar': '#F8FAFC',
    'text': '#111827',
    'text_secondary': '#6B7280',
    'text_secondary_light': "#ACACAC",
    'border': '#E3E8EF',
    'hover': '#F3F4F6',
    'test': "#E2E2E2",
}