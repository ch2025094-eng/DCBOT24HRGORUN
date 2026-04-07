import discord
from discord.ext import commands
from collections import defaultdict
import time
from utils import load, save

DEV_ID = 1442017307332182168

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam = defaultdict(list)

    # =========================
    # 📜 日誌（Embed版）
    # =========================
    async def send_log(self, guild, title, desc, color=discord.Color.red()):
        data = load("database/logs.json")
        gid = str(guild.id)

        channel_id = data.get(gid, {}).get("channel")
        if not channel_id:
            return

        ch = guild.get_channel(channel_id)
        if not ch:
            return

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
            timestamp=discord.utils.utcnow()
        )

        await ch.send(embed=embed)

    # =========================
    # 🚫 防洗版
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        uid = message.author.id
        gid = str(message.guild.id)
        now = time.time()

        g_data = load(f"database/guilds/{gid}.json")
        global_data = load("database/global.json")

        g_data.setdefault("blacklist", [])
        g_data.setdefault("whitelist", [])
        global_data.setdefault("blacklist", [])
        global_data.setdefault("whitelist", [])

        # 🛡️ 白名單
        if uid in global_data["whitelist"] or uid in g_data["whitelist"]:
            return

        # 記錄訊息
        self.spam[uid].append(now)
        self.spam[uid] = [t for t in self.spam[uid] if now - t < 1]

        # 🚫 洗版判定
        if len(self.spam[uid]) >= 5:

            # 加入全域黑名單
            if uid not in global_data["blacklist"]:
                global_data["blacklist"].append(uid)
                save("database/global.json", global_data)

            # 加入伺服器黑名單
            if uid not in g_data["blacklist"]:
                g_data["blacklist"].append(uid)
                save(f"database/guilds/{gid}.json", g_data)

            # 踢出
            try:
                await message.guild.kick(message.author, reason="洗版")
            except:
                pass

            await self.send_log(
                message.guild,
                "🚫 洗版偵測",
                f"使用者：{message.author}\n動作：踢出 + 全域黑名單"
            )

            self.spam[uid] = []

    # =========================
    # 💥 炸群偵測
    # =========================
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild

        user = None
        async for entry in guild.audit_logs(limit=1):
            user = entry.user
            break

        if not user:
            return

        uid = user.id
        gid = str(guild.id)

        g_data = load(f"database/guilds/{gid}.json")
        global_data = load("database/global.json")

        g_data.setdefault("blacklist", [])
        global_data.setdefault("blacklist", [])
        global_data.setdefault("whitelist", [])

        # 🛡️ 白名單
        if uid in global_data["whitelist"]:
            return

        # 加入全域黑名單
        if uid not in global_data["blacklist"]:
            global_data["blacklist"].append(uid)
            save("database/global.json", global_data)

        # 加入伺服器黑名單
        if uid not in g_data["blacklist"]:
            g_data["blacklist"].append(uid)
            save(f"database/guilds/{gid}.json", g_data)

        # 踢出
        try:
            await guild.kick(user, reason="炸群")
        except:
            pass

        await self.send_log(
            guild,
            "💥 炸群偵測",
            f"使用者：{user}\n動作：踢出 + 全域黑名單"
        )

        # 📢 全服警告
        for g in self.bot.guilds:
            try:
                if g.system_channel:
                    await g.system_channel.send(
                        f"⚠️ {user} 因炸群已被列入全域黑名單"
                    )
            except:
                pass

    # =========================
    # 🔧 全域黑名單（開發者）
    # =========================
    @commands.command()
    async def gblack(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")
        data.setdefault("blacklist", [])

        if user.id not in data["blacklist"]:
            data["blacklist"].append(user.id)
            save("database/global.json", data)

            await ctx.send(f"🚫 已加入全域黑名單：{user}")
            await self.send_log(
                ctx.guild,
                "🔧 管理操作",
                f"{ctx.author} 將 {user} 加入全域黑名單"
            )

    @commands.command()
    async def gunblack(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")

        if user.id in data.get("blacklist", []):
            data["blacklist"].remove(user.id)
            save("database/global.json", data)

            await ctx.send(f"🗑️ 已移出全域黑名單：{user}")

    # =========================
    # 🤍 全域白名單
    # =========================
    @commands.command()
    async def gwhite(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")
        data.setdefault("whitelist", [])

        if user.id not in data["whitelist"]:
            data["whitelist"].append(user.id)
            save("database/global.json", data)

            await ctx.send(f"🤍 已加入全域白名單：{user}")

    @commands.command()
    async def gunwhite(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")

        if user.id in data.get("whitelist", []):
            data["whitelist"].remove(user.id)
            save("database/global.json", data)

            await ctx.send(f"🗑️ 已移出全域白名單：{user}")

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
