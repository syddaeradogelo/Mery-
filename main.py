import discord
from discord.ext import commands, tasks
import json
import os
import datetime
import aiofile

# Configurando os intents para rastrear estados de voz e mensagens
intents = discord.Intents.default()
intents.voice_states = True  # Ativa o rastreamento de eventos de estado de voz
intents.messages = True      # Ativa o rastreamento de eventos de mensagens
intents.guilds = True        # Ativa o rastreamento de eventos de guildas
intents.message_content = True  # Ativa o rastreamento de conteúdo das mensagens (necessário para intents privilegidados)

bot = commands.Bot(command_prefix='!', intents=intents)

pd_file = 'pd_data.json'
data_file = 'data.json'

############################################### LODS JSON ###############################################

if not os.path.exists(data_file):
    with open(data_file, 'w') as f:
        json.dump({}, f)

async def load_data():
    async with aiofile.async_open(data_file, 'r') as f:
        data = await f.read()
        return json.loads(data)

async def save_data(data):
    async with aiofile.async_open(data_file, 'w') as f:
        await f.write(json.dumps(data, indent=4))

# Funções auxiliares para carregar e salvar dados
async def load_pd_data():
    async with aiofile.async_open(pd_file, 'r') as f:
        data = await f.read()
        return json.loads(data)

async def save_pd_data(data):
    async with aiofile.async_open(pd_file, 'w') as f:
        await f.write(json.dumps(data, indent=4))

############################################### EVENTS ###############################################

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    check_time_in_call.start()

@bot.event
async def on_voice_state_update(member, before, after):
    data = await load_data()
    user_id = str(member.id)

    if user_id not in data:
        data[user_id] = {
            "time_in_call": 0,
            "last_joined": None
        }

    if before.channel is None and after.channel is not None:
        # Usuário entrou em um canal de voz
        data[user_id]['last_joined'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    elif before.channel is not None and after.channel is None:
        # Usuário saiu de um canal de voz
        if data[user_id]['last_joined'] is not None:
            join_time = datetime.datetime.fromisoformat(data[user_id]['last_joined']).replace(tzinfo=datetime.timezone.utc)
            duration = (datetime.datetime.now(datetime.timezone.utc) - join_time).total_seconds()
            data[user_id]['time_in_call'] += duration
            data[user_id]['last_joined'] = None

    await save_data(data)

@tasks.loop(minutes=1)
async def check_time_in_call():
    data = await load_data()
    for guild in bot.guilds:
        for member in guild.members:
            if member.voice and member.voice.channel:
                user_id = str(member.id)
                if data[user_id]['last_joined'] is not None:
                    join_time = datetime.datetime.fromisoformat(data[user_id]['last_joined']).replace(tzinfo=datetime.timezone.utc)
                    duration = (datetime.datetime.now(datetime.timezone.utc) - join_time).total_seconds()
                    data[user_id]['time_in_call'] += duration
                    data[user_id]['last_joined'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await save_data(data)

############################################### COMANDOS DE CALL ###############################################

@bot.command(name='tempo')
async def tempo(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    data = await load_data()
    user_id = str(member.id)
    if user_id in data:
        time_in_call = data[user_id]['time_in_call']
        hours, remainder = divmod(time_in_call, 3600)
        minutes, seconds = divmod(remainder, 60)
        embed = discord.Embed(
            title=f'Tempo em Call de {member.display_name}',
            description=f'{member.display_name} passou {int(hours)}h {int(minutes)}m {int(seconds)}s em call.',
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Mery' | comando requisitado por : {ctx.author.display_name}")
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)  # Usando default_avatar aqui
        
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f'Nenhum dado encontrado para {member.display_name}.')


@bot.command(name='ranking')
async def ranking(ctx):
    data = await load_data()
    ranking = sorted(data.items(), key=lambda x: x[1]['time_in_call'], reverse=True)[:10]
    description = ''

    guild = ctx.guild

    # Fetch members using get_all_members to ensure all members are cached
    members = guild.members

    for i, (user_id, info) in enumerate(ranking, start=1):
        member = guild.get_member(int(user_id))
        if member:
            hours, remainder = divmod(info['time_in_call'], 3600)
            minutes, seconds = divmod(remainder, 60)
            description += f'**{i}. {member.display_name}** - {int(hours)}h {int(minutes)}m {int(seconds)}s\n'
        else:
            # Caso o membro não seja encontrado, continue para o próximo
            continue

    embed = discord.Embed(
        title='Top 10 Usuários com Mais Tempo em Call',
        description=description,
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Mery' | comando requisitado por : {ctx.author.display_name}")
    embed.set_author(name=guild.name, icon_url=guild.icon.url)
    await ctx.send(embed=embed)

############################################### COMANDOS DE PD ###############################################

@bot.command(name='painelpd')
async def painelpd(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Você não tem permissão para usar este comando.")
        return

    pd_data = await load_pd_data()
    guild_id = str(ctx.guild.id)

    if guild_id not in pd_data:
        pd_data[guild_id] = {
            'name': None,
            'color': None,
            'role_id': None,
            'members': []
        }

    if pd_data[guild_id]['name'] is None:
        await ctx.send("Primeira vez configurando o cargo de Primeira Dama. Por favor, forneça o nome do cargo.")
        name_message = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        pd_data[guild_id]['name'] = name_message.content

        await ctx.send("Agora, forneça a cor do cargo (em formato hexadecimal, por exemplo: #ff0000).")
        color_message = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        color = color_message.content.strip('#')
        pd_data[guild_id]['color'] = int(color, 16)

        await ctx.send("Cargo de Primeira Dama configurado com sucesso!")

        role = await ctx.guild.create_role(
            name=pd_data[guild_id]['name'],
            color=discord.Color(pd_data[guild_id]['color'])
        )
        pd_data[guild_id]['role_id'] = role.id

    else:
        await ctx.send("Configurando o painel de Primeira Dama.")
        embed = discord.Embed(
            title="Painel de Primeira Dama",
            description="Configure o cargo de Primeira Dama",
            color=discord.Color.purple()
        )
        embed.add_field(name="Nome", value=pd_data[guild_id]['name'])
        embed.add_field(name="Cor", value=f"#{pd_data[guild_id]['color']:06x}")
        embed.set_footer(text=f"Mery' | comando requisitado por : {ctx.author.display_name}")
        embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        await ctx.send(embed=embed)

    await save_pd_data(pd_data)


    pd_data = await load_pd_data()
    guild_id = str(ctx.guild.id)

    if guild_id not in pd_data or pd_data[guild_id]['role_id'] is None:
        await ctx.send("O cargo de Primeira Dama não foi configurado neste servidor.")
        return

    role = ctx.guild.get_role(pd_data[guild_id]['role_id'])
    if not role:
        await ctx.send("Não foi possível encontrar o cargo configurado de Primeira Dama.")
        return

    members_with_role = [member.mention for member in ctx.guild.members if role in member.roles]

    if members_with_role:
        embed = discord.Embed(
            title="Membros com Cargo de Primeira Dama",
            description="Lista dos membros que possuem o cargo de Primeira Dama neste servidor",
            color=discord.Color.purple()
        )
        embed.add_field(name="Membros", value=', '.join(members_with_role))
        embed.set_footer(text=f"Mery' | comando requisitado por : {ctx.author.display_name}")
        embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Nenhum membro possui o cargo de Primeira Dama neste servidor.")

@bot.command(name='addpd')
async def addpd(ctx, *members: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Você não tem permissão para usar este comando.")
        return

    pd_data = await load_pd_data()
    guild_id = str(ctx.guild.id)

    if guild_id not in pd_data or pd_data[guild_id]['role_id'] is None:
        await ctx.send("O cargo de Primeira Dama não foi configurado neste servidor.")
        return

    role = ctx.guild.get_role(pd_data[guild_id]['role_id'])
    if not role:
        await ctx.send("Não foi possível encontrar o cargo configurado de Primeira Dama.")
        return

    added_members = []
    for member in members:
        if role not in member.roles:
            await member.add_roles(role)
            added_members.append(member)

    if added_members:
        member_mentions = [member.mention for member in added_members]
        await ctx.send(f"Cargo de Primeira Dama adicionado aos membros: {', '.join(member_mentions)}")
    else:
        await ctx.send("Nenhum novo membro foi adicionado ao cargo de Primeira Dama.")

    # Atualiza os dados do pd_data.json com os membros adicionados
    pd_data[guild_id]['members'] += [member.id for member in added_members]
    await save_pd_data(pd_data)



with open('config.json') as f:
    config = json.load(f)
    token = config['token']

bot.run(token)
