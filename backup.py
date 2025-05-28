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
        await interaction.response.send_modal(FarmModal())

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
class FarmModal(discord.ui.Modal, title="ㅤㅤㅤ┃ Enviar Farm ┃"):
    def __init__(self, valor1="", valor2="", valor3="", valor4=""):
        super().__init__(timeout=None)

        self.valor1 = discord.ui.TextInput(label="Valor 1", placeholder="Digite um número", default=valor1)
        self.valor2 = discord.ui.TextInput(label="Valor 2", placeholder="Digite um número", default=valor2)
        self.valor3 = discord.ui.TextInput(label="Valor 3", placeholder="Digite um número", default=valor3)
        self.valor4 = discord.ui.TextInput(label="Valor 4", placeholder="Digite um número", default=valor4)

        self.add_item(self.valor1)
        self.add_item(self.valor2)
        self.add_item(self.valor3)
        self.add_item(self.valor4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            v1 = int(self.valor1.value)
            v2 = int(self.valor2.value)
            v3 = int(self.valor3.value)
            v4 = int(self.valor4.value)

            await interaction.response.send_message(
                "📸 Envie agora um print da tela neste canal para registrar no log.\n⏳ Você tem 60 segundos.",
                ephemeral=True
            )

            def check(m):
                return (
                    m.author.id == interaction.user.id and
                    m.channel.id == interaction.channel.id and
                    m.attachments and
                    m.attachments[0].content_type.startswith("image/")
                )

            try:
                msg = await interaction.client.wait_for("message", timeout=60.0, check=check)
                attachment = msg.attachments[0]
                image_bytes = await attachment.read()

                # Apagar a imagem do usuário
                await msg.delete()

                # Enviar no canal de log
                CANAL_LOG_ID = 1377368578856325273  # Substitua com o ID real
                canal_log = interaction.client.get_channel(CANAL_LOG_ID)
                if canal_log:
                    await canal_log.send(
                        content=f"🖼️ Print de farm enviado por **{interaction.user}**.",
                        file=discord.File(fp=io.BytesIO(image_bytes), filename="farm_print.png")
                    )
                else:
                    await interaction.followup.send("⚠️ Canal de log não encontrado.", ephemeral=True)
                    return

                # Agora sim: salvar no banco
                bot_id = str(interaction.client.user.id)
                user_name = str(interaction.user)
                user_ref = db.collection(bot_id).document("farms").collection("users").document(user_name)
                doc = user_ref.get()

                if doc.exists:
                    data = doc.to_dict()
                    updated_data = {
                        "valor1": data.get("valor1", 0) + v1,
                        "valor2": data.get("valor2", 0) + v2,
                        "valor3": data.get("valor3", 0) + v3,
                        "valor4": data.get("valor4", 0) + v4,
                        "user_id": interaction.user.id,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    }
                    user_ref.update(updated_data)
                else:
                    new_data = {
                        "valor1": v1,
                        "valor2": v2,
                        "valor3": v3,
                        "valor4": v4,
                        "user_id": interaction.user.id,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    }
                    user_ref.set(new_data)

                await interaction.followup.send("<:verifica:1376988195832729681> Farm registrado com sucesso.", ephemeral=True)

            except asyncio.TimeoutError:
                await interaction.followup.send("⏰ Tempo esgotado! Nenhum print foi enviado. O farm não foi salvo.", ephemeral=True)

        except ValueError:
            valor1 = self.valor1.value
            valor2 = self.valor2.value
            valor3 = self.valor3.value
            valor4 = self.valor4.value

            class CorrigirView(discord.ui.View):
                @discord.ui.button(label="🔁 Corrigir valores", style=discord.ButtonStyle.danger)
                async def corrigir(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    await button_interaction.response.send_modal(
                        FarmModal(valor1, valor2, valor3, valor4)
                    )

            await interaction.response.send_message(
                "<:remove:1377347264963547157> Um ou mais valores são inválidos. Por favor, insira apenas números inteiros.",
                view=CorrigirView(),
                ephemeral=True
            )



    


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