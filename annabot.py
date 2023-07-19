import asyncio
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from PIL import Image, ImageDraw, ImageFont
from unidecode import unidecode

FONT_LOCATION = "/usr/share/fonts/TTF/DejaVuSans.ttf"


class AnnaDB:
    def __init__(self, db_path="anna.db"):
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self.setup_db()

    def setup_db(self):
        self.execute(
            "CREATE TABLE IF NOT EXISTS autodelete(channel_id INTEGER PRIMARY KEY, minutes INTEGER)"
        )
        self.execute(
            "CREATE TABLE IF NOT EXISTS annaposting(guild_id INTEGER, channel_id INTEGER PRIMARY KEY)"
        )
        self.execute(
            "CREATE TABLE IF NOT EXISTS customcommands(command_name TEXT PRIMARY KEY, command_response TEXT)"
        )
        self.execute(
            "CREATE TABLE IF NOT EXISTS newday(channel_id INTEGER PRIMARY KEY)"
        )
        self.commit()

    def close(self):
        self.connection.close()

    def execute(self, *args):
        return self.cursor.execute(*args)

    def commit(self):
        self.connection.commit()

    def get_customcommands(self):
        return self.execute("SELECT * FROM customcommands").fetchall()

    def get_places(self):
        return self.execute("SELECT name, name_locative FROM places").fetchall()

    def get_autodelete(self):
        return self.execute("SELECT * FROM autodelete").fetchall()

    def get_newday(self):
        return self.execute("SELECT * FROM newday").fetchall()


class AnnaBot(commands.Bot):
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    prefix = "."

    def __init__(self):
        super().__init__(command_prefix=self.prefix, intents=self.intents)
        self.db = AnnaDB()
        self.cached_cities: List[str] = self.db.get_places()
        self.setup_commands()

    def setup_commands(self):
        for command_name, command_response in self.db.get_customcommands():
            self.create_command(command_name, message=command_response)

    def create_command(self, name, message=None, file=None):
        async def command(ctx):
            await ctx.send(message, file=file)

        self.add_command(commands.command(name=name)(command))

    def delete_command(self, name):
        self.remove_command(name)


bot = AnnaBot()


# --- Bot Startup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    if not on_each_minute.is_running():
        print("Starting on_each_minute")
        on_each_minute.start()


# ------ Slash Commands ------
@bot.tree.command()
@commands.has_permissions(administrator=True)
async def setup_annaposting(interaction: discord.Interaction):
    """Set channel for posting anna photos"""
    bot.db.execute(
        "INSERT OR REPLACE INTO annaposting(guild_id, channel_id) VALUES (?, ?)",
        (interaction.guild_id, interaction.channel_id),
    )
    bot.db.commit()
    await interaction.response.send_message(
        f"Photos will now be posted in <#{interaction.channel_id}>."
    )


@bot.tree.command()
async def setup_midnight_mesage(interaction: discord.Interaction):
    """Set channel for sending happy new day message"""
    bot.db.execute(
        "INSERT OR REPLACE INTO newday(channel_id) VALUES (?)",
        (interaction.channel_id,),
    )
    bot.db.commit()
    await interaction.response.send_message(
        f"Happy new day message will now be sent in <#{interaction.channel_id}>."
    )


@bot.tree.command()
async def add_annacommand(
    interaction: discord.Interaction,
    command_name: str,
    command_response: str,
):
    """Add custom command"""
    bot.db.execute(
        "INSERT OR REPLACE INTO customcommands(command_name, command_response) VALUES (?, ?)",
        (command_name, command_response),
    )
    bot.db.commit()
    bot.create_command(command_name, message=command_response)
    await interaction.response.send_message(f"Custom command '.{command_name}' added.")


@bot.tree.command()
async def remove_annacommand(
    interaction: discord.Interaction,
    command_name: str,
):
    f"""Remove added custom command. Input command name without the prefix - '{bot.prefix}'"""
    bot.db.execute(
        "DELETE FROM customcommands WHERE command_name = ?",
        (command_name,),
    )
    bot.db.commit()
    bot.delete_command(command_name)
    await interaction.response.send_message(
        f"Custom command '.{command_name}' deleted."
    )


@bot.tree.command()
async def list_annacommands(interaction: discord.Interaction) -> None:
    """List all registered custom commands"""
    commands = bot.db.get_customcommands()
    await interaction.response.send_message(
        "\n".join([f".{command[0]}" for command in commands])
        if commands != []
        else "No custom commands registered."
    )


@bot.tree.command()
async def setup_delete(interaction: discord.Interaction, hours: int) -> None:
    """Set autodelete of old messages in this channel.
    Set to 0 to disable"""
    if hours < 0:
        await interaction.response.send_message("Hours must be a positive integer.")
        return
    bot.db.execute(
        "INSERT OR REPLACE INTO autodelete(channel_id, minutes) VALUES (?, ?)",
        (interaction.channel_id, hours * 60),
    )
    bot.db.commit()
    await interaction.response.send_message(
        f"Messages older than {hours}h will now be deleted in <#{interaction.channel_id}>."
        if hours > 0
        else "Autodelete disabled."
    )


# ------ Classic Commands ------


@bot.command()
@commands.is_owner()
async def sync(ctx: Context) -> None:
    synced = await bot.tree.sync(guild=None)
    await ctx.send(f"Synced {len(synced)} commands globally.")


@bot.command()
@commands.is_owner()
async def clear(ctx: Context) -> None:
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync(guild=None)
    await ctx.send(f"Deleted commands globally.")


# ------ Events ------


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await add_odpusti(message)
    await process_custom_commands_wrapper(message)


@tasks.loop(seconds=0, minutes=1, hours=0, count=None)
async def on_each_minute():
    await send_message_at_midnight()
    await delete_old_messages()


def cleanup_and_format_city_name(name: str) -> Optional[str]:
    def correct_name_length(name: str, max_length: str) -> str:
        return name.replace(" ", "\n", 1) if len(name) > max_length else name

    def get_city_name_or_none(name: str) -> Optional[str]:
        target_city = unidecode(name.upper())
        for city_name, city_name_locative in bot.cached_cities:
            if target_city == unidecode(city_name.upper().replace(" ", "_")):
                return format_city_name(city_name, city_name_locative)
        return None

    def prepend_article(name: str) -> str:
        return "o " if name[0].upper() == "V" else " "

    def format_city_name(city_name: str, locative_name: Optional[str]) -> str:
        if locative_name is None:
            return " " + correct_name_length("meste " + city_name, 11)
        return prepend_article(city_name) + correct_name_length(locative_name, 12)

    return get_city_name_or_none(name)


def create_image_with_text(image, text, pos):
    i = Image.open(image)
    draw = ImageDraw.Draw(i)
    font = ImageFont.truetype(FONT_LOCATION, 14, encoding="unic")
    draw.text(pos, text, font=font, fill=(0, 0, 0))
    image_name = "temp_image.png"
    # workaraound with saving and then deleting the image
    i.save(image_name)
    file = discord.File(image_name)
    os.remove(image_name)
    return file


async def process_custom_commands_wrapper(message: discord.Message):
    content: str = message.content.lower()
    pici_prefix = "pici_"
    command_prefix = bot.prefix + pici_prefix
    original_city_name, _, _ = content.removeprefix(command_prefix).partition(" ")
    temp_command = pici_prefix + original_city_name

    city_name = cleanup_and_format_city_name(original_city_name)
    if content.startswith(command_prefix) and city_name is not None:
        image = create_image_with_text("baseimg_blank.png", city_name, (227, 308))
        # creating temporary command prevents throwing an
        # error when command with that name is not found
        bot.create_command(temp_command, file=image)
        await bot.process_commands(message)
        bot.delete_command(temp_command)
    else:
        await bot.process_commands(message)


async def add_odpusti(message):
    for item in ["odpusti", "odpustí", "odpusť", "odpust"]:
        if (
            item in message.content.lower()
            and ":odpustamti:" not in message.content.lower()
        ):
            odpusti_emote = discord.utils.get(message.guild.emojis, name="odpustamti")
            if odpusti_emote is not None:
                await message.add_reaction(odpusti_emote)


async def delete_old_messages():
    for channel_id, minutes in bot.db.get_autodelete():
        channel = bot.get_channel(channel_id)
        if channel is not None and minutes > 0:
            offset_curent_datetime = datetime.now() - timedelta(minutes=minutes)
            async for message in channel.history(
                limit=20, oldest_first=True, before=offset_curent_datetime
            ):
                await message.delete()
                await asyncio.sleep(2)  # rate limit prevention


async def send_message_at_midnight():
    now = datetime.utcnow()
    for channel_id in bot.db.get_newday():
        if now.hour == 22 and now.minute == 00:
            channel = bot.get_channel(channel_id)
            if now.date().isoweekday() == 1:
                img = bot.db.execute(
                    "SELECT command_response FROM customcommands WHERE command_name = 'pici'"
                ).fetchone()
                await channel.send(f"Šťastný nový pondelok! :((")
                await channel.send(img)
            else:
                await channel.send(f"Šťastný nový deň!")


if __name__ == "__main__":
    bot.run(os.environ.get("TOKEN"))
