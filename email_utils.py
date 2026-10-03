# email_utils.py
"""
Module pour la gestion de l'envoi d'emails
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import customtkinter as ctk


class EmailSender:
    """Classe pour gérer l'envoi d'emails avec pièces jointes"""
    
    def __init__(self, sender_email, password, smtp_server="smtp.gmail.com", smtp_port=587):
        """
        Initialise le gestionnaire d'emails
        
        Args:
            sender_email: Email de l'expéditeur
            password: Mot de passe d'application
            smtp_server: Serveur SMTP (défaut: Gmail)
            smtp_port: Port SMTP (défaut: 587)
        """
        self.sender_email = sender_email
        self.password = password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
    
    def send_email(self, recipient_email, subject, body, attachment_path=None):
        """
        Envoie un email avec pièce jointe optionnelle
        
        Args:
            recipient_email: Email du destinataire
            subject: Sujet de l'email
            body: Corps de l'email
            attachment_path: Chemin vers le fichier à joindre (optionnel)
            
        Returns:
            bool: True si l'envoi a réussi, False sinon
        """
        try:
            # Création du message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            # Ajout du corps du message
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Ajout de la pièce jointe si spécifiée
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f"attachment; filename= {os.path.basename(attachment_path)}"
                    )
                    msg.attach(part)
            
            # Connexion au serveur SMTP et envoi
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'envoi à {recipient_email}: {e}")
            return False
    
    def send_bulk_emails(self, emails_data):
        """
        Envoie des emails en lot
        
        Args:
            emails_data: Liste de dictionnaires avec:
                - 'email': adresse du destinataire
                - 'subject': sujet de l'email
                - 'body': corps de l'email
                - 'attachment_path': chemin vers la pièce jointe (optionnel)
                
        Returns:
            tuple: (nombre d'emails envoyés, liste des erreurs)
        """
        sent_count = 0
        errors = []
        
        try:
            # Connexion unique au serveur SMTP pour tous les emails
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.password)
            
            for email_data in emails_data:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = self.sender_email
                    msg['To'] = email_data['email']
                    msg['Subject'] = email_data['subject']
                    
                    msg.attach(MIMEText(email_data['body'], 'plain', 'utf-8'))
                    
                    # Ajout de la pièce jointe si spécifiée
                    if 'attachment_path' in email_data and email_data['attachment_path'] and os.path.exists(email_data['attachment_path']):
                        with open(email_data['attachment_path'], 'rb') as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f"attachment; filename= {os.path.basename(email_data['attachment_path'])}"
                            )
                            msg.attach(part)
                    
                    server.send_message(msg)
                    sent_count += 1
                    print(f"✓ Email envoyé à {email_data['email']}")
                    
                except Exception as e:
                    error_msg = f"{email_data.get('email', 'Unknown')}: {str(e)}"
                    errors.append(error_msg)
                    print(f"✗ Erreur envoi à {email_data.get('email', 'Unknown')}: {e}")
            
            server.quit()
            
        except Exception as e:
            errors.append(f"Erreur de connexion SMTP: {str(e)}")
            print(f"✗ Erreur connexion SMTP: {e}")
        
        return sent_count, errors


class EmailConfigDialog:
    """Boîte de dialogue pour configurer les paramètres d'email"""
    
    def __init__(self, parent, colors):
        self.parent = parent
        self.colors = colors
        self.result = None
    
    def show(self):
        """Affiche la boîte de dialogue de configuration"""
        config_window = ctk.CTkToplevel(self.parent)
        config_window.title("📧 Configuration Email")
        config_window.geometry("600x650")
        config_window.transient(self.parent)
        config_window.grab_set()
        
        header = ctk.CTkFrame(config_window, fg_color="#3B82F6", corner_radius=10)
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header,
                    text="📧 Configuration de l'envoi par email",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color="white").pack(pady=15)
        
        form_frame = ctk.CTkFrame(config_window, fg_color="transparent")
        form_frame.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Champs de configuration
        ctk.CTkLabel(form_frame, text="Votre email:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 5))
        email_entry = ctk.CTkEntry(form_frame, width=400, placeholder_text="exemple@gmail.com")
        email_entry.pack(pady=(0, 15))
        
        ctk.CTkLabel(form_frame, text="Mot de passe d'application:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 5))
        password_entry = ctk.CTkEntry(form_frame, width=400, show="*", placeholder_text="Mot de passe d'application")
        password_entry.pack(pady=(0, 15))
        
        ctk.CTkLabel(form_frame, text="Serveur SMTP:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 5))
        smtp_entry = ctk.CTkEntry(form_frame, width=400, placeholder_text="smtp.gmail.com")
        smtp_entry.insert(0, "smtp.gmail.com")
        smtp_entry.pack(pady=(0, 15))
        
        ctk.CTkLabel(form_frame, text="Port SMTP:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 5))
        port_entry = ctk.CTkEntry(form_frame, width=400, placeholder_text="587")
        port_entry.insert(0, "587")
        port_entry.pack(pady=(0, 15))
        
        # Informations
        info_text = """💡 Pour Gmail, utilisez un mot de passe d'application:
1. Allez dans votre compte Google
2. Sécurité > Validation en 2 étapes 
3. Mots de passe d'application
4. Générez un mot de passe pour cette application"""
        
        ctk.CTkLabel(form_frame, text=info_text, font=ctk.CTkFont(size=10), 
                    text_color="gray", wraplength=400).pack(pady=10)
        
        def on_send():
            if not email_entry.get() or not password_entry.get():
                self._show_error("❌ Erreur", "Veuillez remplir tous les champs!")
                return
            
            self.result = {
                'sender_email': email_entry.get(),
                'password': password_entry.get(),
                'smtp_server': smtp_entry.get() or "smtp.gmail.com",
                'smtp_port': int(port_entry.get() or "587")
            }
            config_window.destroy()
        
        def on_cancel():
            self.result = None
            config_window.destroy()
        
        button_frame = ctk.CTkFrame(config_window, fg_color="transparent")
        button_frame.pack(pady=20)
        
        ctk.CTkButton(button_frame, text="📧 Envoyer", command=on_send,
                    width=150, height=40, fg_color="#10B981", hover_color="#059669").pack(side="left", padx=10)
        
        ctk.CTkButton(button_frame, text="❌ Annuler", command=on_cancel,
                    width=150, height=40, fg_color="#6B7280", hover_color="#4B5563").pack(side="left", padx=10)
        
        config_window.wait_window()
        return self.result
    
    def _show_error(self, title, message):
        """Affiche un message d'erreur"""
        error_window = ctk.CTkToplevel(self.parent)
        error_window.title(title)
        error_window.geometry("400x200")
        error_window.transient(self.parent)
        error_window.grab_set()
        
        ctk.CTkLabel(error_window, text=message, font=ctk.CTkFont(size=12)).pack(expand=True, padx=20, pady=20)
        ctk.CTkButton(error_window, text="OK", command=error_window.destroy).pack(pady=10)


def create_teacher_email_body(teacher_name, teacher_code):
    """
    Crée le corps de l'email pour un enseignant
    
    Args:
        teacher_name: Nom complet de l'enseignant
        teacher_code: Code de l'enseignant
        
    Returns:
        str: Corps de l'email formaté
    """
    return f"""Bonjour {teacher_name},

Veuillez trouver ci-joint votre affectation pour la surveillance des examens.

Votre code enseignant: {teacher_code}

Merci de bien vouloir consulter le document PDF en pièce jointe pour connaître vos créneaux de surveillance.

Cordialement,
Service des Examens"""


def create_email_subject():
    """Crée le sujet standard pour les emails"""
    return "Planning de Surveillance - Affectation des Examens"
