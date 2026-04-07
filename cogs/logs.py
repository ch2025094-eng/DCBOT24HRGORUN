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
        return guild.get_channel(cid) if cid else None

    def enabled(self, guild, key):
        config = self.get_config(guild)
        return key in config.get("enabled", [])

    # ---------------- 設定 ----------------
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
        if not message.guild or message.author.bot:
            return
        if not self.enabled(message.guild, "message_delete"):
            return

        ch = self.get_channel(message.guild)
        if not ch:
            return

        content = message.content or "（無內容）"
        if len(content) > 1000:
            content = content[:1000] + "..."

        embed = discord.Embed(title="🗑️ 訊息刪除", color=discord.Color.red())
        embed.add_field(name="使用者", value=f"{message.author} ({message.author.id})")
        embed.add_field(name="頻道", value=message.channel.mention)
        embed.add_field(name="內容", value=content, inline=False)

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        if not self.enabled(before.guild, "message_edit"):
            return

        ch = self.get_channel(before.guild)
        if not ch:
            return

        embed = discord.Embed(title="✏️ 訊息編輯", color=discord.Color.orange())
        embed.add_field(name="使用者", value=f"{before.author} ({before.author.id})")
        embed.add_field(name="頻道", value=before.channel.mention)
        embed.add_field(name="修改前", value=(before.content or "無")[:1000], inline=False)
        embed.add_field(name="修改後", value=(after.content or "無")[:1000], inline=False)

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not self.enabled(channel.guild, "channel"):
            return

        ch = self.get_channel(channel.guild)
        if not ch:
            return

        user = "未知"
        async for entry in channel.guild.audit_logs(limit=1):
            user = entry.user
            break

        embed = discord.Embed(title="📁 頻道建立", color=discord.Color.green())
        embed.add_field(name="頻道", value=channel.name)
        embed.add_field(name="操作者", value=str(user))

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not self.enabled(channel.guild, "channel"):
            return

        ch = self.get_channel(channel.guild)
        if not ch:
            return

        user = "未知"
        async for entry in channel.guild.audit_logs(limit=1):
            user = entry.user
            break

        embed = discord.Embed(title="❌ 頻道刪除", color=discord.Color.red())
        embed.add_field(name="頻道", value=channel.name)
        embed.add_field(name="操作者", value=str(user))

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.enabled(member.guild, "voice"):
            return

        ch = self.get_channel(member.guild)
        if not ch:
            return

        action = None
        if not before.channel and after.channel:
            action = f"加入語音：{after.channel.name}"
        elif before.channel and not after.channel:
            action = f"離開語音：{before.channel.name}"
        elif before.channel != after.channel:
            action = f"切換語音：{before.channel.name} → {after.channel.name}"

        if action:
            embed = discord.Embed(
                title="🔊 語音狀態",
                description=action,
                color=discord.Color.blue()
            )
            embed.add_field(name="使用者", value=f"{member} ({member.id})")

            await ch.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logs(bot))
