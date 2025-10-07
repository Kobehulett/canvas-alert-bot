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

# --- Load .env ---
env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

# --- Verify environment ---
missing = []
for key, val in {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "DISCORD_CHANNEL_ID": DISCORD_CHANNEL_ID,
    "CANVAS_BASE_URL": CANVAS_BASE_URL,
    "CANVAS_API_TOKEN": CANVAS_API_TOKEN
}.items():
    if not val:
        missing.append(key)
if missing:
    raise SystemExit(f"❌ Missing environment variables: {', '.join(missing)}")

DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)

# --- Setup Canvas + timezone ---
tz = pytz.timezone(TIMEZONE)
canvas = Canvas(CANVAS_BASE_URL, CANVAS_API_TOKEN)

# --- Setup Discord bot ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone=tz)

# --- Helper: fetch assignments ---
def get_upcoming_assignments(days_ahead=7):
    now = datetime.now(tz)
    horizon = now + timedelta(days=days_ahead)
    assignments = []
    print("📘 Fetching assignments...")
    try:
        for course in canvas.get_courses(enrollment_state="active"):
            for a in course.get_assignments():
                if not a.due_at:
                    continue
                due = datetime.fromisoformat(a.due_at.replace("Z", "+00:00")).astimezone(tz)
                if now <= due <= horizon:
                    assignments.append((course.name, a.name, due, a.html_url))
        print(f"✅ Found {len(assignments)} assignments.")
    except Exception as e:
        print(f"⚠️ Error fetching assignments: {e}")
    return sorted(assignments, key=lambda x: x[2])

# --- Helper: send message to Discord ---
async def send_message(text):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(text)
    else:
        print("❌ Could not find channel:", DISCORD_CHANNEL_ID)

# --- Formatting ---
def format_assignment(course, name, due, url):
    return f"📌 **{name}** ({course}) — due {due.strftime('%b %d %I:%M %p')} \n{url}"

# --- Scheduled digests ---
async def morning_digest():
    assignments = get_upcoming_assignments()
    if assignments:
        msg = "☀️ **Morning Digest**\n" + "\n".join(format_assignment(*a) for a in assignments)
        await send_message(msg)
    else:
        print("No assignments for morning digest.")

async def midday_digest():
    assignments = get_upcoming_assignments()
    if assignments:
        msg = "🕐 **Midday Digest**\n" + "\n".join(format_assignment(*a) for a in assignments)
        await send_message(msg)
    else:
        print("No assignments for midday digest.")

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
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is online. Waiting for schedules...")
    await send_message("✅ Canvas Alert Bot is online (first boot).")

    # Run only once per real schedule (no spam)
    scheduler.add_job(lambda: asyncio.create_task(morning_digest()), CronTrigger(hour=8, minute=0))
    scheduler.add_job(lambda: asyncio.create_task(midday_digest()), CronTrigger(hour=13, minute=0))
    scheduler.add_job(lambda: asyncio.create_task(schedule_two_hour_warnings()), CronTrigger(hour="*", minute=0))
    scheduler.start()

# --- Commands ---
@bot.command()
async def ping(ctx):
    await ctx.send("pong 🏓")

@bot.command()
async def next(ctx):
    assignments = get_upcoming_assignments()
    if not assignments:
        await ctx.send("🎉 No upcoming assignments found.")
    else:
        msg = "📖 **Next Assignments**\n" + "\n".join(format_assignment(*a) for a in assignments[:5])
        await ctx.send(msg)

# --- Run bot ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
