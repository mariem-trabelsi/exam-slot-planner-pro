# export_methods.py
"""
Méthodes d'export PDF et envoi par email.
"""

import os
import glob
from datetime import datetime
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from email_utils import EmailSender, EmailConfigDialog, create_teacher_email_body, create_email_subject
from constants import DAY_NAMES_FR
from traductions import t as _t


class ExportMethods:
    """Méthodes d'export PDF"""
    @staticmethod
    def export_teachers_to_pdf(app_instance, output_folder="exports", send_emails=True):
        """
        Exporte un PDF pour chaque enseignant avec ses créneaux
        
        Args:
            app_instance: Instance de la classe PlanningApp
            output_folder: Dossier de destination
            send_emails: True pour envoyer par email
        """
        if not app_instance.best:
            app_instance.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
            return
        
        # Créer le dossier
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Supprimer les anciens PDFs
        old_pdfs = glob.glob(os.path.join(output_folder, "Affectation_*.pdf"))
        for old_pdf in old_pdfs:
            try:
                os.remove(old_pdf)
            except Exception as e:
                print(f"Impossible de supprimer {old_pdf}: {e}")
        
        # Organiser par enseignant
        teacher_slots = defaultdict(list)
        
        for slot in app_instance.best:
            for teacher in app_instance.best[slot]:
                teacher_slots[teacher].append(slot)
        
        # Session times pour PDF
        SESSION_TIMES_PDF = {
            's1': '08:30:00',
            's2': '10:30:00',
            's3': '12:30:00',
            's4': '14:30:00'
        }

        pdf_count = 0
        email_count = 0
        email_errors = []
        pdfs_to_email = []
        
        # Générer un PDF par enseignant
        for teacher_code in sorted(teacher_slots.keys()):
            if not teacher_slots[teacher_code]:
                continue
            
            teacher_data = app_instance.teachers.get(str(teacher_code), {})
            prenom = teacher_data.get('prenom', '')
            nom = teacher_data.get('nom', '')
            email = teacher_data.get('email', '')
            full_name = f"Mr/Ms {prenom} {nom}" if prenom and nom else f"Enseignant #{teacher_code}"
            
            # Nom du fichier
            safe_name = f"{prenom}_{nom}".replace(' ', '_') if prenom and nom else f"Teacher_{teacher_code}"
            pdf_filename = os.path.join(output_folder, f"Affectation_{safe_name}.pdf")
            
            # Créer le PDF
            doc = SimpleDocTemplate(
                pdf_filename, pagesize=A4,
                rightMargin=2*cm, leftMargin=2*cm,
                topMargin=2*cm, bottomMargin=2*cm
            )
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Styles personnalisés
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1e3a8a'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#1e3a8a'),
                spaceAfter=20,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=20,
                alignment=TA_LEFT
            )
            
            # Header table
            header_data = [
                ['GESTION DES EXAMENS ET\nDÉLIBÉRATIONS', 'EXD-FR-08-01'],
                ["Procédure d'exécution des épreuves", f"Date d'approbation\n{datetime.now().strftime('%d-%m-%y')}"],
                ["Liste d'affectation des surveillants", 'Page 1/1']
            ]
            
            header_table = Table(header_data, colWidths=[14*cm, 4*cm])
            header_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a8a')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e6f0ff')),
                ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 11),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e3a8a')),
            ]))
            
            elements.append(header_table)
            elements.append(Spacer(1, 1*cm))
            
            # Titre
            elements.append(Paragraph("Notes à", subtitle_style))
            elements.append(Spacer(1, 0.3*cm))
            elements.append(Paragraph(f"<b>{full_name}</b>", subtitle_style))
            elements.append(Spacer(1, 0.5*cm))
            
            # Message
            greeting = """Cher (e) Collègue,<br/>
            Vous êtes prié (e) d'assurer la surveillance et (ou) la responsabilité des examens selon le calendrier ci-joint."""
            elements.append(Paragraph(greeting, normal_style))
            elements.append(Spacer(1, 0.5*cm))
            
            # Table des créneaux
            schedule_data = [['Date', 'Heure', 'Durée']]
            
            for slot in sorted(teacher_slots[teacher_code]):
                try:
                    parts = slot.split()
                    date_str = parts[0]
                    session = parts[1].lower()
                    
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    time = SESSION_TIMES_PDF.get(session, '08:30:00')
                    duration = '1.5 H'
                    
                    schedule_data.append([formatted_date, time, duration])
                except:
                    schedule_data.append([slot, 'N/A', '1.5 H'])
            
            schedule_table = Table(schedule_data, colWidths=[6*cm, 6*cm, 6*cm])
            schedule_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 12),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 11),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a8a')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#e6f0ff'), colors.white])
            ]))
            
            elements.append(schedule_table)
            
            # Construire le PDF
            doc.build(elements)
            pdf_count += 1
            
            # Préparer pour l'email
            if send_emails and email:
                pdfs_to_email.append({
                    'teacher_code': teacher_code,
                    'full_name': full_name,
                    'email': email,
                    'pdf_path': pdf_filename
                })
        
        # Envoyer les emails si demandé
        if send_emails and pdfs_to_email:
            # Configuration email
            email_dialog = EmailConfigDialog(app_instance, app_instance.colors)
            email_config = email_dialog.show()
            
            if email_config:
                # Préparation des données d'email
                emails_data = []
                for pdf_info in pdfs_to_email:
                    emails_data.append({
                        'email': pdf_info['email'],
                        'subject': create_email_subject(),
                        'body': create_teacher_email_body(pdf_info['full_name'], pdf_info['teacher_code']),
                        'attachment_path': pdf_info['pdf_path']
                    })
                
                # Envoi des emails
                email_sender = EmailSender(
                    sender_email=email_config['sender_email'],
                    password=email_config['password'],
                    smtp_server=email_config['smtp_server'],
                    smtp_port=email_config['smtp_port']
                )
                
                email_count, email_errors = email_sender.send_bulk_emails(emails_data)
        
        # Message final
        if send_emails:
            if email_errors:
                error_msg = f"{pdf_count} PDF(s) générés.\n{email_count} email(s) envoyés.\n{len(email_errors)} erreur(s):\n" + "\n".join(email_errors[:5])
                if len(email_errors) > 5:
                    error_msg += f"\n... et {len(email_errors) - 5} autres erreurs"
                app_instance.show_error_message("⚠️ Export avec erreurs", error_msg)
            else:
                app_instance.show_success_message(
                    "✅ Export et Envoi Réussis", 
                    f"{pdf_count} PDF(s) générés et {email_count} email(s) envoyés!"
                )
        else:
            app_instance.show_success_message(
                "✅ Export Réussi", 
                f"{pdf_count} PDF(s) générés dans le dossier '{output_folder}'"
            )
        
        return pdf_count
    
    @staticmethod
    @staticmethod
    def _page_conformite(app_instance, styles):
        """La page de conformite jointe au planning general."""
        from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors as _c
        from reportlab.lib.units import cm as _cm
        import genetic_algorithm as _ga
        import regles as _R

        try:
            verdicts = _ga.verifier_planning(
                app_instance.best, app_instance.teachers, dict(app_instance.slots))
        except Exception:
            return []

        conforme = _ga.planning_conforme(verdicts)
        tenues = sum(1 for v in verdicts if v['tenue'])
        sortie = [PageBreak(),
                  Paragraph(_t("Rapport de conformité"), styles['Title']),
                  Spacer(1, 0.3 * _cm),
                  Paragraph(
                      _t("%d règles sur %d sont tenues.") % (tenues, len(verdicts))
                      + " " + (
                          _t("Le planning respecte toutes les règles déclarées obligatoires.")
                          if conforme else
                          _t("ATTENTION : une règle déclarée obligatoire n'est pas tenue.")),
                      styles['Normal']),
                  Spacer(1, 0.5 * _cm)]

        donnees = [[_t("Règle"), _t("Exigence"), _t("Verdict")]]
        for v in verdicts:
            donnees.append([
                "%s  %s" % (v['id'], _t(v['nom'])),
                _t("Obligatoire") if v['nature'] == _R.DURE else _t("Souhaitable"),
                _t("Tenue") if v['tenue'] else "%d %s" % (
                    v['infractions'],
                    _t("infractions") if v['infractions'] > 1 else _t("infraction")),
            ])
        table = Table(donnees, colWidths=[10.5 * _cm, 3.2 * _cm, 3.8 * _cm])
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), _c.HexColor('#1F2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), _c.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.4, _c.HexColor('#D1D5DB')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
        for n, v in enumerate(verdicts, start=1):
            if not v['tenue']:
                style.append(('TEXTCOLOR', (2, n), (2, n),
                              _c.HexColor('#B91C1C' if v['nature'] == _R.DURE else '#B45309')))
            else:
                style.append(('TEXTCOLOR', (2, n), (2, n), _c.HexColor('#047857')))
        table.setStyle(TableStyle(style))
        sortie.append(table)

        details = [v for v in verdicts if not v['tenue'] and v['exemples']]
        if details:
            sortie += [Spacer(1, 0.6 * _cm),
                       Paragraph(_t("Détail des infractions"), styles['Heading2'])]
            for v in details:
                sortie.append(Paragraph("<b>%s %s</b>" % (v['id'], _t(v['nom'])), styles['Normal']))
                for ex in v['exemples']:
                    sortie.append(Paragraph("&nbsp;&nbsp;· %s" % ex, styles['Normal']))
                sortie.append(Spacer(1, 0.2 * _cm))
        return sortie

    def export_general_pdf(app_instance, output_folder="exports"):
        """
        Exporte un PDF général avec toutes les sessions
        
        Args:
            app_instance: Instance de la classe PlanningApp
            output_folder: Dossier de destination
        """
        if not app_instance.best:
            app_instance.show_error_message("❌ Erreur", "Veuillez générer le planning d'abord!")
            return
        
        # Créer le dossier
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Supprimer les anciens PDFs généraux
        old_pdfs = glob.glob(os.path.join(output_folder, "Planning_General_*.pdf"))
        for old_pdf in old_pdfs:
            try:
                os.remove(old_pdf)
            except Exception as e:
                print(f"Impossible de supprimer {old_pdf}: {e}")
        
        # Organiser par date et session
        sessions_data = defaultdict(lambda: defaultdict(list))
        
        for slot in sorted(app_instance.best.keys()):
            try:
                parts = slot.split()
                date_str = parts[0]
                session = parts[1].upper()
                
                teachers = app_instance.best[slot]
                
                # Récupérer les assignations de salles
                room_info = {}
                if hasattr(app_instance, 'room_assignments') and slot in app_instance.room_assignments:
                    for room, room_teachers in app_instance.room_assignments[slot].items():
                        for teacher in room_teachers:
                            room_info[teacher] = room
                
                sessions_data[date_str][session].append({
                    'teachers': teachers,
                    'room_info': room_info
                })
            except:
                continue
        
        # Session times
        # Les horaires viennent de la configuration de l'etablissement : ecrits
        # ici en dur, un etablissement aux seances differentes voyait son PDF
        # annoncer des heures qui n'etaient pas les siennes.
        import parametres as _p
        SESSION_TIMES_DISPLAY = _p.horaires(_p.charger())

        # Nom du fichier
        pdf_filename = os.path.join(
            output_folder,
            f"Planning_General_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
        # Créer le document PDF
        doc = SimpleDocTemplate(
            pdf_filename, pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Traiter chaque date et session
        for date_str in sorted(sessions_data.keys()):
            for session in sorted(sessions_data[date_str].keys()):
                session_info = sessions_data[date_str][session][0]
                
                # Parser la date
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = DAY_NAMES_FR.get(
                        date_obj.strftime('%A'),
                        date_obj.strftime('%A')
                    )
                    formatted_date = date_obj.strftime('%d/%m/%Y')
                except:
                    day_name = ""
                    formatted_date = date_str
                
                # Header
                header_data = [
                    ['GESTION DES EXAMENS ET DÉLIBÉRATIONS', 'EXD-FR-08-01'],
                    ["Procédure d'exécution des épreuves",
                     f"Date d'approbation\n{datetime.now().strftime('%d-%m-%y')}"],
                    ["Liste d'affectation des surveillants", 'Page 1/1']
                ]
                
                header_table = Table(header_data, colWidths=[15*cm, 3*cm])
                header_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a8a')),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e6f0ff')),
                    ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 10),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e3a8a')),
                ]))
                
                elements.append(header_table)
                elements.append(Spacer(1, 0.8*cm))
                
                # Titre de la session
                subtitle_style = ParagraphStyle(
                    'CustomSubtitle',
                    parent=styles['Normal'],
                    fontSize=12,
                    textColor=colors.HexColor('#1e3a8a'),
                    spaceAfter=15,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
                
                session_time = SESSION_TIMES_DISPLAY.get(session, 'N/A')
                session_title = (
                    f"AU : 2024-2025 - Semestre : 2 - Session : Principale<br/>"
                    f"Date : {formatted_date} - Séance : {session}"
                )
                elements.append(Paragraph(session_title, subtitle_style))
                elements.append(Spacer(1, 0.5*cm))
                
                # Table des enseignants
                table_data = [['Enseignant', 'Salle', 'Signature']]
                
                teachers = session_info['teachers']
                room_info = session_info['room_info']
                
                # Liste des enseignants
                teacher_list = []
                for teacher_code in sorted(teachers):
                    teacher_code_str = str(teacher_code)
                    if (hasattr(app_instance, 'teachers') and 
                        teacher_code_str in app_instance.teachers):
                        teacher_data = app_instance.teachers[teacher_code_str]
                        nom = teacher_data.get('nom', '')
                        prenom = teacher_data.get('prenom', '')
                        full_name = f"{nom} {prenom}" if nom and prenom else f"#{teacher_code}"
                    else:
                        full_name = f"#{teacher_code}"
                    
                    room = room_info.get(teacher_code, '')
                    teacher_list.append((full_name, room))
                
                # Ajouter à la table
                for full_name, room in sorted(teacher_list):
                    table_data.append([full_name, room, ''])
                
                # Créer la table
                teachers_table = Table(table_data, colWidths=[8*cm, 5*cm, 5*cm])
                teachers_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 11),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONT', (0, 1), (-1, -1), 'Helvetica', 10),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3a8a')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                     [colors.white, colors.HexColor('#e6f0ff')]),
                    ('ROWHEIGHT', (0, 1), (-1, -1), 0.8*cm)
                ]))
                
                elements.append(teachers_table)
                elements.append(PageBreak())
        
        # Retirer le dernier saut de page
        if elements and isinstance(elements[-1], PageBreak):
            elements.pop()
        
        # Construire le PDF
        # Le planning sort avec sa preuve : le responsable de scolarite doit
        # pouvoir montrer, devant un collegue qui conteste sa convocation, quelle
        # regle a ete tenue et laquelle ne l'a pas ete.
        elements += ExportMethods._page_conformite(app_instance, styles)
        doc.build(elements)
        
        app_instance.show_success_message(
            "✅ Export Réussi", 
            f"PDF général créé:\n{os.path.basename(pdf_filename)}"
        )
        
        return pdf_filename
    


