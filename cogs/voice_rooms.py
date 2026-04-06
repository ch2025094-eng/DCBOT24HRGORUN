import discord
from discord.ext import commands
from utils import load, save

class VoiceRooms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_rooms = {}

    @commands.command()
    async def set_vc(self, ctx, channel: discord.VoiceChannel):
        """設定語音自動房觸發頻道 (群主使用)"""
        data = load("database/vc_settings.json")
        data[str(ctx.guild.id)] = channel.id
        save("database/vc_settings.json", data)
        await ctx.send(f"✅ 已設定 {channel.name} 為自動房觸發頻道")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        data = load("database/vc_settings.json")
        guild_id = str(member.guild.id)
        if guild_id not in data:
            return
        trigger_id = data[guild_id]
        if after.channel and after.channel.id == trigger_id:
            new_channel = await after.channel.clone(name=f"{member.name} 的房間")
            await member.move_to(new_channel)
            self.temp_rooms[new_channel.id] = new_channel
        if before.channel and before.channel.id in self.temp_rooms:
            channel = self.temp_rooms[before.channel.id]
            if len(channel.members) == 0:
                await channel.delete()
                del self.temp_rooms[before.channel.id]

async def setup(bot):
    await bot.add_cog(VoiceRooms(bot))
