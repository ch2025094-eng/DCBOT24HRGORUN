import discord
from discord.ext import commands
import random
from utils import load, save, cooldown_check

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def balance(self, ctx):
        data = load("database/economy.json")
        user = str(ctx.author.id)
        if user not in data:
            data[user] = {"money": 0}
        await ctx.send(f"💰 你的錢：{data[user]['money']}")
        save("database/economy.json", data)

    @commands.command()
    async def work(self, ctx):
        can, remain = await cooldown_check(ctx.author.id, "work", 60)
        if not can:
            return await ctx.send(f"⏳ 冷卻中，還剩 {remain} 秒")
        data = load("database/economy.json")
        user = str(ctx.author.id)
        if user not in data:
            data[user] = {"money": 0}
        earn = random.randint(50, 150)
        data[user]["money"] += earn
        save("database/economy.json", data)
        await ctx.send(f"🧑‍💼 你賺了 {earn} 元！")

    @commands.command()
    async def daily(self, ctx):
        can, remain = await cooldown_check(ctx.author.id, "daily", 86400)
        if not can:
            return await ctx.send(f"⏳ 每日獎勵冷卻中，還剩 {remain} 秒")
        data = load("database/economy.json")
        user = str(ctx.author.id)
        if user not in data:
            data[user] = {"money": 0}
        reward = 500
        data[user]["money"] += reward
        save("database/economy.json", data)
        await ctx.send(f"🎁 你領取了每日獎勵：{reward} 元！")

async def setup(bot):
    await bot.add_cog(Economy(bot))
