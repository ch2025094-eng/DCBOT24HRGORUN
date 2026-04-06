import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin():
        async def predicate(ctx):
            return ctx.author.guild_permissions.administrator
        return commands.check(predicate)

    @commands.command()
    @is_admin()
    async def clear(self, ctx, amount: int):
        await ctx.channel.purge(limit=amount)
        await ctx.send(f"🧹 清除了 {amount} 則訊息", delete_after=5)

    @commands.command()
    @is_admin()
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        await member.kick(reason=reason)
        await ctx.send(f"👢 已踢出 {member}")

    @commands.command()
    @is_admin()
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        await member.ban(reason=reason)
        await ctx.send(f"⛔ 已封鎖 {member}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
