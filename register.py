#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import tempfile

SPOT_STARTUP_SERVICE_NAME = "spot-startup"
SPOT_STARTUP_SERVICE_PATH = f"/etc/systemd/system/{SPOT_STARTUP_SERVICE_NAME}.service"


def run_command(cmd, capture_output=True):
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=capture_output, text=True
        )
        return True, result.stdout if capture_output else ""
    except subprocess.CalledProcessError as e:
        return False, e.stderr if capture_output else str(e)


def manage_systemd(action, service_name):
    """Manage systemd services."""
    cmd = f"sudo systemctl {action} {service_name}"
    return run_command(cmd)


def register_spot_startup_service(script_path="/usr/local/bin/spot_startup_monitor.py"):
    """Register the spot-startup service."""
    print(f"Registering {SPOT_STARTUP_SERVICE_NAME} service...")

    # Make sure the script exists
    if not os.path.exists(script_path):
        return False, f"Script not found at {script_path}"

    # Define the service content
    service_content = f"""[Unit]
Description=AWS Spot Instance Startup Monitor
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {script_path}
RemainAfterExit=true
User=root
Group=root

[Install]
WantedBy=multi-user.target
"""

    try:
        # Write the service file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(service_content)
            temp_file_path = temp_file.name

        # Move the file to the systemd directory (requires sudo)
        success, msg = run_command(
            f"sudo mv {temp_file_path} {SPOT_STARTUP_SERVICE_PATH}"
        )
        if not success:
            return False, f"Failed to create service file: {msg}"

        # Set proper permissions
        success, msg = run_command(f"sudo chmod 644 {SPOT_STARTUP_SERVICE_PATH}")
        if not success:
            return False, f"Failed to set permissions: {msg}"

        # Reload systemd daemon
        success, msg = run_command("sudo systemctl daemon-reload")
        if not success:
            return False, f"Failed to reload systemd: {msg}"

        # Enable the service
        success, msg = run_command(f"sudo systemctl enable {SPOT_STARTUP_SERVICE_NAME}")
        if not success:
            return False, f"Failed to enable service: {msg}"

        return True, f"Service {SPOT_STARTUP_SERVICE_NAME} registered successfully"

    except Exception as e:
        return False, f"Error registering service: {str(e)}"


def unregister_service(service_name):
    """Unregister a systemd service."""
    print(f"Unregistering {service_name} service...")

    # Stop the service if it's running
    manage_systemd("stop", service_name)

    # Disable the service
    success, msg = manage_systemd("disable", service_name)
    if not success:
        print(f"Warning: Failed to disable service: {msg}")

    # Remove the service file
    service_path = f"/etc/systemd/system/{service_name}.service"
    success, msg = run_command(f"sudo rm -f {service_path}")
    if not success:
        return False, f"Failed to remove service file: {msg}"

    # Reload systemd daemon
    success, msg = run_command("sudo systemctl daemon-reload")
    if not success:
        return False, f"Failed to reload systemd: {msg}"

    return True, f"Service {service_name} unregistered successfully"


def get_service_status(service_name):
    """Get the status of a systemd service."""
    cmd = f"sudo systemctl is-active {service_name}"
    is_active, status = run_command(cmd)

    cmd = f"sudo systemctl is-enabled {service_name}"
    is_enabled, enabled_status = run_command(cmd)

    if not is_active:
        status = "inactive"
    if not is_enabled:
        enabled_status = "disabled"

    return f"Service: {service_name}\nActive: {status.strip()}\nEnabled: {enabled_status.strip()}"


def main():
    parser = argparse.ArgumentParser(description="Manage spot startup systemd service")
    parser.add_argument(
        "action", choices=["register", "unregister", "status"], help="Action to perform"
    )
    parser.add_argument(
        "--script-path",
        default="/usr/local/bin/spot_startup_monitor.py",
        help="Path to the startup monitor script (for register action)",
    )

    args = parser.parse_args()

    if args.action == "register":
        success, msg = register_spot_startup_service(args.script_path)
        print(msg)
        if not success:
            sys.exit(1)
    elif args.action == "unregister":
        success, msg = unregister_service(SPOT_STARTUP_SERVICE_NAME)
        print(msg)
        if not success:
            sys.exit(1)
    elif args.action == "status":
        print(get_service_status(SPOT_STARTUP_SERVICE_NAME))


if __name__ == "__main__":
    main()
