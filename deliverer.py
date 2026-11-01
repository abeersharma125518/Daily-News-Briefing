import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_email(html_body: str, email_config: dict) -> bool:
    smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_config.get("smtp_port", 587)
    sender = email_config.get("sender", "")
    password = email_config.get("password", "")
    recipient = email_config.get("recipient", "")

    if not sender or not password:
        logger.warning("Email not configured. Set sender/password in config.yaml")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Personal News Briefing"
    msg["From"] = sender
    msg["To"] = recipient

    text_part = MIMEText("Your news briefing is available in HTML format. Please view with an HTML-compatible email client.", "plain")
    html_part = MIMEText(html_body, "html")
    msg.attach(text_part)
    msg.attach(html_part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        logger.info("Email sent to %s", recipient)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed. Use an App Password (not your regular password).")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def save_html_local(html_body: str, filepath: str) -> bool:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_body)
        logger.info("Briefing saved to %s", filepath)
        return True
    except Exception as e:
        logger.error("Failed to save briefing: %s", e)
        return False
