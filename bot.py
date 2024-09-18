import discord
from discord.ext import commands
import json
import asyncio
import unicodedata
from flask import Flask
import threading

# Load the passwords from a JSON file
with open("passwords.json", "r", encoding="utf-8") as f:
    password_data = json.load(f)

# Load the list of users who have already been messaged
try:
    with open("messaged_users.json", "r", encoding="utf-8") as f:
        messaged_users = set(json.load(f))
except FileNotFoundError:
    messaged_users = set()

# Set up intents and bot
intents = discord.Intents.default()
intents.members = True  # Enable member events
intents.message_content = True  # Enable reading message content (required for commands)
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Role and Channel names
VERIFIED_ROLE_NAME = "Elita Národa"
WELCOME_CHANNEL_NAME = "welcome"
ADMIN_ROLE_NAME = "Admin"  # Replace this with your actual admin role name

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

def normalize_string(s):
    # Normalize diacritics and convert to lowercase
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower())
                   if unicodedata.category(c) != 'Mn')

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
        if not member.bot and role not in member.roles and str(member.id) not in messaged_users:
            try:
                await member.send(f"**Welcome** {member.mention}! Please provide your full name to access the G1.E, **using command !verify your full name.**")
                messaged_users.add(str(member.id))
                with open("messaged_users.json", "w", encoding="utf-8") as f:
                    json.dump(list(messaged_users), f, ensure_ascii=False)
            except discord.Forbidden:
                print(f"Could not DM {member.name}.")
            await asyncio.sleep(1)

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = discord.utils.get(guild.channels, name=WELCOME_CHANNEL_NAME)

    if str(member.id) not in messaged_users:
        try:
            await member.send(f"**Welcome** {member.mention}! Please provide your full name to access the G1.E, **using command !verify your full name.**")
            messaged_users.add(str(member.id))
            with open("messaged_users.json", "w", encoding="utf-8") as f:
                json.dump(list(messaged_users), f, ensure_ascii=False)
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

    normalized_otp = normalize_string(otp)
    exact_name = None

    # Find the exact name with diacritics
    for name in password_data:
        if normalize_string(name) == normalized_otp:
            exact_name = name
            break

    if exact_name:
        if role is None:
            await member.send("Verified role not found. Please contact an admin.")
            return

        member = guild.get_member(member.id)
        if member is None:
            await ctx.send("Couldn't find you in the server.")
            return

        await member.add_roles(role)
        await member.edit(nick=exact_name)

        await member.send("Your name is on the list! You now have access to the server.")

        general_channel = discord.utils.get(guild.channels, name="general")
        if general_channel:
            await general_channel.send(f"Welcome {member.mention}, access granted!")

        del password_data[exact_name]
        with open("passwords.json", "w", encoding="utf-8") as f:
            json.dump(password_data, f, ensure_ascii=False)
    else:
        await member.send("The name you provided is not on the list. Please try again or contact admin.")

# Command to add a new name to the list (Admin only, Server only)
@bot.command()
@commands.has_role(ADMIN_ROLE_NAME)  # Restrict to Admin role
async def add_name(ctx, *, name: str):
    if ctx.guild is None:  # Check if the command is in a server
        await ctx.send("This command can only be used in a server.")
        return
    if name in password_data:
        await ctx.send(f"The name `{name}` is already in the list.")
    else:
        password_data[name] = True
        with open("passwords.json", "w", encoding="utf-8") as f:
            json.dump(password_data, f, ensure_ascii=False)
        await ctx.send(f"Added `{name}` to the list.")

# Command to delete a name from the list (Admin only, Server only)
@bot.command()
@commands.has_role(ADMIN_ROLE_NAME)  # Restrict to Admin role
async def delete_name(ctx, *, name: str):
    if ctx.guild is None:  # Check if the command is in a server
        await ctx.send("This command can only be used in a server.")
        return
    if name in password_data:
        del password_data[name]
        with open("passwords.json", "w", encoding="utf-8") as f:
            json.dump(password_data, f, ensure_ascii=False)
        await ctx.send(f"Deleted `{name}` from the list.")
    else:
        await ctx.send(f"The name `{name}` was not found in the list.")

# Command to send reminder messages to unverified users (Admin only, Server only)
@bot.command()
@commands.has_role(ADMIN_ROLE_NAME)  # Restrict to Admin role
async def ping(ctx):
    if ctx.guild is None:  # Check if the command is in a server
        await ctx.send("This command can only be used in a server.")
        return

    role = discord.utils.get(ctx.guild.roles, name=VERIFIED_ROLE_NAME)
    if role is None:
        await ctx.send("Verified role not found.")
        return

    for member in ctx.guild.members:
        if not member.bot and role not in member.roles and str(member.id) not in messaged_users:
            try:
                await member.send(f"**Reminder** {member.mention}, please provide your full name to access the G1.E using the command `!verify your full name`.")
                messaged_users.add(str(member.id))
                with open("messaged_users.json", "w", encoding="utf-8") as f:
                    json.dump(list(messaged_users), f, ensure_ascii=False)
            except discord.Forbidden:
                print(f"Could not DM {member.name}.")
            await asyncio.sleep(1)

# Help command to provide a list of available commands
@bot.command()
async def help(ctx):
    help_text = """
    **Available Commands:**
    - `!verify your full name`: Verify your identity by providing your full name (only usable in DMs).
    - `!add_name name`: (Admin only) Add a new name to the verification list.
    - `!delete_name name`: (Admin only) Remove a name from the verification list.
    - `!ping`: (Admin only) Send reminder messages to unverified users.
    - `!help`: Display this help message.
    """
    await ctx.send(help_text)

# Keep the bot alive using Flask
keep_alive()

# Run the bot with your token
bot.run("MTI4NTY4MjI2ODAzOTU0NDgzMg.G4Ecqv.UkceLHkH4wVEEKi_vmbHZsf7fcB-SL2Ge9l84c")
