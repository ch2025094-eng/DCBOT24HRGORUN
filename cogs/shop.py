import discord
from discord.ext import commands
from utils import load, save

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def shop(self, ctx):
        shop_data = load("database/shop.json")
        msg = "🛒 商店列表：\n"
        for item, info in shop_data.items():
            msg += f"{item} - 💰 {info['price']}\n"
        await ctx.send(msg)

    @commands.command()
    async def buy(self, ctx, item_name):
        shop_data = load("database/shop.json")
        eco_data = load("database/economy.json")
        user = str(ctx.author.id)

        if item_name not in shop_data:
            return await ctx.send("❌ 沒有這個商品")

        if user not in eco_data:
            eco_data[user] = {"money": 0}

        price = shop_data[item_name]["price"]
        if eco_data[user]["money"] < price:
            return await ctx.send("❌ 錢不夠")

        eco_data[user]["money"] -= price
        save("database/economy.json", eco_data)

        role_id = int(shop_data[item_name]["role_id"])
        role = ctx.guild.get_role(role_id)
        if role is None:
            return await ctx.send("❌ 找不到這個身分組 (ID 錯誤)")

        try:
            await ctx.author.add_roles(role)
            await ctx.send(f"✅ 購買成功：{item_name}")
        except Exception as e:
            await ctx.send(f"❌ 發生錯誤：{e}")

async def setup(bot):
    await bot.add_cog(Shop(bot))
