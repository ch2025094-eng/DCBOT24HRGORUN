import discord
from discord.ext import commands
import random
from utils import cooldown_check

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def gacha(self, ctx):
        can, remain = await cooldown_check(ctx.author.id, "gacha", 10)
        if not can:
            return await ctx.send(f"⏳ 冷卻中，還剩 {remain} 秒")
        rewards = ["垃圾","普通","稀有","傳說"]
        weights = [50,30,15,5]
        result = random.choices(rewards, weights=weights)[0]
        await ctx.send(f"🎰 你抽到了：{result}")

async def setup(bot):
    await bot.add_cog(Gacha(bot))
