import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(subject, recipient, text_body, html_body=None):
    """E-postayı SMTP ile gönderir veya geliştirme kutusuna kaydeder."""
    message_data = {
        'subject': subject,
        'recipient': recipient,
        'text_body': text_body,
        'html_body': html_body,
    }

    if current_app.testing or current_app.config['MAIL_SUPPRESS_SEND']:
        current_app.extensions.setdefault('mail_outbox', []).append(
            message_data
        )

    if current_app.config['MAIL_SUPPRESS_SEND']:
        # Uygulama debug=False ile çalışırken INFO kayıtları terminalde
        # gösterilmez. Geliştirme ortamında sıfırlama bağlantısının kolayca
        # bulunabilmesi için e-postayı WARNING seviyesinde görünür kılarız.
        current_app.logger.warning(
            '\n%s\nGELİŞTİRME E-POSTASI (gerçek e-posta gönderilmedi)\n'
            'Alıcı: %s\nKonu: %s\n%s\n%s',
            '=' * 72,
            recipient,
            subject,
            text_body,
            '=' * 72
        )
        return

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    message['To'] = recipient
    message.set_content(text_body)

    if html_body:
        message.add_alternative(html_body, subtype='html')

    server_name = current_app.config['MAIL_SERVER']
    port = current_app.config['MAIL_PORT']
    use_ssl = current_app.config['MAIL_USE_SSL']
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

    with smtp_class(server_name, port, timeout=10) as server:
        if current_app.config['MAIL_USE_TLS'] and not use_ssl:
            server.starttls(context=ssl.create_default_context())

        username = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']
        if username and password:
            server.login(username, password)

        server.send_message(message)
