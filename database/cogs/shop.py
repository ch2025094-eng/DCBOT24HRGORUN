import discord
from discord.ext import commands
import json

def load(file):
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def shop(self, ctx):
        shop = load("database/shop.json")

        msg = "🛒 商店列表：\n"
        for item in shop:
            msg += f"{item} - 💰 {shop[item]['price']}\n"

        await ctx.send(msg)

    @commands.command()
    async def buy(self, ctx, item_name):
        shop = load("database/shop.json")
        eco = load("database/economy.json")

        user = str(ctx.author.id)

        if item_name not in shop:
            return await ctx.send("❌ 沒有這個商品")

        if user not in eco:
            eco[user] = {"money": 0}

        price = shop[item_name]["price"]

        if eco[user]["money"] < price:
            return await ctx.send("❌ 錢不夠")

        eco[user]["money"] -= price
        save("database/economy.json", eco)

        # 給身分組
        role = ctx.guild.get_role(shop[item_name]["role_id"])
        if role:
            await ctx.author.add_roles(role)

        await ctx.send(f"✅ 購買成功：{item_name}")

async def setup(bot):
    await bot.add_cog(Shop(bot))
