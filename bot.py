# bot.py
import os

import discord
from dotenv import load_dotenv
from discord.ext import commands
import yt_dlp

import asyncio
import re
from datetime import timedelta

import random

import requests

intents = discord.Intents.all()
ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0'
FFMPEG_OPTIONS = {'options' : '-vn'}
YDL_OPTIONS = {'format' : 'bestaudio', 'noplaylist' : True, 'verbose' : True, 'user_agent' : ua}

load_dotenv(".env")
TOKEN = os.environ.get('DISCORD_TOKEN')

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ydl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


class BladeBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command('help')


    
    def parse_time(self, time_str: str) -> timedelta:
        """Converts a time string like '5d', '1h', '30m', '10s' into a timedelta object."""
        
        time_units = {
            'd': 'days',
            'h': 'hours',
            'm': 'minutes',
            's': 'seconds'
        }

        match = re.match(r'(\d+)([dhms])$', time_str)
        
        if match:
            value, unit = match.groups()
            value = int(value)
            
            return timedelta(**{time_units[unit]: value})
        
        raise ValueError("Invalid time format. Use '5d', '1h', '30m', or '10s'.")


    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, query):
        """Plays a file from the local filesystem"""

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {query}')

    @commands.command()
    async def yt(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')
        
    # @commands.command()
    # async def play(self, ctx, *, search):
    #     voice_channel = ctx.author.voice.channel if ctx.author.voice else None
    #     if search == "":
    #         return await ctx.send("Please enter a song name.")
    #     if not voice_channel :
    #         return await ctx.send("Please join a voice channel.")
    #     if not ctx.voice_client:
    #         await voice_channel.connect()

    #     async with ctx.typing():
    #         with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
    #             info = ydl.extract_info(f"ytsearch:{search}", download=False)
    #             if 'entries' in info:
    #                 info = info['entries'][0]
    #             url = info['url']
    #             title = info['title']
    #             self.queue.append((url, title))
    #             await ctx.send(f'{title} has been added to queue.')

    #     if not ctx.voice_client.is_playing():
    #         await self.play_next(ctx)

    @commands.command()
    async def play_next(self, ctx):
        if self.queue:
            url, title = self.queue.pop(0)
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda _:self.client.loop.create_task(self.play_next(ctx)))
            await ctx.send(f'Now playing {title}')
        elif not ctx.voice_client.is_playing():
            await ctx.send("Queue is empty.")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped song.")

    # @commands.command(pass_context=True)
    # async def yt(self, ctx, url):

    #     author = ctx.message.author
    #     voice_channel = author.voice_channel
    #     vc = await client.join_voice_channel(voice_channel)

    #     player = await vc.create_ytdl_player(url)
    #     player.start()

    @commands.command()
    async def read(self, ctx, *, text):
        async with ctx.typing():
            return await ctx.send(str(text))
        
    # *********************************************** UTILITY/MOD COMMANDS ***********************************************
        
    @commands.command()
    async def userinfo(self, ctx, *, username: discord.Member=None):
        if username is None:
            username = ctx.message.author
        
        async with ctx.typing():
            embed = discord.Embed(title=f'Info on {username.display_name}')
            embed.set_thumbnail(url=username.display_avatar.url)
            # user = await self.bot.fetch_user(username.id)
            # banner_url = user.banner.url
            # embed.set_image(url=banner_url)
            embed.add_field(name="Display Name", value=username.display_name, inline=False)
            embed.add_field(name="User Name", value=username, inline=False)
            embed.add_field(name="User ID", value=username.id, inline=False)
            embed.add_field(name="Account Creation Date", value=f'<t:{int(username.created_at.timestamp())}:F>\nIt was <t:{int(username.created_at.timestamp())}:R>!', inline=False)
            embed.add_field(name="Server Join Date", value=f'<t:{int(username.joined_at.timestamp())}:F>\nIt was <t:{int(username.joined_at.timestamp())}:R>!', inline=False)
            embed.add_field(name="Discriminator", value=username.discriminator, inline=False)
            embed.add_field(name="Accent Colour", value=username.accent_colour, inline=False)
            embed.add_field(name="Main Account Colour", value=username.colour, inline=False)
            eachRole = ""
            er = username.roles
            for role in er:
                eachRole += f'<@&{role.id}>\n'
            allroles = str(eachRole).replace("@@everyone", "")
            embed.add_field(name="Roles", value=allroles, inline=False)
            return await ctx.send(embed=embed)
        
    
    @commands.command()
    async def avatar(self, ctx, *, username: discord.Member=None):
        if username is None:
            username = ctx.message.author
        
        async with ctx.typing():
            return await ctx.send(f'{username.display_avatar}')
        
    @commands.command()
    async def roles(self, ctx, *, username: discord.Member=None):
        if username is None:
            username = ctx.message.author

        async with ctx.typing():
            embed = discord.Embed(title=f'Roles of {username.display_name}')
            eachRole = ""
            er = username.roles
            for role in er:
                eachRole += f'<@&{role.id}>\n'
            allroles = str(eachRole).replace("@@everyone", "")
            embed.add_field(name="Roles", value=allroles, inline=False)
            return await ctx.send(embed=embed)
        
    @commands.command()
    async def banner(self, ctx, *, username: discord.Member = None):
        if username is None:
            username = ctx.message.author


        if username.banner != None:
            async with ctx.typing():
                await ctx.send(f" {username.banner.url}")
        else:
            await ctx.send(f"{username.display_name} does not have a banner set.")
        
    @commands.command()
    async def ping(self, ctx):
        async with ctx.typing():
            return await ctx.send(f'My ping is around {round(client.latency * 1000)}ms.')
        
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 1):

        if ctx.author.guild_permissions.administrator:
            async with ctx.typing():
                if amount < 1:
                    await ctx.send(f'lil bro thought he was funny :skull:')
                else:
                    deleted = await ctx.channel.purge(limit=int(amount + 1))
                    await ctx.send(f'Deleted {int(len(deleted) - 1)} message(s).')
        else:
            async with ctx.typing():
                return await ctx.send("You don't have admin rights to run this command!")
        
    @commands.command()
    async def kick(self, ctx, user: discord.Member = None, reason: str = ""):
        if ctx.author.guild_permissions.moderate_members:
            async with ctx.typing():
                if user == None:
                    return await ctx.send("Add a user to kick.")
                else:
                    await user.kick(reason=reason)
                    if reason == "":
                        return await ctx.send(f"Kicked {user}.")
                    else:
                        return await ctx.send(f"Kicked {user} for {reason}.")
        else:
            async with ctx.typing():
                return await ctx.send("You don't have moderation rights to run this command!")
            
    # @commands.command()
    # async def timeout(self, ctx, user: discord.Member = None, duration: str = "", reason: str = ""):
    #     if ctx.author.guild_permissions.moderate_members:
    #         async with ctx.typing():
    #             if user == None:
    #                 return await ctx.send("Add a user to time out.")
    #             else:
    #                 until = 0.0
    #                 time_units = {
    #                     'd': 'days',
    #                     'h': 'hours',
    #                     'm': 'minutes',
    #                     's': 'seconds'
    #                 }

    #                 match = re.match(r'(\d+)([dhms])$', duration)
                    
    #                 if match:
    #                     value, unit = match.groups()
    #                     value = int(value)
                        
    #                     until = discord.utils.utcnow() + timedelta(**{time_units[unit]: value})
    #                 else:
    #                     raise ValueError("Invalid time format. Use something like '5d', '1h', '30m', or '10s'.")
                    
    #                 await user.timeout(until=until, reason=reason)
    #                 if reason == "":
    #                     return await ctx.send(f"Timed out {user}.")
    #                 else:
    #                     return await ctx.send(f"Timed out {user} for {reason}.")
    #     else:
    #         async with ctx.typing():
    #             return await ctx.send("You don't have moderation rights to run this command!")
    
    @commands.command()
    async def warn(self, ctx, user: discord.Member = None, duration: str = "", reason: str = ""):
        if user == None:
            return await ctx.send("Add a user to warn.")
        else:
            if duration == "":
                return await ctx.send("Add a duration to warn the user.")
            else:
                if duration.lower().endswith("s") or duration.lower().endswith("m") or duration.lower().endswith("h") or duration.lower().endswith("d") or duration.lower().endswith("w") or duration.lower().endswith("mo") or duration.lower().endswith("mon") or duration.lower().endswith("y") or duration.lower().endswith("yr"):
                    if reason == "":
                        await user.send(f"You have been warned in {user.guild.name} by <@{ctx.message.author.id}> for {duration}.")
                        await ctx.send(f"Warned {user} for {duration}.")
                    else:
                        await user.send(f"You have been warned in {user.guild.name} by <@{ctx.message.author}> for {duration}.\nReason: {reason}")
                        await ctx.send(f"Warned {user} for {duration} due to {reason}.")
                else:
                    return await ctx.send(f"{duration} is invalid as it must contain a number and an identifier at the end.\nExample: 5d for 5 days.")
                
            
            
    @commands.command()
    async def ban(self, ctx, user: discord.Member = None, reason: str = ""):
        if ctx.author.guild_permissions.moderate_members or ctx.author.guild_permissions.ban_members:
            async with ctx.typing():
                if user == None:
                    return await ctx.send("Add a user to ban.")
                else:
                    await user.ban(reason=reason)
                    if reason == "":
                        return await ctx.send(f"Banned {user}.")
                    else:
                        return await ctx.send(f"Banned {user} for {reason}.")
        else:
            async with ctx.typing():
                return await ctx.send("You don't have moderation rights to run this command!")
            
    # @commands.command()
    # async def unban(self, ctx, user: discord.User = None, reason: str = ""):
    #     if ctx.author.guild_permissions.moderate_members or ctx.author.guild_permissions.ban_members:
    #         async with ctx.typing():
    #             if user == None:
    #                 return await ctx.send("Add a user to unban.")
    #             else:

    #                 bans = await ctx.guild.bans()
    #                 for ban_entry in bans:
    #                     if ban_entry.user.id == user.id:
    #                         await ctx.guild.unban(ban_entry.user, reason=reason)
    #                         if reason != "":
    #                             await ctx.send(f"Unbanned {user.mention} for {reason}.")
    #                         else:
    #                             await ctx.send(f"Unbanned {user.mention}.")
    #                         return

    #                     await ctx.send("This user is not banned.")
    #     else:
    #         async with ctx.typing():
    #             return await ctx.send("You don't have moderation rights to run this command!")

    @commands.command()
    async def unban(self, ctx, user: discord.User = None, *, reason: str = ""):
        if ctx.author.guild_permissions.moderate_members or ctx.author.guild_permissions.ban_members:
            async with ctx.typing():
                if user is None:
                    return await ctx.send("Add a user to unban.")

                bans = await ctx.guild.bans()

                for ban_entry in bans:
                    if ban_entry.user.id == user.id:
                        await ctx.guild.unban(ban_entry.user, reason=reason)
                        await ctx.send(f"Unbanned {user.mention}\nReason:{reason}")
                        return  # Exit after unbanning

                # This line runs **after** the loop only if no match was found
                await ctx.send("This user is not banned.")
        else:
            await ctx.send("You don't have moderation rights to run this command!")

    # ********************************** FUN/ENTERTAINMENT COMMANDS **********************************

    @commands.command()
    async def magic8ball(self, ctx, *, question: str = ""):
        responses = ['It is certain.', 'It is decidedly so.', 'Without a doubt.', 'Yes definitely.', 'You may rely on it.', 'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Yes.', 'Signs point to yes.', 'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.', 'Cannot predict now.', 'Concentrate and ask again.', "Don't count on it.", 'My reply is no.', 'My sources say no.', 'Outlook not so good.', 'Very doubtful.']
        async with ctx.typing():
            if question == "":
                return await ctx.send("You should ask a question.")
            else:
                return await ctx.send(f":8ball:: {random.choice(responses)}")
            
    @commands.command()
    async def quote(self, ctx):
        url = "https://zenquotes.io/api/random"
        response = requests.get(url)
        async with ctx.typing():
            if response.status_code == 200:
                data = response.json()
                return await ctx.send(f'"{data[0]["q"]}" — {data[0]["a"]}')
            else:
                return await ctx.send("Couldn't fetch a quote for some reason, what else can I do for you? ¯\\_(ツ)_/¯")

    @commands.command()
    async def meme(self, ctx):
        url = "https://meme-api.com/gimme"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            return await ctx.send(f'{data['url']}')
        else:
            return await ctx.send("Buddy you are one, what else are you trying to get from this command huh?")
        
    # NICHE

    @commands.command()
    async def define(self, ctx, word: str = ""):
        async with ctx.typing():
            if word == "":
                return await ctx.send("Add a word to define.")
            else:
                url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    meaning = data[0]["meanings"][0]
                    phonetic = data[0]["phonetic"]
                    definition = meaning["definitions"][0]["definition"]
                    part_of_speech = meaning["partOfSpeech"]
                    if word.lower() == "anything":
                        embed = discord.Embed(title="Anything?????")
                        embed.add_field(name="Definition", value=definition, inline=False)
                        embed.add_field(name="Part of Speech", value=part_of_speech, inline=False)
                        embed.add_field(name="Phonetic", value=phonetic, inline=False)
                    elif word.lower() == "nothing":
                        embed = discord.Embed(title=" ")
                        embed.add_field(name="Definition", value=definition, inline=False)
                        embed.add_field(name="Part of Speech", value=part_of_speech, inline=False)
                        embed.add_field(name="Phonetic", value=phonetic, inline=False)
                    elif word.lower() == "everything":
                        embed = discord.Embed(title="EVERYTHING!!!!!")
                        embed.add_field(name="Definition", value=definition, inline=False)
                        embed.add_field(name="Part of Speech", value=part_of_speech, inline=False)
                        embed.add_field(name="Phonetic", value=phonetic, inline=False)
                    elif word.lower() == "everyone":
                        embed = discord.Embed(title="@everyone")
                        embed.add_field(name="Definition", value=definition, inline=False)
                        embed.add_field(name="Part of Speech", value=part_of_speech, inline=False)
                        embed.add_field(name="Phonetic", value=phonetic, inline=False)
                        embed.add_field(name="@everyone", value="@everyone")
                    else:
                        embed = discord.Embed(title=str(word.capitalize()))
                        embed.add_field(name="Definition", value=definition, inline=False)
                        embed.add_field(name="Part of Speech", value=part_of_speech, inline=False)
                        embed.add_field(name="Phonetic", value=phonetic, inline=False)
                    
                    return await ctx.send(embed=embed)
                else:
                    return await ctx.send("Failed to find that word, we didn't want gibberish, so what did you expect?")

    # ********************************** THE LAST COMMAND OF THEM ALL **********************************

    @commands.command()
    async def help(self, ctx, *, command: None):
        if command is None:
            embed = discord.Embed(title="Help")
            embed.add_field(name=f"{prefix}play (DOES NOT WORK ANYMORE)", value=f"Plays music from YT.\n-# Usage: {prefix}play <song name>", inline=False)
            embed.add_field(name=f"{prefix}help", value=f"Provides a list of commands.\n-# Usage: {prefix}help OR {prefix}help <specific command> w/o prefix", inline=False)
            return await ctx.send(embed=embed)
        else:
            return await ctx.send("custom") # DEBUGGING PURPOSES ONLY !!!

prefix = "bb:"
client = commands.Bot(command_prefix=prefix, intents=intents)

async def main():
    await client.add_cog(BladeBot(client))
    await client.start(TOKEN)

asyncio.run(main())

# @client.event
# async def on_ready():
#     print(f'{client.user} has connected to Discord!')

# @client.event
# async def on_message(message):
#     username = str(message.author).split("#")[0]
#     channel = str(message.channel.name)
#     user_message = str(message.content).lower()

#     print(f'Message {user_message} by {username} on {channel}')

#     if message.author == client.user:
#         return

#     if user_message.startswith(prefix):
#         user_command = user_message.replace(prefix, "").lower()
#         print(user_command)
#         if user_command.startswith("play"):
#             if user_command == "play":
#                 await message.channel.send('Please enter the name of the song you want to listen.')
#             else:
#                 if discord.Interaction.user.voice:
#                     await message.channel.send('Ok')
#                 else:
#                     await message.channel.send('Please join a voice channel.')
#         if user_command.startswith("help"):
#             bb_command = user_command.replace("help ", "").lower()
#             if bb_command.startswith("play"):
#                 embed=discord.Embed(title="Help")
#                 embed.add_field(name=f"{prefix}play", value=f"Plays music from YT.\n-# Usage: {prefix}play <song name>", inline=False)
#                 await message.channel.send(embed=embed)
#             elif bb_command != "help" and bb_command.startswith("help"):
#                 embed=discord.Embed(title="Help")
#                 embed.add_field(name=f"{prefix}help", value=f"Provides a list of commands.\n-# Usage: {prefix}help OR {prefix}help <specific command> w/o prefix", inline=False)
#                 await message.channel.send(embed=embed)
#             elif bb_command.startswith("help") and bb_command == "help":
#                 embed=discord.Embed(title="Help",description="Current list of commands.")
#                 
#                 await message.channel.send(embed=embed)

client.run(TOKEN)