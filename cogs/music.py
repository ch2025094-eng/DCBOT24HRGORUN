import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extractaudio': True,
    'audioformat': "mp3",
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}  # guild_id -> player

    @commands.command()
    async def play(self, ctx, *, url):
        """播放音樂"""
        if not ctx.author.voice:
            return await ctx.send("❌ 你不在語音頻道")
        channel = ctx.author.voice.channel
        voice = ctx.guild.voice_client
        if not voice:
            voice = await channel.connect()
        info = ytdl.extract_info(url, download=False)
        url2 = info['url']
        source = discord.FFmpegPCMAudio(url2, **ffmpeg_options)
        voice.play(source)
        await ctx.send(f"▶️ 正在播放：{info['title']}")

    @commands.command()
    async def pause(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ 已暫停")
        else:
            await ctx.send("❌ 沒有播放中的音樂")

    @commands.command()
    async def resume(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ 已繼續")
        else:
            await ctx.send("❌ 沒有暫停的音樂")

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏹️ 已停止播放")
        else:
            await ctx.send("❌ 沒有播放中的音樂")

    @commands.command()
    async def leave(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            await vc.disconnect()
            await ctx.send("👋 已離開語音頻道")
        else:
            await ctx.send("❌ 我不在語音頻道")

async def setup(bot):
    await bot.add_cog(Music(bot))
