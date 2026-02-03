# AWS Spot Instance Email Notification System

Automated email notifications for spot instance termination and restart events.

## Features

- **Termination Alerts**: Sends email when AWS issues spot termination notice (2-minute warning)
- **Restart Notifications**: Sends email when instance restarts with new IP addresses
- **Auto-Recovery**: Automatically restarts monitoring after each instance reboot

## Email Recipients

Notifications are sent to the comma-separated list in `.env` via `RECIPIENT_EMAILS` (see `.env_sample`).

## Installation

### 1. Choose Install Directory

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
├── notice.py           # Termination monitor (runs continuously)
├── restart.py          # Startup monitor (runs once on boot)
├── register.py         # Service registration tool
├── script.sh           # Launcher script
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
- Review logs for error messages

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

```bash
# Unregister the service
cd $APP_DIR
python3 register.py unregister

# Stop any running monitors
screen -S notice_monitor -X quit

# Remove files
rm -rf $APP_DIR
```

## Notes

- This system only activates for spot instances (not on-demand)
- Termination notices typically provide 2 minutes warning
- Email notifications require outbound SMTP access (port 587)
