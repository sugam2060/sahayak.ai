import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from shared.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, 
    MAIL_FROM, FRONTEND_URL
)


def send_verification_email(email: str, subject: str, html_content: str):
    """
    Background task to send a real verification email using smtplib.
    Accepts raw HTML content.
    """
    # Create the email content
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = MAIL_FROM
    message["To"] = email

    message.attach(MIMEText(html_content, "html"))

    try:
        # Connect to SMTP server and send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, email, message.as_string())
        
        print(f"Successfully sent verification email to {email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {email}: {str(e)}")
        # You might want to retry here in a real app
        raise e
