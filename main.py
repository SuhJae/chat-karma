# imports
import configparser
import platform
import time

import nextcord
import redis
from nextcord import Interaction, Locale
from nextcord.ext import commands
from googleapiclient import discovery

from grading import get_grade

# load config & language
config = configparser.ConfigParser()
config.read('config.ini')
fallback_lang = configparser.ConfigParser()
fallback_lang.read('language/fallback.ini')
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
    print(f'Connected to redis.')
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

def lang_check(locale):
    # if locale == "en-US":
    #     return english
    # elif locale == "ko":
    #     return korean
    # elif locale == "zh-CN":
    #     return chinese
    # else:
    return fallback_lang

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

        delete_percentage = r.get(f'del:{message.guild.id}')
        if delete_percentage is None:
            delete_percentage = 70
        else:
            delete_percentage = int(delete_percentage)

        if delete_percentage > 0:
            if evaluation > delete_percentage:
                await message.delete()
                embed = nextcord.Embed(title='메세지 삭제 안내', description=f'메세지가 `{evaluation}%` 부정적이기에 삭제되었습니다.',
                                       color=nextcord.Color.red())
                embed.set_footer(text='이 메세지는 5초 후 삭제됩니다.')
                await message.channel.send(content=f'{message.author.mention}', embed=embed, delete_after=5)

                log_channel = r.get(f'log:{message.guild.id}')
                if log_channel != None:
                    embed = nextcord.Embed(title='', description=message.content, colour=nextcord.Color.red())
                    embed.set_author(name='메세지 삭제', icon_url=message.author.avatar)
                    embed.add_field(name='유저', value=message.author.mention)
                    embed.add_field(name='채널', value=message.channel.mention)
                    embed.add_field(name='부정도', value=f'`{evaluation}%`')
                    embed.set_footer(text=f'유저 ID: {message.author.id} | 메세지 ID: {message.id}')
                    await client.get_channel(int(log_channel)).send(embed=embed)
                return
        reaction_percentage = r.get(f'rea:{message.guild.id}')
        if reaction_percentage is None:
            reaction_percentage = 50
        else:
            reaction_percentage = int(reaction_percentage)
            if reaction_percentage > 0:
                if evaluation > reaction_percentage:
                    await message.add_reaction('💔')


@client.slash_command(name=fallback_lang['KARMA']['name'], description=fallback_lang['KARMA']['description'])
async def karma(interaction: Interaction,
                user: nextcord.User = nextcord.SlashOption(
                    name=fallback_lang['KARMA']['user.name'],
                    description=fallback_lang['KARMA']['user.description'],
                    required=False)):
    if user is None:
        user = interaction.user
    lang = lang_check(interaction.locale)

    if user.bot:
        await interaction.response.send_message(embed=nextcord.Embed(title=lang['KARMA']['error.title'], description=lang['KARMA']['error.bot'], colour=nextcord.Color.red()), ephemeral=True)
        return
    evalue = r.get(f'val:{user.id}')
    message_count = r.get(f'msg:{user.id}')
    if evalue is None:
        await interaction.response.send_message(embed=nextcord.Embed(title=lang['KARMA']['error.title'], description=lang['KARMA']['error.nothing'], colour=nextcord.Color.red()), ephemeral=True)
        return
    else:
        evaluation = 100 - round(float(evalue) / int(message_count), 2)
        embed = nextcord.Embed(title=f'', colour=get_grade(evaluation).color())
        embed.add_field(name=lang['KARMA']['embed.recorded'], value=lang['KARMA']['embed.recorded.description'].format(message_count), inline=True)
        embed.add_field(name=lang['KARMA']['embed.manner'], value=lang['KARMA']['embed.manner.description'].format(evaluation), inline=True)
        embed.set_author(name=lang['KARMA']['embed.title'].format(user.display_name), icon_url=user.avatar)

        img = nextcord.File(f'image/{get_grade(evaluation).letter_grade()}.png', filename='image.png')
        embed.set_thumbnail(url='attachment://image.png')

        await interaction.response.send_message(embed=embed, file=img)


@client.slash_command(name=fallback_lang['DASHBOARD']['name'], description=fallback_lang['DASHBOARD']['description'], default_member_permissions=8)
async def dashboard(interaction: Interaction):
    lang = lang_check(interaction.locale)

    delete_percentage = r.get(f'del:{interaction.guild.id}')
    if delete_percentage is None:
        delete_percentage = 70
        delete_percentage = lang['DASHBOARD']['text.negative'].format(delete_percentage)
    elif delete_percentage == '0':
        delete_percentage = lang['DASHBOARD']['text.disabled']
    else:
        delete_percentage = lang['DASHBOARD']['text.negative'].format(delete_percentage)

    reaction_percentage = r.get(f'rea:{interaction.guild.id}')
    if reaction_percentage is None:
        reaction_percentage = 50
        reaction_percentage = lang['DASHBOARD']['text.negative'].format(reaction_percentage)
    elif reaction_percentage == '0':
        reaction_percentage = lang['DASHBOARD']['text.disabled']
    else:
        reaction_percentage = lang['DASHBOARD']['text.negative'].format(reaction_percentage)

    logging_channel = r.get(f'log:{interaction.guild.id}')
    if logging_channel is None:
        logging_channel = lang['DASHBOARD']['text.disabled']
    else:
        logging_channel = f'<#{logging_channel}>'

    embed = nextcord.Embed(title=lang['DASHBOARD']['embed.title'].format(interaction.guild.name), description=lang['DASHBOARD']['embed.description'], colour=nextcord.Color.green())
    embed.add_field(name=lang['DASHBOARD']['embed.delete'], value=delete_percentage, inline=True)
    embed.add_field(name=lang['DASHBOARD']['embed.reaction'], value=reaction_percentage, inline=True)
    embed.add_field(name=lang['DASHBOARD']['embed.log'], value=f'{logging_channel}', inline=True)
    embed.set_footer(text=lang['DASHBOARD']['embed.footer'])

    selections = [
        nextcord.SelectOption(label=lang['DASHBOARD']['dropdown.delete'], value='del', emoji='🧹'),
        nextcord.SelectOption(label=lang['DASHBOARD']['dropdown.reaction'], value='rea', emoji='💔'),
        nextcord.SelectOption(label=lang['DASHBOARD']['dropdown.log'], value='log', emoji='📝')
    ]
    view = DropdownMenu(selections, lang['DASHBOARD']['dropdown.placeholder'])

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@client.message_command(name='메세지 평가')
async def evaluate_message(interaction: nextcord.Interaction, message: nextcord.Message):
    evaluation = eveluate(message.content)

    if evaluation is None:
        await interaction.response.send_message(
            embed=nextcord.Embed(title='에러', description='메세지를 평가할 수 없었습니다.', color=nextcord.Color.red()),
            ephemeral=True)
    else:
        color = nextcord.Color.from_hsv(0.5 * (1 - evaluation / 100), 0.7, 1)
        await interaction.response.send_message(
            embed=nextcord.Embed(title='메세지 평가', description=f'이 메세지는 `{evaluation}%` 부정적입니다.', color=color),
            ephemeral=True)


# Class to handle the dropdown
class Dropdown(nextcord.ui.Select):
    def __init__(self, options, placeholder):
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == 'del':
            modal = Popup('삭제 기준 변경', '0을 입력하면 메세지 삭제를 비활성화 합니다.', '0~100 사이의 숫자를 입력하세요.', 'del',)
            await interaction.response.send_modal(modal)
        elif self.values[0] == 'rea':
            modal = Popup('반응 기준 변경', '0을 입력하면 메세지 반응을 비활성화 합니다.', '0~100 사이의 숫자를 입력하세요.', 'rea',)
            await interaction.response.send_modal(modal)
        elif self.values[0] == 'log':
            selections = []
            # get channel that bot can send message
            for channel in interaction.guild.channels:
                if channel.permissions_for(interaction.guild.me).send_messages and channel.type == nextcord.ChannelType.text:
                    selections.append(nextcord.SelectOption(label="# " + channel.name, description=str(channel.id), emoji='📝', value=f'set_log:{channel.id}'))

            if len(selections) == 0:
                await interaction.response.send_message(embed=nextcord.Embed(title='오류', description=f'이 봇이 메세지를 보낼 수 있는 채널이 없습니다.', colour=nextcord.Color.red()), ephemeral=True)
            else:
                view = DropdownMenu(selections, '로그 채널을 선택해 주세요.')
                embed = nextcord.Embed(title='로그 채널 변경', description='밑에 있는 드랍다운을 사용하여 로그 채널을 변경할 수 있습니다.', colour=nextcord.Color.green())
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        elif self.values[0].startswith('set_log:'):
            channel_id = self.values[0].split(':')[1]
            r.set(f'log:{interaction.guild.id}', channel_id)
            await interaction.response.send_message(embed=nextcord.Embed(title='완료', description=f'로그 채널이 <#{channel_id}>로 변경되었습니다.', colour=nextcord.Color.green()), ephemeral=True)


class DropdownMenu(nextcord.ui.View):
    def __init__(self, options, placeholder):
        super().__init__()
        self.add_item(Dropdown(options, placeholder))


class Popup(nextcord.ui.Modal):
    def __init__(self, title, label, placeholder, id):
        super().__init__(
            title=title,
            timeout=None,
        )

        self.name = nextcord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            max_length=3,
            custom_id=id,
        )
        self.add_item(self.name)

    async def callback(self, interaction: nextcord.Interaction) -> None:
        if interaction.data['components'][0]['components'][0]['custom_id'] == 'del':
            if self.name.value.isdigit() and 0 <= int(self.name.value) <= 100:
                await interaction.response.send_message(embed=nextcord.Embed(title='설정 완료', description=f'성공적으로 메세지 삭제 기준을 **{self.name.value}%**부정적으로 정했습니다.', colour=nextcord.Color.green()), ephemeral=True)
                r.set(f'del:{interaction.guild.id}', self.name.value)
            else:
                await interaction.response.send_message(embed=nextcord.Embed(title='오류', description=f'잘못된 값(`{self.name.value}`)을 입력하셨습니다. 0~100 사이의 숫자를 입력해 주세요.', colour=nextcord.Color.red()), ephemeral=True)
        elif interaction.data['components'][0]['components'][0]['custom_id'] == 'rea':
            if self.name.value.isdigit() and 0 <= int(self.name.value) <= 100:
                await interaction.response.send_message(embed=nextcord.Embed(title='설정 완료', description=f'성공적으로 메세지 반응 기준을 **{self.name.value}%**부정적으로 정했습니다.', colour=nextcord.Color.green()), ephemeral=True)
                r.set(f'rea:{interaction.guild.id}', self.name.value)
            else:
                await interaction.response.send_message(embed=nextcord.Embed(title='오류', description=f'잘못된 값(`{self.name.value}`)을 입력하셨습니다. 0~100 사이의 숫자를 입력해 주세요.', colour=nextcord.Color.red()), ephemeral=True)


client.run(token)