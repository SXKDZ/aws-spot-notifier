#!/usr/bin/env bash

# ============================================================================
# EXAMPLE: Custom restart script for ML training setup
# ============================================================================
# Copy this to user_script.sh on your instance:
#   cp user_script_example.sh user_script.sh
#   chmod +x user_script.sh
#
# Note: script.sh handles the termination monitor automatically.
# Only add YOUR commands here.
#
# This script runs as the FILE OWNER (e.g., ec2-user), not root.
# The systemd service detects the owner and uses 'sudo -i -u <owner>'
# so your login environment (conda, CUDA, etc.) is fully loaded.
# ============================================================================

# Change to your project directory
cd /home/ec2-user/retrosynthesis

# 1. Start the tool server in a screen session
screen -dmS server bash -c 'python3 -m tools.tool_server base_port=8100 num_instances=16'

# Wait for the server to initialize
sleep 180

# 2. Start the training in another screen session
screen -dmS train bash -c 'KL_COEF=0.00 ADV_ESTIMATOR=gspo bash slime_retro/scripts/train.sh'
ADV_ESTIMATOR=gspo bash slime_retro/scripts/train.sh