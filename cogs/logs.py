import discord
from discord.ext import commands
from utils import load, save

LOG_TYPES = {
    "message_edit": "✏️ 訊息編輯",
    "message_delete": "🗑️ 訊息刪除",
    "channel": "📁 頻道更新",
    "voice": "🔊 語音狀態"
}

# ---------------- UI ----------------
class LogSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=v, value=k)
            for k, v in LOG_TYPES.items()
        ]
        super().__init__(
            placeholder="請選擇您需要的日誌",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        data = load("database/logs.json")
        gid = str(interaction.guild.id)

        data.setdefault(gid, {})
        data[gid]["enabled"] = self.values

        save("database/logs.json", data)

        await interaction.response.send_message("✅ 日誌類型已更新", ephemeral=True)

class LogView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LogSelect())

# ---------------- Cog ----------------
class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self, guild):
        data = load("database/logs.json")
        return data.get(str(guild.id), {})

    def get_channel(self, guild):
        config = self.get_config(guild)
        cid = config.get("channel")
        if cid:
            return guild.get_channel(cid)
        return None

    def enabled(self, guild, key):
        config = self.get_config(guild)
        return key in config.get("enabled", [])

    # 設定 UI
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def logsetup(self, ctx, channel: discord.TextChannel):
        data = load("database/logs.json")
        gid = str(ctx.guild.id)

        data.setdefault(gid, {})
        data[gid]["channel"] = channel.id

        save("database/logs.json", data)

        embed = discord.Embed(
            title="📜 日誌設定",
            description="請選擇您需要的日誌",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed, view=LogView())

    # ---------------- 事件 ----------------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild:
            return
        if not self.enabled(message.guild, "message_delete"):
            return

        ch = self.get_channel(message.guild)
        if ch:
            await ch.send(f"🗑️ {message.author} 刪除訊息：{message.content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild:
            return
        if not self.enabled(before.guild, "message_edit"):
            return

        ch = self.get_channel(before.guild)
        if ch:
            await ch.send(f"✏️ {before.author}：{before.content} → {after.content}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not self.enabled(channel.guild, "channel"):
            return

        ch = self.get_channel(channel.guild)
        if ch:
            await ch.send(f"📁 建立頻道：{channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not self.enabled(channel.guild, "channel"):
            return

        ch = self.get_channel(channel.guild)
        if ch:
            await ch.send(f"❌ 刪除頻道：{channel.name}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.enabled(member.guild, "voice"):
            return

        ch = self.get_channel(member.guild)
        if ch:
            await ch.send(f"🔊 {member} 語音狀態變動")

async def setup(bot):
    await bot.add_cog(Logs(bot))
