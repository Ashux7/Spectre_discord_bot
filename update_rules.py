with open(r'd:\CODES\SPECTRE_DISCORD\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_cmd_start = content.find('@bot.command(name="rules"')
old_cmd_end = content.find('@bot.event', old_cmd_start)

new_func = '''@bot.command(name="rules", aliases=["rulebook"])
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

    embed = discord.Embed(
        title="📜 THE LATTICE • Official Rulebook",
        description=(
            "Welcome participants to **The Lattice**! The full official rulebook, event mechanics, and code of conduct are attached below.\n\n"
            "📄 **Please download and review the attached document carefully.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ **Key Highlights:**\n"
            "• **Team Size:** 2 members (must stay together at all times)\n"
            "• **Duration:** 5.5 hours\n"
            f"• **Trading:** Clues must be traded only in {marketplace_mention}\n"
            "• **Emergency:** Say *'OUT OF GAME'* in case of real emergency"
        ),
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.set_footer(text="The Lattice • SPECTRE x MERAZ", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    file = discord.File(rulebook_path, filename="rulebook.txt")
    await ctx.send(embed=embed, file=file)


'''

updated_content = content[:old_cmd_start] + new_func + content[old_cmd_end:]
with open(r'd:\CODES\SPECTRE_DISCORD\main.py', 'w', encoding='utf-8') as f:
    f.write(updated_content)

print("Updated successfully")

