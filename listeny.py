import json
import os
import random
import time
from typing import List, NamedTuple, Optional
from bs4 import BeautifulSoup

import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
MUSIC_CHANNEL = int(os.environ["MUSIC_CHANNEL"])
ADMIN_CHANNEL = int(os.environ["ADMIN_CHANNEL"])

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

ffmpeg_before_options = "-reconnect 1 -reconnect_on_network_error 1"

class Song(NamedTuple):
    title: str
    url: str
    prank: bool


QUEUE_LIMIT = 30
music_queue: List[Song] = []
current_song: Optional[Song] = None
current_song_start_time: Optional[int] = None

def is_in_channel(*channel_ids):
    def predicate(ctx: commands.Context):
        return ctx.channel.id in channel_ids
    return commands.check(predicate)


def seconds_to_hms(seconds: int):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))

def get_queue_repr():
    return "\n".join([f"{i} - {m.title}" for i,m in enumerate(music_queue, 1)])


def get_play_next_callback(ctx: commands.Context):
    def play_next_callback(error):
        bot.loop.create_task(play_next_in_queue(ctx))
    return play_next_callback


async def add_to_queue(ctx: commands.Context, song: Song):
    if len(music_queue) >= QUEUE_LIMIT:
        await ctx.send("Can't add more songs to queue, limit reached (30)")
    music_queue.append(song)
    await ctx.send(f"Adding to queue:\n{get_queue_repr()}")

async def skip_queue(ctx: commands.Context, song: Song):
    music_queue.insert(0, song)
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    else:
        await play_next_in_queue(ctx)


async def play_next_in_queue(ctx: commands.Context):
    voice_client = ctx.voice_client
    if voice_client and len(music_queue) > 0:
        if voice_client.is_playing():
            voice_client.stop()
        song: Song = music_queue.pop(0)
        await play_song(ctx, song)
        queue_repr = ""
        if len(music_queue) > 0:
            queue_repr = "\nQueue:\n" + get_queue_repr()
        await ctx.send(f"Now playing: {song.title}.{queue_repr}")


def get_song_title_from_spotify_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve page. Status code: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    redirect = soup.find('script', {'id': 'urlSchemeConfig'})
    if redirect is not None:
        redirect_content: dict = json.loads(redirect.string)
        if url := redirect_content.get("redirectUrl"):
            return get_song_title_from_spotify_url(url)

    meta_title = soup.find('meta', property='og:title')
    meta_artist = soup.find('meta', property='og:description')

    if not meta_title or not meta_artist:
        raise Exception("Failed to find artist and title tags")

    song_title = meta_title['content']
    artist_name = meta_artist['content'].split(" · ")[0]
    return song_title, artist_name


@bot.command(name="queue", help="View queue")
async def view_queue(ctx: commands.Context):
    if len(music_queue) > 0:
        await ctx.send("Current queue:\n" + get_queue_repr())
    else:
        await ctx.send("Queue is empty")


def get_rick_roll_url():
    NEVER_GONNA_GIVE_YOU_UP = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with YoutubeDL(youtube_dl_opts) as ydl:
        song_info = ydl.extract_info(NEVER_GONNA_GIVE_YOU_UP, download=False)
    return song_info["url"]


async def play_song(ctx: commands.Context, song: Song, offset: int = 0):
    ctx.voice_client.stop()

    global current_song, current_song_start_time

    before_options = ffmpeg_before_options
    if offset > 0:
        before_options = ffmpeg_before_options + f"-ss {seconds_to_hms(offset)}"

    url = song.url
    if song.prank:
        before_options = ffmpeg_before_options
        url = get_rick_roll_url()

    audio = discord.FFmpegPCMAudio(url, before_options=before_options)
    ctx.voice_client.play(
        audio,
        after=get_play_next_callback(ctx),
    )
    current_song = song
    current_song_start_time = int(time.time())


async def _play_media(ctx: commands.Context, search_query: str, now: bool):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel to play music!")
        return

    voice_channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await voice_channel.connect()

    voice_client = ctx.voice_client

    if search_query.startswith(("https://www.youtube.com/watch?", "https://youtu.be/")):
        url = search_query
        title = None
    else:
        if search_query.startswith("https://open.spotify.com/"):
            try:
                title, artist = get_song_title_from_spotify_url(search_query)
            except Exception as e:
                await ctx.send(f"Failed to get song from spotify url: {str(e)}")
                return
            search_query = f"{title}, {artist}"
        results = YoutubeSearch(search_query, max_results=1).to_dict()
        title = results[0]["title"]
        url = "https://youtube.com" + results[0]["url_suffix"]

    with YoutubeDL(youtube_dl_opts) as ydl:
        song_info = ydl.extract_info(url, download=False)
        if title is None:
            title = song_info["title"]

    is_prank = (ctx.author.name == prank_victim) and (random.random() <= prank_probability)

    if is_prank:
        print(f"Pranking {prank_victim} :D")

    song = Song(title=title, url=song_info["url"], prank=is_prank)

    if not voice_client.is_playing():
        await play_song(ctx, song)
        await ctx.send(f"Now playing: {title}")
        return

    if now:
        await skip_queue(ctx, song)
        return

    await add_to_queue(ctx, song)



# Command to join voice channel and play music
@bot.command(name="play", help="Play music from YouTube")
@is_in_channel(MUSIC_CHANNEL, ADMIN_CHANNEL)
async def play_media(ctx: commands.Context, *, search_query: str):
    await _play_media(ctx, search_query, False)


@bot.command(name="playnow", help="Play music from YouTube without queue")
@is_in_channel(MUSIC_CHANNEL, ADMIN_CHANNEL)
async def play_media_now(ctx: commands.Context, *, search_query: str):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only administrators can use this command!")
        return
    await _play_media(ctx, search_query, True)


@bot.command(name="skip", help="Skip music from queue")
@is_in_channel(MUSIC_CHANNEL, ADMIN_CHANNEL)
async def skip(ctx: commands.Context):
    if ctx.voice_client:
        ctx.voice_client.stop()
        if len(music_queue) == 0:
            await ctx.send("No more songs in queue")
        else:
            await play_next_in_queue(ctx)


# Command to stop playing music and disconnect the bot
@bot.command(name="stop", help="Stop media and leave the voice channel")
@is_in_channel(MUSIC_CHANNEL, ADMIN_CHANNEL)
async def stop_media(ctx: commands.Context):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()


prank_victim = None
prank_probability = 0.0


@bot.command(name="setprank")
@is_in_channel(ADMIN_CHANNEL)
async def set_prank(ctx: commands.Context, *, search_query: str):
    if not ctx.author.guild_permissions.administrator:
        return
    
    victim, probability = search_query.split(" ")

    probability = float(probability)

    if probability < 0.0 or probability > 1.0:
        await ctx.send("Probability must be between 0.0 and 1.0")
        return

    global prank_victim, prank_probability
    prank_victim = victim
    prank_probability = probability
    
    await ctx.send(f"Set prank victim to '{prank_victim}' with probability '{prank_probability}'")


@bot.command(name="getprank")
@is_in_channel(ADMIN_CHANNEL)
async def get_prank(ctx: commands.Context):
    await ctx.send(f"Current prank victim is '{prank_victim}' with probability '{prank_probability}'")


@bot.command(name="clearprank")
@is_in_channel(ADMIN_CHANNEL)
async def clear_prank(ctx: commands.Context):
    global prank_victim, prank_probability
    prank_victim = None
    prank_probability = 0.0
    await ctx.send(f"Cleared prank victim")


bot.run(TOKEN)


# TODO: pause/resume (hard?)
