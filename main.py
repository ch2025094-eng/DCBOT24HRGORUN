import discord
from discord.ext import commands
from discord import app_commands
import matplotlib.pyplot as plt
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import sqlite3

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# =========================
# 資料庫連線
# =========================
db = sqlite3.connect("database.db")
cursor = db.cursor()

# 建立必要資料表
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    punish_channel_id INTEGER,
    anti_channel_create INTEGER DEFAULT 0,
    anti_channel_delete INTEGER DEFAULT 0,
    anti_role_delete INTEGER DEFAULT 0,
    anti_guild_rename INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER PRIMARY KEY
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS violation_counts (
    guild_id INTEGER,
    user_id INTEGER,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    guild_id INTEGER PRIMARY KEY,
    total_timeouts INTEGER DEFAULT 0,
    total_bans INTEGER DEFAULT 0
)
""")
db.commit()

# =========================
# 工具函數
# =========================
def ensure_guild_settings(guild_id):
    cursor.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,))
    cursor.execute("INSERT OR IGNORE INTO stats (guild_id) VALUES (?)", (guild_id,))
    db.commit()

def is_whitelisted(user_id):
    cursor.execute("SELECT 1 FROM whitelist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def is_blacklisted(user_id):
    cursor.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def add_blacklist(user_id):
    cursor.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (user_id,))
    db.commit()

# 日誌頻道（記錄所有行為）
async def send_guild_log(guild, title, description, color=discord.Color.blurple()):
    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id=?", (guild.id,))
    result = cursor.fetchone()
    if result and result[0]:
        channel = guild.get_channel(result[0])
        if channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now(timezone.utc)
            )
            await channel.send(embed=embed)

# 懲罰/踢出訊息頻道
async def send_punish_log(guild, title, description, color=discord.Color.red()):
    cursor.execute("SELECT punish_channel_id FROM settings WHERE guild_id=?", (guild.id,))
    result = cursor.fetchone()
    if result and result[0]:
        channel = guild.get_channel(result[0])
        if channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now(timezone.utc)
            )
            await channel.send(embed=embed)

# =========================
# 處理違規
# =========================
@bot.event
async def punish_user(member: discord.Member, reason: str):
    guild = member.guild

    if is_whitelisted(member.id):
        return  # 白名單不受限制

    # 已經在黑名單，直接踢出
    if is_blacklisted(member.id):
        try:
            await member.kick(reason=f"黑名單成員違規: {reason}")
        except discord.Forbidden:
            await send_punish_log(guild, "⚠ 無法踢出黑名單成員", f"{member.mention} ({member.id})")
        else:
            await send_punish_log(guild, "🚫 黑名單成員已踢出", f"{member.mention} 原因: {reason}")
        return

    # 違規累計計數，達 3 次加入黑名單
    cursor.execute("""
        INSERT INTO violation_counts (guild_id, user_id, count)
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET count=count+1
    """, (guild.id, member.id))
    db.commit()

    cursor.execute("SELECT count FROM violation_counts WHERE guild_id=? AND user_id=?", (guild.id, member.id))
    count = cursor.fetchone()[0]

    if count >= 3:
        add_blacklist(member.id)
        try:
            await member.kick(reason=f"累計違規 3 次加入黑名單: {reason}")
        except discord.Forbidden:
            await send_punish_log(guild, "⚠ 無法踢出累計違規成員", f"{member.mention} ({member.id})")
        else:
            await send_punish_log(guild, "🚫 成員累計違規達 3 次已踢出並加入黑名單", f"{member.mention} 原因: {reason}")
        # 清除違規計數
        cursor.execute("DELETE FROM violation_counts WHERE guild_id=? AND user_id=?", (guild.id, member.id))
        db.commit()
    else:
        until = datetime.now(timezone.utc) + timedelta(seconds=60)
        try:
            await member.timeout(until, reason=reason)
        except discord.Forbidden:
            await send_punish_log(guild, "⚠ 無法禁言成員", f"{member.mention} 原因: {reason}")
        else:
            await send_punish_log(guild, f"⚠ 使用者違規 ({count}/3)", f"{member.mention} 原因: {reason} → Timeout 60 秒")

# =========================
# 防炸事件處理（新增/刪頻道、刪角色、改伺服器名稱）
# =========================
async def handle_guild_event(channel_or_role_or_guild, event_type: str):
    """
    event_type: "新增頻道" / "刪除頻道" / "刪除角色" / "修改伺服器名稱"
    channel_or_role_or_guild: 對應的 discord 對象
    """
    # 取得 guild
    if isinstance(channel_or_role_or_guild, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
        guild = channel_or_role_or_guild.guild
    elif isinstance(channel_or_role_or_guild, discord.Role):
        guild = channel_or_role_or_guild.guild
    elif isinstance(channel_or_role_or_guild, discord.Guild):
        guild = channel_or_role_or_guild
    else:
        return

    # 確認 guild 設定
    ensure_guild_settings(guild.id)

    cursor.execute("""
        SELECT anti_channel_create, anti_channel_delete, anti_role_delete, anti_guild_rename
        FROM settings WHERE guild_id=?
    """, (guild.id,))
    settings = cursor.fetchone() or (0, 0, 0, 0)

    trigger = False
    if event_type == "新增頻道" and settings[0]:
        trigger = True
    elif event_type == "刪除頻道" and settings[1]:
        trigger = True
    elif event_type == "刪除角色" and settings[2]:
        trigger = True
    elif event_type == "修改伺服器名稱" and settings[3]:
        trigger = True

    if not trigger:
        return

    # 取得最後一筆 audit log 的操作者
    async for entry in guild.audit_logs(limit=1,
                                        action={
                                            "新增頻道": discord.AuditLogAction.channel_create,
                                            "刪除頻道": discord.AuditLogAction.channel_delete,
                                            "刪除角色": discord.AuditLogAction.role_delete,
                                            "修改伺服器名稱": discord.AuditLogAction.guild_update
                                        }[event_type]):
        actor = entry.user
        break
    else:
        return  # 沒找到操作者

    # 白名單不受限制
    if is_whitelisted(actor.id):
        return

    # 進行懲罰
    await punish_user(actor, f"管理事件違規: {event_type}")

    # 記錄到日誌頻道
    await send_guild_log(guild,
                         f"管理事件觸發: {event_type}",
                         f"{actor.mention} ({actor.id}) 觸發事件: {event_type}")

# 日誌頻道
@bot.event
async def on_message_delete(message):

    if message.guild is None:
        return

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (message.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])
    if not log_channel:
        return

    deleter = "未知"

    async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
        if entry.target.id == message.author.id:
            deleter = entry.user
            break

    embed = discord.Embed(
        title="🗑 訊息被刪除",
        color=discord.Color.red()
    )

    embed.add_field(name="訊息作者", value=f"{message.author} ({message.author.id})")
    embed.add_field(name="刪除者", value=str(deleter))
    embed.add_field(name="頻道", value=message.channel.mention)

    embed.add_field(
        name="訊息內容",
        value=message.content if message.content else "（沒有文字內容）",
        inline=False
    )

    await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):

    if before.guild is None:
        return

    if before.content == after.content:
        return

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (before.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])
    if not log_channel:
        return

    embed = discord.Embed(
        title="✏️ 訊息被編輯",
        color=discord.Color.orange()
    )

    embed.add_field(name="使用者", value=f"{before.author} ({before.author.id})")
    embed.add_field(name="頻道", value=before.channel.mention)

    embed.add_field(
        name="修改前",
        value=before.content if before.content else "（沒有文字內容）",
        inline=False
    )

    embed.add_field(
        name="修改後",
        value=after.content if after.content else "（沒有文字內容）",
        inline=False
    )

    await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.guild is None or before.author.bot:
        return

    if before.content == after.content:
        return

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (before.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    embed = discord.Embed(
        title="✏️ 訊息被編輯",
        color=discord.Color.orange()
    )
    embed.add_field(name="使用者", value=before.author.mention)
    embed.add_field(name="頻道", value=before.channel.mention)
    embed.add_field(name="修改前", value=before.content or "無內容", inline=False)
    embed.add_field(name="修改後", value=after.content or "無內容", inline=False)

    await log_channel.send(embed=embed)

@bot.event
async def on_member_update(before, after):
    if before.display_name == after.display_name:
        return

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (before.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    embed = discord.Embed(
        title="👤 成員改名",
        color=discord.Color.blue()
    )
    embed.add_field(name="使用者", value=after.mention)
    embed.add_field(name="修改前", value=before.display_name)
    embed.add_field(name="修改後", value=after.display_name)

    await log_channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    embed = discord.Embed(color=discord.Color.green())

    if before.channel is None and after.channel is not None:
        embed.title = "🔊 加入語音頻道"
        embed.add_field(name="使用者", value=member.mention)
        embed.add_field(name="頻道", value=after.channel.name)

    elif before.channel is not None and after.channel is None:
        embed.title = "🔇 離開語音頻道"
        embed.add_field(name="使用者", value=member.mention)
        embed.add_field(name="頻道", value=before.channel.name)

    elif before.channel != after.channel:
        embed.title = "🔁 切換語音頻道"
        embed.add_field(name="使用者", value=member.mention)
        embed.add_field(name="原頻道", value=before.channel.name)
        embed.add_field(name="新頻道", value=after.channel.name)

    else:
        return

    await log_channel.send(embed=embed)

@bot.event
async def on_member_join(member):

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    embed = discord.Embed(
        title="🚪 成員加入",
        color=discord.Color.green()
    )
    embed.add_field(name="使用者", value=member.mention)
    embed.add_field(name="帳號ID", value=member.id)

    await log_channel.send(embed=embed)


@bot.event
async def on_member_remove(member):

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    embed = discord.Embed(
        title="🚪 成員離開",
        color=discord.Color.red()
    )
    embed.add_field(name="使用者", value=f"{member}")
    embed.add_field(name="ID", value=member.id)

    await log_channel.send(embed=embed)

@bot.event
async def on_member_ban(guild, user):

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):

        embed = discord.Embed(
            title="🔨 成員被封鎖",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="被封鎖", value=user)
        embed.add_field(name="執行者", value=entry.user)

        await log_channel.send(embed=embed)
        break

@bot.event
async def on_member_remove(member):

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):

        if entry.target.id == member.id:

            embed = discord.Embed(
                title="👢 成員被踢出",
                color=discord.Color.orange()
            )
            embed.add_field(name="被踢", value=member)
            embed.add_field(name="執行者", value=entry.user)

            await log_channel.send(embed=embed)
            return

@bot.event
async def on_guild_channel_delete(channel):

    guild = channel.guild

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):

        embed = discord.Embed(
            title="⚠️ 頻道被刪除",
            color=discord.Color.red()
        )
        embed.add_field(name="頻道名稱", value=channel.name)
        embed.add_field(name="執行者", value=entry.user)

        await log_channel.send(embed=embed)
        break

@bot.event
async def on_guild_role_delete(role):

    guild = role.guild

    cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (guild.id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = bot.get_channel(result[0])

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):

        embed = discord.Embed(
            title="⚠️ 身分組被刪除",
            color=discord.Color.red()
        )
        embed.add_field(name="身分組", value=role.name)
        embed.add_field(name="執行者", value=entry.user)

        await log_channel.send(embed=embed)
        break

@bot.event
async def on_member_join(member):

    cursor.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (member.id,))
    result = cursor.fetchone()

    if result:
        try:
            await member.kick(reason="黑名單使用者自動踢出")
        except:
            pass
    
# =========================
# 洗版/刷頻檢查
# =========================
@bot.event
async def on_message_violation(member, violation_type):
    """
    violation_type: '刷頻' 或 '洗版'
    達 3 次直接列入黑名單
    """
    if is_whitelisted(member.id):
        return

    reason = f"{violation_type}違規達3次"
    await punish_user(member, reason, force_blacklist=True)
# =========================
# 啟動
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 已登入 {bot.user}")
# =========================
# 事件防護區
# =========================
@bot.event
async def on_guild_channel_create(channel):
    await handle_guild_event(channel, "新增頻道")

@bot.event
async def on_guild_channel_delete(channel):
    await handle_guild_event(channel, "刪除頻道")

@bot.event
async def on_guild_role_delete(role):
    await handle_guild_event(role, "刪除角色")

@bot.event
async def on_guild_update(before, after):
    if before.name != after.name:
        await handle_guild_event(after, "修改伺服器名稱")

@bot.event
async def on_member_join(member):

    cursor.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (member.id,))
    result = cursor.fetchone()

    if result:
        try:
            await member.kick(reason="黑名單使用者自動踢出")

            cursor.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
            log = cursor.fetchone()

            if log and log[0]:
                log_channel = bot.get_channel(log[0])

                embed = discord.Embed(
                    title="🚫 黑名單使用者自動踢出",
                    color=discord.Color.red()
                )

                embed.add_field(name="使用者", value=f"{member} ({member.id})")
                embed.add_field(name="原因", value="黑名單使用者加入伺服器")

                await log_channel.send(embed=embed)

        except:
            pass
# =========================
# Slash 指令（全部有介紹）
# =========================
@bot.tree.command(name="加入黑名單", description="將指定使用者加入黑名單")
@app_commands.checks.has_permissions(administrator=True)
async def add_black(interaction: discord.Interaction, member: discord.Member):

    add_blacklist(member.id)

    # 如果人在伺服器內就踢出
    try:
        await member.kick(reason="被加入黑名單")
    except:
        pass

    await interaction.response.send_message(
        f"🚫 {member.mention} 已加入黑名單並踢出伺服器"
    )

@bot.tree.command(name="移除黑名單", description="將指定使用者移出黑名單")
@app_commands.checks.has_permissions(administrator=True)
async def remove_black(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM blacklist WHERE user_id=?", (member.id,))
    db.commit()
    await interaction.response.send_message(f"✅ {member.mention} 已移出黑名單")

@bot.tree.command(name="查看黑名單", description="查看全伺服器黑名單成員")
@app_commands.checks.has_permissions(administrator=True)
async def view_black(interaction: discord.Interaction):
    cursor.execute("SELECT user_id FROM blacklist")
    data = cursor.fetchall()
    if not data:
        await interaction.response.send_message("黑名單為空")
        return
    msg = "\n".join([f"<@{u[0]}>" for u in data])
    await interaction.response.send_message(msg)

@bot.tree.command(name="加入白名單", description="將指定使用者加入白名單（不受防護影響）")
@app_commands.checks.has_permissions(administrator=True)
async def add_white(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (member.id,))
    db.commit()
    await interaction.response.send_message(f"✅ {member.mention} 已加入白名單")

@bot.tree.command(name="移除白名單", description="將指定使用者移出白名單")
@app_commands.checks.has_permissions(administrator=True)
async def remove_white(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM whitelist WHERE user_id=?", (member.id,))
    db.commit()
    await interaction.response.send_message(f"🚫 {member.mention} 已移出白名單")

@bot.tree.command(name="查看白名單", description="查看全伺服器白名單成員")
@app_commands.checks.has_permissions(administrator=True)
async def view_white(interaction: discord.Interaction):
    cursor.execute("SELECT user_id FROM whitelist")
    data = cursor.fetchall()
    if not data:
        await interaction.response.send_message("白名單為空")
        return
    msg = "\n".join([f"<@{u[0]}>" for u in data])
    await interaction.response.send_message(msg)

@bot.tree.command(name="後台統計", description="查看機器人封鎖與處罰統計")
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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
@app_commands.checks.has_permissions(administrator=True)
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

# 設置違規懲罰訊息頻道
@bot.tree.command(
    name="違規懲罰訊息設置",
    description="設置違規懲罰訊息頻道"
)
@app_commands.checks.has_permissions(administrator=True)
async def set_punish_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    # 確保 guild 有資料行
    ensure_guild_settings(interaction.guild.id)
    # 只更新 punish_channel_id，不會覆蓋其他欄位
    cursor.execute(
        "UPDATE settings SET punish_channel_id=? WHERE guild_id=?",
        (channel.id, interaction.guild.id)
    )
    db.commit()
    await interaction.response.send_message(f"✅ 已設置 {channel.mention} 為違規懲罰訊息頻道")

# 設置日誌頻道
@bot.tree.command(
    name="設置日誌頻道",
    description="設置日誌頻道，紀錄所有成員動作"
)
@app_commands.checks.has_permissions(administrator=True)
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    ensure_guild_settings(interaction.guild.id)
    cursor.execute(
        "UPDATE settings SET log_channel_id=? WHERE guild_id=?",
        (channel.id, interaction.guild.id)
    )
    db.commit()
    await interaction.response.send_message(f"✅ 已設置 {channel.mention} 為日誌頻道")
# =========================

bot.run(TOKEN)






































