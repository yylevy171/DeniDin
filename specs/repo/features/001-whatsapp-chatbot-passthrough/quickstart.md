# Quickstart Guide: WhatsApp AI Chatbot Passthrough

**Feature**: DeniDin WhatsApp AI Chatbot  
**Target Audience**: Developers setting up the bot for the first time  
**Time to Complete**: ~30 minutes

## Prerequisites

Before starting, ensure you have:

1. **Python 3.8+** installed (3.11 recommended)
   ```bash
   python --version
   # Should output: Python 3.8.x or higher
   ```

2. **Green API Account** with WhatsApp Business instance
   - Sign up at [console.green-api.com](https://console.green-api.com/en)
   - Create an instance and link your WhatsApp Business number
   - Note your `Instance ID` and `API Token`

3. **OpenAI API Key**
   - Sign up at [platform.openai.com](https://platform.openai.com)
   - Generate API key from [API Keys page](https://platform.openai.com/api-keys)
   - Note your API key (starts with `sk-`)

4. **Git** (optional, for cloning repository)

---

## Step 1: Project Setup (5 minutes)

### 1.1 Create Project Directory

```bash
mkdir denidin-bot
cd denidin-bot
```

### 1.2 Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Verify activation (you should see (venv) in prompt)
which python  # Should point to venv/bin/python
```

### 1.3 Create Project Structure

```bash
# Create directories
mkdir -p src/{handlers,models,utils} tests/{unit,integration,fixtures} config logs state

# Create __init__.py files
touch src/__init__.py
touch src/handlers/__init__.py
touch src/models/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
```

Your structure should look like:

```
denidin-bot/
├── src/
│   ├── __init__.py
│   ├── handlers/
│   ├── models/
│   └── utils/
├── tests/
├── config/
├── logs/
└── state/
```

---

## Step 2: Install Dependencies (3 minutes)

### 2.1 Create `requirements.txt`

```bash
cat > requirements.txt << 'EOF'
whatsapp-chatbot-python>=0.5.1
whatsapp-api-client-python>=0.76.0
whatsapp-chatgpt-python>=0.0.1
openai>=1.12.0
python-dotenv>=1.0.0
PyYAML>=6.0
tenacity>=8.0.0
pytest>=7.0.0
EOF
```

### 2.2 Install Packages

```bash
pip install -r requirements.txt

# Verify installation
pip list | grep whatsapp
# Should show: whatsapp-chatbot-python, whatsapp-api-client-python, whatsapp-chatgpt-python
```

---

## Step 3: Configuration (5 minutes)

### 3.1 Create `.env` File

```bash
cat > config/.env << 'EOF'
# Green API Credentials
GREEN_API_INSTANCE_ID=your_instance_id_here
GREEN_API_TOKEN=your_api_token_here

# OpenAI Credentials
OPENAI_API_KEY=sk-your-openai-key-here

# Bot Configuration
AI_MODEL=gpt-4o
SYSTEM_MESSAGE=You are DeniDin, a helpful AI assistant integrated with WhatsApp. Be concise and accurate.
MAX_TOKENS=1000
TEMPERATURE=0.7

# Operational Settings
LOG_LEVEL=INFO
POLL_INTERVAL=3
MAX_RETRIES=3
EOF
```

### 3.2 Add Your Credentials

**Edit `config/.env`** and replace placeholders:

1. `GREEN_API_INSTANCE_ID`: Your instance ID (numeric, e.g., "1234567890")
2. `GREEN_API_TOKEN`: Your API token (alphanumeric string)
3. `OPENAI_API_KEY`: Your OpenAI API key (starts with "sk-")

**Verify credentials**:

```bash
cat config/.env | grep -E "GREEN_API_INSTANCE_ID|GREEN_API_TOKEN|OPENAI_API_KEY"
# Should NOT contain "your_instance_id_here" or similar placeholders
```

### 3.3 Create `.env.example` (for version control)

```bash
cat > config/.env.example << 'EOF'
GREEN_API_INSTANCE_ID=your_instance_id_here
GREEN_API_TOKEN=your_api_token_here
OPENAI_API_KEY=sk-your-openai-key-here
AI_MODEL=gpt-4o
SYSTEM_MESSAGE=You are DeniDin, a helpful AI assistant integrated with WhatsApp. Be concise and accurate.
MAX_TOKENS=1000
TEMPERATURE=0.7
LOG_LEVEL=INFO
POLL_INTERVAL=3
MAX_RETRIES=3
EOF
```

### 3.4 Create `.gitignore`

```bash
cat > .gitignore << 'EOF'
# Environment
venv/
.env
config/.env

# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/

# Logs
logs/
*.log

# State
state/

# IDE
.vscode/
.idea/
*.swp
*.swo
EOF
```

---

## Step 4: Create Minimal Bot (10 minutes)

### 4.1 Create `bot.py` (Main Entry Point)

```bash
cat > bot.py << 'EOF'
#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Chatbot - Main Entry Point
"""
import logging
from pathlib import Path
from dotenv import load_dotenv
from whatsapp_chatbot_python import GreenAPIBot, Notification
from openai import OpenAI
import os

# Load environment variables
load_dotenv('config/.env')

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/denidin.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Green API bot
bot = GreenAPIBot(
    id_instance=os.getenv('GREEN_API_INSTANCE_ID'),
    api_token_instance=os.getenv('GREEN_API_TOKEN')
)

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    timeout=30.0
)

@bot.router.message(type_message=["textMessage"])
def handle_text_message(notification: Notification) -> None:
    """Handle incoming text messages and relay to ChatGPT"""
    try:
        # Extract message details
        message_text = notification.event.get('messageData', {}).get('textMessageData', {}).get('textMessage', '')
        sender_name = notification.event.get('senderData', {}).get('senderName', 'User')
        
        logger.info(f"Received message from {sender_name}: {message_text[:50]}...")
        
        # Get AI response
        response = openai_client.chat.completions.create(
            model=os.getenv('AI_MODEL', 'gpt-4o'),
            messages=[
                {"role": "system", "content": os.getenv('SYSTEM_MESSAGE', 'You are a helpful assistant.')},
                {"role": "user", "content": message_text}
            ],
            max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
            temperature=float(os.getenv('TEMPERATURE', '0.7'))
        )
        
        ai_response_text = response.choices[0].message.content
        logger.info(f"AI response: {ai_response_text[:50]}...")
        
        # Send response back to WhatsApp
        notification.answer(ai_response_text)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        notification.answer("Sorry, I encountered an error processing your message. Please try again.")

if __name__ == "__main__":
    logger.info("DeniDin bot starting...")
    logger.info(f"Instance ID: {os.getenv('GREEN_API_INSTANCE_ID')}")
    logger.info(f"AI Model: {os.getenv('AI_MODEL', 'gpt-4o')}")
    
    # Start the bot (blocks here, polls for messages)
    bot.run_forever()
EOF
```

### 4.2 Make Bot Executable

```bash
chmod +x bot.py
```

---

## Step 5: First Run Test (5 minutes)

### 5.1 Start the Bot

```bash
python bot.py
```

**Expected Output**:

```
2026-01-15 10:30:00 - __main__ - INFO - DeniDin bot starting...
2026-01-15 10:30:00 - __main__ - INFO - Instance ID: 1234567890
2026-01-15 10:30:00 - __main__ - INFO - AI Model: gpt-4o
2026-01-15 10:30:05 - whatsapp_chatbot_python - INFO - Settings updated successfully
2026-01-15 10:30:05 - whatsapp_chatbot_python - INFO - Clearing old notifications...
2026-01-15 10:30:10 - whatsapp_chatbot_python - INFO - Bot is now listening for messages
```

**Note**: First run may take 5-10 minutes while Green API configures instance settings. Subsequent runs are instant.

### 5.2 Send Test Message

1. Open WhatsApp on your phone
2. Send a message to your WhatsApp Business number
3. Example: "Hello, DeniDin! What is 2+2?"

**Expected Bot Behavior**:

```
2026-01-15 10:31:00 - __main__ - INFO - Received message from John Doe: Hello, DeniDin! What is 2+2?...
2026-01-15 10:31:03 - __main__ - INFO - AI response: Hello! 2 + 2 equals 4....
```

**Expected WhatsApp Response**:

```
Hello! 2 + 2 equals 4.
```

### 5.3 Verify Success

✅ **Success Criteria**:
- Bot starts without errors
- WhatsApp message is received by bot (see logs)
- AI generates a response (see logs)
- Response appears in WhatsApp within 30 seconds

❌ **If it doesn't work**, see Troubleshooting section below

---

## Step 6: Test Scenarios

### Scenario 1: Basic Q&A

**Send**: "What is the capital of France?"  
**Expected**: "The capital of France is Paris."

### Scenario 2: Multi-turn (Independent)

**Send**: "Tell me about dogs"  
**Expected**: Informative response about dogs

**Send**: "What about cats?" (separate message)  
**Expected**: Informative response about cats (no memory of previous question in Phase 1)

### Scenario 3: Long Response

**Send**: "Write a 500-word essay on climate change"  
**Expected**: Response split into multiple WhatsApp messages (if > 4096 chars)

### Scenario 4: Error Handling

**Stop the bot** (Ctrl+C), then **send a message**.  
**Restart the bot**.  
**Expected**: Bot processes the queued message on startup.

---

## Troubleshooting

### Issue 1: Bot Won't Start - "Missing required environment variables"

**Cause**: `.env` file not found or missing credentials

**Fix**:
```bash
# Verify .env exists
ls -la config/.env

# Check if credentials are set
cat config/.env | grep -v "^#" | grep -v "^$"

# Ensure you're loading from correct path
cat bot.py | grep "load_dotenv"
# Should show: load_dotenv('config/.env')
```

### Issue 2: Bot Starts but Doesn't Receive Messages

**Cause**: Green API instance not configured or WhatsApp not linked

**Fix**:
1. Log into [Green API Console](https://console.green-api.com)
2. Check instance status (should be "Authorized")
3. Verify QR code was scanned if first setup
4. Check instance settings have webhooks enabled

**Verify in logs**:
```bash
grep "Settings updated" logs/denidin.log
# Should show: "Settings updated successfully"
```

### Issue 3: AI Responses Not Sending

**Cause**: OpenAI API key invalid or quota exceeded

**Fix**:
```bash
# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_API_KEY"

# Should return list of models, not an error

# Check usage at: https://platform.openai.com/usage
```

### Issue 4: Bot Crashes on Message

**Cause**: Missing Python packages or syntax error

**Fix**:
```bash
# Re-install dependencies
pip install -r requirements.txt --upgrade

# Check Python version
python --version  # Should be 3.8+

# View full error traceback
tail -50 logs/denidin.log
```

### Issue 5: Slow Responses (> 30 seconds)

**Cause**: Using gpt-4 model (slower) or high max_tokens

**Fix in `config/.env`**:
```env
AI_MODEL=gpt-4o-mini  # Faster, cheaper
MAX_TOKENS=500         # Reduce for shorter responses
```

---

## Stopping the Bot

**Graceful Shutdown**:
```bash
# Press Ctrl+C in terminal where bot is running
^C
# Bot will finish processing current message then exit
```

**Check Logs**:
```bash
tail -20 logs/denidin.log
```

---

## Next Steps

After successful testing:

1. **Customize AI Behavior**: Edit `SYSTEM_MESSAGE` in `config/.env`
2. **Deploy to Server**: Run bot as a systemd service (Linux) or background process
3. **Add Error Handling**: Implement retry logic and better error messages
4. **Monitor Costs**: Track OpenAI API usage at [platform.openai.com/usage](https://platform.openai.com/usage)
5. **Phase 2 Features**: Add conversation history, context management, media support

---

## Verification Checklist

Before marking this feature as complete:

- [ ] Bot starts without errors
- [ ] Receives and logs WhatsApp messages
- [ ] Sends prompts to OpenAI successfully
- [ ] Returns AI responses to WhatsApp
- [ ] Handles errors gracefully (sends fallback message)
- [ ] Logs are written to `logs/denidin.log`
- [ ] Credentials are in `.env` (not hardcoded)
- [ ] `.env` is gitignored
- [ ] Bot can be stopped and restarted without issues

---

## Common Commands Reference

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install/update dependencies
pip install -r requirements.txt

# Run bot
python bot.py

# View logs (real-time)
tail -f logs/denidin.log

# View logs (last 50 lines)
tail -50 logs/denidin.log

# Clear logs
> logs/denidin.log

# Deactivate virtual environment
deactivate
```

---

## Support Resources

- **Green API Docs**: https://green-api.com/en/docs/
- **OpenAI API Docs**: https://platform.openai.com/docs/
- **Python whatsapp-chatbot-python**: https://github.com/green-api/whatsapp-chatbot-python
- **Feature Spec**: `specs/001-whatsapp-chatbot-passthrough/spec.md`
- **Implementation Plan**: `specs/001-whatsapp-chatbot-passthrough/plan.md`
