import discord
from discord.ext import commands
import asyncio, os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"載入 {file}")
            except Exception as e:
                print(f"❌ {file} 載入失敗: {e}")

@bot.event
async def on_ready():
    print(f"已登入：{bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Slash同步 {len(synced)} 個指令")
    except Exception as e:
        print(e)

async def main():
    async with bot:
        await load_cogs()
        await bot.start("DISCORD_TOKEN")

asyncio.run(main())
