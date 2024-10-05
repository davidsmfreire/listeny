import os
from typing import List, NamedTuple

import discord
from discord.ext import commands
from dotenv import load_dotenv
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

youtube_dl_opts = {
    "format": "bestaudio/best",
    "noplaylist": "True",
    "quiet": True,
    "extract_flat": "True",
}

class Song(NamedTuple):
    title: str
    audio: discord.FFmpegPCMAudio


QUEUE_LIMIT = 30
music_queue: List[Song] = []


def get_queue_repr():
    return "\n".join([f"{i} - {m.title}" for i,m in enumerate(music_queue, 1)])


def get_play_next_callback(ctx):
    def play_next_callback(e):
        bot.loop.create_task(play_next_in_queue(ctx))
    return play_next_callback


async def add_to_queue(ctx, song):
    if len(music_queue) >= QUEUE_LIMIT:
        await ctx.send("Can't add more songs to queue, limit reached (30)")
    music_queue.append(song)
    await ctx.send(f"Adding to queue:\n{get_queue_repr()}")


async def play_next_in_queue(ctx):
    voice_client = ctx.voice_client
    if voice_client and len(music_queue) > 0:
        if voice_client.is_playing():
            voice_client.stop()
        song: Song = music_queue.pop(0)
        voice_client.play(song.audio, after=get_play_next_callback(ctx))
        queue_repr = ""
        if len(music_queue) > 0:
            queue_repr = "\nQueue:\n" + get_queue_repr()
        await ctx.send(f"Now playing: {song.title}.{queue_repr}")


@bot.command(name="queue", help="View queue")
async def view_queue(ctx):
    if len(music_queue) > 0:
        await ctx.send("Current queue:\n" + get_queue_repr())
    else:
        await ctx.send("Queue is empty")


# Command to join voice channel and play music
@bot.command(name="play", help="Play music from YouTube")
async def play_media(ctx, *, search_query: str):
    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel

        if not ctx.voice_client:
            await voice_channel.connect()

        voice_client = ctx.voice_client

        if "https://" in search_query:
            url = search_query
            title = None
        else:
            results = YoutubeSearch(search_query, max_results=1).to_dict()
            title = results[0]["title"]
            url = "https://youtube.com" + results[0]["url_suffix"]

        with YoutubeDL(youtube_dl_opts) as ydl:
            song_info = ydl.extract_info(url, download=False)
            if title is None:
                title = song_info["title"]

        audio_source = discord.FFmpegPCMAudio(song_info["url"])

        if not voice_client.is_playing():
            voice_client.play(
                audio_source,
                after=get_play_next_callback(ctx),
            )
            await ctx.send(f"Now playing: {title}")
        else:
            await add_to_queue(ctx, song=Song(title=title, audio=audio_source))
    else:
        await ctx.send("You need to be in a voice channel to play music!")


@bot.command(name="skip", help="Skip music from queue")
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        if len(music_queue) == 0:
            await ctx.send("No more songs in queue")
        else:
            await play_next_in_queue(ctx)


# Command to stop playing music and disconnect the bot
@bot.command(name="stop", help="Stop media and leave the voice channel")
async def stop_media(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

bot.run(TOKEN)


# TODO: pause/resume (hard?)
# TODO: accept spotify urls
