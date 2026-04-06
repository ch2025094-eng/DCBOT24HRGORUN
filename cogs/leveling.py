import discord
from discord.ext import commands
import random
from utils import load, save

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        data = load("database/levels.json")
        user = str(message.author.id)
        if user not in data:
            data[user] = {"xp":0,"level":1}
        xp = random.randint(5,15)
        data[user]["xp"] += xp
        if data[user]["xp"] >= data[user]["level"]*100:
            data[user]["xp"] = 0
            data[user]["level"] += 1
            await message.channel.send(f"🎉 {message.author} 升到 Lv.{data[user]['level']}")
        save("database/levels.json", data)
        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
