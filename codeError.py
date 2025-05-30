# esse codigo deu mt erro. dps tento arrumar

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio               # contador de tempo
from datetime import datetime
import pytz
import io                    # carregar imagem

tz = pytz.timezone('America/Sao_Paulo')
timestamp = datetime.now(tz)
print(datetime.now(tz))

# timestamp = datetime.now(tz)
# timestamp = data.get("timestamp")


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

#============================================================================================================================================#

                                                                # Firebase

import firebase_admin
from firebase_admin import credentials, firestore
#from google.cloud import firestore

if not firebase_admin._apps:
    cred = credentials.Certificate(os.getenv("FIREBASE_KEY_PATH"))
    firebase_admin.initialize_app(cred)
db = firestore.client()

#============================================================================================================================================#

# Ligar o Bot

class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"O Bot {self.user} foi ligado com sucesso")
        
bot = Bot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)

#============================================================================================================================================#

# Ligar os botões quando o bot inicializa ou reinicia !

@bot.event
async def on_ready():
    print(f"Bot está online como {bot.user}!")
    
    # Registrar a View persistente
    bot.add_view(RegisterButton())
    bot.add_view(ApproveButton())
    bot.add_view(FarmView())
    bot.add_view(PersistentAprovacaoView())
    
#============================================================================================================================================#

# Função que verifica se o autor tem o cargo permitido

def check_cargo_permitido(nome_cargo: str):
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True  # admins sempre podem
        return any(role.name == nome_cargo for role in interaction.user.roles)
    return app_commands.check(predicate)

#============================================================================================================================================#



class RegisterButton(discord.ui.View):                            # Classe do Botão de se registrar
    def __init__(self):
        super().__init__(timeout=None)  # ❗ Faz com que o botão não expire NUNCA

    @discord.ui.button(
        label="Registrar",
        emoji="<:register2:1377304024923115632>",
        style=discord.ButtonStyle.secondary,
        custom_id="register_button"  # ❗ custom_id fixo = necessário para persistência
    )
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegisterModal())     # chama o modal do registro
        
        
class ApproveButton(discord.ui.View):                             # Classe do Botão de aprovar o registro
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Aprovar",
        emoji="<:verifica:1376988195832729681>",
        style=discord.ButtonStyle.secondary,
        custom_id="approve_button"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        emoji_verificar = discord.PartialEmoji.from_str("<:verifica2:1376988479891837009>")

        # 📌 Extrair embed e user_id
        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text

        if "ID do usuário:" not in footer_text:
            await interaction.response.send_message("<:remove:1377347264963547157> ID do usuário não encontrado no embed.", ephemeral=True)
            return

        user_id = int(footer_text.split("ID do usuário:")[1].strip())

        # 🎯 Obter o membro e os cargos
        guild = interaction.guild
        member = guild.get_member(user_id)
        cargo_aprovado = guild.get_role(1376997518314963084)  # Cargo para membros aprovados
        cargo_gerente = guild.get_role(1377010279640076368)  # 🚨 Substitua com o ID real do cargo Gerente

        if not member or not cargo_aprovado:
            await interaction.response.send_message("<:remove:1377347264963547157> Membro ou cargo não encontrado.", ephemeral=True)
            return

        # ✅ Extrair nome e ID do embed
        nome = embed.fields[0].value
        id_game = embed.fields[1].value

        # 🧾 Novo apelido
        novo_apelido = f"『M』{nome}・{id_game}"

        try:
            await member.add_roles(cargo_aprovado, reason="Registro aprovado")
            await member.edit(nick=novo_apelido, reason="Apelido ajustado após aprovação")
        except discord.Forbidden:
            await interaction.response.send_message("<:remove:1377347264963547157> Permissões insuficientes para modificar o usuário.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"<:remove:1377347264963547157> Erro ao modificar o usuário: {e}", ephemeral=True)
            return

        # ✅ Criar canal em "Farm"
        categoria = discord.utils.get(guild.categories, name="Farm")
        if not categoria:
            categoria = await guild.create_category("Farm")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        if cargo_gerente:
            overwrites[cargo_gerente] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        canal = await guild.create_text_channel(
            name=f"🚚・『M』{nome}・{id_game}",
            category=categoria,
            overwrites=overwrites,
            reason="Canal criado após aprovação"
        )

        # ✅ Atualizar botão
        button.label = f"Aprovado por {interaction.user.display_name}"
        button.emoji = emoji_verificar
        button.style = discord.ButtonStyle.success
        button.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"<:verifica:1376988195832729681> **┃ Usuário aprovado com sucesso!**\n📁 Canal criado: {canal.mention}",
            ephemeral=True
        )
        
        embed_farm = discord.Embed(                                                              # Cria o Painel de farm individual no canal do membro
            title="📦 Painel de Farm",
            description=f"Bem-vindo {member.mention}! Aqui é seu controle pessoal de farm.\nUtilize os botões abaixo para interagir com o sistema de farm.",
            color=discord.Color.blurple()
        )
        embed_farm.set_thumbnail(url=member.avatar.url)
        
        user = await interaction.client.fetch_user(member.id)  # ou await member.fetch()

        if user.banner:
            banner_url = user.banner.url
            print(banner_url)  # ou use no embed
        else:
            pass
        if user.banner:
            embed_farm.set_image(url=user.banner.url)


        await canal.send(embed=embed_farm, view=FarmView())


class RegisterModal(discord.ui.Modal, title="­­  ­­­­­┃𝐅𝐨𝐫𝐦𝐮𝐥á𝐫𝐢𝐨 𝐝𝐞 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐨┃"):              # Classe do formulário de registro📜
    nome = discord.ui.TextInput(label="👤Qual Seu nome?", 
                                placeholder="Digite seu nome...", 
                                required=True)
    id_game = discord.ui.TextInput(label="🆔Qual Seu ID In-Game?",
                                   placeholder="Ex: 123456", 
                                   required=True,
                                   min_length=2,
                                   max_length=6)
    recrutador = discord.ui.TextInput(label="🕵️Quem Te Recrutou?", 
                                      placeholder="Nome do recrutador", 
                                      required=True)
    telefone_game = discord.ui.TextInput(label="📱Qual Seu Número In-Game? (opcional)", 
                                         placeholder="Ex: 123-456", 
                                         required=False,
                                         min_length=6,
                                         max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id                                # 📌 Pega o ID do usuário
        # Aqui você pode salvar os dados ou enviar resposta       
        await interaction.response.send_message(
            f"<:verifica:1376988195832729681> Registro enviado com sucesso!\n\n**👤Nome:** {self.nome}\n**🆔ID:** {self.id_game}\n**🕵️Recrutador:** {self.recrutador}",
            ephemeral=True
        )


        embed_approve = discord.Embed(
            title="📥 **Novo Registro**",
            description="**Um novo registro foi enviado.**",
            color=discord.Color.from_str("#00FF00")
        )
        embed_approve.add_field(name="👤 Nome", value=self.nome, inline=True)
        embed_approve.add_field(name="🆔 ID In-Game", value=self.id_game, inline=True)
        embed_approve.add_field(name="📱 Telefone In-Game", value=self.telefone_game or "Não informado", inline=False)
        embed_approve.add_field(name="🕵️ Recrutador", value=self.recrutador, inline=False)
        
        member = interaction.guild.get_member(user_id)        # Tenta puxar o avatar do userID e jogar no registro
        if member:
            embed_approve.set_thumbnail(url=member.display_avatar.url)
        else:
            embed_approve.set_thumbnail(url=interaction.client.user.avatar.url)  # fallback pro bot

        embed_approve.set_footer(text=f"ID do usuário: {user_id}")
        embed_approve.timestamp = discord.utils.utcnow()


        canal_log_register = 1376933289025208382                # canal que vai enviar o registro
            
        # Obter o canal pelo ID
        canal = interaction.client.get_channel(canal_log_register)
        if canal:
            # Enviar mensagem pública no canal
            await canal.send(embed=embed_approve, view=ApproveButton())
        else:
            print(f"Canal com ID {canal_log_register} não encontrado.")
            
            
        
                   
@bot.tree.command(name="painel_registro", description="Envia o painel fixo de registro")    # Criar o painel de registro // Depois precisa criar uma função com todos os paineis
@check_cargo_permitido("Gerente")                                       # Substitua pelo nome exato do cargo
async def send_embed(interaction: discord.Interaction):
    embed_register = discord.Embed(
        title="CENTRAL DE REGISTRO・Chicletões Norte",
        description="Seja bem-vindo(a) à Chicletões Norte! Para ter acesso\n a todos os nossos canais, por favor, realize\n seu registro abaixo.",
        color=discord.Color.blurple()
    )
    embed_register.set_thumbnail(
        url=interaction.client.user.avatar.url 
    )
    embed_register.set_footer(icon_url=interaction.client.user.avatar.url,
                              text="Todos os direitos reservados a mim mesmo")

    view = RegisterButton()
    await interaction.channel.send(embed=embed_register, view=view)
    await interaction.response.send_message("Painel enviado com sucesso!", ephemeral=True)
    
    
# 🔘 Botões fora da classe ApproveButton
class FarmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📤 Enviar Farm", style=discord.ButtonStyle.secondary, custom_id="farm_button",)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FarmModal(interaction.client))

class PainelFarmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📊 Painel de Farm", style=discord.ButtonStyle.secondary, custom_id="painel_farm_button")

    async def callback(self, interaction: discord.Interaction):
        user_name = str(interaction.user)
        bot_id = str(interaction.client.user.id)

        # Caminho para o documento do usuário
        user_ref = db.collection(bot_id) \
                     .document("farms") \
                     .collection("users") \
                     .document(user_name)

        doc = user_ref.get()

        if doc.exists:
            data = doc.to_dict()

            embed = discord.Embed(
                title="📊 Painel de Farm",
                description=f"Usuário: **{user_name}**",
                color=discord.Color.blurple()
            )

            embed.add_field(name="Valor 1", value=str(data.get("valor1", 0)), inline=True)
            embed.add_field(name="Valor 2", value=str(data.get("valor2", 0)), inline=True)
            embed.add_field(name="Valor 3", value=str(data.get("valor3", 0)), inline=True)
            embed.add_field(name="Valor 4", value=str(data.get("valor4", 0)), inline=True)

            timestamp = datetime.now(tz)
            if timestamp:
                embed.set_footer(text=f"Última atualização: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "<:remove:1377347264963547157> Você ainda não enviou nenhum farm para exibir.",
                ephemeral=True
            )

# ✅ View que junta os botões
class FarmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FarmButton())
        self.add_item(PainelFarmButton())

    
# Modal de envio de farm

pending_farms = {} 

class FarmModal(discord.ui.Modal, title="ㅤㅤㅤ┃ Enviar Farm ┃"):
    def __init__(self, bot, valor1="", valor2="", valor3="", valor4=""):
        super().__init__()
        self.bot = bot
        self.valor1 = discord.ui.TextInput(label="Valor 1", default=valor1)
        self.valor2 = discord.ui.TextInput(label="Valor 2", default=valor2)
        self.valor3 = discord.ui.TextInput(label="Valor 3", default=valor3)
        self.valor4 = discord.ui.TextInput(label="Valor 4", default=valor4)
        self.add_item(self.valor1)
        self.add_item(self.valor2)
        self.add_item(self.valor3)
        self.add_item(self.valor4)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📸 Agora envie um print para comprovar seu farm.", ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.attachments and m.channel.id == interaction.channel.id

        try:
            message = await self.bot.wait_for("message", check=check, timeout=60)
            image = message.attachments[0]
            image_bytes = await image.read()
            await message.delete()

            LOG_CHANNEL_ID = 1377378645219344465
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

            embed = discord.Embed(
                title="📤 **・Farm aguardando aprovação**",
                description=f"Usuário: **{interaction.guild.get_member(interaction.user.id).display_name}**",
                color=discord.Color.orange()
            )

            embed.add_field(name="Valor 1", value=self.valor1.value)
            embed.add_field(name="Valor 2", value=self.valor2.value)
            embed.add_field(name="Valor 3", value=self.valor3.value)
            embed.add_field(name="Valor 4", value=self.valor4.value)
            embed.set_image(url="attachment://farm.png")

            msg = await log_channel.send(
                embed=embed,
                file=discord.File(io.BytesIO(image_bytes), filename="farm.png"),
                view=AprovacaoView(
                    user_id=interaction.user.id,
                    v1=int(self.valor1.value),
                    v2=int(self.valor2.value),
                    v3=int(self.valor3.value),
                    v4=int(self.valor4.value)
                )
            )

            # Salva farm pendente no Firestore
            farm_id = str(msg.id)
            bot_id = str(self.bot.user.id)
            user_name = str(interaction.user)

            db.collection(bot_id).document("farms_pendentes").collection("users").document(farm_id).set({
                "user_id": interaction.user.id,
                "user_name": user_name,
                "valor1": int(self.valor1.value),
                "valor2": int(self.valor2.value),
                "valor3": int(self.valor3.value),
                "valor4": int(self.valor4.value),
                "farmID": farm_id,
                "timestamp": fb_firestore.SERVER_TIMESTAMP
            })

            canal_embed = discord.Embed(
                title="🚚 **・Pendente**",
                description="Seu farm foi enviado e está aguardando aprovação.",
                color=discord.Color.orange()
            )
            canal_embed.set_thumbnail(url="https://emojitool.com/img/microsoft/windows-11-23h2-June-2024/windows-11-23h2-june-2024-update-552.png")
            canal_embed.set_image(url="attachment://farm.png")

            await interaction.channel.send(
                embed=canal_embed,
                file=discord.File(io.BytesIO(image_bytes), filename="farm.png")
            )

        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado. Envio cancelado.", ephemeral=True)

class AprovacaoView(discord.ui.View):
    def __init__(self, user_id, v1, v2, v3, v4):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.v1 = v1
        self.v2 = v2
        self.v3 = v3
        self.v4 = v4

        self.aprovar_button = discord.ui.Button(
            label="Aprovar",
            emoji="<:verifica2:1376988479891837009>",
            style=discord.ButtonStyle.success,
            custom_id="aprovar_farm"
        )
        self.rejeitar_button = discord.ui.Button(
            label="Rejeitar",
            emoji="<:remove1:1377385311428022446>",
            style=discord.ButtonStyle.danger,
            custom_id="rejeitar_farm"
        )

        self.aprovar_button.callback = self.aprovar
        self.rejeitar_button.callback = self.rejeitar

        self.add_item(self.aprovar_button)
        self.add_item(self.rejeitar_button)

    async def aprovar(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "<:remove:1377347264963547157> Você não tem permissão para aprovar.", ephemeral=True
            )
            return

        await interaction.response.defer()

        bot_id = str(interaction.client.user.id)
        user = interaction.guild.get_member(self.user_id)
        user_name = str(user)

        user_ref = db.collection(bot_id).document("farms").collection("users").document(user_name)
        doc = user_ref.get()

        if doc.exists:
            data = doc.to_dict()
            user_ref.update({
                "valor1": data.get("valor1", 0) + self.v1,
                "valor2": data.get("valor2", 0) + self.v2,
                "valor3": data.get("valor3", 0) + self.v3,
                "valor4": data.get("valor4", 0) + self.v4,
                "user_id": self.user_id,
                "timestamp": fb_firestore.SERVER_TIMESTAMP
            })
        else:
            user_ref.set({
                "valor1": self.v1,
                "valor2": self.v2,
                "valor3": self.v3,
                "valor4": self.v4,
                "user_id": self.user_id,
                "timestamp": fb_firestore.SERVER_TIMESTAMP
            })

        # Remove do firestore de pendentes
        await db.collection(bot_id).document("farms_pendentes").collection("users").document(str(interaction.message.id)).delete()

        self.aprovar_button.disabled = True
        self.aprovar_button.label = "Aprovado"
        self.rejeitar_button.disabled = True
        self.rejeitar_button.style = discord.ButtonStyle.secondary

        await interaction.edit_original_response(view=self)
        await interaction.followup.send("<:verifica:1376988195832729681> Farm aprovado e registrado com sucesso!", ephemeral=True)

    async def rejeitar(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "<:remove:1377347264963547157> Você não tem permissão para rejeitar.", ephemeral=True
            )
            return

        await interaction.response.defer()

        bot_id = str(interaction.client.user.id)
        await db.collection(bot_id).document("farms_pendentes").collection("users").document(str(interaction.message.id)).delete()

        self.aprovar_button.disabled = True
        self.aprovar_button.style = discord.ButtonStyle.secondary
        self.rejeitar_button.disabled = True
        self.rejeitar_button.label = "Rejeitado"

        await interaction.edit_original_response(view=self)
        await interaction.followup.send("<:remove:1377347264963547157> Farm rejeitado. Nenhum dado foi salvo.", ephemeral=True)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Conectado como {bot.user}")
    bot_id = str(bot.user.id)
    farms_ref = db.collection(bot_id).document("farms_pendentes").collection("users")
    docs = farms_ref.stream()

    for doc in docs:
        farm = doc.to_dict()
        farm_id = int(farm["farmID"])
        v1 = farm["valor1"]
        v2 = farm["valor2"]
        v3 = farm["valor3"]
        v4 = farm["valor4"]
        user_id = farm["user_id"]

        try:
            log_channel = bot.get_channel(1377378645219344465)
            msg = await log_channel.fetch_message(farm_id)
            await msg.edit(view=AprovacaoView(user_id, v1, v2, v3, v4))
        except Exception as e:
            print(f"Erro ao restaurar farm {farm_id}: {e}")

@bot.command()
async def enviarfarm(ctx):
    await ctx.send_modal(FarmModal(bot))
        
        
class PersistentAprovacaoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(
            label="Aprovar",
            style=discord.ButtonStyle.success,
            emoji="<:verifica2:1376988479891837009>",
            custom_id="aprovar_farm"
        ))

        self.add_item(discord.ui.Button(
            label="Rejeitar",
            style=discord.ButtonStyle.danger,
            emoji="<:remove1:1377385311428022446>",
            custom_id="rejeitar_farm"
        ))


    


@bot.tree.command(name="teste", description="descrição teste")
async def teste(interaction: discord.Interaction):
    await interaction.response.send_message("Hello World")

@bot.tree.command(name="farm", description="Insira seu farm aqui")
@app_commands.describe(
    ferro="Insira a quantidade de ferro que você está colocando no baú",
    alumínio="Insira a quantidade de alumínio que você está colocando no baú",
    cobre="Insira a quantidade de cobre que você está colocando no baú",
    titânio="Insira a quantidade de titânio que você está colocando no baú"
)
async def farm(interaction: discord.Interaction, ferro: int, alumínio: int, cobre: int, titânio: int):
    await interaction.response.send_message("Farm cadastrado com sucesso!", ephemeral=True)

bot.run(TOKEN)