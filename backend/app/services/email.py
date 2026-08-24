"""Email service using SendGrid."""
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_email(to_emails: list[str], subject: str, content: str) -> bool:
    """
    Sends an email using SendGrid. Returns True if successful, False otherwise.
    """
    api_key = settings.SENDGRID_API_KEY
    if not api_key or api_key == "YOUR_SENDGRID_KEY":
        logger.info(f"Mocking email to {to_emails}: {subject}")
        # Return True for local testing if no key is configured
        return True

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Format the 'to' list for SendGrid
    to_list = [{"email": email} for email in to_emails]
    
    payload = {
        "personalizations": [
            {
                "to": to_list,
                "subject": subject
            }
        ],
        "from": {"email": "noreply@healthcare-demo.local"}, # In prod this must be a verified sender
        "content": [
            {
                "type": "text/plain",
                "value": content
            }
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_emails}: {str(e)}")
        return False
