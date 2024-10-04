import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix='/', intents=intents)

youtube_dl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'quiet': True,
    'extract_flat': 'True'
}

# Command to join voice channel and play music
@bot.command(name='play', help='Play music from YouTube')
async def play_media(ctx, *, search_query: str):
    # Check if the user is in a voice channel
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel

        # If the bot is not already connected, connect to the user's voice channel
        if not ctx.voice_client:
            await voice_channel.connect()

        voice_client = ctx.voice_client

        # Search and extract YouTube video URL
        
        results = YoutubeSearch(search_query, max_results=1).to_dict()
        title = results[0]["title"]
        url = "https://youtube.com" + results[0]["url_suffix"]

        with YoutubeDL(youtube_dl_opts) as ydl:
            song_info = ydl.extract_info(url, download=False)

        # Play the audio from the extracted URL
        audio_source = discord.FFmpegPCMAudio(song_info["url"])
        if not voice_client.is_playing():
            voice_client.play(audio_source)
            await ctx.send(f"Now playing: {title}")
        else:
            await ctx.send("Already playing music!")
    else:
        await ctx.send("You need to be in a voice channel to play music!")


# Command to stop playing music and disconnect the bot
@bot.command(name='stop', help='Stop media and leave the voice channel')
async def stop_media(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Stopped the music and disconnected.")
    else:
        await ctx.send("I'm not connected to any voice channel.")


bot.run(TOKEN)

# TODO: song queue
# TODO: pause/resume (hard?)
# TODO: accept urls (youtube and spotify)
