import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_reply(subject, email, email_body):
    sender_email = "chessmate.support@gmail.com"
    receiver_email = str(email)
    app_password = "pcqb gcuv avgh zjsj"

    # Build the HTML email with the verification code
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    body = email_body
    msg.attach(MIMEText(body, "html"))

    # Connect to Gmail's SMTP server and send the email
    smtp_server = "smtp.gmail.com"
    port = 587

    try:
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print("Error:", e)
    finally:
        server.quit()
