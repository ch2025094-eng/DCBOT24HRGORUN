import discord
from discord.ext import commands
from utils import load

class RoleButtons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setup_roles(self, ctx):
        """建立一個角色按鈕訊息"""
        role_data = load("database/shop.json")
        class RoleView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                for item, info in role_data.items():
                    role_id = int(info["role_id"])
                    button = discord.ui.Button(label=item, style=discord.ButtonStyle.primary)
                    async def callback(interaction, r_id=role_id):
                        role = ctx.guild.get_role(r_id)
                        if role in interaction.user.roles:
                            await interaction.user.remove_roles(role)
                            await interaction.response.send_message(f"❌ 移除 {role.name}", ephemeral=True)
                        else:
                            await interaction.user.add_roles(role)
                            await interaction.response.send_message(f"✅ 獲得 {role.name}", ephemeral=True)
                    button.callback = callback
                    self.add_item(button)
        await ctx.send("點擊按鈕領取身分組：", view=RoleView())

async def setup(bot):
    await bot.add_cog(RoleButtons(bot))
