# config/mailersend_backend.py
#
# Replaces raw SMTP entirely. Railway blocks outbound SMTP connections at
# the network level -- confirmed 2026-07-27: both smtp.gmail.com:587 and
# mail.pokebulk.co.za:465 timed out identically at the socket.connect()
# step, on two completely different mail providers, which rules out a
# provider-specific block and points at Railway's platform-level outbound
# port restriction instead. HTTPS (port 443) is not blocked -- every other
# API call this app makes already proves that -- so this backend sends
# email over MailerSend's HTTPS API instead of SMTP, sidestepping the
# blocked port entirely.
#
# Because this is a full Django EMAIL_BACKEND, every existing call site
# using EmailMultiAlternatives(...).send() -- password reset, invoice
# emails, buy-order receipts -- keeps working completely unchanged. Only
# settings.py needs to point EMAIL_BACKEND here.
#
# Requires env var MAILERSEND_API_KEY (Railway Variables). No new pip
# package needed -- uses `requests`, already in requirements.txt.

import base64
import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"


class MailerSendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "MAILERSEND_API_KEY", "")
        if not api_key:
            logger.error("MAILERSEND_API_KEY is not set -- cannot send email.")
            if not self.fail_silently:
                raise RuntimeError("MAILERSEND_API_KEY is not configured.")
            return 0

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        sent_count = 0
        for message in email_messages:
            try:
                payload = self._build_payload(message)
            except Exception:
                logger.exception("Failed to build MailerSend payload for message subject=%s", message.subject)
                if not self.fail_silently:
                    raise
                continue

            try:
                response = requests.post(
                    MAILERSEND_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=getattr(settings, "EMAIL_TIMEOUT", 30),
                )
                if response.status_code in (200, 201, 202):
                    sent_count += 1
                    logger.info(
                        "Email sent via MailerSend: subject=%s to=%s status=%s",
                        message.subject, message.to, response.status_code,
                    )
                else:
                    logger.error(
                        "MailerSend API rejected the email: status=%s body=%s subject=%s to=%s",
                        response.status_code, response.text, message.subject, message.to,
                    )
                    if not self.fail_silently:
                        raise RuntimeError(
                            f"MailerSend API error {response.status_code}: {response.text}"
                        )
            except requests.RequestException:
                logger.exception(
                    "Network error calling MailerSend API for subject=%s to=%s",
                    message.subject, message.to,
                )
                if not self.fail_silently:
                    raise

        return sent_count

    def _build_payload(self, message):
        """Converts a Django EmailMessage/EmailMultiAlternatives into MailerSend's JSON format."""
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        from_name, from_addr = self._split_name_email(from_email)

        payload = {
            "from": {"email": from_addr, **({"name": from_name} if from_name else {})},
            "to": [self._to_recipient(addr) for addr in message.to],
            "subject": message.subject,
            "text": message.body,
        }

        if message.cc:
            payload["cc"] = [self._to_recipient(addr) for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [self._to_recipient(addr) for addr in message.bcc]
        if message.reply_to:
            reply_name, reply_addr = self._split_name_email(message.reply_to[0])
            payload["reply_to"] = {"email": reply_addr, **({"name": reply_name} if reply_name else {})}

        # HTML alternative (attach_alternative(html, 'text/html')) -- every
        # call site in this project uses this pattern for the HTML body.
        html_body = None
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_body = content
                break
        if html_body:
            payload["html"] = html_body

        # Attachments (PDF invoices/receipts) -- message.attachments is a
        # list of (filename, content, mimetype) tuples.
        attachments = []
        for filename, content, mimetype in getattr(message, "attachments", []):
            if isinstance(content, str):
                content = content.encode("utf-8")
            attachments.append({
                "filename": filename,
                "content": base64.b64encode(content).decode("ascii"),
                "disposition": "attachment",
            })
        if attachments:
            payload["attachments"] = attachments

        return payload

    @staticmethod
    def _to_recipient(addr):
        name, email = MailerSendBackend._split_name_email(addr)
        return {"email": email, **({"name": name} if name else {})}

    @staticmethod
    def _split_name_email(addr):
        """Handles both 'email@x.com' and 'Display Name <email@x.com>' formats."""
        if "<" in addr and ">" in addr:
            name = addr.split("<")[0].strip().strip('"')
            email = addr.split("<")[1].split(">")[0].strip()
            return name, email
        return "", addr.strip()
