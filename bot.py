import discord
from discord.ext import commands
import json
import asyncio
from flask import Flask
import threading

# Load the passwords from a JSON file
with open("passwords.json", "r", encoding="utf-8") as f:
    password_data = json.load(f)

# Set up intents and bot
intents = discord.Intents.default()
intents.members = True  # Enable member events
bot = commands.Bot(command_prefix="!", intents=intents)

# Role and Channel names
VERIFIED_ROLE_NAME = "Elita Národa"
WELCOME_CHANNEL_NAME = "welcome"

# Flask app for uptime monitoring
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=3000)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

    # Get the first guild (server) the bot is in
    global guild
    guild = bot.guilds[0]

    # Check if the "welcome" channel exists; if not, create it
    welcome_channel = discord.utils.get(guild.channels, name=WELCOME_CHANNEL_NAME)
    if welcome_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        }
        welcome_channel = await guild.create_text_channel(WELCOME_CHANNEL_NAME, overwrites=overwrites)
        print(f'Welcome channel "{WELCOME_CHANNEL_NAME}" created.')

    # Check if the "Verified" role exists; if not, create it
    role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if role is None:
        role = await guild.create_role(name=VERIFIED_ROLE_NAME)
        print(f'Role "{VERIFIED_ROLE_NAME}" created.')

    # DM all unverified users
    await dm_unverified_users()

async def dm_unverified_users():
    role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if role is None:
        return

    for member in guild.members:
        if not member.bot and role not in member.roles:
            try:
                await member.send(f"**Welcome** {member.mention}! Please provide your one-time full name to access the G1.E, **using command !verify yourfullname.**")
            except discord.Forbidden:
                print(f"Could not DM {member.name}.")
            await asyncio.sleep(1)

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = discord.utils.get(guild.channels, name=WELCOME_CHANNEL_NAME)

    try:
        await member.send(f"**Welcome** {member.mention}! Please provide your one-time full name to access the G1.E, **using command !verify yourfullname.**")
    except discord.Forbidden:
        if welcome_channel:
            await welcome_channel.send(f"Hey {member.mention}, I couldn't DM you! Please check your settings and try again.")

@bot.command()
async def verify(ctx, *, otp: str):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("This command can only be used in DMs.")
        return

    member = ctx.author
    guild = bot.guilds[0]
    role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)

    if otp in password_data:
        if role is None:
            await member.send("Verified role not found. Please contact an admin.")
            return

        member = guild.get_member(member.id)
        if member is None:
            await ctx.send("Couldn't find you in the server.")
            return

        await member.add_roles(role)
        await member.edit(nick=otp)

        await member.send("Your name is on the list! You now have access to the server.")

        general_channel = discord.utils.get(guild.channels, name="general")
        if general_channel:
            await general_channel.send(f"Welcome {member.mention}, access granted!")

        del password_data[otp]
        with open("passwords.json", "w", encoding="utf-8") as f:
            json.dump(password_data, f, ensure_ascii=False)
    else:
        await member.send("The name you provided is not on the list. Please try again or contact admin.")

# Keep the bot alive using Flask
keep_alive()

# Run the bot with your token
bot.run("MTI4NTY4MjI2ODAzOTU0NDgzMg.G4Ecqv.UkceLHkH4wVEEKi_vmbHZsf7fcB-SL2Ge9l84c")