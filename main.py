import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio               # contador de tempo
from datetime import datetime
import pytz
import io                    # carregar imagem
import uuid
import re     # remover depois / não estou mais usando

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
    
    # Registrar as Views persistentes primeiro
    bot.add_view(RegisterButton())
    bot.add_view(ApproveButton())
    bot.add_view(FarmView())
    
    # Executa a restauração em segundo plano
    bot.loop.create_task(restaurar_farms_pendentes(bot))
    
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
        user_name = str(interaction.user.id)
        user_nick = str(interaction.user)
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
                description=f"Usuário: **{user_nick}**",
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

LOG_CHANNEL_ID = 1377378645219344465

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
            return (
                m.author.id == interaction.user.id and 
                m.attachments and 
                m.channel.id == interaction.channel.id
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=60)
            image = message.attachments[0]
            image_bytes = await image.read()
            await message.delete()

            # 1. Cria embed no canal de log de aprovação
            LOG_CHANNEL_ID = 1377378645219344465
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

            embed_log = discord.Embed(
                title="📤 **Farm aguardando aprovação**",
                description=f"Usuário: **{interaction.guild.get_member(interaction.user.id).display_name}**",
                color=discord.Color.orange()
            )
            embed_log.add_field(name="Valor 1", value=self.valor1.value)
            embed_log.add_field(name="Valor 2", value=self.valor2.value)
            embed_log.add_field(name="Valor 3", value=self.valor3.value)
            embed_log.add_field(name="Valor 4", value=self.valor4.value)
            embed_log.set_image(url="attachment://farm.png")
            
            user_id = interaction.user.id   
            embed_log.set_footer(text=f"ID do usuário: {user_id}")
            embed_log.timestamp = discord.utils.utcnow()

            # Envia para o canal de log
            log_msg = await log_channel.send(
                embed=embed_log,
                file=discord.File(io.BytesIO(image_bytes), filename="farm.png"),
                view=AprovacaoView(
                    user_id=interaction.user.id,
                    v1=int(self.valor1.value),
                    v2=int(self.valor2.value),
                    v3=int(self.valor3.value),
                    v4=int(self.valor4.value)
                )
            )
            
            # 🔹 Gera o farmID
            farm_id = str(log_msg.id)
            
            # 2. Cria embed no canal do membro
            embed_member = discord.Embed(
                title="📦 **・Farm Enviado Com Sucesso**",
                description="Seu farm foi enviado e está aguardando aprovação.",
                color=discord.Color.orange()
            )
            embed_member.set_thumbnail(url="https://emojitool.com/img/microsoft/windows-11-23h2-June-2024/windows-11-23h2-june-2024-update-552.png")
            embed_member.set_image(url="attachment://farm.png")
            embed_member.add_field(name="**Status:**", value="<a:loading:1377690003550896289> Pendente")
            
            member_msg = await interaction.channel.send(
                embed=embed_member
                #file=discord.File(io.BytesIO(image_bytes), filename="farm.png")
            )

            # 3. Armazena no Firebase
            bot_id = str(self.bot.user.id)
            db.collection(str(self.bot.user.id)).document("farmsPendentes").collection("items").document(farm_id).set({
            "user_id": str(interaction.user.id),
            "valor1": int(self.valor1.value),
            "valor2": int(self.valor2.value),
            "valor3": int(self.valor3.value),
            "valor4": int(self.valor4.value),
            "farm_id": farm_id,
            "log_msg_id": str(log_msg.id),
            "log_channel_id": str(log_channel.id),
            "member_msg_id": str(member_msg.id),
            "member_channel_id": str(interaction.channel.id),
            "timestamp": firestore.SERVER_TIMESTAMP 
            })

        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado. Envio cancelado.", ephemeral=True)
            
            
# Lógica para restaurar os farms pendentes quando o bot reiniciar

pending_farms = {} 

# Lógica para restaurar os farms pendentes quando o bot reiniciar
async def restaurar_farms_pendentes(bot):
    try:
        print("Iniciando restauração de farms pendentes...")
        bot_id = str(bot.user.id)
        farms_ref = db.collection(bot_id).document("farmsPendentes").collection("items")
        
        # Usamos limit para evitar sobrecarga
        docs = farms_ref.limit(50).stream()
        
        restored_count = 0
        
        for doc in docs:
            try:
                data = doc.to_dict()
                
                # Pega os IDs dos canais e mensagens (convertendo para int)
                log_channel_id = int(data.get("log_channel_id")) if data.get("log_channel_id") else None
                log_msg_id = int(data.get("log_msg_id")) if data.get("log_msg_id") else None
                
                if not log_channel_id or not log_msg_id:
                    print(f"Farm {doc.id} sem IDs de canal/mensagem válidos")
                    continue
                
                # Obtém o canal e a mensagem
                canal = bot.get_channel(log_channel_id)
                if canal is None:
                    print(f"Canal {log_channel_id} não encontrado para farm {doc.id}")
                    continue
                
                try:
                    mensagem = await canal.fetch_message(log_msg_id)
                except discord.NotFound:
                    print(f"Mensagem {log_msg_id} não encontrada - deletando farm pendente")
                    await doc.reference.delete()  # Deleta o farm se a mensagem não existir mais
                    continue
                
                # Recria a view com os dados originais
                view = AprovacaoView(
                    user_id=int(data["user_id"]),
                    v1=data["valor1"],
                    v2=data["valor2"],
                    v3=data["valor3"],
                    v4=data["valor4"]
                )
                
                await mensagem.edit(view=view)
                restored_count += 1
                
                # Dá uma pausa para evitar bloquear o heartbeat
                await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"Erro ao restaurar farm {doc.id}: {e}")
                continue
                
        print(f"✅ Restauração concluída! {restored_count} farms restaurados com sucesso.")
        
    except Exception as e:
        print(f"Erro crítico ao restaurar farms: {e}")

class AprovacaoView(discord.ui.View):
    def __init__(self, user_id, v1, v2, v3, v4):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.v1 = v1
        self.v2 = v2
        self.v3 = v3
        self.v4 = v4

        # Botões
        self.aprovar_button = discord.ui.Button(
            label="Aprovar",
            emoji="<:verifica2:1376988479891837009>",
            style=discord.ButtonStyle.success
        )
        self.rejeitar_button = discord.ui.Button(
            label="Rejeitar",
            emoji="<:remove1:1377385311428022446>",
            style=discord.ButtonStyle.danger
        )

        self.aprovar_button.callback = self.aprovar
        self.rejeitar_button.callback = self.rejeitar

        self.add_item(self.aprovar_button)
        self.add_item(self.rejeitar_button)

    async def aprovar(self, interaction: discord.Interaction):
        try:
            print("\nIniciando processo de aprovação...")  # DEBUG
            
            if not interaction.user.guild_permissions.manage_messages:
                print("Usuário sem permissão")  # DEBUG
                return await interaction.response.send_message("<:remove:1377347264963547157> Sem permissão.", ephemeral=True)

            # 1. Primeiro respondemos a interação
            print("Enviando defer...")  # DEBUG
            await interaction.response.defer(ephemeral=True)
            
            bot_id = str(interaction.client.user.id)
            farm_id = str(interaction.message.id)
            print(f"Farm ID: {farm_id}")  # DEBUG
            
            # 2. Referência ao documento
            farm_ref = db.collection(bot_id).document("farmsPendentes").collection("items").document(farm_id)
            print("Referência ao documento obtida")  # DEBUG
            
            # 3. Verifica se o documento existe
            print("Verificando existência do documento...")  # DEBUG
            farm_snapshot = farm_ref.get()
            if not farm_snapshot.exists:
                print("Documento não encontrado!")  # DEBUG
                return await interaction.followup.send("❌ Farm não encontrado no banco de dados.", ephemeral=True)
            
            farm_data = farm_snapshot.to_dict()
            print("Dados do farm:", farm_data)  # DEBUG
            
            # 4. Deleta o farm pendente
            print(f"Deletando farm {farm_id}...")  # DEBUG
            farm_ref.delete()
            print("Farm deletado com sucesso!")  # DEBUG
            
            # 5. Restante da lógica de aprovação...
            user_ref = db.collection(bot_id).document("farms").collection("users").document(str(self.user_id))
            doc = user_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                user_ref.update({
                    "valor1": data.get("valor1", 0) + self.v1,
                    "valor2": data.get("valor2", 0) + self.v2,
                    "valor3": data.get("valor3", 0) + self.v3,
                    "valor4": data.get("valor4", 0) + self.v4,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
            else:
                user_ref.set({
                    "valor1": self.v1,
                    "valor2": self.v2,
                    "valor3": self.v3,
                    "valor4": self.v4,
                    "user_id": self.user_id,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })

            # 6. Atualiza mensagem do membro (se existir)
            if 'member_channel_id' in farm_data and 'member_msg_id' in farm_data:
                try:
                    member_channel = interaction.client.get_channel(int(farm_data["member_channel_id"]))
                    if member_channel:
                        member_msg = await member_channel.fetch_message(int(farm_data["member_msg_id"]))
                        embed = member_msg.embeds[0]
                        embed.color = discord.Color.green()
                        embed.set_field_at(0, name="**Status:**", value="<:verifica:1376988195832729681> Aprovado")
                        await member_msg.edit(embed=embed)
                except Exception as e:
                    print(f"Erro ao atualizar mensagem do membro: {e}")

            # 7. Atualiza os botões
            self.aprovar_button.disabled = True
            self.aprovar_button.label = "Aprovado"
            self.rejeitar_button.disabled = True
            
            await interaction.message.edit(view=self)
            await interaction.followup.send("<:verifica:1376988195832729681> Farm aprovado com sucesso!", ephemeral=True)
            print("Processo de aprovação concluído com sucesso!")  # DEBUG

        except Exception as e:
            print(f"ERRO CRÍTICO no processo de aprovação: {str(e)}")  # DEBUG
            try:
                await interaction.followup.send("❌ Ocorreu um erro crítico ao aprovar o farm.", ephemeral=True)
            except:
                print("Não foi possível enviar mensagem de erro")

    async def rejeitar(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("<:remove:1377347264963547157> Sem permissão.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            bot_id = str(interaction.client.user.id)
            farm_id = str(interaction.message.id)
            
            # 1. Deleta o farm pendente
            farm_ref = db.collection(bot_id).document("farmsPendentes").collection("items").document(farm_id)
            print(farm_id)
            farm_data = farm_ref.get().to_dict()
            print(f"Deletando farm {farm_id}...")
            farm_ref.delete()
            print("Farm deletado com sucesso!")

            # 2. Atualiza a mensagem no canal do membro (opcional)
            if farm_data:
                try:
                    member_channel = interaction.client.get_channel(int(farm_data["member_channel_id"]))
                    if member_channel:
                        member_msg = await member_channel.fetch_message(int(farm_data["member_msg_id"]))
                        embed = member_msg.embeds[0]
                        embed.color = discord.Color.red()
                        embed.set_field_at(0, name="**Status:**", value="<:remove:1377347264963547157> Rejeitado")
                        await member_msg.edit(embed=embed)
                except Exception as e:
                    print(f"Erro ao atualizar mensagem do membro: {e}")

            # 3. Atualiza os botões
            self.aprovar_button.disabled = True
            self.rejeitar_button.disabled = True
            self.rejeitar_button.label = "Rejeitado"
            
            await interaction.message.edit(view=self)
            await interaction.followup.send("<:remove:1377347264963547157> Farm rejeitado.", ephemeral=True)

        except Exception as e:
            print(f"Erro ao rejeitar farm: {e}")
            try:
                await interaction.followup.send("❌ Erro ao rejeitar farm.", ephemeral=True)
            except:
                print("Não foi possível enviar mensagem de erro")
                
                

# Comando para criar a lista
@bot.tree.command(name="lista", description="Cria uma lista personalizada")
@check_cargo_permitido("Gerente")
@app_commands.describe(
    nome="Nome da lista",
    quantidade="Número de pessoas que cabem (0 = sem limite)",
    tempo="Tempo (em minutos) que a lista ficará aberta"
)
async def lista(
    interaction: discord.Interaction,
    nome: str,
    quantidade: int,
    tempo: int
):
    await interaction.response.defer()

    embed = discord.Embed(
        title=f"📋 {nome}",
        description="Carregando...",
        color=discord.Color.blue()
    )

    view = ListaView(nome, quantidade, interaction.user, embed)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message  # Associar a message à View

    # Atualiza a embed inicial
    embed.description = (
        f"👥 Capacidade: {'Sem limite' if quantidade == 0 else f'{quantidade} pessoas'}\n"
        f"🛡️ Criada por: {interaction.user.mention}\n\n**Participantes:** *(vazio)*\n\n"
        "*Clique no botão abaixo para entrar na lista!*"
    )
    await message.edit(embed=embed, view=view)

    # Espera o tempo para encerrar a lista
    await asyncio.sleep(tempo * 60)

    view.disable_all_items()
    embed.title += " (Encerrada)"
    embed.color = discord.Color.red()
    await message.edit(embed=embed, view=view)
    await interaction.followup.send(f"A lista **{nome}** foi encerrada ⏳", ephemeral=True)


# View da lista com botão de entrada
class ListaView(discord.ui.View):
    def __init__(self, nome, quantidade, autor, embed):
        super().__init__(timeout=None)
        self.nome = nome
        self.quantidade = quantidade
        self.autor = autor
        self.embed = embed
        self.participantes: list[discord.User] = []
        self.message = None  # Será atribuído depois do envio inicial

    @discord.ui.button(label="Entrar na lista", style=discord.ButtonStyle.green)
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user in self.participantes:
            await interaction.response.send_message("Você já está na lista!", ephemeral=True)
            return

        if self.quantidade != 0 and len(self.participantes) >= self.quantidade:
            await interaction.response.send_message("A lista já está cheia!", ephemeral=True)
            return

        self.participantes.append(user)

        # Atualiza o embed com os nomes dos participantes
        lista_formatada = "\n".join(f"{i+1}. {p.mention}" for i, p in enumerate(self.participantes))
        self.embed.description = (
            f"👥 Capacidade: {'Sem limite' if self.quantidade == 0 else f'{self.quantidade} pessoas'}\n"
            f"⏱️ Criada por: {self.autor.mention}\n\n**Participantes:**\n{lista_formatada}\n\n"
            "*Clique no botão abaixo para entrar na lista!*"
        )

        await self.message.edit(embed=self.embed, view=self)
        await interaction.response.send_message(f"{user.mention}, você entrou na lista **{self.nome}** ✅", ephemeral=True)

        # Envia mensagem no privado com botão para sair
        try:
            sair_view = SairDaListaView(self, user)
            await user.send(
                f"Olá {user.mention}, você entrou na lista **{self.nome}**.\n"
                "Caso deseje sair, clique no botão abaixo:",
                view=sair_view
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{user.mention}, não consegui te enviar DM. Verifique suas configurações de privacidade.",
                ephemeral=True
            )

    def disable_all_items(self):
        for item in self.children:
            item.disabled = True


# View com botão de sair da lista (enviada via DM)
class SairDaListaView(discord.ui.View):
    def __init__(self, lista_view: ListaView, usuario: discord.User):
        super().__init__(timeout=None)
        self.lista_view = lista_view
        self.usuario = usuario

    @discord.ui.button(label="Sair da lista", style=discord.ButtonStyle.red)
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.usuario:
            await interaction.response.send_message("Você não pode usar esse botão!", ephemeral=True)
            return

        if self.usuario in self.lista_view.participantes:
            self.lista_view.participantes.remove(self.usuario)

            # Atualiza embed no canal
            lista_formatada = "\n".join(f"{i+1}. {p.mention}" for i, p in enumerate(self.lista_view.participantes)) or "*(vazio)*"
            self.lista_view.embed.description = (
                f"👥 Capacidade: {'Sem limite' if self.lista_view.quantidade == 0 else f'{self.lista_view.quantidade} pessoas'}\n"
                f"⏱️ Criada por: {self.lista_view.autor.mention}\n\n**Participantes:**\n{lista_formatada}\n\n"
                "*Clique no botão abaixo para entrar na lista!*"
            )

            await self.lista_view.message.edit(embed=self.lista_view.embed, view=self.lista_view)
            await interaction.response.send_message("Você saiu da lista com sucesso ✅", ephemeral=True)
            self.stop()
        else:
            await interaction.response.send_message("Você já não está mais na lista.", ephemeral=True)
            


@bot.tree.command(name="teste", description="descrição teste")
async def teste(interaction: discord.Interaction):
    await interaction.response.send_message("Hello World")


bot.run(TOKEN)