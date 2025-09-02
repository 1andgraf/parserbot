import os
import re
import asyncio
from urllib.parse import urljoin, urlparse
import phonenumbers
import io
import zipfile

import tldextract
import httpx
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("Set TELEGRAM_TOKEN environment variable")

MAX_BYTES = 2_000_000
TIMEOUT = 15.0
SOCIAL_DOMAINS = [
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "tiktok.com", "youtube.com", "yt.be", "vimeo.com"
]

email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', re.I)
phone_re = re.compile(r'\+\d[\d\s\-().]{6,}\d')
mailto_re = re.compile(r'^mailto:(.+)', re.I)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

user_settings = {}

def get_user_settings(user_id: int):
    if user_id not in user_settings:
        user_settings[user_id] = {
            "send_images": True,
            "send_videos": True,
            "send_files": True,
        }
    return user_settings[user_id]

async def fetch_url(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, follow_redirects=True, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"fetch error: {e}"}
    ct = resp.headers.get("content-type", "")
    if "text/html" not in ct:
        return {"error": f"content-type not HTML: {ct}"}
    content = resp.content[:MAX_BYTES]
    return {"url": str(resp.url), "status": resp.status_code, "content": content, "headers": dict(resp.headers)}


def normalize_phone(raw: str):
    try:
        pn = phonenumbers.parse(raw, None)
        if phonenumbers.is_possible_number(pn) and phonenumbers.is_valid_number(pn):
            return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None

def extract_from_text(text: str):
    emails = set(email_re.findall(text))
    phones = set()
    for m in phone_re.findall(text):
        p = normalize_phone(m)
        if p:
            phones.add(p)
    return emails, phones

def extract_social_links(soup: BeautifulSoup, base_url: str):
    found = {}
    anchors = soup.find_all("a", href=True)
    for a in anchors:
        href = a["href"].strip()
        if not href:
            continue
        parsed = urlparse(urljoin(base_url, href))
        host = parsed.netloc.lower()
        for s in SOCIAL_DOMAINS:
            if s in host:
                found.setdefault(s, set()).add(urljoin(base_url, href))
    return {k: sorted(v) for k, v in found.items()}

def extract_meta(soup: BeautifulSoup):
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    desc = ""
    d = soup.find("meta", attrs={"name": "description"})
    if d and d.get("content"):
        desc = d.get("content").strip()
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    imgs = [img.get("src") for img in soup.find_all("img", src=True)]
    json_ld = []
    for s in soup.find_all("script", type="application/ld+json"):
        if s.string:
            json_ld.append(s.string.strip())
    return {"title": title, "description": desc, "h1s": h1s, "links_count": len(links), "images_count": len(imgs), "json_ld_count": len(json_ld)}

def extract_from_html(html: bytes, base_url: str):
    text = html.decode(errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    meta = extract_meta(soup)
    social = extract_social_links(soup, base_url)
    emails = set(email_re.findall(text))
    phones = set()
    anchors = soup.find_all("a", href=True)
    for a in anchors:
        href = a["href"].strip()
        m = mailto_re.match(href)
        if m:
            emails.add(m.group(1))
    for m in phone_re.findall(text):
        p = normalize_phone(m)
        if p:
            phones.add(p)
    for tag in soup.find_all(string=True):
        if tag.parent.name in ("script", "style"):
            continue
        for em in email_re.findall(tag):
            emails.add(em)
        for ph in phone_re.findall(tag):
            p = normalize_phone(ph)
            if p:
                phones.add(p)
    emails = sorted({e.lower() for e in emails})
    phones = sorted(phones)
    return {"emails": emails, "phones": phones, "meta": meta, "social": social, "soup": soup}

def format_result(result: dict):
    if "error" in result:
        return f"*❌ Error:* `{result['error']}`"
    
    lines = [f"*🌐 URL:* `{result.get('url')}`", ""]
    meta = result["data"]["meta"]
    
    if meta.get("title"):
        lines.append(f"*📄 Title:* {meta['title']}")
    if meta.get("description"):
        lines.append(f"*📄 Meta Description:* {meta['description']}")
        lines.append("")
    lines.append(f"*🔗 Links Found:* `{meta.get('links_count')}`")
    lines.append(f"*🖼️ Images Found:* `{meta.get('images_count')}`")
    lines.append("")
    
    emails = result["data"]["emails"]
    if emails:
        lines.append("*✉️ Emails:*")
        for e in emails:
            lines.append(f"  • `{e}`")
        lines.append("")
    else:
        lines.append("*✉️ Emails:* None found")
        lines.append("")
    
    phones = result["data"]["phones"]
    if phones:
        lines.append("*📞 Phones:*")
        for p in phones:
            lines.append(f"  • `{p}`")
        lines.append("")
    else:
        lines.append("*📞 Phones:* None found")
        lines.append("")
    
    social = result["data"]["social"]
    if social:
        lines.append("*📱 Social Links:*")
        for platform, urls in social.items():
            lines.append(f"  • *{platform}*")
            for u in urls[:5]:
                lines.append(f"      `{u}`")
        lines.append("")
    
    return "\n".join(lines)

def split_message_safe(text: str, limit: int = 3900):
    """
    Splits the text into chunks not exceeding the limit,
    splitting on line boundaries to avoid breaking Markdown formatting.
    """
    lines = text.splitlines(keepends=True)
    chunks = []
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) > limit:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                # single line longer than limit, force split
                chunks.append(line[:limit])
                current_chunk = line[limit:]
        else:
            current_chunk += line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Scan URL", callback_data="scan_url"),
        InlineKeyboardButton("Settings", callback_data="settings")
    )
    await message.reply("Choose an option:", reply_markup=keyboard)

def build_settings_keyboard(user_id: int):
    settings = get_user_settings(user_id)
    def mark(value: bool):
        return "✅" if value else "❌"
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"Images: {mark(settings['send_images'])}", callback_data="toggle_images"),
        InlineKeyboardButton(f"Videos: {mark(settings['send_videos'])}", callback_data="toggle_videos"),
        InlineKeyboardButton(f"Files: {mark(settings['send_files'])}", callback_data="toggle_files"),
    )
    keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data == "scan_url")
async def callback_scan_url(callback_query: types.CallbackQuery):
    await callback_query.answer()
    try:
        await callback_query.message.delete()   # remove the start menu
    except Exception:
        pass
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start"))
    await callback_query.message.answer(
        "Send a single URL. Bot returns emails, phones, social links, title and basic metadata.",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "settings")
async def callback_settings(callback_query: types.CallbackQuery):
    await callback_query.answer()
    try:
        await callback_query.message.delete()   # remove the start menu
    except Exception:
        pass
    keyboard = build_settings_keyboard(callback_query.from_user.id)
    await callback_query.message.answer("Toggle settings:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data in ("toggle_images", "toggle_videos", "toggle_files"))
async def callback_toggle_setting(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    settings = get_user_settings(user_id)
    key = None
    if callback_query.data == "toggle_images":
        key = "send_images"
    elif callback_query.data == "toggle_videos":
        key = "send_videos"
    elif callback_query.data == "toggle_files":
        key = "send_files"
    if key:
        settings[key] = not settings[key]
    keyboard = build_settings_keyboard(user_id)
    await callback_query.answer()
    await callback_query.message.edit_reply_markup(reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "back_to_start")
async def callback_back_to_start(callback_query: types.CallbackQuery):
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        pass

    # Build the original start menu inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Scan URL", callback_data="scan_url"),
        InlineKeyboardButton("Settings", callback_data="settings")
    )

    await callback_query.message.answer("Choose an option:", reply_markup=keyboard)
    
@dp.callback_query_handler(lambda c: c.data == "back_to_start_no")
async def callback_back_to_start(callback_query: types.CallbackQuery):
    await callback_query.answer()

    # Build the original start menu inline keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Scan URL", callback_data="scan_url"),
        InlineKeyboardButton("Settings", callback_data="settings")
    )

    await callback_query.message.answer("Choose an option:", reply_markup=keyboard)

@dp.message_handler()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        await message.reply("Send a full URL starting with http:// or https://", parse_mode="Markdown")
        return
    await message.chat.do('typing')
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent":"ParserBot/1.0"}) as client:
        fetch = await fetch_url(client, text)
        if "error" in fetch:
            await message.reply(fetch["error"], parse_mode="Markdown")
            return
        data = extract_from_html(fetch["content"], fetch["url"])
        out = {"url": fetch["url"], "status": fetch["status"], "data": data}
        formatted = format_result(out)

        soup = data.get("soup")
        if not soup:
            # If no soup, just send formatted result
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start_no"))
            if len(formatted) > 4000:
                for chunk in split_message_safe(formatted):
                    await message.reply(chunk, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
            else:
                await message.reply(formatted, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
            return

        # Send metadata first
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start_no"))
        if len(formatted) > 4000:
            for chunk in split_message_safe(formatted):
                await message.reply(chunk, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
        else:
            await message.reply(formatted, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)

        # Collect images
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if src:
                full_url = urljoin(fetch["url"], src)
                full_url = full_url.split('?')[0]
                images.append(full_url)
        print(f"Collected image URLs: {images}")

        # Collect videos
        videos = []
        for video_tag in soup.find_all("video"):
            src = video_tag.get("src")
            if src:
                full_url = urljoin(fetch["url"], src)
                full_url = full_url.split('?')[0]
                videos.append(full_url)
            # Also check for source tags inside video
            for source_tag in video_tag.find_all("source", src=True):
                src = source_tag["src"].strip()
                if src:
                    full_url = urljoin(fetch["url"], src)
                    full_url = full_url.split('?')[0]
                    videos.append(full_url)
        print(f"Collected video URLs: {videos}")

        # Collect links to PDF/ZIP/DOCX files
        file_extensions = (".pdf", ".zip", ".docx")
        files = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().endswith(file_extensions):
                full_url = urljoin(fetch["url"], href)
                files.append(full_url)
        print(f"Collected file URLs: {files}")

        settings = get_user_settings(message.from_user.id)

        # Send images messages
        if settings.get("send_images") and images:
            image_parts = ["*Images:*"]
            for url_ in images:
                filename = os.path.basename(url_)
                image_parts.append(f"  • [{filename}]({url_})")
            image_parts.append("")
            image_message = "\n".join(image_parts)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start_no"))
            if len(image_message) > 4000:
                for chunk in split_message_safe(image_message):
                    await message.reply(chunk, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
            else:
                await message.reply(image_message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)

        # Send videos messages
        if settings.get("send_videos") and videos:
            video_parts = ["*Videos:*"]
            for url_ in videos:
                filename = os.path.basename(url_)
                video_parts.append(f"  • [{filename}]({url_})")
            video_parts.append("")
            video_message = "\n".join(video_parts)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start_no"))
            if len(video_message) > 4000:
                for chunk in split_message_safe(video_message):
                    await message.reply(chunk, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
            else:
                await message.reply(video_message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)

        # Send files messages
        if settings.get("send_files") and files:
            file_parts = ["*Files:*"]
            for url_ in files:
                filename = os.path.basename(url_)
                file_parts.append(f"  • [{filename}]({url_})")
            file_parts.append("")
            file_message = "\n".join(file_parts)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Back", callback_data="back_to_start_no"))
            if len(file_message) > 4000:
                for chunk in split_message_safe(file_message):
                    await message.reply(chunk, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
            else:
                await message.reply(file_message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)