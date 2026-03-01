# PogoFest Tickets Discord Bot

A Discord bot that monitors the Pokemon GO official site for GO Fest 2026 ticket availability and instantly alerts your server the moment tickets go on sale.

## How It Works

The bot checks the GO Fest 2026 event pages every 3 minutes. When it detects a purchase link appear on the page, it sends an embed alert with a ping to every configured server.

Monitored events:
- GO Fest 2026: Tokyo
- GO Fest 2026: Chicago
- GO Fest 2026: Copenhagen

---

## Requirements

- Python 3.10 or newer
- A Discord bot token ([create one here](https://discord.com/developers/applications))

### Python Dependencies

| Package | Version |
|---|---|
| discord.py | >= 2.3.0 |
| aiohttp | >= 3.9.0 |
| beautifulsoup4 | >= 4.12.0 |
| python-dotenv | >= 1.0.0 |
| aiosqlite | >= 0.19.0 |

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/PogoFestTicketsDiscordBot.git
cd PogoFestTicketsDiscordBot
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure your bot token**

Copy the example env file and fill in your Discord bot token:

```bash
cp .env.example .env
```

Open `.env` and replace `your_discord_bot_token_here` with your actual token:

```
DISCORD_TOKEN=your_discord_bot_token_here
```

**4. Run the bot**

```bash
python bot.py
```

---

## Discord Bot Setup

Before running the bot, make sure your Discord application has the correct settings:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and open your application
2. Under **Bot**, enable **Server Members Intent** if needed
3. Under **OAuth2 > URL Generator**, select the `bot` and `applications.commands` scopes
4. Under **Bot Permissions**, select:
   - Send Messages
   - Embed Links
   - Mention Everyone (required to ping @everyone)
5. Use the generated URL to invite the bot to your server

---

## Server Configuration (Slash Commands)

Once the bot is in your server, use these slash commands to set it up:

| Command | Description | Required Permission |
|---|---|---|
| `/set-channel [channel]` | Set which channel receives ticket alerts | Manage Channels |
| `/ping-role [role]` | Set a role to ping on alerts (omit for @everyone) | Manage Roles |
| `/remove-channel` | Remove this server's alert configuration | Manage Channels |
| `/status` | View current monitoring status and event availability | Anyone |
| `/test-alert` | Send a test alert to verify your setup | Manage Channels |

### Quick Setup

1. Run `/set-channel #your-channel` to choose where alerts are posted
2. Run `/ping-role @YourRole` (or omit the role to ping @everyone)
3. Run `/test-alert` to confirm everything is working

---

## Files

| File | Purpose |
|---|---|
| `bot.py` | Main entry point — slash commands, background task, Discord events |
| `database.py` | SQLite wrapper for per-server channel/role configuration |
| `monitor.py` | Web scraper — detects ticket availability and persists state |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

### Runtime files (auto-generated, git-ignored)

| File | Purpose |
|---|---|
| `bot_data.db` | SQLite database storing each server's config |
| `ticket_state.json` | Last-known availability state for each event |
