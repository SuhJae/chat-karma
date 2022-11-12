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
        toxicity = round(100 * (response['attributeScores']['TOXICITY']['summaryScore']['value']), 2)
        language = response['languages']
        return {'toxicity': toxicity, 'language': language}
    except:
        return None


def lang_check(locale):
    if locale in ["en-US", "en"]:
        return english
    elif locale == "ko":
        return korean
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
    response = eveluate(message.content)
    evaluation = response['toxicity']
    lang = lang_check(response['language'][0])
    if evaluation is not None:
        evalue = r.get(f'val:{message.author.id}')
        message_count = r.get(f'msg:{message.author.id}')
        if evalue is None:
            total_evaluation = evaluation
            total_message = 1
            r.set(f'val:{message.author.id}', total_evaluation)
            r.set(f'msg:{message.author.id}', total_message)
        else:
            total_evaluation = float(evalue) + evaluation
            total_message = int(message_count) + 1
            r.set(f'val:{message.author.id}', (float(evalue) + evaluation))
            r.set(f'msg:{message.author.id}', int(message_count) + 1)

        manner_score = 100 - (total_evaluation / total_message)
        r.zadd('manner', {message.author.id: manner_score})

        delete_percentage = r.get(f'del:{message.guild.id}')
        if delete_percentage is None:
            delete_percentage = 70
        else:
            delete_percentage = int(delete_percentage)

        if delete_percentage > 0:
            if evaluation > delete_percentage:
                await message.delete()
                embed = nextcord.Embed(title='', description=lang['DELETION']['description'].format(evaluation),
                                       color=nextcord.Color.red())
                embed.set_author(name=lang['DELETION']['title'], icon_url=message.author.avatar)
                embed.set_footer(text=lang['DELETION']['footer'])
                await message.channel.send(content=f'{message.author.mention}', embed=embed, delete_after=5)

                log_channel = r.get(f'log:{message.guild.id}')
                if log_channel != None:
                    embed = nextcord.Embed(title='', description=message.content, colour=nextcord.Color.red())
                    embed.set_author(name=lang['LOG']['title'], icon_url=message.author.avatar)
                    embed.add_field(name=lang['LOG']['user'], value=message.author.mention)
                    embed.add_field(name=lang['LOG']['channel'], value=message.channel.mention)
                    embed.add_field(name=lang['LOG']['negativity'], value=f'`{evaluation}%`')
                    embed.set_footer(text=lang['LOG']['footer'].format(message.author.id, message.id))
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


@client.slash_command(name=fallback_lang['KARMA']['name'], description=fallback_lang['KARMA']['description'], dm_permission=True)
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
        ranking = r.zrevrank('manner', interaction.user.id) + 1
        total_users = r.zcard('manner')
        top_percent = round((ranking / total_users) * 100, 2)

        evaluation = 100 - round(float(evalue) / int(message_count), 2)
        embed = nextcord.Embed(title=f'', colour=get_grade(evaluation).color())
        embed.add_field(name=lang['KARMA']['embed.manner'], value=lang['KARMA']['embed.manner.description'].format(evaluation), inline=True)
        embed.add_field(name=lang['KARMA']['embed.rank'], value=lang['KARMA']['embed.rank.description'].format(top_percent, ranking, total_users), inline=True)
        embed.set_author(name=lang['KARMA']['embed.title'].format(user.display_name), icon_url=user.avatar)

        embed.set_footer(text=lang['KARMA']['embed.footer'].format(message_count))

        img = nextcord.File(f'image/{get_grade(evaluation).letter_grade()}.png', filename='image.png')
        embed.set_thumbnail(url='attachment://image.png')

        await interaction.response.send_message(embed=embed, file=img)

@client.slash_command(name=fallback_lang['PING']['name'], description=fallback_lang['PING']['description'],
                      dm_permission=True)
async def ping(interaction: Interaction):
    templang = lang_check(interaction.locale)
    embed = nextcord.Embed(title=templang['PING']['embed.title'],
                           description=templang['PING']['embed.description'].format(round(client.latency * 1000)),
                           color=nextcord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.slash_command(name=fallback_lang['DASHBOARD']['name'], description=fallback_lang['DASHBOARD']['description'], default_member_permissions=8, dm_permission=False)
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


@client.slash_command(name=fallback_lang['HELP']['name'], description=fallback_lang['HELP']['description'], dm_permission=True)
async def help(interaction: Interaction):
    lang = lang_check(interaction.locale)

    embed = nextcord.Embed(title=lang['HELP']['embed.title'], description=lang['HELP']['embed.description'], colour=nextcord.Color.green())
    embed.add_field(name=f"**· /{lang['KARMA']['name']}**", value=f"{lang['KARMA']['description']}", inline=False)
    embed.add_field(name=f"**· /{lang['DASHBOARD']['name']}**", value=f"{lang['DASHBOARD']['description']}", inline=False)
    embed.add_field(name=f"**· /{lang['PING']['name']}**", value=f"{lang['PING']['description']}", inline=False)
    embed.add_field(name=f"**· /{lang['HELP']['name']}**", value=f"{lang['HELP']['description']}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.message_command(name=fallback_lang['EVALUATE']['name'])
async def evaluate_message(interaction: nextcord.Interaction, message: nextcord.Message):
    evaluation = eveluate(message.content)['toxicity']
    lang = lang_check(interaction.locale)

    if evaluation is None:
        await interaction.response.send_message(
            embed=nextcord.Embed(title=lang['EVALUATE']['error'], description=lang['EVALUATE']['error.description'], color=nextcord.Color.red()),
            ephemeral=True)
    else:
        color = nextcord.Color.from_hsv(0.5 * (1 - evaluation / 100), 0.7, 1)
        embed = nextcord.Embed(title='', description=lang['EVALUATE']['description'].format(evaluation), color=color)
        embed.set_author(name=lang['EVALUATE']['title'].format(message.author.display_name), icon_url=message.author.avatar)
        embed.set_footer(text=lang['EVALUATE']['footer'])
        await interaction.response.send_message(embed=embed ,ephemeral=True)


# Class to handle the dropdown
class Dropdown(nextcord.ui.Select):
    def __init__(self, options, placeholder):
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: Interaction):
        lang = lang_check(interaction.locale)
        if self.values[0] == 'del':
            modal = Popup(lang['DROPDOWN']['delete.title'], lang['DROPDOWN']['delete.label'], lang['DROPDOWN']['delete.placeholder'], 'del',)
            await interaction.response.send_modal(modal)
        elif self.values[0] == 'rea':
            modal = Popup(lang['DROPDOWN']['reaction.title'], lang['DROPDOWN']['reaction.label'], lang['DROPDOWN']['reaction.placeholder'], 'rea',)
            await interaction.response.send_modal(modal)
        elif self.values[0] == 'log':
            selections = []
            # get channel that bot can send message
            for channel in interaction.guild.channels:
                if channel.permissions_for(interaction.guild.me).send_messages and channel.type == nextcord.ChannelType.text:
                    selections.append(nextcord.SelectOption(label="# " + channel.name, description=str(channel.id), emoji='📝', value=f'set_log:{channel.id}'))

            if len(selections) == 0:
                await interaction.response.send_message(embed=nextcord.Embed(title=lang['DROPDOWN']['error'], description=lang['DROPDOWN']['log.no_channel'], colour=nextcord.Color.red()), ephemeral=True)
            else:
                view = DropdownMenu(selections, lang['DROPDOWN']['log.dropdown.placeholder'])
                embed = nextcord.Embed(title=lang['DROPDOWN']['log.title'], description=lang['DROPDOWN']['log.description'], colour=nextcord.Color.green())
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        elif self.values[0].startswith('set_log:'):
            channel_id = self.values[0].split(':')[1]
            r.set(f'log:{interaction.guild.id}', channel_id)
            await interaction.response.send_message(embed=nextcord.Embed(title=lang['DROPDOWN']['log.success'], description=lang['DROPDOWN']['log.success.description'].format(f'<#{channel_id}>'), colour=nextcord.Color.green()), ephemeral=True)


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
        lang = lang_check(interaction.locale)
        if interaction.data['components'][0]['components'][0]['custom_id'] == 'del':
            if self.name.value.isdigit() and 0 <= int(self.name.value) <= 100:
                await interaction.response.send_message(embed=nextcord.Embed(title=lang['POPUP']['success'], description=lang['POPUP']['success.delete'].format(self.name.value), colour=nextcord.Color.green()), ephemeral=True)
                r.set(f'del:{interaction.guild.id}', self.name.value)
            else:
                await interaction.response.send_message(embed=nextcord.Embed(title=lang['POPUP']['error'], description=lang['POPUP']['error.int'].format(self.name.value), colour=nextcord.Color.red()), ephemeral=True)
        elif interaction.data['components'][0]['components'][0]['custom_id'] == 'rea':
            if self.name.value.isdigit() and 0 <= int(self.name.value) <= 100:
                await interaction.response.send_message(embed=nextcord.Embed(title=lang['POPUP']['success'], description=lang['POPUP']['success.reaction'].format(self.name.value), colour=nextcord.Color.green()), ephemeral=True)
                r.set(f'rea:{interaction.guild.id}', self.name.value)
            else:
                await interaction.response.send_message(embed=nextcord.Embed(title=lang['POPUP']['error'], description=lang['POPUP']['error.int'].format(self.name.value), colour=nextcord.Color.red()), ephemeral=True)


# code that will add all users to the ranking
if not r.exists('manner'):
    keys = r.keys('val:*')
    for key in keys:
        print(f'{(r.get(key.replace("val", "msg")))} - {(r.get(key))}')
        id = key.split(':')[1]

        manner_score = 100 - float(r.get(key)) / float(r.get(key.replace("val", "msg")))
        print(manner_score)
        r.zadd('manner', {id: manner_score})

client.run(token)