import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

intents = discord.Intents.all()
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== DB =====
db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()

# ===== 建表 =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel INTEGER,
    punish_channel INTEGER,
    anti_raid INTEGER DEFAULT 0
)
""")

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
CREATE TABLE IF NOT EXISTS violation_counts (
    guild_id INTEGER,
    user_id INTEGER,
    count INTEGER,
    PRIMARY KEY (guild_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    guild_id INTEGER PRIMARY KEY,
    total_messages INTEGER DEFAULT 0,
    total_joins INTEGER DEFAULT 0,
    total_leaves INTEGER DEFAULT 0,
    total_bans INTEGER DEFAULT 0,
    total_timeouts INTEGER DEFAULT 0
)
""")

db.commit()

def is_blacklisted(user_id):
    cursor.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def is_whitelisted(user_id):
    cursor.execute("SELECT 1 FROM whitelist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def add_blacklist(user_id):
    cursor.execute("INSERT OR IGNORE INTO blacklist VALUES (?)", (user_id,))
    db.commit()

def remove_blacklist(user_id):
    cursor.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
    db.commit()

def is_anti_raid_enabled(guild_id):
    cursor.execute("SELECT anti_raid FROM settings WHERE guild_id=?", (guild_id,))
    r = cursor.fetchone()
    return r and r[0] == 1

async def send_log(guild, title, desc):
    cursor.execute("SELECT log_channel FROM settings WHERE guild_id=?", (guild.id,))
    r = cursor.fetchone()
    if not r or not r[0]:
        return

    channel = guild.get_channel(r[0])
    if channel:
        embed = discord.Embed(title=title, description=desc, color=0x3498db)
        embed.timestamp = datetime.now()
        await channel.send(embed=embed)

async def send_punish_log(guild, title, desc):
    cursor.execute("SELECT punish_channel FROM settings WHERE guild_id=?", (guild.id,))
    r = cursor.fetchone()
    if not r or not r[0]:
        return

    channel = guild.get_channel(r[0])
    if channel:
        embed = discord.Embed(title=title, description=desc, color=0xe74c3c)
        embed.timestamp = datetime.now()
        await channel.send(embed=embed)

async def punish_user(member, reason):
    if is_whitelisted(member.id):
        return

    guild = member.guild

    # 違規+1
    cursor.execute("""
    INSERT INTO violation_counts (guild_id, user_id, count)
    VALUES (?, ?, 1)
    ON CONFLICT(guild_id, user_id)
    DO UPDATE SET count = count + 1
    """, (guild.id, member.id))

    db.commit()

    cursor.execute("SELECT count FROM violation_counts WHERE guild_id=? AND user_id=?", (guild.id, member.id))
    count = cursor.fetchone()[0]

    # ===== 達3次 =====
    if count >= 3:
        add_blacklist(member.id)

        try:
            await member.kick(reason=f"累計違規3次: {reason}")

            cursor.execute("""
            INSERT INTO stats (guild_id, total_bans)
            VALUES (?, 1)
            ON CONFLICT(guild_id)
            DO UPDATE SET total_bans = total_bans + 1
            """, (guild.id,))
            db.commit()

            await send_punish_log(guild, "🚫 達3次違規已踢出", f"{member.mention} 原因: {reason}")

        except discord.Forbidden:
            await send_punish_log(guild, "⚠ 無法踢出", f"{member.mention}")

        return

    # ===== 未達3次 → timeout =====
    until = datetime.now(timezone.utc) + timedelta(seconds=60)
    try:
        await member.timeout(until, reason=reason)

        cursor.execute("""
        INSERT INTO stats (guild_id, total_timeouts)
        VALUES (?, 1)
        ON CONFLICT(guild_id)
        DO UPDATE SET total_timeouts = total_timeouts + 1
        """, (guild.id,))
        db.commit()

        await send_punish_log(guild, f"⚠ 違規 ({count}/3)", f"{member.mention} → Timeout 60秒")

    except discord.Forbidden:
        await send_punish_log(guild, "⚠ 無法禁言", f"{member.mention}")

spam_data = {}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild = message.guild
    user_id = message.author.id

    now = datetime.now().timestamp()

    if user_id not in spam_data:
        spam_data[user_id] = []

    spam_data[user_id].append(now)

    # 5秒內5則
    spam_data[user_id] = [t for t in spam_data[user_id] if now - t < 5]

    if len(spam_data[user_id]) >= 5:
        await message.delete()
        spam_data[user_id].clear()
        await punish_user(message.author, "刷頻")
        return

    # 重複訊息
    history = [msg async for msg in message.channel.history(limit=5)]
    if sum(1 for m in history if m.author == message.author and m.content == message.content) >= 3:
        await message.delete()
        await punish_user(message.author, "洗版")
        return

    # 記錄訊息數
    cursor.execute("""
    INSERT INTO stats (guild_id, total_messages)
    VALUES (?, 1)
    ON CONFLICT(guild_id)
    DO UPDATE SET total_messages = total_messages + 1
    """, (guild.id,))
    db.commit()

    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    guild = member.guild

    if is_blacklisted(member.id):
        try:
            await member.kick(reason="黑名單自動踢出")
            await send_punish_log(guild, "🚫 黑名單自動踢出", f"{member.mention}")
        except:
            pass

    cursor.execute("""
    INSERT INTO stats (guild_id, total_joins)
    VALUES (?, 1)
    ON CONFLICT(guild_id)
    DO UPDATE SET total_joins = total_joins + 1
    """, (guild.id,))
    db.commit()

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild

    if not is_anti_raid_enabled(guild.id):
        return

    await asyncio.sleep(1)

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user

        if is_whitelisted(user.id):
            return

        try:
            await guild.ban(user, reason="刪除頻道")
        except:
            pass

        # 還原頻道
        await guild.create_text_channel(name=channel.name)

        await send_log(guild, "⚠ 防炸", f"{user} 刪除頻道 → 已還原+封鎖")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} 已同步 slash 指令！")


# 全域白名單
whitelist = set()

if not any(c.name == "加入白名單" for c in bot.tree.walk_commands()):
    @bot.tree.command(name="加入白名單", description="將使用者加入白名單")
    @app_commands.describe(user="要加入白名單的使用者")
    async def 加入白名單(interaction: discord.Interaction, user: discord.Member):
        if user.id in whitelist:
            await interaction.response.send_message(f"❌ {user} 已經在白名單中", ephemeral=True)
        else:
            whitelist.add(user.id)
            await interaction.response.send_message(f"✅ {user} 已加入白名單", ephemeral=True)

if not any(c.name == "移除白名單" for c in bot.tree.walk_commands()):
    @bot.tree.command(name="移除白名單", description="將使用者從白名單移除")
    @app_commands.describe(user="要移除白名單的使用者")
    async def 移除白名單(interaction: discord.Interaction, user: discord.Member):
        if user.id in whitelist:
            whitelist.remove(user.id)
            await interaction.response.send_message(f"✅ {user} 已從白名單移除", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {user} 不在白名單中", ephemeral=True)

@bot.tree.command(name="設置日誌頻道", description="設定伺服器日誌輸出頻道")
@app_commands.checks.has_permissions(administrator=True)
async def set_log(interaction: discord.Interaction, channel: discord.TextChannel):

    cursor.execute("""
    INSERT INTO settings (guild_id, log_channel)
    VALUES (?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET log_channel=excluded.log_channel
    """, (interaction.guild.id, channel.id))

    db.commit()

    await interaction.response.send_message(f"日誌頻道已設為 {channel.mention}")

@bot.tree.command(
    name="設置違規懲罰訊息頻道",
    description="設定違規、踢出、黑名單等通知頻道"
)
@app_commands.checks.has_permissions(administrator=True)
async def set_punish(interaction: discord.Interaction, channel: discord.TextChannel):

    cursor.execute("""
    INSERT INTO settings (guild_id, punish_channel)
    VALUES (?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET punish_channel=excluded.punish_channel
    """, (interaction.guild.id, channel.id))

    db.commit()

    await interaction.response.send_message(f"懲罰訊息頻道已設為 {channel.mention}")

@bot.tree.command(name="防炸開關", description="開啟或關閉防炸系統")
@app_commands.checks.has_permissions(administrator=True)
async def raid(interaction: discord.Interaction, state: bool):

    cursor.execute("""
    INSERT INTO settings (guild_id, anti_raid)
    VALUES (?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET anti_raid=excluded.anti_raid
    """, (interaction.guild.id, int(state)))

    db.commit()

    await interaction.response.send_message(
        f"🛡️ 防炸系統已 {'開啟' if state else '關閉'}"
    )

@bot.tree.command(name="加入黑名單", description="將指定使用者加入黑名單")
@app_commands.checks.has_permissions(administrator=True)
async def add_black(interaction: discord.Interaction, member: discord.Member):
    add_blacklist(member.id)

    await interaction.response.send_message(
        f"🚫 {member.mention} 已加入黑名單"
    )

@bot.tree.command(name="移除黑名單", description="將使用者從黑名單移除")
@app_commands.checks.has_permissions(administrator=True)
async def remove_black(interaction: discord.Interaction, user: discord.User):

    remove_blacklist(user.id)

    await interaction.response.send_message(
        f"✅ {user.mention} 已移出黑名單"
    )

@bot.tree.command(name="查看設定", description="查看目前伺服器所有設定")
async def view_settings(interaction: discord.Interaction):

    cursor.execute("""
    SELECT log_channel, punish_channel, anti_raid
    FROM settings WHERE guild_id=?
    """, (interaction.guild.id,))

    r = cursor.fetchone()

    if not r:
        await interaction.response.send_message("尚未有任何設定")
        return

    log_ch, punish_ch, raid = r

    embed = discord.Embed(title="⚙️ 伺服器設定", color=0x3498db)
    embed.add_field(name="📜 日誌頻道", value=f"<#{log_ch}>" if log_ch else "未設定", inline=False)
    embed.add_field(name="🚨 懲罰頻道", value=f"<#{punish_ch}>" if punish_ch else "未設定", inline=False)
    embed.add_field(name="🛡 防炸系統", value="開啟" if raid else "關閉", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="黑白名單列表", description="查看黑名單與白名單")
async def list_bw(interaction: discord.Interaction):

    cursor.execute("SELECT user_id FROM blacklist")
    blacks = [f"<@{row[0]}>" for row in cursor.fetchall()]

    cursor.execute("SELECT user_id FROM whitelist")
    whites = [f"<@{row[0]}>" for row in cursor.fetchall()]

    embed = discord.Embed(title="📋 黑白名單", color=0x2ecc71)

    embed.add_field(
        name="🚫 黑名單",
        value="\n".join(blacks) if blacks else "無",
        inline=False
    )

    embed.add_field(
        name="✅ 白名單",
        value="\n".join(whites) if whites else "無",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="後台統計", description="查看伺服器統計數據")
async def stats(interaction: discord.Interaction):

    cursor.execute("""
    SELECT total_messages, total_joins, total_leaves,
           total_bans, total_timeouts
    FROM stats WHERE guild_id=?
    """, (interaction.guild.id,))

    r = cursor.fetchone()

    if not r:
        await interaction.response.send_message("尚無統計資料")
        return

    msg, join, leave, ban, timeout = r

    embed = discord.Embed(title="📊 後台統計", color=0x9b59b6)
    embed.add_field(name="💬 訊息數", value=msg, inline=True)
    embed.add_field(name="📥 加入", value=join, inline=True)
    embed.add_field(name="📤 離開", value=leave, inline=True)
    embed.add_field(name="🔨 封鎖", value=ban, inline=True)
    embed.add_field(name="⏱ 禁言", value=timeout, inline=True)

    await interaction.response.send_message(embed=embed)

import matplotlib.pyplot as plt

@bot.tree.command(name="統計圖表", description="顯示統計圖表")
async def chart(interaction: discord.Interaction):

    cursor.execute("""
    SELECT total_messages, total_joins, total_leaves,
           total_bans, total_timeouts
    FROM stats WHERE guild_id=?
    """, (interaction.guild.id,))

    r = cursor.fetchone()

    if not r:
        await interaction.response.send_message("沒有資料")
        return

    labels = ["訊息", "加入", "離開", "封鎖", "禁言"]
    values = list(r)

    plt.figure()
    plt.bar(labels, values)

    plt.savefig("chart.png")
    plt.close()

    await interaction.response.send_message(file=discord.File("chart.png"))

import platform

@bot.tree.command(name="機器人狀態", description="查看機器人運行狀態")
async def bot_status(interaction: discord.Interaction):

    embed = discord.Embed(title="🤖 機器人狀態", color=0x1abc9c)

    embed.add_field(name="🟢 延遲", value=f"{round(bot.latency * 1000)} ms")
    embed.add_field(name="🖥 系統", value=platform.system())
    embed.add_field(name="🐍 Python", value=platform.python_version())
    embed.add_field(name="📡 伺服器數", value=len(bot.guilds))

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="查看指令", description="查看所有指令")
async def help_cmd(interaction: discord.Interaction):

    embed = discord.Embed(title="📖 指令總覽", color=0xf1c40f)

    embed.add_field(name="⚙️ 設定類",
                    value="/設置日誌頻道\n/設置違規懲罰訊息頻道\n/防炸開關",
                    inline=False)

    embed.add_field(name="🚫 管理類",
                    value="/加入黑名單\n/移除黑名單\n/黑白名單列表",
                    inline=False)

    embed.add_field(name="📊 系統類",
                    value="/查看設定\n/後台統計\n/統計圖表\n/機器人狀態",
                    inline=False)

    await interaction.response.send_message(embed=embed)

import os

# ===== 啟動 Bot =====
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")  # 建議用環境變數（最安全）

    if not TOKEN:
        print("❌ 未找到 TOKEN，請設定環境變數 DISCORD_TOKEN")
    else:
        bot.run(TOKEN)


   
