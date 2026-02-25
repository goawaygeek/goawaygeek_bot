# goawaygeek_bot

A personal Telegram bot that captures messages you send from your phone and stores them locally on a Raspberry Pi. Your own "second brain" — send it a thought, idea, or note anytime and it's saved.

## What It Does

- Listens for Telegram messages from **one authorized user** (you)
- Saves each message to a local log file with timestamps
- Replies "Saved." to confirm receipt
- Silently ignores messages from anyone else
- Auto-starts on Pi boot via systemd

## Prerequisites

- A Telegram account
- A Raspberry Pi (any model) with an SD card
- A computer to flash the SD card and develop on
- Python 3.9+ (3.11+ on the Pi)

## 1. Create Your Bot with BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a display name (e.g., "GoAwayGeek Bot")
4. Choose a username (must end in `bot`, e.g., `goawaygeek_bot`)
5. BotFather will give you an **API token** — save it, you'll need it for `.env`

## 2. Find Your Telegram User ID

1. Open Telegram and search for **@userinfobot**
2. Send `/start`
3. It will reply with your **numeric user ID** — save it for `.env`

## 3. Development Setup (Mac/Linux)

Requires [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/goawaygeek/goawaygeek_bot.git
cd goawaygeek_bot

# Create and activate virtual environment
uv venv venv
source venv/bin/activate

# Install dependencies
uv pip install -r requirements-dev.txt

# Create your config
cp .env.example .env
# Edit .env with your bot token and user ID
```

### Run Locally

```bash
python bot.py
```

Send a message to your bot on Telegram. You should get "Saved." back, and the message appears in `data/messages.log`.

### Run Tests

```bash
python -m pytest tests/ -v
```

## 4. Raspberry Pi Setup

### Flash the SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose **Raspberry Pi OS Lite (64-bit)** — no desktop needed
3. Click the gear icon to pre-configure:
   - Set hostname (e.g., `goawaygeek`)
   - Enable SSH with password authentication
   - Set username and password
   - Configure Wi-Fi (SSID and password)
4. Flash to your SD card

### First Boot

1. Insert the SD card and power on the Pi
2. Wait a couple of minutes for it to boot and connect to Wi-Fi
3. Find it on your network: `ping goawaygeek.local` (or check your router)
4. SSH in: `ssh scott@goawaygeek.local`

### Install Git

Pi OS Lite doesn't include git out of the box. Install it first:

```bash
sudo apt-get update && sudo apt-get install -y git
```

### Run the Setup Script

The `setup.sh` script handles everything: Tailscale, Python, dependencies, systemd.

```bash
# From your SSH session on the Pi:
git clone https://github.com/goawaygeek/goawaygeek_bot.git
cd goawaygeek_bot
bash setup.sh
```

The script will:
1. Update system packages
2. Install [Tailscale](https://tailscale.com/) for secure remote access
3. Install Python 3, git, and [uv](https://docs.astral.sh/uv/)
4. Create a virtual environment and install dependencies (via uv)
5. Prompt you to configure `.env` with your bot token and user ID
6. Install and start the systemd service

After setup, the bot starts automatically on every boot.

### Tailscale

Tailscale lets you SSH into your Pi from anywhere without port forwarding. After the setup script installs it:

```bash
sudo tailscale up
```

Follow the URL to authenticate. Once connected, you can SSH using the Tailscale IP:

```bash
ssh scott@100.x.x.x
```

## 5. Managing the Bot

```bash
# Check if it's running
sudo systemctl status goawaygeek_bot

# View live logs
sudo journalctl -u goawaygeek_bot -f

# Restart after changes
sudo systemctl restart goawaygeek_bot

# Stop the bot
sudo systemctl stop goawaygeek_bot

# Update to latest code
cd ~/goawaygeek_bot && git pull && uv pip install -r requirements.txt --python venv/bin/python && sudo systemctl restart goawaygeek_bot
```

## 6. Creating the GitHub Repository

If you're setting this up from scratch (not cloning an existing repo):

```bash
# Install GitHub CLI
# macOS:
brew install gh
# Debian/Ubuntu/Pi:
sudo apt install gh

# Authenticate
gh auth login

# Create the repo and push
cd goawaygeek_bot
git init
git add .
git commit -m "Initial commit: Telegram bot for personal knowledge capture"
gh repo create goawaygeek_bot --public --source=. --remote=origin --push \
    --description "Personal Telegram bot for knowledge capture - runs on Raspberry Pi"
```

## Project Structure

```
goawaygeek_bot/
├── bot.py                     # Main entry point — message handlers, polling loop
├── config.py                  # Loads and validates .env configuration
├── storage.py                 # Writes messages to file (designed for future upgrades)
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Test dependencies (includes production deps)
├── .env.example               # Template — copy to .env and fill in your values
├── .gitignore                 # Keeps secrets and data out of git
├── goawaygeek_bot.service     # systemd unit file for auto-start on Pi
├── setup.sh                   # One-script Pi provisioning
├── LICENSE                    # MIT
└── tests/
    ├── conftest.py            # Shared test fixtures
    ├── test_config.py         # Config validation tests
    ├── test_storage.py        # Storage format and file writing tests
    └── test_bot.py            # Bot handler and integration tests
```

## Troubleshooting

**Bot doesn't respond:**
- Check it's running: `sudo systemctl status goawaygeek_bot`
- Check logs: `sudo journalctl -u goawaygeek_bot -n 50`
- Verify `.env` has the correct `BOT_TOKEN` and `AUTHORIZED_USER_ID`

**"Error: BOT_TOKEN is not set" on startup:**
- Make sure `.env` exists in the project directory
- Make sure it contains `BOT_TOKEN=your-actual-token`

**Can't SSH into Pi:**
- Make sure the Pi is on the same network, or use Tailscale
- Try `ssh scott@goawaygeek.local` or the Pi's IP address

**Service fails after reboot:**
- Check `sudo journalctl -u goawaygeek_bot -b` for boot-time errors
- Network might not be ready — the service waits for `network-online.target` but Wi-Fi can be slow

## Future Ideas

- Search through saved messages
- Tag and categorize messages with `/tag`
- Multiple storage backends (SQLite, Markdown files)
- Export messages to other formats
- Voice message transcription
- Periodic summaries

## License

MIT — see [LICENSE](LICENSE) for details.
