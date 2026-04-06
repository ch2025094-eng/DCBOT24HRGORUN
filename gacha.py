import discord
from discord.ext import commands
import random

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def gacha(self, ctx):
        rewards = ["垃圾", "普通", "稀有", "超稀有"]
        result = random.choices(rewards, weights=[50, 30, 15, 5])[0]

        await ctx.send(f"🎰 你抽到了：{result}")

async def setup(bot):
    await bot.add_cog(Gacha(bot))
