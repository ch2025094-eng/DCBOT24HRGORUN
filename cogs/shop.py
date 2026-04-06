import discord
from discord.ext import commands
from utils import load, save

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 查看商店
    @commands.command()
    async def shop(self, ctx):
        shop_data = load("database/shop.json")
        if not shop_data:
            return await ctx.send("🛒 商店目前沒有任何商品")
        msg = "🛒 商店列表：\n"
        for item, info in shop_data.items():
            msg += f"{item} - 💰 {info['price']}\n"
        await ctx.send(msg)

    # 購買商品
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

        # 給身分組（如果有設定 role_id）
        if "role_id" in shop_data[item_name]:
            role_id = int(shop_data[item_name]["role_id"])
            role = ctx.guild.get_role(role_id)
            if role:
                await ctx.author.add_roles(role)

        await ctx.send(f"✅ 購買成功：{item_name}")

    # 新增商品（管理員專用）
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def additem(self, ctx, item_name, price: int, role_id: int = None):
        shop_data = load("database/shop.json")
        if item_name in shop_data:
            return await ctx.send("❌ 這個商品已經存在")
        shop_data[item_name] = {"price": price}
        if role_id:
            shop_data[item_name]["role_id"] = role_id
        save("database/shop.json", shop_data)
        await ctx.send(f"✅ 已新增商品：{item_name} - 💰 {price}")

    # 刪除商品（管理員專用）
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removeitem(self, ctx, item_name):
        shop_data = load("database/shop.json")
        if item_name not in shop_data:
            return await ctx.send("❌ 這個商品不存在")
        del shop_data[item_name]
        save("database/shop.json", shop_data)
        await ctx.send(f"🗑️ 已刪除商品：{item_name}")

async def setup(bot):
    await bot.add_cog(Shop(bot))
