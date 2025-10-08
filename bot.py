import os
import asyncio
import pathlib
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv
from canvasapi import Canvas
from datetime import datetime, timedelta
import pytz

# ✅ KEEP-ALIVE WEB SERVER (to prevent Render sleep)
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# --- Load .env explicitly ---
env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

# Debug print
print("DEBUG - DISCORD_CHANNEL_ID:", DISCORD_CHANNEL_ID)
print("DEBUG - CANVAS_BASE_URL:", CANVAS_BASE_URL)

# Validate env values
missing = []
if not DISCORD_TOKEN:
    missing.append("DISCORD_TOKEN")
if not DISCORD_CHANNEL_ID:
    missing.append("DISCORD_CHANNEL_ID")
if not CANVAS_BASE_URL:
    missing.append("CANVAS_BASE_URL")
if not CANVAS_API_TOKEN:
    missing.append("CANVAS_API_TOKEN")

if missing:
    raise SystemExit(f"❌ Missing environment variables: {', '.join(missing)}")

# Convert channel ID to int
DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)

# --- Setup timezone + Canvas API ---
tz = pytz.timezone(TIMEZONE)
canvas = Canvas(CANVAS_BASE_URL, CANVAS_API_TOKEN)

# --- Setup Discord bot ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone=tz)

# --- Helpers ---
def get_upcoming_assignments(days_ahead=7):
    now = datetime.now(tz)
    horizon = now + timedelta(days=days_ahead)
    assignments = []
    for course in canvas.get_courses(enrollment_state="active"):
        try:
            for a in course.get_assignments():
                if not a.due_at:
                    continue
                due = datetime.fromisoformat(a.due_at.replace("Z", "+00:00")).astimezone(tz)
                if now <= due <= horizon:
                    assignments.append((course.name, a.name, due, a.html_url))
        except Exception:
            continue
    return sorted(assignments, key=lambda x: x[2])

async def send_message(text):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(text)
    else:
        print("❌ Could not find channel ID:", DISCORD_CHANNEL_ID)

def format_assignment(course, name, due, url):
    return f"📌 **{name}** ({course}) — due {due.strftime('%b %d %I:%M %p')} \n{url}"

# --- Scheduled Jobs ---
async def morning_digest():
    assignments = get_upcoming_assignments()
    if assignments:
        msg = "☀️ **Morning Digest**\n" + "\n".join(format_assignment(*a) for a in assignments)
        await send_message(msg)

async def midday_digest():
    assignments = get_upcoming_assignments()
    if assignments:
        msg = "🕐 **Midday Digest**\n" + "\n".join(format_assignment(*a) for a in assignments)
        await send_message(msg)

async def schedule_two_hour_warnings():
    assignments = get_upcoming_assignments()
    now = datetime.now(tz)
    for course, name, due, url in assignments:
        warn_time = due - timedelta(hours=2)
        if warn_time > now:
            async def send_warning(c=course, n=name, d=due, u=url):
                await send_message(f"⏳ Reminder: **{n}** ({c}) is due in 2 hours! {u}")
            scheduler.add_job(lambda: asyncio.create_task(send_warning()), DateTrigger(run_date=warn_time))

# --- Events ---
@bot.event
async def on_ready():
    if not hasattr(bot, 'booted'):
        print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send("✅ Canvas Alert Bot is online (first boot).")
        bot.booted = True
    else:
        print("♻️ Bot reconnected (no announcement).")

    if not scheduler.running:
        scheduler.add_job(lambda: asyncio.create_task(morning_digest()), CronTrigger(hour=8, minute=0))
        scheduler.add_job(lambda: asyncio.create_task(midday_digest()), CronTrigger(hour=13, minute=0))
        scheduler.add_job(lambda: asyncio.create_task(schedule_two_hour_warnings()), CronTrigger(minute="*/30"))
        scheduler.start()

@bot.command()
async def ping(ctx):
    await ctx.send("pong 🚨")

@bot.command()
async def next(ctx):
    """Shows upcoming Canvas assignments."""
    await ctx.send("📘 Checking Canvas for upcoming assignments...")
    assignments = get_upcoming_assignments()
    if not assignments:
        await ctx.send("🎉 No upcoming assignments found.")
    else:
        msg = "**Upcoming Assignments:**\n" + "\n".join(format_assignment(*a) for a in assignments[:5])
        await ctx.send(msg)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
