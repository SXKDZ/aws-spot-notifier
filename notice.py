import json
import os
import time
import logging
import signal
import sys
import socket
from datetime import datetime

import requests

from config import (
    METADATA_SPOT_URL,
    INSTANCE_ID_URL,
    INSTANCE_TYPE_URL,
    PUBLIC_IP_URL,
    PRIVATE_IP_URL,
    TOKEN_TTL_SECONDS,
    CHECK_INTERVAL,
    LOG_DIR,
    get_metadata_token,
    get_instance_metadata,
    send_email,
)

# Configure logging
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "spot_termination_monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def check_for_termination_notice(token):
    """Check the instance metadata service for a spot interruption notice.

    Uses the spot/instance-action endpoint which covers all interruption
    types: terminate, stop, and hibernate.

    Returns a dict with 'action' and 'time' keys on notice, or None.
    """
    if not token:
        logger.error("No valid token available for metadata service")
        return None

    try:
        response = requests.get(
            METADATA_SPOT_URL,
            headers={"X-aws-ec2-metadata-token": token},
            timeout=2,
        )

        if response.status_code == 200:
            notice = json.loads(response.text)
            logger.warning(
                f"Spot instance interruption notice received! "
                f"Action: {notice['action']}, Time: {notice['time']}"
            )
            return notice
        elif response.status_code == 404:
            return None
        else:
            logger.error(
                f"Unexpected status code checking interruption: {response.status_code}"
            )
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking for interruption notice: {e}")
        return None


def handle_interruption(token, notice):
    """Handle the spot instance interruption by sending an alert email.

    Returns True if the email was sent successfully.
    """
    action = notice["action"]
    action_time = notice["time"]

    logger.warning(f"Starting interruption handling (action={action})...")

    instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
    instance_type = get_instance_metadata(token, INSTANCE_TYPE_URL)
    public_ip = get_instance_metadata(token, PUBLIC_IP_URL)
    private_ip = get_instance_metadata(token, PRIVATE_IP_URL)
    hostname = socket.gethostname()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = f"⚠️ ALERT: AWS Spot Instance {action.title()} Notice - {instance_id}"
    body = f"""\
SPOT INSTANCE INTERRUPTION NOTICE

Time of Notice: {current_time}
Action: {action}
Scheduled Time: {action_time}

INSTANCE DETAILS:
- Instance ID: {instance_id}
- Instance Type: {instance_type}
- Public IP: {public_ip}
- Private IP: {private_ip}
- Hostname: {hostname}

AWS will {action} this spot instance at {action_time}.
Please take any necessary actions to save data or migrate services.

This is an automated message from the Spot Interruption Monitor.
"""

    success = send_email(subject, body)
    if success:
        logger.info("Interruption email sent successfully")
    else:
        logger.error("Failed to send interruption email")
    return success


def run_interruption_monitor():
    """Main loop: continuously monitor for spot interruption notices."""
    logger.info("Starting spot instance interruption monitor (IMDSv2)")

    token = None
    last_token_time = 0
    email_sent = False

    try:
        while True:
            try:
                current_time = time.time()
                if token is None or (
                    current_time - last_token_time > TOKEN_TTL_SECONDS - 60
                ):
                    token = get_metadata_token()
                    if token:
                        last_token_time = current_time
                        if not email_sent:
                            instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
                            instance_type = get_instance_metadata(
                                token, INSTANCE_TYPE_URL
                            )
                            logger.info(
                                f"Monitoring spot instance: {instance_id} ({instance_type})"
                            )
                    else:
                        time.sleep(CHECK_INTERVAL)
                        continue

                notice = check_for_termination_notice(token)
                if notice and not email_sent:
                    if handle_interruption(token, notice):
                        email_sent = True
                elif notice and email_sent:
                    logger.info(
                        f"Interruption notice still active "
                        f"(action={notice['action']}, time={notice['time']})"
                    )

            except Exception as e:
                logger.error(
                    f"Error in monitor loop (will retry): {e}", exc_info=True
                )

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Interruption monitor stopped by user")
    finally:
        logger.info("Interruption monitor shutting down")


def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, shutting down gracefully")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_interruption_monitor()
