import discord
from discord.ext import commands
import random
from utils import load, save

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
        data = load("database/economy.json")
        user = str(ctx.author.id)

        if user not in data:
            data[user] = {"money": 0}

        earn = random.randint(50, 150)
        data[user]["money"] += earn
        save("database/economy.json", data)

        await ctx.send(f"🧑‍💼 你賺了 {earn} 元！")

async def setup(bot):
    await bot.add_cog(Economy(bot))
