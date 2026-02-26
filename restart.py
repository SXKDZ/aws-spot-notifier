import time
import logging
import os
import sys
import socket
import subprocess
from datetime import datetime

from config import (
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
    send_email,
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


def send_startup_email(instance_info):
    """Send email notification about the spot instance startup."""
    subject = f"✅ ALERT: AWS Spot Instance Restarted - {instance_info['instance_id']}"
    body = f"""\
SPOT INSTANCE RESTART NOTIFICATION

Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

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
    return send_email(subject, body)


def run_custom_script():
    """Run the specified script after startup."""
    if not os.path.exists(SCRIPT_TO_RUN):
        logger.error(f"Custom script not found at {SCRIPT_TO_RUN}")
        return False

    if not os.access(SCRIPT_TO_RUN, os.X_OK):
        logger.warning(
            f"Script is not executable, attempting to make it executable: {SCRIPT_TO_RUN}"
        )
        try:
            os.chmod(SCRIPT_TO_RUN, 0o755)
        except Exception as e:
            logger.error(f"Failed to make script executable: {e}")
            return False

    try:
        logger.info(f"Running custom script as detached process: {SCRIPT_TO_RUN}")
        process = subprocess.Popen(
            [SCRIPT_TO_RUN],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
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

    token = get_metadata_token()
    if not token:
        logger.error("Failed to get metadata token. Exiting.")
        return 1

    instance_info = {
        "instance_id": get_instance_metadata(token, INSTANCE_ID_URL),
        "instance_type": get_instance_metadata(token, INSTANCE_TYPE_URL),
        "public_ip": get_instance_metadata(token, PUBLIC_IP_URL),
        "private_ip": get_instance_metadata(token, PRIVATE_IP_URL),
        "az": get_instance_metadata(token, AZ_URL),
        "lifecycle": get_instance_metadata(token, INSTANCE_LIFECYCLE_URL),
        "hostname": socket.gethostname(),
    }

    logger.info(f"Instance ID: {instance_info['instance_id']}")
    logger.info(f"Instance Type: {instance_info['instance_type']}")
    logger.info(f"Lifecycle: {instance_info['lifecycle']}")
    logger.info(f"Public IP: {instance_info['public_ip']}")
    logger.info(f"Private IP: {instance_info['private_ip']}")

    if instance_info["lifecycle"] != "spot":
        logger.info("This is not a spot instance. No need to send notifications.")
        return 0

    if not send_startup_email(instance_info):
        logger.warning("Failed to send startup email notification")

    if not run_custom_script():
        logger.warning("Custom script execution failed")

    logger.info("Spot instance startup processing complete")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
