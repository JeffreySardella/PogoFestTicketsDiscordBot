import logging
import os

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import Database
from monitor import TicketMonitor

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()
monitor = TicketMonitor()

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    await db.init()
    await bot.tree.sync()
    check_tickets.start()
    logger.info("Logged in as %s (id: %s)", bot.user, bot.user.id)


@bot.event
async def on_guild_remove(guild: discord.Guild):
    await db.remove_config(guild.id)
    logger.info("Left guild %s — config removed.", guild.id)

# ---------------------------------------------------------------------------
# Background monitoring task
# ---------------------------------------------------------------------------

@tasks.loop(minutes=3)
async def check_tickets():
    logger.info("Running ticket check...")
    try:
        newly_available = await monitor.check_all()
    except Exception as exc:
        logger.error("check_all() raised an exception: %s", exc)
        return

    if not newly_available:
        return

    configs = await db.get_all_configs()
    for config in configs:
        channel_id = config.get("channel_id")
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            continue

        role_id = config.get("role_id")
        ping = f"<@&{role_id}>" if role_id else "@everyone"

        for event in newly_available:
            embed = discord.Embed(
                title="🎟️ GO FEST 2026 TICKETS ARE LIVE! 🎟️",
                description=f"**{event['name']}** tickets are now available — act fast!",
                color=discord.Color.gold(),
            )
            embed.add_field(name="Dates", value=event["dates"], inline=True)
            embed.add_field(name="Location", value=event["location"], inline=True)
            embed.add_field(
                name="Buy Tickets",
                value=f"[Click Here]({event['url']})",
                inline=False,
            )
            embed.set_footer(text="Tickets sell out in minutes. Good luck, Trainer!")

            try:
                await channel.send(
                    content=f"🚨 {ping} **TICKETS ARE LIVE!** 🚨",
                    embed=embed,
                )
            except discord.Forbidden:
                logger.warning("No permission to send in channel %s (guild %s)", channel_id, config.get("guild_id"))
            except discord.HTTPException as exc:
                logger.error("Failed to send alert: %s", exc)


@check_tickets.before_loop
async def before_check():
    await bot.wait_until_ready()


@check_tickets.error
async def check_tickets_error(error: Exception):
    logger.error("Unhandled error in check_tickets loop: %s", error)

# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="set-channel",
    description="Set the channel where GO Fest 2026 ticket alerts will be posted.",
)
@discord.app_commands.describe(channel="The text channel to send alerts to.")
@discord.app_commands.default_permissions(manage_channels=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.set_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"✅ Ticket alerts will be sent to {channel.mention}.", ephemeral=True
    )


@bot.tree.command(
    name="ping-role",
    description="Set the role that gets pinged when tickets go live (leave blank for @everyone).",
)
@discord.app_commands.describe(role="Role to ping. Omit to use @everyone.")
@discord.app_commands.default_permissions(manage_roles=True)
async def ping_role(interaction: discord.Interaction, role: discord.Role = None):
    role_id = role.id if role else None
    await db.set_role(interaction.guild_id, role_id)
    if role:
        await interaction.response.send_message(
            f"✅ Will ping {role.mention} when tickets go live.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "✅ Will ping **@everyone** when tickets go live.", ephemeral=True
        )


@bot.tree.command(
    name="remove-channel",
    description="Remove this server's GO Fest alert configuration.",
)
@discord.app_commands.default_permissions(manage_channels=True)
async def remove_channel(interaction: discord.Interaction):
    await db.remove_config(interaction.guild_id)
    await interaction.response.send_message(
        "✅ Alert configuration removed for this server.", ephemeral=True
    )


@bot.tree.command(
    name="status",
    description="Show the bot's current monitoring status and event availability.",
)
async def status(interaction: discord.Interaction):
    config = await db.get_config(interaction.guild_id)
    channel_str = f"<#{config['channel_id']}>" if config and config.get("channel_id") else "Not set"
    role_str = f"<@&{config['role_id']}>" if config and config.get("role_id") else "@everyone"

    embed = discord.Embed(title="🤖 PogoFest Ticket Bot — Status", color=discord.Color.blue())
    embed.add_field(name="Alert Channel", value=channel_str, inline=False)
    embed.add_field(name="Ping Role", value=role_str, inline=False)
    embed.add_field(
        name="Monitor Loop",
        value="✅ Running" if check_tickets.is_running() else "❌ Stopped",
        inline=False,
    )

    events_status = monitor.get_events_status()
    lines = []
    for ev in events_status:
        dot = "🟢" if ev["available"] else "🔴"
        lines.append(f"{dot} **{ev['name']}** — {ev['status']}")
    embed.add_field(name="Event Status", value="\n".join(lines) or "Unknown", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="test-alert",
    description="Send a test ticket alert to the configured channel to verify setup.",
)
@discord.app_commands.default_permissions(manage_channels=True)
async def test_alert(interaction: discord.Interaction):
    config = await db.get_config(interaction.guild_id)
    if not config or not config.get("channel_id"):
        await interaction.response.send_message(
            "❌ No alert channel set. Use `/set-channel` first.", ephemeral=True
        )
        return

    channel = bot.get_channel(config["channel_id"])
    if channel is None:
        await interaction.response.send_message(
            "❌ Could not find the configured channel. Has it been deleted?", ephemeral=True
        )
        return

    role_id = config.get("role_id")
    ping = f"<@&{role_id}>" if role_id else "@everyone"

    embed = discord.Embed(
        title="🎟️ TEST ALERT — GO Fest 2026 Tickets!",
        description="This is a **test**. When real tickets go live, you'll see a message just like this!",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Dates", value="June 5–7, 2026", inline=True)
    embed.add_field(name="Location", value="Chicago, IL, USA", inline=True)
    embed.add_field(
        name="Buy Tickets",
        value="[Click Here](https://pokemongolive.com)",
        inline=False,
    )
    embed.set_footer(text="Tickets sell out in minutes. Good luck, Trainer!")

    try:
        await channel.send(content=f"🚨 {ping} **TEST ALERT** 🚨", embed=embed)
        await interaction.response.send_message("✅ Test alert sent!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to send messages in that channel.", ephemeral=True
        )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
bot.run(TOKEN)
