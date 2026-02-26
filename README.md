# AWS Spot Instance Email Notification System

Automated email notifications for spot instance termination and restart events.

## 🚀 Quick Start - One Line Installation

SSH into your EC2 instance and run:

```bash
curl -sSL https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh | bash
```

This interactive installer will guide you through the entire setup process. See [INSTALL_ONELINER.md](INSTALL_ONELINER.md) for detailed installation options.

## Features

- **Termination Alerts**: Sends email when AWS issues spot termination notice (2-minute warning)
- **Restart Notifications**: Sends email when instance restarts with new IP addresses
- **Auto-Recovery**: Automatically restarts monitoring after each instance reboot
- **Interactive Setup**: Simple one-line installation with guided configuration

## Email Recipients

Notifications are sent to the comma-separated list in `.env` via `RECIPIENT_EMAILS` (see `.env_sample`).

## Prerequisites

Before running the installer, make sure you have:

1. **AWS EC2 Spot Instance** - The system only sends notifications for spot instances
2. **Email credentials** - SMTP server details and login credentials
   - For Gmail: Use an [App Password](https://support.google.com/accounts/answer/185833)
   - For other providers: SMTP server address, port, username, and password
3. **SSH access** - You need to be logged into your EC2 instance
4. **sudo privileges** - The installer needs to install system packages

## What the Installer Does

1. **Detects your OS** - Works with Amazon Linux, Ubuntu, Debian, and RHEL-based systems
2. **Installs dependencies** - Automatically installs screen, git, python3, and pip
3. **Interactive configuration** - Guides you through setting up:
   - SMTP server details (with Gmail defaults)
   - Email credentials
   - Notification recipients
   - Monitoring intervals
4. **Sets up the system** - Automatically:
   - Clones the repository
   - Installs Python requirements
   - Creates systemd service
   - Starts monitoring immediately
   - Tests email configuration

## Installation Methods

### Method 1: One-Line Installation (Recommended)

SSH into your EC2 instance and run:

```bash
curl -sSL https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh | bash
```

Or if you prefer wget:

```bash
wget -qO- https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh | bash
```

### Method 2: Review Script First

If you prefer to review the script before running:

```bash
# Download the installer
curl -sSL https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh -o install.sh

# Review the script
less install.sh

# Make it executable and run
chmod +x install.sh
./install.sh
```

### Method 3: Custom Installation Directory

By default, the installer uses `/opt/aws-spot-notifier`. You can change this during the interactive setup, or set it beforehand:

```bash
export APP_DIR="/home/ec2-user/spot-notifier"
curl -sSL https://raw.githubusercontent.com/SXKDZ/aws-spot-notifier/main/install.sh | bash
```

### Method 4: Manual Installation

If you prefer manual installation:

#### 1. Choose Install Directory

Pick a location for the app (any path works):

```bash
APP_DIR=/opt/aws-spot-notifier
```

### 2. Upload or Clone

Upload the entire `restart` folder to your EC2 instance:

```bash
# On your local machine:
scp -r restart ec2-user@<instance-ip>:$APP_DIR

# If $APP_DIR requires sudo, upload to /tmp instead:
# scp -r restart ec2-user@<instance-ip>:/tmp/aws-spot-notifier
```

Or clone it directly on the instance:

```bash
git clone https://github.com/SXKDZ/aws-spot-notifier.git $APP_DIR
```

If you need sudo to write to `$APP_DIR`, upload to `/tmp` and move it after SSH.

### 3. SSH into EC2 Instance

```bash
ssh ec2-user@<instance-ip>
```

```bash
# Use the same install path you chose above
APP_DIR=/opt/aws-spot-notifier
```

If you uploaded to `/tmp`, move it now:

```bash
sudo mkdir -p "$APP_DIR"
sudo mv /tmp/aws-spot-notifier "$APP_DIR"
sudo chown -R ec2-user:ec2-user "$APP_DIR"
```

### 4. Install Dependencies

```bash
# Install screen (required for background monitoring)
sudo yum install screen -y

# Install Python dependencies
pip install -r $APP_DIR/requirements.txt
```

### 5. Configure Environment

Copy the sample env file and edit it with your SMTP credentials and recipients:

```bash
cp $APP_DIR/.env_sample $APP_DIR/.env
vi $APP_DIR/.env
```

`SCRIPT_TO_RUN` defaults to `$APP_DIR/script.sh` if not set.

### 6. Make Scripts Executable

```bash
chmod +x $APP_DIR/script.sh
```

### 7. Register Startup Service

```bash
cd $APP_DIR

# Register the systemd service
python3 register.py register --script-path $APP_DIR/restart.py

# Verify registration
python3 register.py status
```

### 8. Test the Setup

```bash
# Test the termination monitor manually
python3 $APP_DIR/notice.py
# Press Ctrl+C to stop after verifying it starts successfully

# Test the script.sh
$APP_DIR/script.sh

# Verify it's running in screen
screen -ls
# Should show: notice_monitor

# Attach to view logs (optional)
screen -r notice_monitor
# Detach with: Ctrl+A then D
```

## Email Provider Settings

### Gmail
- SMTP Server: `smtp.gmail.com`
- Port: `587`
- Authentication: Use [App Password](https://support.google.com/accounts/answer/185833) (not your regular password)
- Enable "Less secure app access" or use App Passwords

### Outlook/Office365
- SMTP Server: `smtp-mail.outlook.com`
- Port: `587`
- Authentication: Email and password

### Yahoo
- SMTP Server: `smtp.mail.yahoo.com`
- Port: `587` or `465`
- Authentication: Email and [App Password](https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html)

### AWS SES
- SMTP Server: `email-smtp.[region].amazonaws.com`
- Port: `587`
- Authentication: SMTP credentials (not IAM credentials)

## How It Works

1. **On Instance Start**:
   - `restart.py` runs automatically (systemd service)
   - Sends restart email with new IP addresses
   - Launches `script.sh`

2. **script.sh**:
   - Starts `notice.py` in a detached screen session
   - Keeps termination monitor running in background

3. **During Runtime**:
   - `notice.py` continuously monitors AWS metadata API
   - Sends termination email if spot termination notice detected

4. **Cycle Repeats**:
   - After instance restart, the process begins again automatically

## File Structure

```
$APP_DIR/
├── .env_sample         # Sample environment configuration
├── .env                # Environment configuration
├── config.py           # Configuration loader and utilities
├── notice.py           # Termination monitor (runs continuously)
├── restart.py          # Startup monitor (runs once on boot)
├── register.py         # Service registration tool
├── script.sh           # Launcher script
├── install.sh          # Interactive installer script
├── uninstall.sh        # Uninstallation script
└── README.md           # This file
```

## Verification

### Check Service Status
```bash
python3 $APP_DIR/register.py status
```

### Check if Monitor is Running
```bash
screen -ls | grep notice_monitor
ps aux | grep notice.py
```

### View Monitor Logs
```bash
screen -r notice_monitor
# Detach with: Ctrl+A then D
```

### Check Startup Logs
```bash
sudo journalctl -u spot-startup -n 50
```

## Troubleshooting

### Monitor not running after reboot
```bash
# Check if startup service ran
sudo journalctl -u spot-startup -n 50

# Manually start the monitor
$APP_DIR/script.sh
```

### Email not sending
- Verify SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password
- Check AWS Security Group allows outbound port 587
- Review logs for error messages
- The system now includes automatic retry (3 attempts) for failed emails

### Service registration failed
```bash
# Ensure you have sudo privileges
sudo systemctl daemon-reload

# Re-register the service
cd $APP_DIR
python3 register.py unregister
python3 register.py register --script-path $APP_DIR/restart.py
```

## Uninstall

To completely remove the system, use the provided uninstall script:

```bash
/opt/aws-spot-notifier/uninstall.sh
```

Or if you installed in a custom directory:

```bash
/path/to/your/installation/uninstall.sh
```

The uninstaller will:
- Stop and remove the systemd service
- Terminate monitoring processes
- Backup your configuration to `/tmp`
- Remove all application files

## Updating

To update to the latest version:

```bash
cd /opt/aws-spot-notifier
git pull origin main
pip3 install -r requirements.txt
sudo systemctl restart spot-startup
```

## Tips & Best Practices

- Run the installer in a `screen` or `tmux` session to prevent disconnection issues
- Keep a backup of your `.env` file: `cp /opt/aws-spot-notifier/.env ~/spot-notifier-env-backup`
- For production use, consider using AWS SES for better deliverability
- The system only monitors for termination on actual Spot instances, not On-Demand instances
- Test your setup periodically to ensure emails are being delivered

## Notes

- This system only activates for spot instances (not on-demand)
- Termination notices typically provide 2 minutes warning
- Email notifications require outbound SMTP access (port 587)
- Gmail and Yahoo require App Passwords instead of regular passwords
