import time
import logging
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
import subprocess
import datetime
from time import sleep
from config import (
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_PASSWORD,
    RECIPIENT_EMAILS,
    INSTANCE_ID_URL,
    INSTANCE_TYPE_URL,
    PUBLIC_IP_URL,
    PRIVATE_IP_URL,
    AZ_URL,
    INSTANCE_LIFECYCLE_URL,
    SCRIPT_TO_RUN,
    LOG_DIR,
    get_metadata_token,
    get_instance_metadata,
)

# Configure logging
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "spot_instance_startup.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def send_startup_email(instance_info, max_retries=3, retry_delay=5):
    """Send email notification about the spot instance startup with retry logic."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("Email configuration missing. Cannot send notification.")
        return False

    # Create email message
    subject = f"✅ ALERT: AWS Spot Instance Restarted - {instance_info['instance_id']}"

    body = f"""
SPOT INSTANCE RESTART NOTIFICATION

Time: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

INSTANCE DETAILS:
- Instance ID: {instance_info['instance_id']}
- Instance Type: {instance_info['instance_type']}
- Lifecycle: {instance_info['lifecycle']}
- Availability Zone: {instance_info['az']}
- NEW Public IP: {instance_info['public_ip']}
- NEW Private IP: {instance_info['private_ip']}
- Hostname: {instance_info['hostname']}

This instance has been restarted after a previous spot instance termination.
The system is now online with the new IP addresses listed above.

This is an automated message from the Spot Instance Startup Monitor.
    """

    # Track which recipients succeeded
    failed_recipients = []

    # Send emails to all recipients with retry logic
    for idx, recipient_email in enumerate(RECIPIENT_EMAILS):
        email_sent = False

        for attempt in range(max_retries):
            try:
                message = MIMEMultipart()
                message["From"] = SENDER_EMAIL
                message["To"] = recipient_email
                message["Subject"] = subject
                message.attach(MIMEText(body, "plain"))

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(message)

                logger.info(f"[{idx + 1}] Startup email sent to {recipient_email}")
                email_sent = True
                break  # Success, no need to retry

            except smtplib.SMTPServerDisconnected as e:
                logger.warning(f"SMTP connection lost for {recipient_email} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    sleep(retry_delay)
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP authentication failed for {recipient_email}: {e}")
                break  # No point retrying auth errors
            except Exception as e:
                logger.warning(f"Failed to send email to {recipient_email} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    sleep(retry_delay)

        if not email_sent:
            failed_recipients.append(recipient_email)
            logger.error(f"Failed to send startup email to {recipient_email} after {max_retries} attempts")

    # Return True if at least one email was sent successfully
    success = len(failed_recipients) < len(RECIPIENT_EMAILS)
    if failed_recipients:
        logger.warning(f"Failed to send emails to: {', '.join(failed_recipients)}")

    return success


def run_custom_script():
    """Run the specified script after startup."""
    if not os.path.exists(SCRIPT_TO_RUN):
        logger.error(f"Custom script not found at {SCRIPT_TO_RUN}")
        return False

    # Validate that the script is executable
    if not os.access(SCRIPT_TO_RUN, os.X_OK):
        logger.warning(f"Script is not executable, attempting to make it executable: {SCRIPT_TO_RUN}")
        try:
            os.chmod(SCRIPT_TO_RUN, 0o755)
        except Exception as e:
            logger.error(f"Failed to make script executable: {e}")
            return False

    try:
        logger.info(f"Running custom script as detached process: {SCRIPT_TO_RUN}")

        # Use Popen without shell=True for security
        # Pass the script directly as an executable
        process = subprocess.Popen(
            [SCRIPT_TO_RUN],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,  # Creates a new process group
            # Removed shell=True for security - script must be executable
        )

        # Don't wait for the process to complete
        logger.info(f"Custom script launched successfully with PID: {process.pid}")
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to launch custom script: {e}")
        return False


def main():
    """Main function to handle spot instance startup."""
    logger.info("Spot instance startup monitor is running")

    # Wait a bit for all network services to be fully initialized
    time.sleep(10)

    # Get IMDSv2 token
    token = get_metadata_token()
    if not token:
        logger.error("Failed to get metadata token. Exiting.")
        return 1

    # Gather instance information
    instance_info = {
        "instance_id": get_instance_metadata(token, INSTANCE_ID_URL),
        "instance_type": get_instance_metadata(token, INSTANCE_TYPE_URL),
        "public_ip": get_instance_metadata(token, PUBLIC_IP_URL),
        "private_ip": get_instance_metadata(token, PRIVATE_IP_URL),
        "az": get_instance_metadata(token, AZ_URL),
        "lifecycle": get_instance_metadata(token, INSTANCE_LIFECYCLE_URL),
        "hostname": socket.gethostname(),
    }

    # Log the instance information
    logger.info(f"Instance ID: {instance_info['instance_id']}")
    logger.info(f"Instance Type: {instance_info['instance_type']}")
    logger.info(f"Lifecycle: {instance_info['lifecycle']}")
    logger.info(f"Public IP: {instance_info['public_ip']}")
    logger.info(f"Private IP: {instance_info['private_ip']}")

    # Only proceed if this is a spot instance
    if instance_info["lifecycle"] != "spot":
        logger.info("This is not a spot instance. No need to send notifications.")
        return 0

    # Send email notification
    email_sent = send_startup_email(instance_info)
    if not email_sent:
        logger.warning("Failed to send startup email notification")

    # Run the custom script
    script_success = run_custom_script()
    if not script_success:
        logger.warning("Custom script execution failed")

    logger.info("Spot instance startup processing complete")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
