# DeniDin Bot - Production Deployment Guide

**Last Updated**: January 17, 2026  
**Version**: Phase 6 (US4 - Configuration & Deployment)

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Server Requirements](#server-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running as a System Service](#running-as-a-system-service)
6. [Log Monitoring](#log-monitoring)
7. [Green API Webhook Setup](#green-api-webhook-setup)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python**: 3.9 or higher
- **Green API Account**: Active WhatsApp Business account via Green API
- **OpenAI API Key**: Valid OpenAI API key with sufficient credits
- **Operating System**: Linux (Ubuntu 20.04+ or similar) recommended for production

---

## Server Requirements

### Recommended Cloud VM Specifications

For production deployment, use a cloud VM with the following minimum specifications:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU      | 1 vCPU  | 2 vCPU      |
| RAM      | 1 GB    | 2 GB        |
| Storage  | 10 GB   | 20 GB       |
| Network  | 1 Mbps  | 5 Mbps      |

**Supported Cloud Providers**:
- AWS EC2 (t2.micro or t3.micro)
- Google Cloud Compute Engine (e2-micro or e2-small)
- Azure Virtual Machines (B1s or B1ms)
- DigitalOcean Droplets ($6/month tier)
- Linode (Nanode 1GB or 2GB)

---

## Installation

### 1. Clone Repository

```bash
cd /opt
sudo git clone https://github.com/yylevy171/DeniDin.git
cd DeniDin/denidin-bot
```

### 2. Install Python Dependencies

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
python3 -c "import whatsapp_chatbot_python; import openai; print('Dependencies OK')"
```

---

## Configuration

### 1. Create Configuration File

Copy the example configuration and edit with your credentials:

```bash
cp config/config.example.json config/config.json
chmod 600 config/config.json  # Restrict permissions
```

### 2. Edit config.json

```json
{
  "green_api_instance_id": "YOUR_INSTANCE_ID",
  "green_api_token": "YOUR_API_TOKEN",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "ai_model": "gpt-4o-mini",
  "system_message": "You are a helpful assistant.",
  "max_tokens": 1000,
  "temperature": 0.7,
  "log_level": "INFO",
  "poll_interval_seconds": 5,
  "max_retries": 3
}
```

### 3. Required Fields

The following fields are **REQUIRED** and must be present:

- `green_api_instance_id`: Your Green API instance ID (from Green API console)
- `green_api_token`: Your Green API token (from Green API console)
- `openai_api_key`: Your OpenAI API key (from OpenAI console)

All other fields have sensible defaults if omitted.

### 4. Validate Configuration

Test your configuration before deployment:

```bash
python3 -c "from src.models.config import BotConfiguration; c = BotConfiguration.from_file('config/config.json'); c.validate(); print('Config OK')"
```

---

## Running as a System Service

For production, run DeniDin as a systemd service to ensure automatic startup and restart on failure.

### 1. Create systemd Service File

Create `/etc/systemd/system/denidin.service`:

```ini
[Unit]
Description=DeniDin WhatsApp AI Chatbot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=denidin
Group=denidin
WorkingDirectory=/opt/DeniDin/denidin-bot
Environment="PATH=/opt/DeniDin/denidin-bot/venv/bin"
ExecStart=/opt/DeniDin/denidin-bot/venv/bin/python3 /opt/DeniDin/denidin-bot/denidin.py

# Alternative: Use management scripts for single-instance enforcement
# ExecStart=/opt/DeniDin/denidin-bot/run_denidin.sh
# ExecStop=/opt/DeniDin/denidin-bot/stop_denidin.sh

# Restart policy
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/DeniDin/denidin-bot/logs /opt/DeniDin/denidin-bot/state

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=denidin

[Install]
WantedBy=multi-user.target
```

### 2. Create Dedicated User (Recommended)

```bash
sudo useradd -r -s /bin/false denidin
sudo chown -R denidin:denidin /opt/DeniDin/denidin-bot
```

### 3. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable denidin.service
sudo systemctl start denidin.service
```

### 4. Check Service Status

```bash
sudo systemctl status denidin.service
```

### 5. View Service Logs

```bash
# Follow live logs
sudo journalctl -u denidin.service -f

# View recent logs
sudo journalctl -u denidin.service -n 100
```

---

## Log Monitoring

### Application Logs

DeniDin writes logs to `logs/denidin.log` with automatic rotation:

- **Max File Size**: 10 MB
- **Backup Count**: 5 files (.1, .2, .3, .4, .5)
- **Log Format**: `YYYY-MM-DD HH:MM:SS - module - LEVEL - message`

### Monitor Logs in Real-Time

```bash
# Follow application logs
tail -f /opt/DeniDin/denidin-bot/logs/denidin.log

# Follow with grep filtering
tail -f /opt/DeniDin/denidin-bot/logs/denidin.log | grep ERROR

# View last 100 lines
tail -n 100 /opt/DeniDin/denidin-bot/logs/denidin.log
```

### Log Levels

- **INFO**: Standard operations (recommended for production)
- **DEBUG**: Detailed debugging information (use for troubleshooting)

Set log level in `config/config.json`:

```json
{
  "log_level": "INFO"
}
```

### Message Tracking in Logs

All log messages related to WhatsApp messages include tracking information:

```
[msg_id=550e8400-e29b-41d4-a716-446655440000] [recv_ts=2026-01-17T10:30:45.123456+00:00] Received message from John Doe
```

This allows you to trace the entire lifecycle of each message through the logs.

---

## Green API Webhook Setup

For production deployments, configure webhooks for real-time message delivery (optional - polling is used by default).

### Current Mode: Polling

DeniDin uses **polling mode** by default:
- Polls Green API every 5 seconds (configurable via `poll_interval_seconds`)
- No webhook configuration needed
- Works behind firewalls and NAT
- Slight delay in message processing (5-10 seconds)

### Future: Webhook Mode (Advanced)

If you want real-time message delivery, you can set up webhooks:

1. **Expose your server** with a public IP or domain
2. **Configure SSL/TLS** certificate for HTTPS
3. **Set webhook URL** in Green API console:
   ```
   https://your-domain.com/webhook/greenapi
   ```
4. **Update bot code** to use webhook receiver instead of polling

> **Note**: Webhook mode is not yet implemented. Current version uses polling only.

---

## Security Best Practices

### 1. Protect config.json

The configuration file contains sensitive API keys. Protect it:

```bash
# Set restrictive permissions (owner read/write only)
chmod 600 config/config.json

# Verify permissions
ls -l config/config.json
# Should show: -rw------- (600)

# Set correct ownership
sudo chown denidin:denidin config/config.json
```

### 2. Encrypt Configuration (Optional)

For enhanced security, consider encrypting config.json:

```bash
# Encrypt with GPG
gpg -c config/config.json
# Creates config/config.json.gpg

# Decrypt before running bot
gpg -d config/config.json.gpg > config/config.json
```

### 3. Use Environment Variables (Alternative)

Set `CONFIG_PATH` environment variable to specify config location:

```bash
export CONFIG_PATH=/etc/denidin/config.json
./run_denidin.sh
# Or manually:
python3 denidin.py
```

### 4. Firewall Configuration

Restrict inbound connections (only allow SSH):

```bash
# Ubuntu/Debian
sudo ufw allow 22/tcp
sudo ufw enable

# Verify
sudo ufw status
```

### 5. Keep Secrets Out of Git

**NEVER commit config.json to version control!**

The `.gitignore` file already excludes it, but verify:

```bash
grep config.json .gitignore
# Should show: config/config.json
```

### 6. Rotate API Keys Regularly

- Change OpenAI API key every 90 days
- Change Green API token if compromised
- Update config.json and restart service

### 7. Monitor for Unauthorized Access

```bash
# Check systemd logs for failed starts
sudo journalctl -u denidin.service | grep -i "error\|failed"

# Monitor authentication attempts
tail -f /var/log/auth.log
```

---

## Troubleshooting

### Bot Won't Start

**Check service status:**
```bash
sudo systemctl status denidin.service
```

**Check logs:**
```bash
sudo journalctl -u denidin.service -n 50
```

**Common issues:**
- Missing config.json → Create from config.example.json
- Invalid API keys → Verify credentials in Green API and OpenAI consoles
- Python dependencies missing → Run `pip install -r requirements.txt`

### Configuration Errors

**Validate config:**
```bash
python3 -c "from src.models.config import BotConfiguration; BotConfiguration.from_file('config/config.json').validate()"
```

**Common errors:**
- `ValueError: Missing required field` → Add required field to config.json
- `ValueError: temperature must be between 0.0 and 1.0` → Fix temperature value
- `ValueError: poll_interval_seconds must be >= 1` → Fix poll interval

### No Messages Received

**Check Green API connection:**
```bash
# In Python
python3 -c "from whatsapp_chatbot_python import GreenAPIBot; bot = GreenAPIBot('INSTANCE_ID', 'TOKEN'); print('Connected')"
```

**Verify polling:**
- Check `poll_interval_seconds` in config.json
- Look for "Waiting for WhatsApp messages" in logs
- Ensure WhatsApp account is active and connected

### OpenAI API Errors

**Check API key:**
```bash
python3 -c "from openai import OpenAI; client = OpenAI(api_key='YOUR_KEY'); print('Connected')"
```

**Common errors:**
- Rate limit → Wait or upgrade OpenAI plan
- Insufficient credits → Add credits to OpenAI account
- Invalid API key → Regenerate key in OpenAI console

### High Memory Usage

**Monitor memory:**
```bash
top -p $(pgrep -f denidin.py)
```

**Reduce memory:**
- Set `max_tokens` to lower value (e.g., 500)
- Use `gpt-4o-mini` instead of larger models
- Restart service weekly: `sudo systemctl restart denidin.service`

### Disk Space Issues

**Check log size:**
```bash
du -h logs/
```

**Log rotation is automatic** (10MB max per file, 5 backups), but if needed:

```bash
# Manually archive old logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/denidin.log.*
rm logs/denidin.log.*
```

---

## Support

For issues and questions:

- **GitHub Issues**: https://github.com/yylevy171/DeniDin/issues
- **Documentation**: See `README.md` in project root
- **Logs**: Always include relevant logs from `logs/denidin.log` when reporting issues

---

**End of Deployment Guide**
