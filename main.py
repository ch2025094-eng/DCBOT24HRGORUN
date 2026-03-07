import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import matplotlib.pyplot as plt
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    guild_id INTEGER PRIMARY KEY,
    total_timeouts INTEGER DEFAULT 0,
    total_bans INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS welcome (
    guild_id TEXT PRIMARY KEY,
    enabled INTEGER,
    channel_id TEXT,
    message TEXT
)
""")
conn.commit()
db.commit()

# =========================
# 工具函數
# =========================
def ensure_guild_settings(guild_id):
    cursor.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,))
    cursor.execute("INSERT OR IGNORE INTO stats (guild_id) VALUES (?)", (guild_id,))
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

    ensure_guild_settings(member.guild.id)

    if is_blacklisted(member.id):
        await member.ban(reason=f"黑名單再次違規: {reason}")

        cursor.execute("""
            UPDATE stats
            SET total_bans = total_bans + 1
            WHERE guild_id=?
        """, (member.guild.id,))
        db.commit()

        await send_log(
            member.guild,
            "🚫 黑名單再次違規",
            f"使用者: {member.mention}\n原因: {reason}\n處罰: 永久封鎖"
        )
        return

    add_blacklist(member.id)

    until = datetime.now(timezone.utc) + timedelta(seconds=60)
    await member.timeout(until, reason=reason)

    cursor.execute("""
        UPDATE stats
        SET total_timeouts = total_timeouts + 1
        WHERE guild_id=?
    """, (member.guild.id,))
    db.commit()

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

@bot.event
async def on_member_join(member):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT enabled, channel_id, message FROM welcome WHERE guild_id=?",
        (str(member.guild.id),)
    )

    data = cursor.fetchone()
    conn.close()

    if not data:
        return

    enabled, channel_id, message = data

    if not enabled:
        return

    channel = member.guild.get_channel(int(channel_id))

    if not channel:
        return

    message = message.replace("{user}", member.mention)
    message = message.replace("{server}", member.guild.name)

    await channel.send(message)

@bot.event
async def on_member_join(member):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT enabled, channel_id, message FROM welcome WHERE guild_id=?",
        (str(member.guild.id),)
    )

    data = cursor.fetchone()
    conn.close()

    if not data:
        return

    enabled, channel_id, message = data

    if enabled != 1:
        return

    try:
        channel = member.guild.get_channel(int(channel_id))
    except:
        return

    if channel is None:
        return

    msg = message.replace("{user}", member.mention)
    msg = msg.replace("{server}", member.guild.name)

    await channel.send(msg)

# =========================
# 事件防護
# =========================
@bot.event
async def on_guild_channel_create(channel):
    ensure_guild_settings(channel.guild.id)

    cursor.execute(
        "SELECT anti_channel_create FROM settings WHERE guild_id=?",
        (channel.guild.id,)
    )
    if cursor.fetchone()[0] == 0:
        return

    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        user = entry.user
        break
    else:
        return

    if user.bot:
        return

    await punish_user(user, "未授權新增頻道")
    await channel.delete()

@bot.event
async def on_guild_channel_delete(channel):
    ensure_guild_settings(channel.guild.id)

    cursor.execute(
        "SELECT anti_channel_delete FROM settings WHERE guild_id=?",
        (channel.guild.id,)
    )
    if cursor.fetchone()[0] == 0:
        return

    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        break
    else:
        return

    if user.bot:
        return

    await punish_user(user, "未授權刪除頻道")

@bot.event
async def on_guild_role_delete(role):
    ensure_guild_settings(role.guild.id)

    cursor.execute(
        "SELECT anti_role_delete FROM settings WHERE guild_id=?",
        (role.guild.id,)
    )
    if cursor.fetchone()[0] == 0:
        return

    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        user = entry.user
        break
    else:
        return

    if user.bot:
        return

    await punish_user(user, "未授權刪除角色")

@bot.event
async def on_guild_update(before, after):
    ensure_guild_settings(after.id)

    cursor.execute(
        "SELECT anti_guild_rename FROM settings WHERE guild_id=?",
        (after.id,)
    )
    if cursor.fetchone()[0] == 0:
        return

    if before.name == after.name:
        return

    async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
        user = entry.user
        break
    else:
        return

    if user.bot:
        return

    await punish_user(user, "未授權修改伺服器名稱")
    
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

@bot.tree.command(name="後台統計", description="查看機器人封鎖與處罰統計")
async def backend_stats(interaction: discord.Interaction):
    ensure_guild_settings(interaction.guild.id)

    cursor.execute("""
        SELECT total_timeouts, total_bans
        FROM stats
        WHERE guild_id=?
    """, (interaction.guild.id,))
    data = cursor.fetchone()

    timeouts = data[0]
    bans = data[1]

    embed = discord.Embed(
        title="📊 機器人統計後台",
        color=discord.Color.blue()
    )

    embed.add_field(name="Timeout 次數", value=str(timeouts))
    embed.add_field(name="Ban 次數", value=str(bans))
    embed.add_field(name="總處罰次數", value=str(timeouts + bans))

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="統計圖表", description="生成封鎖與禁言統計圖表")
async def stats_chart(interaction: discord.Interaction):
    ensure_guild_settings(interaction.guild.id)

    cursor.execute("""
        SELECT total_timeouts, total_bans
        FROM stats
        WHERE guild_id=?
    """, (interaction.guild.id,))
    data = cursor.fetchone()

    labels = ["Timeout", "Ban"]
    values = [data[0], data[1]]

    plt.figure()
    plt.bar(labels, values)
    plt.title("Bot Moderation Statistics")
    plt.xlabel("Type")
    plt.ylabel("Count")

    file_path = "stats.png"
    plt.savefig(file_path)
    plt.close()

    await interaction.response.send_message(file=discord.File(file_path))

@bot.tree.command(name="防護狀態", description="查看目前防炸系統開關狀態")
async def protection_status(interaction: discord.Interaction):
    ensure_guild_settings(interaction.guild.id)

    cursor.execute("""
        SELECT anti_role_delete,
               anti_guild_rename,
               anti_channel_delete,
               anti_channel_create
        FROM settings
        WHERE guild_id=?
    """, (interaction.guild.id,))
    data = cursor.fetchone()

    embed = discord.Embed(
        title="🛡 防護系統狀態",
        color=discord.Color.green()
    )

    embed.add_field(name="防刪角色", value="開啟" if data[0] else "關閉")
    embed.add_field(name="防改名稱", value="開啟" if data[1] else "關閉")
    embed.add_field(name="防刪頻道", value="開啟" if data[2] else "關閉")
    embed.add_field(name="防新增頻道", value="開啟" if data[3] else "關閉")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="機器人狀態", description="查看機器人上線狀態與延遲")
async def bot_status(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    embed = discord.Embed(
        title="🤖 機器人狀態",
        color=discord.Color.purple()
    )

    embed.add_field(name="上線狀態", value="🟢 Online")
    embed.add_field(name="延遲", value=f"{latency} ms")

    await interaction.response.send_message(embed=embed)

from discord import app_commands

# ===============================
#  防炸系統開關
# ===============================

anti_settings = {
    "anti_channel_create": True,
    "anti_channel_delete": True,
    "anti_role_delete": True,
    "anti_guild_update": True
}

def check_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


@bot.tree.command(name="防新增頻道開關", description="防新增頻道的開關")
@app_commands.choices(state=[
    app_commands.Choice(name="開啟", value="on"),
    app_commands.Choice(name="關閉", value="off")
])
async def toggle_channel_create(interaction: discord.Interaction, state: str):
    ensure_guild_settings(interaction.guild.id)

    value = 1 if state.lower() == "on" else 0

    cursor.execute(
        "UPDATE settings SET anti_channel_create=? WHERE guild_id=?",
        (value, interaction.guild.id)
    )
    db.commit()

    embed = discord.Embed(
        title="🔒 防新增頻道",
        description=f"狀態：{'🟢 開啟' if value else '🔴 關閉'}",
        color=discord.Color.green() if value else discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="防刪頻道開關", description="防刪除頻道的開關")
@app_commands.choices(state=[
    app_commands.Choice(name="開啟", value="on"),
    app_commands.Choice(name="關閉", value="off")
])
async def toggle_channel_delete(interaction: discord.Interaction, state: str):
    ensure_guild_settings(interaction.guild.id)

    value = 1 if state.lower() == "on" else 0

    cursor.execute(
        "UPDATE settings SET anti_channel_delete=? WHERE guild_id=?",
        (value, interaction.guild.id)
    )
    db.commit()

    embed = discord.Embed(
        title="🛡 防刪頻道",
        description=f"狀態：{'🟢 開啟' if value else '🔴 關閉'}",
        color=discord.Color.green() if value else discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="防刪角色開關", description="防防刪除角色的開關")
@app_commands.choices(state=[
    app_commands.Choice(name="開啟", value="on"),
    app_commands.Choice(name="關閉", value="off")
])
async def toggle_role_delete(interaction: discord.Interaction, state: str):
    ensure_guild_settings(interaction.guild.id)

    value = 1 if state.lower() == "on" else 0

    cursor.execute(
        "UPDATE settings SET anti_role_delete=? WHERE guild_id=?",
        (value, interaction.guild.id)
    )
    db.commit()

    embed = discord.Embed(
        title="🧱 防刪角色",
        description=f"狀態：{'🟢 開啟' if value else '🔴 關閉'}",
        color=discord.Color.green() if value else discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="防改伺服器名稱開關", description="防改伺服器名稱的開關")
@app_commands.choices(state=[
    app_commands.Choice(name="開啟", value="on"),
    app_commands.Choice(name="關閉", value="off")
])
async def toggle_guild_rename(interaction: discord.Interaction, state: str):
    ensure_guild_settings(interaction.guild.id)

    value = 1 if state.lower() == "on" else 0

    cursor.execute(
        "UPDATE settings SET anti_guild_rename=? WHERE guild_id=?",
        (value, interaction.guild.id)
    )
    db.commit()

    embed = discord.Embed(
        title="🏷 防改伺服器名稱",
        description=f"狀態：{'🟢 開啟' if value else '🔴 關閉'}",
        color=discord.Color.green() if value else discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="防炸總開關", description="所有防炸功能的一次全部開 or 關")
async def toggle_all_protection(interaction: discord.Interaction, state: str):
    ensure_guild_settings(interaction.guild.id)

    value = 1 if state.lower() == "on" else 0

    cursor.execute("""
        UPDATE settings
        SET anti_channel_create=?,
            anti_channel_delete=?,
            anti_role_delete=?,
            anti_guild_rename=?
        WHERE guild_id=?
    """, (value, value, value, value, interaction.guild.id))

    db.commit()

    embed = discord.Embed(
        title="🛡 防炸系統總開關",
        description=f"目前狀態：{'🟢 全部開啟' if value else '🔴 全部關閉'}",
        color=discord.Color.green() if value else discord.Color.red()
    )

    embed.add_field(name="防新增頻道", value="同步變更", inline=True)
    embed.add_field(name="防刪頻道", value="同步變更", inline=True)
    embed.add_field(name="防刪角色", value="同步變更", inline=True)
    embed.add_field(name="防改伺服器名稱", value="同步變更", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="查看防炸系統", description="查看防炸系統狀態")
async def anti_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡 喵總管 防炸系統狀態",
        color=0x3498db
    )

    for key, value in anti_settings.items():
        embed.add_field(
            name=key,
            value="🟢 ON" if value else "🔴 OFF",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


# =========================

bot.run(TOKEN)


















