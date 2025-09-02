# Telegram Website Parser Bot

A Telegram bot that parses a website URL and returns emails, phone numbers, social links, metadata, and lists of images, videos, and files. Users can control which content types are returned via settings.

## Features

- Send a website URL and receive:
  - Emails
  - Phone numbers (international format)
  - Social media links
  - Page title and meta description
  - H1 headings
  - Images, videos, files (PDF/ZIP/DOCX)
- Per-user settings to enable/disable images, videos, or file messages
- Inline menu with:
  - **Scan URL**
  - **Settings** (toggle content types)
- Back buttons to navigate menus without clutter
- Messages automatically chunked to respect Telegram's 4096-character limit
- Links displayed as filenames instead of raw URLs, with previews disabled

## Installation

1. Clone the repository:

```bash
git clone <repo_url>
cd <repo_folder>
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

## Usage

Start the bot:

```bash
python app.py
```

### Bot Workflow

1. `/start` command displays an inline menu with **Scan URL** and **Settings**.
2. **Scan URL**: prompts the user to send a website URL.
3. **Settings**: toggle sending of images, videos, and files.
4. After sending a URL, the bot replies with structured messages for metadata, images, videos, and files.
5. **Back buttons** allow navigation to the main menu.

## Dependencies

- Python 3.9+
- [aiogram](https://docs.aiogram.dev/) – Telegram bot framework
- [httpx](https://www.python-httpx.org/) – HTTP client
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) – HTML parsing
- [tldextract](https://github.com/john-kurkowski/tldextract) – Domain parsing
- [phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) – Phone number validation

## Notes

- Telegram limits message length to 4096 characters and documents to 50 MB.
- Links in messages are formatted with filenames and **previews are disabled**.
- Per-user settings are stored in memory and reset when the bot restarts.

## License

MIT License

