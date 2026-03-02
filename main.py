import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# 資料庫
# =========================
db = sqlite3.connect("data.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    anti_role_delete INTEGER DEFAULT 0,
    anti_guild_rename INTEGER DEFAULT 0,
    anti_channel_delete INTEGER DEFAULT 0,
    anti_channel_create INTEGER DEFAULT 0
)
""")

db.commit()

# =========================
# 工具函數
# =========================
def ensure_guild_settings(guild_id):
    cursor.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,))
    db.commit()

def get_log_channel(guild):
    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id=?", (guild.id,))
    data = cursor.fetchone()
    if data and data[0]:
        return guild.get_channel(data[0])
    return None

async def send_log(guild, title, description, color=discord.Color.red()):
    channel = get_log_channel(guild)
    if not channel:
        return
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    await channel.send(embed=embed)

def is_whitelisted(user_id):
    cursor.execute("SELECT 1 FROM whitelist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def is_blacklisted(user_id):
    cursor.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def add_blacklist(user_id):
    cursor.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (user_id,))
    db.commit()

async def punish_user(member, reason):
    if is_whitelisted(member.id):
        return

    if is_blacklisted(member.id):
        await member.ban(reason=f"黑名單再次違規: {reason}")
        await send_log(
            member.guild,
            "🚫 黑名單再次違規",
            f"使用者: {member.mention}\n原因: {reason}\n處罰: 永久封鎖"
        )
        return

    add_blacklist(member.id)
    until = datetime.now(timezone.utc) + timedelta(seconds=60)
    await member.timeout(until, reason=reason)

    await send_log(
        member.guild,
        "⚠ 使用者違規",
        f"使用者: {member.mention}\n原因: {reason}\n處罰: Timeout 60秒 + 加入黑名單"
    )

# =========================
# 啟動
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 已登入 {bot.user}")

# =========================
# 反刷頻
# =========================
message_tracker = defaultdict(list)
mention_tracker = defaultdict(list)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now().timestamp()

    # 6秒8則
    message_tracker[message.author.id].append(now)
    message_tracker[message.author.id] = [
        t for t in message_tracker[message.author.id]
        if now - t < 6
    ]

    if len(message_tracker[message.author.id]) >= 8:
        await punish_user(message.author, "刷頻")
        return

    # 3秒3次 @everyone
    if "@everyone" in message.content:
        mention_tracker[message.author.id].append(now)
        mention_tracker[message.author.id] = [
            t for t in mention_tracker[message.author.id]
            if now - t < 3
        ]

        if len(mention_tracker[message.author.id]) >= 3:
            await punish_user(message.author, "短時間多次@everyone")
            return

        if message.content.count("@everyone") > 2:
            await punish_user(message.author, "單則大量@everyone")
            return

    await bot.process_commands(message)

# =========================
# 事件防護
# =========================
@bot.event
async def on_guild_channel_create(channel):
    ensure_guild_settings(channel.guild.id)
    cursor.execute("SELECT anti_channel_create FROM settings WHERE guild_id=?", (channel.guild.id,))
    if cursor.fetchone()[0] == 0:
        return

    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        user = entry.user
        break

    if user.bot:
        return

    await punish_user(user, "未授權新增頻道或分類")
    await channel.delete()

# =========================
# Slash 指令（全部有介紹）
# =========================

@bot.tree.command(name="設置日誌頻道", description="設定機器人發送違規與防護紀錄的頻道")
async def set_log_channel(interaction: discord.Interaction, 頻道: discord.TextChannel):
    ensure_guild_settings(interaction.guild.id)
    cursor.execute("UPDATE settings SET log_channel_id=? WHERE guild_id=?",
                   (頻道.id, interaction.guild.id))
    db.commit()
    await interaction.response.send_message(f"✅ 日誌頻道已設為 {頻道.mention}")

@bot.tree.command(name="加入黑名單", description="將指定使用者加入黑名單")
async def add_black(interaction: discord.Interaction, member: discord.Member):
    add_blacklist(member.id)
    await interaction.response.send_message(f"🚫 {member.mention} 已加入黑名單")

@bot.tree.command(name="移除黑名單", description="將指定使用者移出黑名單")
async def remove_black(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM blacklist WHERE user_id=?", (member.id,))
    db.commit()
    await interaction.response.send_message(f"✅ {member.mention} 已移出黑名單")

@bot.tree.command(name="查看黑名單", description="查看全伺服器黑名單成員")
async def view_black(interaction: discord.Interaction):
    cursor.execute("SELECT user_id FROM blacklist")
    data = cursor.fetchall()
    if not data:
        await interaction.response.send_message("黑名單為空")
        return
    msg = "\n".join([f"<@{u[0]}>" for u in data])
    await interaction.response.send_message(msg)

@bot.tree.command(name="加入白名單", description="將指定使用者加入白名單（不受防護影響）")
async def add_white(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (member.id,))
    db.commit()
    await interaction.response.send_message(f"✅ {member.mention} 已加入白名單")

@bot.tree.command(name="移除白名單", description="將指定使用者移出白名單")
async def remove_white(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM whitelist WHERE user_id=?", (member.id,))
    db.commit()
    await interaction.response.send_message(f"🚫 {member.mention} 已移出白名單")

@bot.tree.command(name="查看白名單", description="查看全伺服器白名單成員")
async def view_white(interaction: discord.Interaction):
    cursor.execute("SELECT user_id FROM whitelist")
    data = cursor.fetchall()
    if not data:
        await interaction.response.send_message("白名單為空")
        return
    msg = "\n".join([f"<@{u[0]}>" for u in data])
    await interaction.response.send_message(msg)

# =========================

bot.run(TOKEN)






