import os
import random
from datetime import datetime, timezone
from pathlib import Path
from email.utils import format_datetime

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"
MESSAGES_FILE = ROOT / "positive_messages.txt"
RSS_FILE = ROOT / "index.xml"

SITE_BASE = os.environ["SITE_BASE_URL"].rstrip("/")
SHOW_TITLE = os.environ.get("SHOW_TITLE", "Ale's Daily Drive Intro")
SHOW_DESCRIPTION = os.environ.get(
    "SHOW_DESCRIPTION",
    "A short daily intro for Ale's Daily Drive."
)
SHOW_EMAIL = os.environ["PODCAST_EMAIL"]
SHOW_AUTHOR = os.environ.get("SHOW_AUTHOR", "Ale")
VOICE = os.environ.get("OPENAI_VOICE", "marin")
MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

EPISODES_DIR.mkdir(parents=True, exist_ok=True)

def load_messages():
    lines = MESSAGES_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]

def build_script_text():
    today = datetime.now()
    date_str = today.strftime("%A, %B %d").replace(" 0", " ")

    messages = load_messages()
    message = random.choice(messages)

    return (
        f"Good morning, Alejandra. "
        f"Today is {date_str}. "
        f"{message} "
        f"Here’s your Daily Drive."
    )
  
def generate_audio(text: str, out_path: Path):
    with client.audio.speech.with_streaming_response.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        format="mp3",
    ) as response:
        response.stream_to_file(out_path)

def make_episode_filename():
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{today}-intro.mp3"

def file_size(path: Path) -> int:
    return path.stat().st_size

def build_rss_item(title: str, filename: str, pub_dt: datetime, description: str) -> str:
    url = f"{SITE_BASE}/episodes/{filename}"
    guid = url
    length = file_size(EPISODES_DIR / filename)
    pub_date = format_datetime(pub_dt)

    return f"""
    <item>
      <title><![CDATA[{title}]]></title>
      <description><![CDATA[{description}]]></description>
      <enclosure url="{url}" length="{length}" type="audio/mpeg" />
      <guid>{guid}</guid>
      <pubDate>{pub_date}</pubDate>
    </item>""".rstrip()

def write_rss(latest_item: str):
    now = datetime.now(timezone.utc)
    pub_date = format_datetime(now)
    site_link = SITE_BASE

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title><![CDATA[{SHOW_TITLE}]]></title>
    <link>{site_link}</link>
    <description><![CDATA[{SHOW_DESCRIPTION}]]></description>
    <language>en-us</language>
    <managingEditor>{SHOW_EMAIL} ({SHOW_AUTHOR})</managingEditor>
    <webMaster>{SHOW_EMAIL} ({SHOW_AUTHOR})</webMaster>
    <lastBuildDate>{pub_date}</lastBuildDate>
{latest_item}
  </channel>
</rss>
"""
    RSS_FILE.write_text(rss, encoding="utf-8")

def main():
    text = build_script_text()
    filename = make_episode_filename()
    out_path = EPISODES_DIR / filename

    generate_audio(text, out_path)

    now = datetime.now(timezone.utc)
    title = f"Daily Intro for {datetime.now().strftime('%B %d, %Y')}"
    item = build_rss_item(title, filename, now, text)
    write_rss(item)

    print(f"Created {out_path}")
    print(text)

if __name__ == "__main__":
    main()
