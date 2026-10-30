import os
import smtplib
import ssl
from email.message import EmailMessage


def enviar_codigo_email(destinatario: str, codigo: str, operacao: str) -> None:
    host = os.getenv("AUTONOME_SMTP_HOST", "").strip()
    usuario = os.getenv("AUTONOME_SMTP_USER", "").strip()
    senha = os.getenv("AUTONOME_SMTP_PASSWORD", "")
    remetente = os.getenv("AUTONOME_SMTP_FROM", usuario).strip()
    porta = int(os.getenv("AUTONOME_SMTP_PORT", "587"))
    if not all((host, usuario, senha, remetente)):
        raise RuntimeError("Configure AUTONOME_SMTP_HOST, USER, PASSWORD e FROM no arquivo .env.")

    finalidade = "criar sua conta" if operacao == "cadastro" else "desativar sua conta"
    mensagem = EmailMessage()
    mensagem["Subject"] = "Código de verificação do AutonoMe"
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(
        f"Seu código para {finalidade} no AutonoMe é: {codigo}\n\n"
        "O código expira em 10 minutos. Se você não solicitou esta ação, ignore este e-mail."
    )

    contexto = ssl.create_default_context()
    with smtplib.SMTP(host, porta, timeout=15) as servidor:
        servidor.ehlo()
        servidor.starttls(context=contexto)
        servidor.ehlo()
        servidor.login(usuario, senha)
        servidor.send_message(mensagem)
