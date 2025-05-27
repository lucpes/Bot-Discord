import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


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

#============================================================================================================================================#

# Ligar os botões quando o bot inicializa ou reinicia !

@bot.event
async def on_ready():
    print(f"Bot está online como {bot.user}!")
    
    # Registrar a View persistente
    bot.add_view(RegisterButton())
    bot.add_view(ApproveButton())

#============================================================================================================================================#




class RegisterButton(discord.ui.View):                            # Classe do Botão de se registrar
    def __init__(self):
        super().__init__(timeout=None)  # ❗ Faz com que o botão não expire NUNCA

    @discord.ui.button(
        label="Registrar",
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
            await interaction.response.send_message("❌ ID do usuário não encontrado no embed.", ephemeral=True)
            return

        user_id = int(footer_text.split("ID do usuário:")[1].strip())

        # 🎯 Obter o membro e os cargos
        guild = interaction.guild
        member = guild.get_member(user_id)
        cargo_aprovado = guild.get_role(1376997518314963084)  # Cargo para membros aprovados
        cargo_gerente = guild.get_role(1377010279640076368)  # 🚨 Substitua com o ID real do cargo Gerente

        if not member or not cargo_aprovado:
            await interaction.response.send_message("❌ Membro ou cargo não encontrado.", ephemeral=True)
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
            await interaction.response.send_message("❌ Permissões insuficientes para modificar o usuário.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Erro ao modificar o usuário: {e}", ephemeral=True)
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



class RegisterModal(discord.ui.Modal, title="📜Formulário de Registro📜"):              # Classe do formulário de registro
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
    await interaction.response.send_message("Embed enviado com sucesso!", ephemeral=True)
    
    

    
    
    



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