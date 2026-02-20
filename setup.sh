#!/usr/bin/env bash
#
# Pi provisioning script for goawaygeek_bot
# Run this on a fresh Raspberry Pi OS Lite installation.
# Usage: bash setup.sh
#
set -e

REPO_URL="https://github.com/goawaygeek/goawaygeek_bot.git"
INSTALL_DIR="$HOME/goawaygeek_bot"
SERVICE_NAME="goawaygeek_bot"

echo "=== goawaygeek_bot Pi Setup ==="
echo ""

# --- 1. Update system packages ---
echo "[1/7] Updating system packages..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# --- 2. Install Tailscale ---
if command -v tailscale &>/dev/null; then
    echo "[2/7] Tailscale is already installed."
else
    echo "[2/7] Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

if ! tailscale status &>/dev/null; then
    echo ""
    echo ">>> Tailscale is installed but not connected."
    echo ">>> Run: sudo tailscale up"
    echo ">>> Authenticate in your browser, then re-run this script."
    echo ""
    read -p "Press Enter after you've run 'sudo tailscale up' and authenticated, or Ctrl+C to exit..."
fi

# --- 3. Install Python and git ---
echo "[3/7] Installing Python 3, python3-venv, and git..."
sudo apt-get install -y -qq python3 python3-venv python3-pip git

# --- 4. Clone the repository ---
if [ -d "$INSTALL_DIR" ]; then
    echo "[4/7] Repository already exists at $INSTALL_DIR. Pulling latest..."
    cd "$INSTALL_DIR" && git pull
else
    echo "[4/7] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# --- 5. Create virtual environment and install dependencies ---
echo "[5/7] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
echo "    Dependencies installed."

# --- 6. Configure .env ---
if [ ! -f ".env" ]; then
    echo ""
    echo "[6/7] Creating .env from template..."
    cp .env.example .env
    echo ""
    echo ">>> IMPORTANT: Edit .env with your bot token and user ID:"
    echo ">>>   nano $INSTALL_DIR/.env"
    echo ""
    read -p "Press Enter after you've configured .env, or Ctrl+C to exit and do it later..."
else
    echo "[6/7] .env already exists. Skipping."
fi

# --- 7. Install and enable systemd service ---
echo "[7/7] Installing systemd service..."

# Update the service file paths to match the current user and install directory
CURRENT_USER="$(whoami)"
sed -e "s|User=scott|User=$CURRENT_USER|" \
    -e "s|/home/scott/goawaygeek_bot|$INSTALL_DIR|g" \
    goawaygeek_bot.service | sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Bot status:"
sudo systemctl status ${SERVICE_NAME} --no-pager || true
echo ""
echo "Useful commands:"
echo "  Check status:  sudo systemctl status ${SERVICE_NAME}"
echo "  View logs:     sudo journalctl -u ${SERVICE_NAME} -f"
echo "  Restart:       sudo systemctl restart ${SERVICE_NAME}"
echo "  Stop:          sudo systemctl stop ${SERVICE_NAME}"
echo "  Update bot:    cd $INSTALL_DIR && git pull && sudo systemctl restart ${SERVICE_NAME}"
