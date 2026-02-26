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
    get_metadata_token,
    get_instance_metadata,
    send_email,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_for_termination_notice(token):
    """Check the instance metadata service for a spot termination notice."""
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
            termination_time = response.text
            logger.warning(
                f"Spot instance termination notice received! "
                f"Termination time: {termination_time}"
            )
            return termination_time
        elif response.status_code == 404:
            return None
        else:
            logger.error(
                f"Unexpected status code checking termination: {response.status_code}"
            )
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking for termination notice: {e}")
        return None


def handle_termination(token, termination_time):
    """Handle the spot instance termination by sending an alert email."""
    logger.warning("Starting termination handling procedures...")

    instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
    instance_type = get_instance_metadata(token, INSTANCE_TYPE_URL)
    public_ip = get_instance_metadata(token, PUBLIC_IP_URL)
    private_ip = get_instance_metadata(token, PRIVATE_IP_URL)
    hostname = socket.gethostname()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = f"⚠️ ALERT: AWS Spot Instance Termination Notice - {instance_id}"
    body = f"""\
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

    send_email(subject, body)
    logger.info("Termination handling complete")


def run_termination_monitor():
    """Main loop: continuously monitor for termination notices."""
    logger.info("Starting spot instance termination monitor (IMDSv2)")

    token = None
    last_token_time = 0
    termination_handled = False

    try:
        while True:
            current_time = time.time()
            if token is None or (
                current_time - last_token_time > TOKEN_TTL_SECONDS - 60
            ):
                token = get_metadata_token()
                if token:
                    last_token_time = current_time
                    if not termination_handled:
                        instance_id = get_instance_metadata(token, INSTANCE_ID_URL)
                        instance_type = get_instance_metadata(token, INSTANCE_TYPE_URL)
                        logger.info(
                            f"Monitoring spot instance: {instance_id} ({instance_type})"
                        )
                else:
                    time.sleep(CHECK_INTERVAL)
                    continue

            termination_time = check_for_termination_notice(token)
            if termination_time and not termination_handled:
                handle_termination(token, termination_time)
                termination_handled = True
            elif termination_time and termination_handled:
                logger.info("Termination notice still active, time remaining...")

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
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_termination_monitor()
