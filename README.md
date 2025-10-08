# Canvas Alert Bot

## What the Bot Does
This bot connects to Canvas LMS and automatically checks for upcoming assignments.  
It sends reminders and updates to a Discord channel because i keep forgetting due dates.  
You can also use commands like `!ping` to check if it’s online and `!next` to see upcoming assignments.

## How to Run It
1. Add your Canvas and Discord credentials to a `.env` file:

2. Install dependencies:
3. Run the bot:

4. (Optional) Deploy on Render and add UptimeRobot to keep it running online.

## Why I Hosted It This Way
I wanted the bot to run 24/7 without paying for hosting.  
By using **Render’s free web service** and **UptimeRobot** to ping it every few minutes, the bot stays online permanently for free.
