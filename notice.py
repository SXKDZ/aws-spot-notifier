import requests
import time
import logging
import signal
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
from datetime import datetime
from config import (
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_PASSWORD,
    RECIPIENT_EMAILS,
    METADATA_SPOT_URL,
    INSTANCE_ID_URL,
    INSTANCE_TYPE_URL,
    PUBLIC_IP_URL,
    PRIVATE_IP_URL,
    TOKEN_TTL_SECONDS,
    CHECK_INTERVAL,
    get_metadata_token,
    get_instance_metadata,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_for_termination_notice(token):
    """Check the instance metadata service for a spot termination notice using IMDSv2 token."""
    if not token:
        logger.error("No valid token available for metadata service")
        return None

    try:
        response = requests.get(
            METADATA_SPOT_URL, headers={"X-aws-ec2-metadata-token": token}, timeout=2
        )

        if response.status_code == 200:
            termination_time = response.text
            logger.warning(
                f"Spot instance termination notice received! Termination time: {termination_time}"
            )
            return termination_time
        elif response.status_code == 404:
            # 404 is expected when there's no termination notice
            return None
        else:
            logger.error(
                f"Unexpected status code checking termination: {response.status_code}"
            )
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking for termination notice: {e}")
        return None


def send_termination_email(token, termination_time):
    """Send email notification about the spot instance termination."""

    # Get instance information
    instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
    instance_type = get_instance_metadata(token, INSTANCE_TYPE_URL)
    public_ip = get_instance_metadata(token, PUBLIC_IP_URL)
    private_ip = get_instance_metadata(token, PRIVATE_IP_URL)
    hostname = socket.gethostname()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create email message
    subject = f"⚠️ ALERT: AWS Spot Instance Termination Notice - {instance_id}"

    body = f"""
SPOT INSTANCE TERMINATION NOTICE

Time of Notice: {current_time}
Termination Time: {termination_time}

INSTANCE DETAILS:
- Instance ID: {instance_id}
- Instance Type: {instance_type}
- Public IP: {public_ip}
- Private IP: {private_ip}
- Hostname: {hostname}

This instance will be terminated by AWS in approximately 2 minutes.
Please take any necessary actions to save data or migrate services.

This is an automated message from the Spot Termination Monitor.
    """

    # Create message container
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["Subject"] = subject

    # Attach body
    message.attach(MIMEText(body, "plain"))

    try:
        # Send emails to all recipients
        for idx, recipient_email in enumerate(RECIPIENT_EMAILS):
            msg_copy = MIMEMultipart()
            msg_copy["From"] = SENDER_EMAIL
            msg_copy["To"] = recipient_email
            msg_copy["Subject"] = subject
            msg_copy.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg_copy)

            logger.info(f"[{idx + 1}] Termination email sent to {recipient_email}")

        return True
    except Exception as e:
        logger.error(f"Failed to send termination email: {e}")
        return False


def handle_termination(token, termination_time):
    """Handle the spot instance termination."""
    logger.warning("Starting termination handling procedures...")

    # Send email notification
    send_termination_email(token, termination_time)

    # Add additional cleanup code here
    # Examples:
    # - Save application state
    # - Flush data to persistent storage
    # - Notify other system components
    # - Gracefully shutdown services

    logger.info("Termination handling complete")


def run_termination_monitor():
    """Main function to continuously monitor for termination notices."""
    logger.info("Starting spot instance termination monitor (IMDSv2)")

    # Check email configuration
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.warning(
            "Email sender details not configured! Email notifications will not be sent."
        )

    # Track token refresh time
    token = None
    last_token_time = 0

    # Track if termination notice has been handled
    termination_handled = False

    try:
        while True:
            # Refresh token if needed
            current_time = time.time()
            if token is None or (
                current_time - last_token_time > TOKEN_TTL_SECONDS - 60
            ):
                token = get_metadata_token()
                if token:
                    last_token_time = current_time

                    # Get instance info on startup or token refresh
                    if not termination_handled:
                        instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
                        instance_type = get_instance_metadata(token, INSTANCE_TYPE_URL)
                        logger.info(
                            f"Monitoring spot instance: {instance_id} ({instance_type})"
                        )
                else:
                    # Wait before trying again
                    time.sleep(CHECK_INTERVAL)
                    continue

            termination_time = check_for_termination_notice(token)
            if termination_time and not termination_handled:
                handle_termination(token, termination_time)
                termination_handled = True
                # Continue checking, but don't handle again
            elif termination_time and termination_handled:
                # We've already handled it, but log that we're still seeing the notice
                logger.info(f"Termination notice still active, time remaining...")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Termination monitor stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in termination monitor: {e}", exc_info=True)
    finally:
        logger.info("Termination monitor shutting down")


def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, shutting down gracefully")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the monitor
    run_termination_monitor()
