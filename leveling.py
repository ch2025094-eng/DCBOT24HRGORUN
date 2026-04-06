import discord
from discord.ext import commands
import json
import random

def load_data():
    with open("database/levels.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("database/levels.json", "w") as f:
        json.dump(data, f, indent=4)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        data = load_data()
        user = str(message.author.id)

        if user not in data:
            data[user] = {"xp": 0, "level": 1}

        xp_gain = random.randint(5, 15)
        data[user]["xp"] += xp_gain

        if data[user]["xp"] >= data[user]["level"] * 100:
            data[user]["xp"] = 0
            data[user]["level"] += 1
            await message.channel.send(f"🎉 {message.author} 升級了！Lv.{data[user]['level']}")

        save_data(data)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
