#!/bin/bash

# AWS Spot Instance Notification System - Bootstrap Script
# This is a minimal script to download and run the full installer

set -e

# Configuration
GITHUB_USER="SXKDZ"
GITHUB_REPO="aws-spot-notifier"
BRANCH="main"
INSTALL_SCRIPT_URL="https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${BRANCH}/install.sh"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Download and run the installer
echo -e "${GREEN}Downloading AWS Spot Instance Notification System installer...${NC}"

# Create temp file
TEMP_INSTALLER=$(mktemp /tmp/aws-spot-installer.XXXXXX.sh)
trap 'rm -f "$TEMP_INSTALLER"' EXIT

# Download with curl or wget
if command -v curl >/dev/null 2>&1; then
    curl -sSL "$INSTALL_SCRIPT_URL" -o "$TEMP_INSTALLER"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TEMP_INSTALLER" "$INSTALL_SCRIPT_URL"
else
    echo -e "${RED}Error: Neither curl nor wget is available. Please install one of them.${NC}"
    exit 1
fi

# Make executable and run
chmod +x "$TEMP_INSTALLER"
bash "$TEMP_INSTALLER"