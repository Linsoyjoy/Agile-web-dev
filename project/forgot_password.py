import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def reset_password_email(username, email, code):
    sender_email = "chessmate.support@gmail.com"
    receiver_email = str(email)
    app_password = "pcqb gcuv avgh zjsj"
    readablecode = ""

    # Create the email
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = "Chessmate password reset"
    body = f"""   <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; text-align: center;">
        
        <h2 style="color: #333;">Password reset verification code</h2>
        
        <p style="font-size: 16px; color: #555;">
            Hi {username}, we have recieved a request to reset your accounts password. Use the code below to complete this process.
        </p>
        
        <div style="font-size: 28px; font-weight: bold; letter-spacing: 4px; margin: 20px 0; color: #000;">
            {code}
        </div>
        
        <p style="font-size: 14px; color: #888;">
            This code will expire in 60 minutes.
        </p>
        
        <p style="font-size: 12px; color: #aaa; margin-top: 20px;">
            If you didn’t request this, you can safely ignore this email.
        </p>
        
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(body, "html"))

    # Gmail SMTP server
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