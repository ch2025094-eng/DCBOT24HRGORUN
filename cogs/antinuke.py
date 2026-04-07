import discord
from discord.ext import commands
from collections import defaultdict
import time

DEV_ID = 1442017307332182168  # 🔥 只允許你操作全域名單

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam = defaultdict(list)

    async def send_log(guild, text):
        from utils import load
        
    data = load("database/logs.json")
    gid = str(guild.id)

    channel_id = data.get(gid, {}).get("channel")
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    await channel.send(text)
    
    # ------------------------
    # 🚫 防洗版
    # ------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = str(message.guild.id)
        now = time.time()

        # 讀資料
        g_data = load(f"database/guilds/{guild_id}.json")
        global_data = load("database/global.json")

        g_data.setdefault("blacklist", [])
        g_data.setdefault("whitelist", [])
        global_data.setdefault("blacklist", [])
        global_data.setdefault("whitelist", [])

        # ✅ 白名單保護
        if user_id in global_data["whitelist"] or user_id in g_data["whitelist"]:
            if user_id in g_data["blacklist"]:
                g_data["blacklist"].remove(user_id)
                save(f"database/guilds/{guild_id}.json", g_data)
            return

        # 記錄訊息
        self.spam[user_id].append(now)

        # 保留1秒
        self.spam[user_id] = [
            t for t in self.spam[user_id] if now - t < 1
        ]

        # 🚫 洗版判定
        if len(self.spam[user_id]) >= 5:

            # 加入伺服器黑名單
            if user_id not in g_data["blacklist"]:
                g_data["blacklist"].append(user_id)
                save(f"database/guilds/{guild_id}.json", g_data)

            # 踢出
            try:
                await message.guild.kick(message.author, reason="洗版")
            except:
                pass

    await send_log(
    message.guild,
    f"🚫 {message.author} 因洗版被踢出並加入黑名單"
)
    # 清空紀錄（避免一直觸發）
        self.spam[user_id] = []
    # ------------------------
    # 💥 炸群偵測（簡化範例：大量刪頻道/建頻道）
    # ------------------------
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1):
            user = entry.user
            break

        if not user:
            return

        user_id = user.id
        guild_id = str(guild.id)

        g_data = load(f"database/guilds/{guild_id}.json")
        global_data = load("database/global.json")

        g_data.setdefault("blacklist", [])
        global_data.setdefault("blacklist", [])
        global_data.setdefault("whitelist", [])

        # ✅ 全域白名單保護
        if user_id in global_data["whitelist"]:
            return

        # 🔥 加入黑名單
        if user_id not in global_data["blacklist"]:
            global_data["blacklist"].append(user_id)
            save("database/global.json", global_data)

        if user_id not in g_data["blacklist"]:
            g_data["blacklist"].append(user_id)
            save(f"database/guilds/{guild_id}.json", g_data)

        # 踢出
        try:
            await guild.kick(user, reason="炸群")
        except:
            pass

    await send_log(
    guild,
    f"💥 {user} 因炸群被踢出並加入全域黑名單"
)

        # 📢 全域公告
        for g in self.bot.guilds:
            try:
                if g.system_channel:
                    await g.system_channel.send(
                        f"@everyone ⚠️請注意!!! {user} 因炸群，被加入全域黑名單"
                    )
            except:
                pass

    # ------------------------
    # 🔧 全域黑白名單（開發者限定）
    # ------------------------
    @commands.command()
    async def gblack(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")
        data.setdefault("blacklist", [])

        if user.id not in data["blacklist"]:
            data["blacklist"].append(user.id)
            save("database/global.json", data)
            await ctx.send(f"已加入全域黑名單: {user}")

    @commands.command()
    async def gunblack(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")
        if user.id in data["blacklist"]:
            data["blacklist"].remove(user.id)
            save("database/global.json", data)
            await ctx.send(f"已移除全域黑名單: {user}")

    @commands.command()
    async def gwhite(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")
        data.setdefault("whitelist", [])

        if user.id not in data["whitelist"]:
            data["whitelist"].append(user.id)
            save("database/global.json", data)
            await ctx.send(f"已加入全域白名單: {user}")
    # ------------------------
    # 💾 備份 / 還原
    # ------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx):
        data = {"channels": []}

        for ch in ctx.guild.channels:
            data["channels"].append({
                "name": ch.name,
                "type": str(ch.type)
            })

        config = load("database/security.json")
        gid = str(ctx.guild.id)

        config.setdefault(gid, {})
        config[gid]["backup"] = data

        save("database/security.json", config)

        await ctx.send("💾 已備份伺服器頻道")

    async def restore_guild(self, guild):
        config = load("database/security.json")
        gid = str(guild.id)

        data = config.get(gid, {}).get("backup")
        if not data:
            return

        # 刪除現有頻道
        for ch in guild.channels:
            try:
                await ch.delete()
            except:
                pass

        # 重建
        for ch in data["channels"]:
            try:
                if "text" in ch["type"]:
                    await guild.create_text_channel(ch["name"])
                elif "voice" in ch["type"]:
                    await guild.create_voice_channel(ch["name"])
            except:
                pass
# ------------------------
# 🌍 全域黑名單管理
# ------------------------
@commands.command()
@commands.is_owner()
async def globalblacklist_add(self, ctx, user: discord.User):
    data = load("database/global.json")
    data.setdefault("blacklist", [])
    data.setdefault("whitelist", [])

    if user.id in data["blacklist"]:
        return await ctx.send("❌ 已經在全域黑名單")

    data["blacklist"].append(user.id)

    # 🔥 自動移出白名單
    if user.id in data["whitelist"]:
        data["whitelist"].remove(user.id)

    save("database/global.json", data)
    await ctx.send(f"🚫 已加入全域黑名單：{user}")
    await send_log(
    ctx.guild,
    f"🔧 {ctx.author} 將 {user} 加入全域黑名單"
)


@commands.command()
@commands.is_owner()
async def globalblacklist_remove(self, ctx, user: discord.User):
    data = load("database/global.json")

    if user.id not in data.get("blacklist", []):
        return await ctx.send("❌ 不在黑名單")

    data["blacklist"].remove(user.id)
    save("database/global.json", data)

    await ctx.send(f"🗑️ 已移出全域黑名單：{user}")


# ------------------------
# 🌍 全域白名單管理
# ------------------------
@commands.command()
@commands.is_owner()
async def globalwhitelist_add(self, ctx, user: discord.User):
    data = load("database/global.json")
    data.setdefault("whitelist", [])
    data.setdefault("blacklist", [])

    if user.id in data["whitelist"]:
        return await ctx.send("❌ 已經在全域白名單")

    data["whitelist"].append(user.id)

    # 🔥 自動移出黑名單
    if user.id in data["blacklist"]:
        data["blacklist"].remove(user.id)

    save("database/global.json", data)
    await ctx.send(f"🤍 已加入全域白名單：{user}")


@commands.command()
@commands.is_owner()
async def globalwhitelist_remove(self, ctx, user: discord.User):
    data = load("database/global.json")

    if user.id not in data.get("whitelist", []):
        return await ctx.send("❌ 不在白名單")

    data["whitelist"].remove(user.id)
    save("database/global.json", data)

    await ctx.send(f"🗑️ 已移出全域白名單：{user}")


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
