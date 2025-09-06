# bot.py
import os
import discord
from discord.ext import commands
from discord import PermissionOverwrite
from flask import Flask
import threading

# ---------- إعدادات ----------
PREFIX = "!"
TICKET_CATEGORY_NAME = "Tickets"
TICKET_ROLE_NAME = "Support"
MUTED_ROLE_NAME = "Muted"   # الرتبة الخاصة بالكتم
PORT = int(os.environ.get("PORT", 8080))
TOKEN = os.environ.get("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("Please set the DISCORD_TOKEN environment variable.")

# ---------- Intents ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ---------- Flask app ----------
app = Flask("keep_alive_app")

@app.route("/")
def home():
    return "Bot is running."

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# ---------- Utilities ----------
async def get_or_create_ticket_category(guild: discord.Guild):
    for c in guild.categories:
        if c.name == TICKET_CATEGORY_NAME:
            return c
    overwrites = {
        guild.default_role: PermissionOverwrite(read_messages=False),
        guild.me: PermissionOverwrite(read_messages=True)
    }
    return await guild.create_category(TICKET_CATEGORY_NAME, overwrites=overwrites)

# ---------- Ticket Commands ----------
@bot.command(name="ticket")
async def ticket(ctx, action: str = None, *, reason: str = None):
    if action is None:
        await ctx.send("استخدم: `!ticket open <السبب>` أو `!ticket close`.")
        return

    guild = ctx.guild

    if action.lower() in ("open", "فتح"):
        category = await get_or_create_ticket_category(guild)
        chan_name = f"ticket-{ctx.author.name}".lower().replace(" ", "-")
        existing = discord.utils.get(category.text_channels, name=chan_name)
        if existing:
            await ctx.send(f"لديك تكت مفتوح: {existing.mention}")
            return

        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            ctx.author: PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: PermissionOverwrite(read_messages=True, send_messages=True)
        }
        support_role = discord.utils.get(guild.roles, name=TICKET_ROLE_NAME)
        if support_role:
            overwrites[support_role] = PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=chan_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {ctx.author}"
        )

        await channel.send(f"{ctx.author.mention} تم فتح التذكرة!\n**السبب:** {reason or 'بدون سبب'}")
        await ctx.send(f"تم فتح التذكرة: {channel.mention}")

    elif action.lower() in ("close", "اغلاق", "غلق"):
        if ctx.channel.category and ctx.channel.category.name == TICKET_CATEGORY_NAME:
            await ctx.send("سيتم إغلاق التذكرة الآن...")
            await ctx.channel.delete(reason=f"Closed by {ctx.author}")
        else:
            await ctx.send("الأمر يستعمل داخل قناة التذكرة فقط.")

# ---------- Moderation ----------
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = None):
    await member.kick(reason=reason)
    await ctx.send(f"🚪 تم طرد {member.mention} | السبب: {reason or 'بدون سبب'}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = None):
    await member.ban(reason=reason)
    await ctx.send(f"⛔ تم باند {member.mention} | السبب: {reason or 'بدون سبب'}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member_name: str):
    banned = await ctx.guild.bans()
    for entry in banned:
        user = entry.user
        if f"{user.name}#{user.discriminator}" == member_name or user.name == member_name:
            await ctx.guild.unban(user)
            await ctx.send(f"✅ تم فك الباند عن {user.mention}")
            return
    await ctx.send("ما لقيت هذا الشخص في قائمة الباند.")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 تم مسح {len(deleted)-1} رسالة.", delete_after=5)

# ---------- Mute / Unmute ----------
@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason: str = None):
    muted_role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    if not muted_role:
        muted_role = await ctx.guild.create_role(name=MUTED_ROLE_NAME)
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False)

    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"🔇 تم كتم {member.mention} | السبب: {reason or 'بدون سبب'}")

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f"🔊 تم فك الكتم عن {member.mention}")
    else:
        await ctx.send("هذا العضو مو مكتوم.")

# ---------- Lock / Unlock ----------
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 تم قفل القناة.")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 تم فتح القناة.")

# ---------- Roles ----------
@bot.command(name="giverole")
@commands.has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, *, role: discord.Role):
    await member.add_roles(role)
    await ctx.send(f"🎖️ تم اعطاء {member.mention} رتبة {role.name}")

@bot.command(name="removerole")
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send(f"🗑️ تم إزالة رتبة {role.name} من {member.mention}")

# ---------- Say ----------
@bot.command(name="say")
async def say(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)

# ---------- Help ----------
@bot.command(name="help")
async def help_command(ctx):
    help_text = f"""
**قائمة أوامر البوت — Prefix: {PREFIX}**

🟢 التذاكر
`!ticket open <السبب>` — فتح تذكرة
`!ticket close` — إغلاق تذكرة

🔨 الإدارة
`!kick <@member> [سبب]` — طرد
`!ban <@member> [سبب]` — باند
`!unban <username#1234>` — فك باند
`!clear <عدد>` — مسح رسائل
`!mute <@member> [سبب]` — كتم
`!unmute <@member>` — فك الكتم
`!lock` — قفل القناة
`!unlock` — فتح القناة

🏷️ الرتب
`!giverole <@member> <@role>` — اعطاء رتبة
`!removerole <@member> <@role>` — إزالة رتبة

💬 متفرقات
`!say <النص>` — البوت يكرر الرسالة
`!help` — قائمة الأوامر
"""
    await ctx.send(help_text)

# ---------- Run Flask + Bot ----------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(TOKEN)
