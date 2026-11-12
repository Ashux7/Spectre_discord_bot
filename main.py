import os
import asyncio
import logging
from datetime import datetime, timezone
import discord
from discord.ext import commands
from dotenv import load_dotenv
import time
import re

load_dotenv()
token = os.getenv('TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

GROUP_MANAGER_ROLE_ID = 1421557314598473799



@bot.check
async def globally_check_group_manager(ctx: commands.Context):
    # Allow 'trade' command for everyone
    if ctx.command and ctx.command.name in ("trade", "help"):
        return True
    
    if not ctx.guild:
        return False
        
    role = ctx.guild.get_role(GROUP_MANAGER_ROLE_ID)
    if role and role in ctx.author.roles:
        return True
        
    raise commands.MissingRole(role.name if role else "Group_Manager")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    # If the command has its own error handler (like clear), let it handle it
    if hasattr(ctx.command, 'on_error'):
        return

    if isinstance(error, commands.MissingRole):
        await ctx.send("❌ You do not have permission to use this command! Only **Group_Manager** can use it.", delete_after=5)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You do not meet the requirements to run this command.", delete_after=5)
    else:
        # Ignore or log other unhandled command errors
        pass




@bot.before_invoke
async def delete_command_invoker_message(ctx: commands.Context):
    """Automatically deletes the message that triggered any command except !trade."""
    if ctx.command and ctx.command.name != "trade":
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass


# ----------------- Ticket Timer & Logger -----------------
async def handle_ticket_lifecycle(channel: discord.TextChannel, creator: discord.Member, claimer: discord.Member):
    # Wait 4 minutes (240s), then send a 1-minute warning
    await asyncio.sleep(240)
    try:
        await channel.send("⚠️ **This ticket channel will self-destruct in 1 minute!** Chat logs will be saved.")
    except discord.NotFound:
        return  # Channel was manually deleted early

    # Wait final 1 minute (60s)
    await asyncio.sleep(60)

    # 1. Fetch chat history and save to a log file
    os.makedirs("ticket_logs", exist_ok=True)
    log_filename = f"ticket_logs/ticket_{channel.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(log_filename, "w", encoding="utf-8") as f:
        f.write("================ TICKET LOG ================\n")
        f.write(f"Channel ID : {channel.id}\n")
        f.write(f"Creator    : {creator.name} ({creator.id})\n")
        f.write(f"Claimer    : {claimer.name} ({claimer.id})\n")
        f.write(f"Closed At  : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write("============================================\n\n")

        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            f.write(f"[{timestamp}] {msg.author.name} ({msg.author.display_name}): {msg.content}\n")
            if msg.attachments:
                for attachment in msg.attachments:
                    f.write(f"    [Attachment] {attachment.url}\n")

    # 2. (Optional) Send log transcript copy to both users via DM
    for user in (creator, claimer):
        try:
            await user.send(
                content=f"📄 Transcript for your ticket with **{claimer.display_name if user == creator else creator.display_name}**:",
                file=discord.File(log_filename)
            )
        except (discord.Forbidden, discord.HTTPException):
            pass  # User has DMs closed

    # 3. Delete the channel
    try:
        await channel.delete(reason="Ticket expired (5-minute limit).")
    except discord.NotFound:
        pass


# ----------------- Button View -----------------
class TicketClaimView(discord.ui.View):
    def __init__(self, creator: discord.Member):
        super().__init__(timeout=None)
        self.creator = creator
        self.claimed = False

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, emoji="📩")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent creator from claiming their own ticket
        if interaction.user.id == self.creator.id:
            await interaction.response.send_message("❌ You cannot claim your own ticket!", ephemeral=True)
            return

        # Prevent double-claims
        if self.claimed:
            await interaction.response.send_message("❌ This ticket has already been claimed!", ephemeral=True)
            return

        self.claimed = True
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

        guild = interaction.guild
        claimer = interaction.user

        # Set private permissions: only creator, claimer, and bot can view/send
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), # type: ignore
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True), # type: ignore
            self.creator: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            claimer: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        # Keep it in the same category as the current channel if available
        category = interaction.channel.category if isinstance(interaction.channel, discord.TextChannel) else None
        channel_name = f"ticket-{self.creator.name[:10]}-{claimer.name[:10]}"

        # Create private text channel
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category) # type: ignore

        # Notify inside the new channel
        embed = discord.Embed(
            title="Private Ticket Channel",
            description=(
                f"Welcome {self.creator.mention} and {claimer.mention}!\n\n"
                "⏳ **This channel will automatically self-destruct in 5 minutes.**\n"
                "All messages will be logged and saved."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        await ticket_channel.send(content=f"{self.creator.mention} {claimer.mention}", embed=embed)

        # Confirm to claimer
        await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

        # Start the 5-minute timer in the background
        bot.loop.create_task(handle_ticket_lifecycle(ticket_channel, self.creator, claimer)) # type: ignore


# ----------------- Commands -----------------
@bot.command(name="trade")
@commands.guild_only()
async def create_ticket(ctx: commands.Context):
    """Creates a trade ticket embed with a claim button (only in #marketplace)."""
    # Enforce #marketplace channel only
    if ctx.channel.name != "marketplace":
        marketplace = discord.utils.get(ctx.guild.text_channels, name="marketplace")
        marketplace_mention = marketplace.mention if marketplace else "#marketplace"
        await ctx.send(
            f"❌ The `!trade` command can only be used in {marketplace_mention}!",
            delete_after=5
        )
        return

    embed = discord.Embed(
        title="1-on-1 Trade Ticket",
        description=(
            f"**Creator:** {ctx.author.mention}\n\n"
            "Click **Claim Ticket** below to start a private 1-on-1 trade channel with the creator.\n"
            "⚡ *Only the first person to click can enter. The channel self-destructs after 5 minutes.*"
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Spectre Ticket System")

    view = TicketClaimView(creator=ctx.author) # type: ignore
    await ctx.send(embed=embed, view=view)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """Shows the bot's latency."""
    # WebSocket heartbeat latency
    ws_latency = round(bot.latency * 1000)

    # Calculate message round-trip (API latency)
    start_time = time.monotonic()
    message = await ctx.send("🏓 Pinging...")
    end_time = time.monotonic()
    api_latency = round((end_time - start_time) * 1000)

    await message.edit(
        content=(
            f"🏓 **Pong!**\n"
            f"📡 **WebSocket Latency:** `{ws_latency}ms`\n"
            f"⚡ **API Latency:** `{api_latency}ms`"
        )
    )


@bot.command(name="clear", aliases=["purge"])
@commands.guild_only()
async def clear(ctx: commands.Context, amount: int):
    """Clears the specified number of messages from the channel."""
    if amount <= 0:
        await ctx.send("❌ Please specify a number greater than 0.", delete_after=5)
        return

    # Delete amount + 1 so it also deletes the '!clear' command message itself
    deleted = await ctx.channel.purge(limit=amount + 1) # type: ignore
    # Count messages deleted excluding the command invocation itself
    cleared_count = max(0, len(deleted) - 1)
    await ctx.send(f"Cleared **{cleared_count}** messages.", delete_after=5)


@clear.error
async def clear_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingRole):
        await ctx.send("❌ You do not have permission to use this command! Only **Group_Manager** can clear messages.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Please specify how many messages to clear. Example: `!clear 10`", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Please provide a valid number. Example: `!clear 10`", delete_after=5)
    else:
        await ctx.send(f"❌ Error: {error}", delete_after=5)


@bot.command(name="welcom_gen", aliases=["welcome_gen"])
@commands.guild_only()
async def welcom_gen(ctx: commands.Context):
    """Sends the official SPECTRE Cybersecurity Club general welcome embed."""
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    desc = (
        "```ini\n"
        "[ SPECTRE // CYBERSECURITY CLUB // IIT BHILAI ]\n"
        "[ ACCESS_LEVEL: 001 // STATUS: INITIALIZED     ]\n"
        "```\n"
        "### ⚡ BREAK THE CODE.\n"
        "*Tired of vibe-coding tutorials? Come break things instead.*\n\n"
        "**ETHICAL HACKING // BUG HUNTING // CTFs**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 **WHAT'S THE POINT?**\n"
        "Writing code is one skill. Reading it well enough to find where it breaks is another.\n\n"
        "That's what bug hunting and ethical hacking actually are—not typing code like a corpse, "
        "but seeing through the syntax and finding hidden gaps everyone else scrolls past.\n\n"
        "Here at **SPECTRE**, we explore what the realm of cybersecurity truly looks like:\n"
        "• **Hunt Real Bugs:** Find vulnerabilities in real-world apps and web infrastructure.\n"
        "• **Master CTFs:** Sharpen your skills through competitive Capture The Flag challenges.\n"
        "• **Hands-On Labs:** Break into isolated machines legally built for practice.\n\n"
        "```bash\n"
        "root@spectre:~$ ./discover_vulnerabilities\n"
        "> scanning curiosity... [OK]\n"
        "> loading CTF environment... [OK]\n"
        "> access granted.\n"
        "```\n"
        "👁️ *Ever wondered how people discover zero-days, exploit vulnerable machines for fun, "
        "or want to play GTA 6 without spending even a single penny?*\n\n"
        "**This is your entry point. Welcome to the grid.**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    embed = discord.Embed(
        title="☠️ WELCOME TO SPECTRE",
        description=desc,
        color=discord.Color.from_rgb(0, 255, 65)  # Matrix / Terminal Hacker Green
    )
    embed.set_footer(
        text="SPECTRE • Cybersecurity Club of IIT Bhilai",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else None
    )

    await ctx.send(embed=embed)


@bot.command(name="welcome", aliases=["intro"])
@commands.guild_only()
async def welcome(ctx: commands.Context):

    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass
    
    """Sends the official welcome embed for The Lattice event."""
    marketplace = discord.utils.get(ctx.guild.text_channels, name="marketplace")
    marketplace_mention = marketplace.mention if marketplace else "#marketplace"

    embed = discord.Embed(
        title="🕵️ WELCOME TO THE LATTICE",
        description=(
            "Somewhere between the agreements signed in quiet rooms and the peace that holds when everything says it shouldn't, there is a structure. "
            "You have heard its voice. You are about to become part of it.\n\n"
            "**THE LATTICE** is a campus-wide mystery game. Teams of two follow clues across recordings, Instagram pages, ciphers, and a few things.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Important Instruction:**\n"
            f"Participants are requested to trade their clues only in {marketplace_mention}."
        ),
        color=discord.Color.from_rgb(139, 0, 0)  # Dark Crimson Noir style
    )
    embed.set_footer(text="The Lattice • SPECTRE x MERAZ", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    image_path = os.path.join(os.path.dirname(__file__), "the_lattice.jpg")
    if os.path.exists(image_path):
        file = discord.File(image_path, filename="the_lattice.jpg")
        embed.set_image(url="attachment://the_lattice.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)


@bot.command(name="rules", aliases=["rulebook"])
@commands.guild_only()
async def rules(ctx: commands.Context):
    """Sends the official rulebook file directly and deletes the command invocation."""
    # Delete the user's !rules message immediately
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    rulebook_path = os.path.join(os.path.dirname(__file__), "rulebook.txt")
    if not os.path.exists(rulebook_path):
        await ctx.send("❌ `rulebook.txt` could not be found.", delete_after=5)
        return

    marketplace = discord.utils.get(ctx.guild.text_channels, name="marketplace")
    marketplace_mention = marketplace.mention if marketplace else "#marketplace"

    description_text = (
        "Welcome participants to **The Lattice**! The full official rulebook, event mechanics, and code of conduct are attached below.\n\n"
        "📄 **Please download and review the attached document carefully.**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ **Key Highlights:**\n"
        "• **Team Size:** 2 members (must stay together at all times)\n"
        "• **Duration:** 5.5 hours\n"
        f"• **Trading:** Clues must be traded only in {marketplace_mention}\n"
        "• **Emergency:** Say *'OUT OF GAME'* in case of real emergency"
    )

    embed = discord.Embed(
        title="📜 THE LATTICE • Official Rulebook",
        description=description_text,
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.set_footer(text="The Lattice • SPECTRE x MERAZ", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    file = discord.File(rulebook_path, filename="rulebook.txt")
    await ctx.send(embed=embed, file=file)


LATTICE_ROLE_ID = 1563637980604796978


class LatticeRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Click to Enter The Lattice",
        style=discord.ButtonStyle.danger,
        emoji="🚪",
        custom_id="enter_the_lattice_button"
    )
    async def enter_lattice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ This button can only be used in a server.", ephemeral=True)
            return

        role = guild.get_role(LATTICE_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Error: LATTICE role not found. Please contact an admin.", ephemeral=True)
            return

        # Find #init channel for interactive link
        init_channel = discord.utils.get(guild.text_channels, name="init")
        init_mention = init_channel.mention if init_channel else "#init"

        if isinstance(interaction.user, discord.Member):
            if role in interaction.user.roles:
                await interaction.response.send_message(
                    f"⚠️ You already have the **LATTICE** role! Please go to {init_mention}.",
                    ephemeral=True
                )
                return

            try:
                await interaction.user.add_roles(role, reason="Entered The Lattice via button")
                await interaction.response.send_message(
                    f"✅ You have entered **The Lattice** and received the **LATTICE** role! Please go to {init_mention}.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to give you the role. Please ensure my bot role is higher than the LATTICE role.",
                    ephemeral=True
                )


@bot.command(name="help")
@commands.guild_only()
async def custom_help(ctx: commands.Context):
    """Displays all available commands and their required roles."""
    desc = (
        "Here is the list of all available commands and the minimum role required to run each:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👥 **Accessible to Everyone:**\n"
        "• `!trade` - Creates a private 1-on-1 trading ticket in #marketplace (self-destructs after 5 mins).\n"
        "• `!help` - Displays this help guide.\n\n"
        "🔒 **Requires Role: Group_Manager:**\n"
        "• `!lattice` - Generates the interactive button allowing users to claim the `LATTICE` role.\n"
        "• `!welcome_gen` (alias: `!welcom_gen`) - Sends the official SPECTRE Cybersecurity Club welcome message.\n• `!welcome` (alias: `!intro`) - Sends the official welcome & event overview embed.\n"
        "• `!rules` (alias: `!rulebook`) - Sends the event rulebook file attachment & overview.\n"
        "• `!clear <number>` (alias: `!purge`) - Clears the last `n` messages in the channel.\n"
        "• `!ping` - Shows WebSocket and API response latency.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    embed = discord.Embed(
        title="🤖 SPECTRE Bot Commands & Permissions",
        description=desc,
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.set_footer(text="The Lattice • SPECTRE x MERAZ", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)


@bot.command(name="lattice")
@commands.guild_only()
async def lattice(ctx: commands.Context):
    """Generates the embed and button to enter The Lattice."""
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    embed = discord.Embed(
        title="🌐 THE LATTICE",
        description="Somewhere between the agreements signed in quiet rooms and the peace that holds when everything says it shouldn't, there is a structure.\n\n👉 **Click to enter The Lattice.**",
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.set_footer(text="The Lattice • SPECTRE x MERAZ", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    view = LatticeRoleView()
    await ctx.send(embed=embed, view=view)


@bot.event
async def on_ready():
    bot.add_view(LatticeRoleView())

    print(f"Logged in as {bot.user} (ID: {bot.user.id})") # type: ignore


bot.run(token, log_handler=handler, log_level=logging.INFO) #type:ignore