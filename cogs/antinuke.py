import discord
from discord.ext import commands
import time
from utils import load, save

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_actions = {}  # 防炸
        self.spam = {}  # 防洗版

    # ------------------------
    # 🔥 防炸（頻道大量新增/刪除）
    # ------------------------
    def check_nuke(self, guild_id):
        now = time.time()

        if guild_id not in self.channel_actions:
            self.channel_actions[guild_id] = []

        self.channel_actions[guild_id].append(now)

        # 保留 5 秒內的操作
        self.channel_actions[guild_id] = [
            t for t in self.channel_actions[guild_id] if now - t < 5
        ]

        return len(self.channel_actions[guild_id]) >= 5

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if self.check_nuke(channel.guild.id):
            await self.handle_nuke(channel.guild)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if self.check_nuke(channel.guild.id):
            await self.handle_nuke(channel.guild)

    async def handle_nuke(self, guild):
        config = load("database/security.json")
        gid = str(guild.id)

        if gid not in config:
            return

        if "backup" not in config[gid]:
            return

        await self.restore_guild(guild)

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
    # 🚫 防洗版
    # ------------------------
    @commands.Cog.listener()
async def on_message(self, message):
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = time.time()

    # 初始化
    if user_id not in self.spam:
        self.spam[user_id] = []

    self.spam[user_id].append(now)

    # ✅ 保留 1 秒內訊息
    self.spam[user_id] = [
        t for t in self.spam[user_id] if now - t < 1
    ]

    # 🚫 1秒5則 = 洗版
    if len(self.spam[user_id]) >= 5:
        try:
            await message.delete()
        except:
            pass

        # 🔥 加入全域黑名單
        data = load("database/global.json")
        data.setdefault("blacklist", [])

        if user_id not in data["blacklist"]:
            data["blacklist"].append(user_id)
            save("database/global.json", data)

            try:
                await message.channel.send(
                    f"🚫 {message.author.mention} 因洗版已被加入全域黑名單"
                )
            except:
                pass

        # 清空紀錄（避免一直觸發）
        self.spam[user_id] = []

    # ------------------------
    # 🌍 全域黑白名單（限制指令）
    # ------------------------
    @commands.Cog.listener()
    async def on_command(self, ctx):
        global_data = load("database/global.json")
        security = load("database/security.json")
        gid = str(ctx.guild.id)

        # ✅ 全域白名單（直接放行）
        if ctx.author.id in global_data.get("whitelist", []):
            return

        # ❌ 全域黑名單
        if ctx.author.id in global_data.get("blacklist", []):
            raise commands.CheckFailure("你在全域黑名單")

        # 🏠 伺服器白名單
        whitelist = security.get(gid, {}).get("whitelist", [])
        if whitelist:
            if ctx.author.id not in whitelist:
                raise commands.CheckFailure("你不在白名單")

        # 🚫 伺服器黑名單
        blacklist = security.get(gid, {}).get("blacklist", [])
        if ctx.author.id in blacklist:
            raise commands.CheckFailure("你被封鎖")

    # ------------------------
    # 🌍 全域白名單管理
    # ------------------------
    @commands.command()
    @commands.is_owner()
    async def globalwhitelist_add(self, ctx, user: discord.User):
        data = load("database/global.json")
        data.setdefault("whitelist", [])

        if user.id in data["whitelist"]:
            return await ctx.send("❌ 已經在全域白名單")

        data["whitelist"].append(user.id)
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

    # ------------------------
    # 🏠 伺服器白名單管理
    # ------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def whitelist_add(self, ctx, user: discord.Member):
        data = load("database/security.json")
        gid = str(ctx.guild.id)

        data.setdefault(gid, {}).setdefault("whitelist", [])

        if user.id in data[gid]["whitelist"]:
            return await ctx.send("❌ 已經在白名單")

        data[gid]["whitelist"].append(user.id)
        save("database/security.json", data)

        await ctx.send(f"🤍 已加入白名單：{user}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def whitelist_remove(self, ctx, user: discord.Member):
        data = load("database/security.json")
        gid = str(ctx.guild.id)

        if user.id not in data.get(gid, {}).get("whitelist", []):
            return await ctx.send("❌ 不在白名單")

        data[gid]["whitelist"].remove(user.id)
        save("database/security.json", data)

        await ctx.send(f"🗑️ 已移出白名單：{user}")

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
