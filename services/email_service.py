import os
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import Optional

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class EmailService:
    @staticmethod
    def get_gmail_service():
        """
        สร้าง Gmail API service โดยใช้ Refresh Token
        """
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
        
        if not all([client_id, client_secret, refresh_token]):
            missing = []
            if not client_id: missing.append("GMAIL_CLIENT_ID")
            if not client_secret: missing.append("GMAIL_CLIENT_SECRET")
            if not refresh_token: missing.append("GMAIL_REFRESH_TOKEN")
            raise ValueError(f"Missing credentials: {', '.join(missing)}")
        
        creds = Credentials.from_authorized_user_info({
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'type': 'authorized_user'
        }, SCOPES)
        
        # Refresh token ถ้าหมดอายุ
        if creds.expired:
            creds.refresh(Request())
        
        return build('gmail', 'v1', credentials=creds)

    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str, text_content: str, reply_to: str = None, sender_name: str = None, sender_email: str = None):
        """
        ส่งอีเมลผ่าน Gmail API
        """
        try:
            service = EmailService.get_gmail_service()
            
            # สร้างอีเมล
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["To"] = to_email
            
            if reply_to:
                msg["Reply-To"] = reply_to

            if sender_email:
                if sender_name:
                    msg["From"] = f'"{sender_name}" <{sender_email}>'
                else:
                    msg["From"] = sender_email
            
            # เพิ่มเนื้อหา
            part1 = MIMEText(text_content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Encode เป็น base64
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            
            # ส่งอีเมล
            service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            # เราไม่ raise error เพื่อไม่ให้ background task พัง แต่ log ไว้
            return False
