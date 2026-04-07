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

    # ✅ 修正 send_log
    async def send_log(self, guild, text):
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

        g_data = load(f"database/guilds/{guild_id}.json")
        global_data = load("database/global.json")

        g_data.setdefault("blacklist", [])
        g_data.setdefault("whitelist", [])
        global_data.setdefault("blacklist", [])
        global_data.setdefault("whitelist", [])

        # 白名單
        if user_id in global_data["whitelist"] or user_id in g_data["whitelist"]:
            return

        # 記錄訊息
        self.spam[user_id].append(now)
        self.spam[user_id] = [t for t in self.spam[user_id] if now - t < 1]

        if len(self.spam[user_id]) >= 5:
            if user_id not in g_data["blacklist"]:
                g_data["blacklist"].append(user_id)
                save(f"database/guilds/{guild_id}.json", g_data)

            try:
                await message.guild.kick(message.author, reason="洗版")
            except:
                pass

            await self.send_log(
                message.guild,
                f"🚫 {message.author} 因洗版被踢出並加入黑名單"
            )

            self.spam[user_id] = []

    # ------------------------
    # 💥 炸群偵測
    # ------------------------
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild

        user = None
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

        if user_id in global_data["whitelist"]:
            return

        if user_id not in global_data["blacklist"]:
            global_data["blacklist"].append(user_id)
            save("database/global.json", global_data)

        if user_id not in g_data["blacklist"]:
            g_data["blacklist"].append(user_id)
            save(f"database/guilds/{guild_id}.json", g_data)

        try:
            await guild.kick(user, reason="炸群")
        except:
            pass

        await self.send_log(
            guild,
            f"💥 {user} 因炸群被踢出並加入全域黑名單"
        )

    # ------------------------
    # 🔧 全域黑名單（開發者）
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
            await self.send_log(ctx.guild, f"🔧 {ctx.author} 將 {user} 加入全域黑名單")

    @commands.command()
    async def gunblack(self, ctx, user: discord.User):
        if ctx.author.id != DEV_ID:
            return

        data = load("database/global.json")

        if user.id in data.get("blacklist", []):
            data["blacklist"].remove(user.id)
            save("database/global.json", data)

            await ctx.send(f"已移除全域黑名單: {user}")

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
