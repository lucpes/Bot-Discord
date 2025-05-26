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

class RegisterButton(discord.ui.View):
    @discord.ui.button(label="Registrar", style=discord.ButtonStyle.success, custom_id="register_button")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Você clicou no botão de registro!", ephemeral=True)


@bot.tree.command(name="embed_register", description="Registrar")
async def enviarembed(interaction: discord.Interaction):
    embed_register = discord.Embed(
        title="Registre-se",
        description="Clique no botão abaixo para se registrar.",
        colour=discord.Color.red()
    )
    embed_register.set_author(
        name="Autor",
        icon_url="https://cdn2.steamgriddb.com/icon/c8b9abffb45bf79a630fb613dcd23449/24/256x256.png"
    )
    embed_register.set_thumbnail(
        url="https://cdn2.steamgriddb.com/icon/c8b9abffb45bf79a630fb613dcd23449/24/256x256.png"
    )
    embed_register.add_field(name="Importante", value="Leia as regras com atenção!", inline=False)
    embed_register.set_footer(text="Bot criado pela cara mais foda")
    
    view = RegisterButton()
    await interaction.response.send_message(embed=embed_register, view=view)

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