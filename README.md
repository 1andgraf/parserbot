# Telegram Website Parser Bot

A Telegram bot that parses a website URL and returns emails, phone numbers, social links, metadata, and lists of images, videos, and files. Users can control which content types are returned via settings.

## Try the bot:

https://t.me/landgrafparserbot

## Installation

1. Clone the repository:

```bash
git clone https://github.com/1andgraf/parserbot.git
cd parserbot
```

2. Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set the Telegram bot token in a `.env` file:

```text
TELEGRAM_TOKEN=your_bot_token_here
```

Or export it in your shell:

```bash
export TELEGRAM_TOKEN="your_bot_token_here"  # macOS/Linux
set TELEGRAM_TOKEN="your_bot_token_here"     # Windows
```

5. Start the bot:

```bash
python app.py
```

## Dependencies

- Python 3.9+
- [aiogram](https://docs.aiogram.dev/) – Telegram bot framework
- [httpx](https://www.python-httpx.org/) – HTTP client
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) – HTML parsing
- [tldextract](https://github.com/john-kurkowski/tldextract) – Domain parsing
- [phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) – Phone number validation
