#!/bin/bash

# AWS Spot Instance Email Notification System - Interactive Installer
# Run with: curl -sSL https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh -o /tmp/spot-install.sh && bash /tmp/spot-install.sh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_APP_DIR="/opt/aws-spot-notifier"
DEFAULT_SMTP_PORT="587"
DEFAULT_CHECK_INTERVAL="5"
DEFAULT_TOKEN_TTL="21600"
GITHUB_REPO="https://github.com/SXKDZ/aws-spot-notifier.git"

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      AWS Spot Instance Email Notification System Installer     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local response

    echo -ne "${BLUE}?${NC} $prompt [$default]: "
    read -r response
    if [ -z "$response" ]; then
        printf -v "$var_name" '%s' "$default"
    else
        printf -v "$var_name" '%s' "$response"
    fi
}

prompt_password() {
    local prompt="$1"
    local var_name="$2"
    local response

    echo -ne "${BLUE}?${NC} $prompt: "
    read -rs response
    echo
    printf -v "$var_name" '%s' "$response"
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_FAMILY=$ID_LIKE
    else
        print_error "Cannot detect operating system"
        exit 1
    fi
}

check_python() {
    print_info "Checking Python environment..."

    # Check if /usr/bin/python3 exists (required for systemd service)
    if [ ! -x /usr/bin/python3 ]; then
        print_error "/usr/bin/python3 not found - systemd service will not work"
        exit 1
    fi

    # Show which Python will be used
    PYTHON_VERSION=$(/usr/bin/python3 --version 2>&1)
    print_info "Using Python: $PYTHON_VERSION"

    # Check if pip is available for this Python
    if ! /usr/bin/python3 -m pip --version >/dev/null 2>&1; then
        print_error "pip not available for /usr/bin/python3"
        print_info "Installing pip..."
        curl -sS https://bootstrap.pypa.io/get-pip.py | /usr/bin/python3
    fi
}

install_dependencies() {
    print_info "Installing system dependencies..."

    if [[ "$OS_FAMILY" == *"rhel"* ]] || [[ "$OS" == "amzn" ]]; then
        sudo yum update -y >/dev/null 2>&1 || true
        if ! sudo yum install -y git screen python3 python3-pip 2>&1; then
            print_error "Failed to install dependencies via yum"
            exit 1
        fi
    elif [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        sudo apt-get update -y >/dev/null 2>&1 || true
        if ! sudo apt-get install -y git screen python3 python3-pip 2>&1; then
            print_error "Failed to install dependencies via apt"
            exit 1
        fi
    else
        print_error "Unsupported OS: $OS"
        exit 1
    fi

    print_success "System dependencies installed"
}

check_aws_instance() {
    print_info "Checking if running on AWS EC2..."

    # Use IMDSv2 token-based authentication
    local token
    token=$(curl -s -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null) || true

    if [ -n "$token" ]; then
        local imds_header="X-aws-ec2-metadata-token: $token"
        INSTANCE_ID=$(curl -s -H "$imds_header" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null)
        INSTANCE_TYPE=$(curl -s -H "$imds_header" http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null)
        print_success "Running on AWS EC2 instance: $INSTANCE_ID ($INSTANCE_TYPE)"

        # Check if it's a spot instance
        local lifecycle
        lifecycle=$(curl -s -H "$imds_header" http://169.254.169.254/latest/meta-data/instance-life-cycle 2>/dev/null) || true
        if [ "$lifecycle" = "spot" ]; then
            print_success "This is a Spot instance - perfect!"
        else
            print_info "This is not a Spot instance - notifications will only work on Spot instances"
        fi
    else
        print_info "Not running on AWS EC2 - assuming local testing environment"
    fi
}

setup_application() {
    print_info "Setting up application directory..."

    # Create directory if it doesn't exist
    if [ ! -d "$APP_DIR" ]; then
        sudo mkdir -p "$APP_DIR"
    fi

    # Clone or download the repository
    if [ -d "$APP_DIR/.git" ]; then
        print_info "Repository already exists, pulling latest changes..."
        cd "$APP_DIR"
        sudo git pull origin main >/dev/null 2>&1
    else
        print_info "Cloning repository..."
        sudo git clone "$GITHUB_REPO" "$APP_DIR" >/dev/null 2>&1
    fi

    # Set proper ownership
    sudo chown -R "$(whoami):$(whoami)" "$APP_DIR"

    print_success "Application files ready"
}

configure_environment() {
    print_header
    echo -e "${GREEN}Configuration Setup${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    echo

    # SMTP Configuration
    echo -e "${YELLOW}Email Server Configuration:${NC}"
    prompt_with_default "SMTP Server (e.g., smtp.gmail.com)" "smtp.gmail.com" SMTP_SERVER
    prompt_with_default "SMTP Port" "$DEFAULT_SMTP_PORT" SMTP_PORT
    prompt_with_default "Sender Email" "" SENDER_EMAIL

    while [ -z "$SENDER_EMAIL" ]; do
        print_error "Sender email is required"
        prompt_with_default "Sender Email" "" SENDER_EMAIL
    done

    prompt_password "Sender Password (or App Password for Gmail)" SENDER_PASSWORD

    while [ -z "$SENDER_PASSWORD" ]; do
        print_error "Password is required"
        prompt_password "Sender Password (or App Password for Gmail)" SENDER_PASSWORD
    done

    echo
    echo -e "${YELLOW}Notification Recipients:${NC}"
    prompt_with_default "Recipient Emails (comma-separated)" "$SENDER_EMAIL" RECIPIENT_EMAILS

    echo
    echo -e "${YELLOW}Monitoring Configuration:${NC}"
    prompt_with_default "Check Interval (seconds)" "$DEFAULT_CHECK_INTERVAL" CHECK_INTERVAL
    prompt_with_default "Token TTL (seconds)" "$DEFAULT_TOKEN_TTL" TOKEN_TTL_SECONDS

    # Write .env file
    cat > "$APP_DIR/.env" << EOF
# Email configuration
SMTP_SERVER=$SMTP_SERVER
SMTP_PORT=$SMTP_PORT
SENDER_EMAIL=$SENDER_EMAIL
SENDER_PASSWORD=$SENDER_PASSWORD
RECIPIENT_EMAILS=$RECIPIENT_EMAILS

# Monitoring configuration
TOKEN_TTL_SECONDS=$TOKEN_TTL_SECONDS
CHECK_INTERVAL=$CHECK_INTERVAL

# Paths
SCRIPT_TO_RUN=$APP_DIR/script.sh
LOG_DIR=/var/log
EOF

    chmod 600 "$APP_DIR/.env"
    print_success "Configuration saved to $APP_DIR/.env"
}

install_python_deps() {
    print_info "Installing Python dependencies..."

    cd "$APP_DIR"

    # The systemd service uses /usr/bin/python3, so we must install packages for that exact Python
    # to avoid version mismatches
    if [ -x /usr/bin/python3 ]; then
        print_info "Installing for system Python (/usr/bin/python3)..."
        /usr/bin/python3 -m pip install -r requirements.txt 2>&1 | tail -5
    else
        print_info "Installing with default pip3..."
        pip3 install -r requirements.txt 2>&1 | tail -5
    fi

    print_success "Python dependencies installed"
}

setup_service() {
    print_info "Setting up systemd service..."

    cd "$APP_DIR"
    chmod +x "$APP_DIR/script.sh"

    # Register the service using the same Python that systemd will use
    /usr/bin/python3 register.py register --script-path "$APP_DIR/restart.py" >/dev/null 2>&1

    # Enable and start the service
    sudo systemctl enable spot-startup >/dev/null 2>&1
    sudo systemctl start spot-startup >/dev/null 2>&1

    print_success "Systemd service configured and started"
}

test_setup() {
    print_header
    echo -e "${GREEN}Testing Installation${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    echo

    # Test email configuration
    print_info "Testing email configuration..."
    /usr/bin/python3 -c "
import smtplib, sys
sys.path.insert(0, '$APP_DIR')
from config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD

try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.quit()
    print('Email configuration is valid')
except Exception as e:
    print(f'Email configuration error: {e}')
    sys.exit(1)
" && print_success "Email configuration verified" || print_error "Email configuration failed - please check credentials"

    # Check if monitoring is running
    sleep 2
    if screen -ls | grep -q notice_monitor; then
        print_success "Monitoring process is running"
    else
        print_info "Starting monitoring process..."
        "$APP_DIR/script.sh" >/dev/null 2>&1
        sleep 2
        if screen -ls | grep -q notice_monitor; then
            print_success "Monitoring process started successfully"
        else
            print_error "Failed to start monitoring process"
        fi
    fi

    # Check service status
    if systemctl is-active spot-startup >/dev/null 2>&1; then
        print_success "Systemd service is active"
    else
        print_error "Systemd service is not active"
    fi
}

print_completion() {
    print_header
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    echo
    echo -e "${GREEN}✓${NC} AWS Spot Instance Notification System has been installed successfully!"
    echo
    echo -e "${YELLOW}Important Commands:${NC}"
    echo "  • Check service status:     python3 $APP_DIR/register.py status"
    echo "  • View monitor logs:        screen -r notice_monitor"
    echo "  • Check startup logs:       sudo journalctl -u spot-startup -n 50"
    echo "  • Edit configuration:       vi $APP_DIR/.env"
    echo "  • Uninstall:                $APP_DIR/uninstall.sh"
    echo
    echo -e "${YELLOW}What happens next:${NC}"
    echo "  1. The system is now monitoring for spot termination notices"
    echo "  2. You'll receive an email when a termination notice is detected"
    echo "  3. After instance restart, you'll get an email with new IP addresses"
    echo "  4. The monitoring will automatically resume after each restart"
    echo
    echo -e "${BLUE}Documentation:${NC} https://github.com/SXKDZ/aws-spot-notifier"
    echo
}

main() {
    clear
    print_header

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this installer as root"
        exit 1
    fi

    echo "This installer will set up the AWS Spot Instance Email Notification System"
    echo "on your EC2 instance. It will:"
    echo "  • Install required dependencies (screen, python3)"
    echo "  • Configure email notifications"
    echo "  • Set up automatic monitoring"
    echo "  • Register a systemd service for auto-start"
    echo

    echo -ne "${BLUE}?${NC} Continue with installation? [Y/n]: "
    read -r CONTINUE
    if [[ "$CONTINUE" =~ ^[Nn]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi

    echo
    detect_os
    check_python
    check_aws_instance

    echo
    prompt_with_default "Installation directory" "$DEFAULT_APP_DIR" APP_DIR

    install_dependencies
    setup_application
    configure_environment
    install_python_deps
    setup_service
    test_setup
    print_completion
}

# Run main function
main "$@"
