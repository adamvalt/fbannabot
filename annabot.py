import os
from typing import Literal, Optional
import asyncio
import discord
from datetime import datetime
from discord.ext.commands import Greedy, Context
from discord.ext import commands, tasks

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)
synced = []

channel_ids = {
    827552957951901716: 827552957951901720,
    1056344795699757126: 1056344795699757129,
}

data = {
    "niezle": "https://cdn.discordapp.com/attachments/827552957951901720/1108861667779035156/niezle.png",
    "pici": "https://cdn.discordapp.com/attachments/827552957951901720/1108861667334443038/pici.png",
    "pici_brezno": "https://cdn.discordapp.com/attachments/1056352797978787841/1105750043463520286/IMG_20230507_184356.png",
    "rejnou": "https://tenor.com/view/eeej-dobre-rejnou-dobre-rano-gm-gif-25805857",
    "picus": "https://cdn.discordapp.com/attachments/827552957951901720/1121836399411351613/picus.jpg",
}


# --- Bot Startup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}! posting to {channel_ids}")
    if not send_message_at_midnight.is_running():
        send_message_at_midnight.start()


# ------ Slash Commands ------
@bot.tree.command()
async def setchannel(
    interaction: discord.Interaction,
):
    """Set channel for posting anna photos"""
    channel_ids[interaction.guild_id] = interaction.channel_id
    print(channel_ids)
    await interaction.response.send_message(
        f"Photos will now be posted in <#{channel_ids[interaction.guild_id]}>."
    )


@bot.command()
@commands.is_owner()
async def sync(
    ctx: Context,
    guilds: Greedy[discord.Object],
    spec: Optional[Literal["~", "*", "^"]] = None,
) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


# ------ Custom Commands ------


@bot.command()
async def cat(ctx):
    await ctx.send("meow")


@bot.command()
async def niezle(ctx):
    await ctx.send(data["niezle"])


@bot.command()
async def pici(ctx):
    await ctx.send(data["pici"])


@bot.command()
async def brezno(ctx):
    await ctx.send(data["pici_brezno"])


@bot.command()
async def rejnou(ctx):
    await ctx.send(data["rejnou"])


@bot.command()
async def picus(ctx):
    await ctx.send(data["picus"])


# ------ Custom Events ------


@bot.event
async def on_message(message):
    for item in ["odpusti", "odpustí", "odpusť", "odpust"]:
        if (
            item in message.content.lower()
            and ":odpustamti:" not in message.content.lower()
        ):
            odpusti_emote = discord.utils.get(message.guild.emojis, name="odpustamti")
            if odpusti_emote is not None:
                await message.add_reaction(odpusti_emote)
                # await bot.process_commands(message)
                # return
    await bot.process_commands(message)


@tasks.loop(seconds=0, minutes=1, hours=0, count=None)
async def send_message_at_midnight():
    now = datetime.now()
    guild_id = 1056344795699757126
    channel_id = 1056344795699757129
    if now.hour == 22 and now.minute == 00:
        try:
            guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
            channel = guild.get_channel(channel_id) or await guild.fetch_channel(
                channel_id
            )

            if now.date().isoweekday() == 1:
                await channel.send(f"Šťastný nový pondelok! :((")
                await channel.send(data["pici"])
            else:
                await channel.send(f"Šťastný nový deň!")
        except Exception as e:
            print("Can not post to ", guild_id, channel_id, "because: ", e)
        await asyncio.sleep(60)


bot.run(os.environ.get("TOKEN"))
