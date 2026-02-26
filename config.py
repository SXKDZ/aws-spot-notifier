import os
import time
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables from .env file next to this module
BASE_DIR = Path(__file__).resolve().parent
DOTENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=DOTENV_PATH)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAILS = [
    email.strip()
    for email in os.getenv("RECIPIENT_EMAILS", "").split(",")
    if email.strip()
]

# AWS IMDS URLs
METADATA_TOKEN_URL = "http://169.254.169.254/latest/api/token"
METADATA_SPOT_URL = "http://169.254.169.254/latest/meta-data/spot/termination-time"
INSTANCE_ID_URL = "http://169.254.169.254/latest/meta-data/instance-id"
INSTANCE_TYPE_URL = "http://169.254.169.254/latest/meta-data/instance-type"
PUBLIC_IP_URL = "http://169.254.169.254/latest/meta-data/public-ipv4"
PRIVATE_IP_URL = "http://169.254.169.254/latest/meta-data/local-ipv4"
AZ_URL = "http://169.254.169.254/latest/meta-data/placement/availability-zone"
INSTANCE_LIFECYCLE_URL = "http://169.254.169.254/latest/meta-data/instance-life-cycle"

# Configuration values
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", 21600))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 5))

# Paths
SCRIPT_TO_RUN = os.getenv("SCRIPT_TO_RUN", str(BASE_DIR / "script.sh"))
LOG_DIR = os.getenv("LOG_DIR", "/var/log")

logger = logging.getLogger(__name__)


def get_metadata_token():
    """Get a session token for IMDSv2."""
    try:
        response = requests.put(
            METADATA_TOKEN_URL,
            headers={"X-aws-ec2-metadata-token-ttl-seconds": str(TOKEN_TTL_SECONDS)},
            timeout=5,
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting IMDSv2 token: {e}")
        return None


def get_instance_metadata(token, url):
    """Get instance metadata using IMDSv2 token."""
    if not token:
        return "Unknown"

    try:
        response = requests.get(
            url, headers={"X-aws-ec2-metadata-token": token}, timeout=5
        )
        if response.status_code == 200:
            return response.text
        else:
            return "Unknown"
    except requests.exceptions.RequestException:
        return "Unknown"


def send_email(subject, body, max_retries=3, retry_delay=5):
    """Send an email to all configured recipients with retry logic.

    Returns True if at least one recipient was reached.
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("Email configuration missing. Cannot send notification.")
        return False

    if not RECIPIENT_EMAILS:
        logger.error("No recipient emails configured.")
        return False

    failed_recipients = []

    for idx, recipient_email in enumerate(RECIPIENT_EMAILS):
        email_sent = False

        for attempt in range(max_retries):
            try:
                msg = MIMEMultipart()
                msg["From"] = SENDER_EMAIL
                msg["To"] = recipient_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(msg)

                logger.info(f"[{idx + 1}] Email sent to {recipient_email}")
                email_sent = True
                break

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP authentication failed for {recipient_email}: {e}")
                break  # No point retrying auth errors
            except smtplib.SMTPServerDisconnected as e:
                logger.warning(
                    f"SMTP connection lost for {recipient_email} "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                logger.warning(
                    f"Failed to send email to {recipient_email} "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        if not email_sent:
            failed_recipients.append(recipient_email)
            logger.error(
                f"Failed to send email to {recipient_email} "
                f"after {max_retries} attempts"
            )

    if failed_recipients:
        logger.warning(f"Failed to send emails to: {', '.join(failed_recipients)}")

    return len(failed_recipients) < len(RECIPIENT_EMAILS)
