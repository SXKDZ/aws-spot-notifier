#!/bin/bash

# AWS Spot Instance Email Notification System - Uninstaller

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default app directory
DEFAULT_APP_DIR="/opt/aws-spot-notifier"

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       AWS Spot Instance Notification System - Uninstaller      ║${NC}"
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

main() {
    clear
    print_header

    # Determine app directory
    if [ -n "${1:-}" ]; then
        APP_DIR="$1"
    elif [ -d "$DEFAULT_APP_DIR" ]; then
        APP_DIR="$DEFAULT_APP_DIR"
    else
        echo -ne "${BLUE}?${NC} Enter installation directory: "
        read -r APP_DIR
    fi

    if [ ! -d "$APP_DIR" ]; then
        print_error "Installation directory not found: $APP_DIR"
        exit 1
    fi

    echo "This will completely remove the AWS Spot Instance Notification System from:"
    echo "  $APP_DIR"
    echo
    echo "The following will be removed:"
    echo "  • Systemd service (spot-startup)"
    echo "  • Running monitoring processes"
    echo "  • All application files"
    echo "  • Configuration files (including .env)"
    echo

    echo -ne "${BLUE}?${NC} Are you sure you want to uninstall? [y/N]: "
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi

    echo

    # Stop and unregister the service
    print_info "Stopping and removing systemd service..."
    if systemctl is-active spot-startup >/dev/null 2>&1; then
        sudo systemctl stop spot-startup >/dev/null 2>&1
    fi

    if [ -f "$APP_DIR/register.py" ]; then
        cd "$APP_DIR"
        python3 register.py unregister >/dev/null 2>&1 || true
    fi

    if [ -f /etc/systemd/system/spot-startup.service ]; then
        sudo systemctl disable spot-startup >/dev/null 2>&1 || true
        sudo rm -f /etc/systemd/system/spot-startup.service
        sudo systemctl daemon-reload
    fi
    print_success "Systemd service removed"

    # Stop any running monitors
    print_info "Stopping monitoring processes..."
    screen -S notice_monitor -X quit >/dev/null 2>&1 || true
    pkill -f notice.py >/dev/null 2>&1 || true
    print_success "Monitoring processes stopped"

    # Backup configuration if it exists
    if [ -f "$APP_DIR/.env" ]; then
        BACKUP_FILE="/tmp/aws-spot-notifier-env-backup-$(date +%Y%m%d-%H%M%S)"
        cp "$APP_DIR/.env" "$BACKUP_FILE"
        print_info "Configuration backed up to: $BACKUP_FILE"
    fi

    # Remove application directory
    print_info "Removing application files..."
    sudo rm -rf "$APP_DIR"
    print_success "Application files removed"

    echo
    print_success "AWS Spot Instance Notification System has been uninstalled successfully!"

    if [ -n "${BACKUP_FILE:-}" ]; then
        echo
        echo -e "${YELLOW}Note:${NC} Your configuration has been backed up to:"
        echo "  $BACKUP_FILE"
        echo "  You can restore it if you reinstall the system."
    fi

    echo
}

main "$@"