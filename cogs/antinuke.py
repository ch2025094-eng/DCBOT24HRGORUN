import discord
from discord.ext import commands
import time
from utils import load, save

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_actions = {}  # guild_id: [timestamps]
        self.spam = {}  # user_id: [timestamps]

    # ------------------------
    # 防炸頻道（新增/刪除）
    # ------------------------
    def check_nuke(self, guild_id):
        now = time.time()
        if guild_id not in self.channel_actions:
            self.channel_actions[guild_id] = []
        self.channel_actions[guild_id].append(now)

        # 保留最近5秒
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
        guild_id = str(guild.id)

        if guild_id not in config or not config[guild_id].get("backup"):
            return

        await self.restore_guild(guild)

    # ------------------------
    # 備份 / 還原
    # ------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx):
        data = {"channels": []}

        for ch in ctx.guild.channels:
            data["channels"].append({
                "name": ch.name,
                "type": str(ch.type),
                "position": ch.position
            })

        config = load("database/security.json")
        config[str(ctx.guild.id)] = {"backup": data}
        save("database/security.json", config)

        await ctx.send("💾 已備份伺服器頻道")

    async def restore_guild(self, guild):
        config = load("database/security.json")
        data = config[str(guild.id)]["backup"]

        # 刪除現有頻道
        for ch in guild.channels:
            try:
                await ch.delete()
            except:
                pass

        # 重建
        for ch in data["channels"]:
            if ch["type"] == "text":
                await guild.create_text_channel(ch["name"])
            elif ch["type"] == "voice":
                await guild.create_voice_channel(ch["name"])

    # ------------------------
    # 防洗版
    # ------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user = str(message.author.id)
        now = time.time()

        if user not in self.spam:
            self.spam[user] = []

        self.spam[user].append(now)
        self.spam[user] = [t for t in self.spam[user] if now - t < 1]

        if len(self.spam[user]) >= 5:
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention} 請勿洗版")
    
    # ------------------------
    # 黑白名單（全域）
    # ------------------------
    @commands.command()
    @commands.is_owner()
    async def globalban(self, ctx, user: discord.User):
        data = load("database/global.json")
        data.setdefault("blacklist", [])
        data["blacklist"].append(user.id)
        save("database/global.json", data)
        await ctx.send("🌍 已加入全域黑名單")

    @commands.command()
    @commands.is_owner()
    async def globalunban(self, ctx, user: discord.User):
        data = load("database/global.json")
        if user.id in data.get("blacklist", []):
            data["blacklist"].remove(user.id)
        save("database/global.json", data)
        await ctx.send("🌍 已移出全域黑名單")

    # ------------------------
    # 伺服器黑名單
    # ------------------------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def banuser(self, ctx, user: discord.Member):
        data = load("database/security.json")
        gid = str(ctx.guild.id)
        data.setdefault(gid, {}).setdefault("blacklist", [])
        data[gid]["blacklist"].append(user.id)
        save("database/security.json", data)
        await ctx.send("🚫 已封鎖（機器人層級）")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        data = load("database/security.json")
        gid = str(ctx.guild.id)

        if ctx.author.id in data.get(gid, {}).get("blacklist", []):
            raise commands.CheckFailure("你被封鎖")

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
