import os
import random
from datetime import datetime, timezone
from pathlib import Path
from email.utils import format_datetime

from openai import OpenAI
from pydub import AudioSegment

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
VOICE = os.environ.get("OPENAI_VOICE", "cedar")
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
        f"Good morning Alejandra! "
        f"Today is {date_str}. "
        f"{message} "
        f"Here’s your Daily Drive."
    )


def generate_audio(text: str, out_path: Path):
    temp_voice = EPISODES_DIR / "voice_temp.mp3"
    background_path = ROOT / "background.mp3"

    # Timing settings
    intro_lead_ms = 10000
    outro_tail_ms = 7000
    fade_in_ms = 2000
    fade_out_ms = 3000

    # Make music audible (we will tune this later if needed)
    background_reduction_db = 0  # TEMP: loud for testing

    # Generate voice
    with client.audio.speech.with_streaming_response.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        response_format="mp3",
    ) as response:
        response.stream_to_file(temp_voice)

    voice = AudioSegment.from_file(temp_voice)
    music = AudioSegment.from_file(background_path)

    # Normalize channels
    if music.channels != voice.channels:
        music = music.set_channels(voice.channels)

    # Normalize sample rate
    if music.frame_rate != voice.frame_rate:
        music = music.set_frame_rate(voice.frame_rate)

    total_needed = intro_lead_ms + len(voice) + outro_tail_ms

    # Loop music if needed
    while len(music) < total_needed:
        music += music

    # Trim to exact length
    music = music[:total_needed]

    # Adjust volume
    music = music - background_reduction_db

    # Add fade in/out
    music = music.fade_in(fade_in_ms).fade_out(fade_out_ms)

    # Overlay voice after intro lead time
    final_audio = music.overlay(voice, position=intro_lead_ms)

    # Export final
    final_audio.export(out_path, format="mp3")

    # Cleanup
    if temp_voice.exists():
        temp_voice.unlink()


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
    cover_url = f"{SITE_BASE}/cover.jpg"

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title><![CDATA[{SHOW_TITLE}]]></title>
    <link>{site_link}</link>
    <description><![CDATA[{SHOW_DESCRIPTION}]]></description>
    <language>en-us</language>

    <itunes:author>{SHOW_AUTHOR}</itunes:author>
    <itunes:owner>
      <itunes:name>{SHOW_AUTHOR}</itunes:name>
      <itunes:email>{SHOW_EMAIL}</itunes:email>
    </itunes:owner>

    <itunes:image href="{cover_url}" />

    <lastBuildDate>{pub_date}</lastBuildDate>

{latest_item}

  </channel>
</rss>
"""
    RSS_FILE.write_text(rss, encoding="utf-8")


def main():
    text = build_script_text()
    filename = datetime.now().strftime("%Y-%m-%d") + "-intro.mp3"
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
