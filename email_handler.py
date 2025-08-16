import smtplib
from email.message import EmailMessage

def send_email_smtp(recipient_email, subject, body):

    sender_email = "yigitkagankilic@gmail.com"
    sender_password = "fvhr zmoc emex jpbq"

    msg = EmailMessage()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.set_content(body)

    # Gmail SMTP sunucusuna bağlan (TLS)
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        # Giriş yap
        smtp.login(sender_email, sender_password)

        # Maili gönder
        smtp.send_message(msg)

    print("Mail başarıyla gönderildi.")

# # Kullanım örneği
# if __name__ == "__main__":
#     send_email_smtp(
#         recipient_email="yigitkagankilic98@gmail.com",
#         subject="Merhaba",
#         body="Bu SMTP ile gönderilmiş bir test mailidir."
#     )
