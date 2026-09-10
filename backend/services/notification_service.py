# backend/services/notification_service.py

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import settings
from typing import Optional
import structlog

logger = structlog.get_logger()


class NotificationService:
    """Email notification service using Gmail SMTP (free)."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """Send an email notification."""
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            logger.warning("email_not_configured")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["From"] = settings.EMAIL_FROM or settings.SMTP_USERNAME
            message["To"] = to_email
            message["Subject"] = subject

            if text_body:
                message.attach(MIMEText(text_body, "plain"))
            message.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_tls=False,
                start_tls=True,
            )

            logger.info(
                "email_sent", to=to_email, subject=subject
            )
            return True

        except Exception as e:
            logger.error(
                "email_send_failed", to=to_email, error=str(e)
            )
            return False

    async def send_rti_created_notification(
        self,
        to_email: str,
        user_name: str,
        tracking_number: str,
        department: str,
        category: str,
    ):
        """Send notification when RTI is created."""
        subject = (
            f"RTI Application Created - {tracking_number}"
        )
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #1a365d; color: white; padding: 20px; text-align: center;">
                <h1>RTI Filing System</h1>
            </div>
            <div style="padding: 20px;">
                <h2>Dear {user_name},</h2>
                <p>Your RTI application has been successfully generated.</p>

                <div style="background: #f7fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p><strong>Tracking Number:</strong> {tracking_number}</p>
                    <p><strong>Category:</strong> {category.replace('_', ' ').title()}</p>
                    <p><strong>Department:</strong> {department}</p>
                    <p><strong>Status:</strong> Generated (Pending Filing)</p>
                </div>

                <p>You can review and file your RTI application from your dashboard.</p>
                <p>Once filed, the government department has <strong>30 days</strong> to respond.</p>

                <div style="margin-top: 20px; padding: 10px; background: #fff3cd; border-radius: 4px;">
                    <strong>⚠️ Important:</strong> Please review the generated application
                    carefully before filing. You can modify the text if needed.
                </div>
            </div>
            <div style="background: #f7fafc; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>This is an automated email from RTI Filing System.</p>
                <p>© 2024 RTI Filing System. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        await self.send_email(to_email, subject, html_body)

    async def send_rti_filed_notification(
        self,
        to_email: str,
        user_name: str,
        tracking_number: str,
        portal_reference: str,
        response_due_date: str,
    ):
        """Send notification when RTI is filed on portal."""
        subject = (
            f"RTI Filed Successfully - {tracking_number}"
        )
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #276749; color: white; padding: 20px; text-align: center;">
                <h1>✅ RTI Filed Successfully!</h1>
            </div>
            <div style="padding: 20px;">
                <h2>Dear {user_name},</h2>
                <p>Your RTI application has been successfully filed on the government portal.</p>

                <div style="background: #f0fff4; border: 1px solid #c6f6d5; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p><strong>Our Tracking Number:</strong> {tracking_number}</p>
                    <p><strong>Portal Reference Number:</strong> {portal_reference}</p>
                    <p><strong>Response Due Date:</strong> {response_due_date}</p>
                </div>

                <p>The government department is legally bound to respond within 30 days.</p>

                <div style="margin-top: 20px;">
                    <h3>What's Next?</h3>
                    <ul>
                        <li>We will monitor your application status.</li>
                        <li>You will receive a notification when a response is received.</li>
                        <li>If no response within 30 days, you can file a First Appeal.</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        await self.send_email(to_email, subject, html_body)