import discord
from discord.ext import commands
import json
import random

def load_data():
    with open("database/economy.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("database/economy.json", "w") as f:
        json.dump(data, f, indent=4)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def balance(self, ctx):
        data = load_data()
        user = str(ctx.author.id)

        if user not in data:
            data[user] = {"money": 0}
            save_data(data)

        await ctx.send(f"💰 你的錢：{data[user]['money']}")

    @commands.command()
    async def work(self, ctx):
        data = load_data()
        user = str(ctx.author.id)

        if user not in data:
            data[user] = {"money": 0}

        earn = random.randint(50, 150)
        data[user]["money"] += earn
        save_data(data)

        await ctx.send(f"🧑‍💼 你賺了 {earn} 元！")

async def setup(bot):
    await bot.add_cog(Economy(bot))
