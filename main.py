# imports
import configparser
import platform
import time

import nextcord
import redis
from nextcord import Interaction, Locale
from nextcord.ext import commands
from googleapiclient import discovery

# load config & language
config = configparser.ConfigParser()
config.read('config.ini')
fallback_lang = configparser.ConfigParser()
fallback_lang.read('language.ini')
english = configparser.ConfigParser()
english.read('language/en_us.ini')
korean = configparser.ConfigParser()
korean.read('language/ko_kr.ini')
chinese = configparser.ConfigParser()
chinese.read('language/zh_cn.ini')

token = config['CREDENTIALS']['token']
owner_id = str(config['CREDENTIALS']['owner_id'])
prefix = config['SETTINGS']['prefix']
status = config['SETTINGS']['status']
status_message = config['SETTINGS']['status_message']
status_type = config['SETTINGS']['status_type']
host = config['REDIS']['host']
port = config['REDIS']['port']
password = config['REDIS']['password']
db = config['REDIS']['db']

# check config
error_count = 0

if len(prefix) > 1:
    print('Error: Prefix must be only one character.')
    error_count += 1

if status not in ['online', 'idle', 'dnd', 'invisible']:
    print('Error: Status must be one of online, idle, dnd, or invisible.')
    error_count += 1

if status_type not in ['playing', 'streaming', 'listening', 'watching']:
    print('Error: Status type must be one of playing, streaming, listening, or watching.')
    error_count += 1

if len(status_message) > 128:
    print('Error: Status message must be less than 128 characters.')
    error_count += 1

if error_count > 0:
    print('Please change the config file (config.ini) and try again.')
    print('Exiting in 5 seconds...')
    time.sleep(5)
    exit()

# check redis connection
try:
    print(f'Connecting to Redis... ({host}:{port} Database: {db})')
    r = redis.Redis(host=host, port=port, password=password, decode_responses=True, db=db)
    r.ping()
    print(f"Connected to redis.")
except:
    print('Error: Could not connect to Redis server.')
    print('Please change the config file (config.ini) and try again.')
    print('Exiting in 5 seconds...')
    time.sleep(5)
    exit()

try:
    google = discovery.build(
        "commentanalyzer",
        "v1alpha1",
        developerKey=config['GOOGLE']['api_key'],
        discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
        static_discovery=False,
    )
except:
    print('Error: Could not connect to Google API.')
    print('Please change the config file (config.ini) and try again.')
    print('Exiting in 5 seconds...')
    time.sleep(5)
    exit()

# discord setup
intents = nextcord.Intents.default()
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix=prefix, intents=intents)

def eveluate(expression):
    analyze_request = {'comment': {'text': expression}, 'requestedAttributes': {'TOXICITY': {}}}
    try:
        response = google.comments().analyze(body=analyze_request).execute()
        return round(100 * (response['attributeScores']['TOXICITY']['summaryScore']['value']), 2)
    except:
        return None

# Bot startup
@client.event
async def on_ready():
    # set status
    if status_type == 'playing':
        await client.change_presence(activity=nextcord.Game(name=status_message), status=status)
    elif status_type == 'streaming':
        await client.change_presence(activity=nextcord.Streaming(name=status_message, url='https://twich.tv'),
                                     status=status)
    elif status_type == 'listening':
        await client.change_presence(
            activity=nextcord.Activity(type=nextcord.ActivityType.listening, name=status_message), status=status)
    elif status_type == 'watching':
        await client.change_presence(
            activity=nextcord.Activity(type=nextcord.ActivityType.watching, name=status_message), status=status)
    # print startup message
    owner_name = await client.fetch_user(owner_id)
    print('======================================')
    print(f'Logged in as {client.user.name}#{client.user.discriminator} ({client.user.id})')
    print(f"Owner: {owner_name} ({owner_id})")
    print(f'Currenly running nextcord {nextcord.__version__} on python {platform.python_version()}')
    print('======================================')

@client.event
async def on_message(message):
    if message.author.bot:
        return
    evaluation = eveluate(message.content)
    if evaluation is not None:
        evalue = r.get(f'val:{message.author.id}')
        message_count = r.get(f'msg:{message.author.id}')
        if evalue is None:
            r.set(f'val:{message.author.id}', evaluation)
            r.set(f'msg:{message.author.id}', 1)
        else:
            r.set(f'val:{message.author.id}', (float(evalue) + evaluation))
            r.set(f'msg:{message.author.id}', int(message_count) + 1)

        if evaluation > 70:
            await message.delete()
            embed = nextcord.Embed(title='메세지 삭제 안내', description=f'메세지가 `{evaluation}%` 부정적이기에 삭제되었습니다.', color=nextcord.Color.red())
            embed.set_footer(text='이 메세지는 5초 후 삭제됩니다.')
            await message.channel.send(content=f'{message.author.mention}' ,embed=embed, delete_after=5)
        elif evaluation > 50:
            await message.add_reaction('🙁')

@client.slash_command(name='전적', description='특적 유저의 메세지 전적을 확인합니다.')
async def karma(interaction:Interaction,
                user: nextcord.User = nextcord.SlashOption(
                           description='전적을 확인할 유저를 선택해 주세요.',
                           required=False)):
    if user is None:
        user = interaction.user
    if user.bot:
        await interaction.response.send_message('봇의 전적은 확인할 수 없습니다.', ephemeral=True)
        return
    evalue = r.get(f'val:{user.id}')
    message_count = r.get(f'msg:{user.id}')
    if evalue is None:
        await interaction.response.send_message('해당 유저는 전적이 없습니다.', ephemeral=True)
        return
    else:
        evaluation = 100 - round(float(evalue) / int(message_count), 2)
        embed = nextcord.Embed(title=f'**{user.name}**님의 전적', colour=nextcord.Color.from_hsv(0.5 * (evaluation / 100), 0.7, 1))
        embed.add_field(name='봇에 기록된 메세지', value=f'**{message_count}**개', inline=True)
        embed.add_field(name='매너 점수', value=f'**{evaluation}**점', inline=True)
        await interaction.response.send_message(embed=embed)


@client.message_command(guild_ids=[1023440388352114749])
async def evaluate_message(interaction: nextcord.Interaction, message: nextcord.Message):
    evaluation = eveluate(message.content)

    if evaluation is None:
        await interaction.response.send_message(
            embed=nextcord.Embed(title='에러', description='메세지를 평가할 수 없었습니다.', color=nextcord.Color.red()),
            ephemeral=True)
    else:
        color = nextcord.Color.from_hsv(0.5 * (1 - evaluation / 100), 0.7, 1)
        await interaction.response.send_message(embed=nextcord.Embed(title='메세지 평가', description=f'이 메세지는 `{evaluation}%` 부정적입니다.', color=color), ephemeral=True)

client.run(token)