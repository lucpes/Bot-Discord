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
        super().__init__(
            command_prefix = "/",           # prefixo para chamar o bot
            intents = intents
        )
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        await self.tree.sync()      # mexer aqui para adicionar comandos diferentes para mais de um servidor
        
    async def on_ready(self):       # ligar o bot
        print(f"O Bot {self.user} foi ligado com sucesso")
        
bot = Bot()

@bot.tree.command(name="embed_register",description="Registrar")
async def enviarembed(ctx):
    embed_register = discord.Embed(
        title = "Registre-se",
        description = "Descrição registro",
        colour = 16711680
    )
    
    embed.set_author(name="Autor",
    icon_url="https://cdn2.steamgriddb.com/icon/c8b9abffb45bf79a630fb613dcd23449/24/256x256.png")
    
    embed.set_thumbnail
    

@bot.tree.command(name="teste",description="descrição teste")
async def teste(interaction:discord.Interaction):
    await interaction.response.send_message("Hello World")
    
@bot.tree.command(name="farm",description="Insira seu farm aqui")
@app_commands.describe(
    ferro="Insira a quantidade de ferro que você está colocando no baú",
    alumínio="Insira a quantidade de alumínio que você está colocando no baú",
    cobre="Insira a quantidade de cobre que você está colocando no baú",
    titânio="Insira a quantidade de titânio que você está colocando no baú"
)
async def farm(interaction:discord.Interaction, ferro:int, alumínio:int, cobre:int, titânio:int):
    
    await interaction.response.send_message("Farm cadastrado com sucasso!", ephemeral=True)   # ephemeral manda mensagem privada





bot.run(TOKEN)  # roda o bot usando o token