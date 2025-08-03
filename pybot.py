import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import asyncio
from threading import Thread
from flask import Flask, jsonify

# Cargar variables de entorno
load_dotenv()

# ===== SERVIDOR WEB PARA RENDER =====
app = Flask(__name__)

@app.route('/')
def home():
    if hasattr(bot, 'user') and bot.user:
        return f"""
        <h1>🤖 Bot Discord Activo</h1>
        <p><strong>Bot:</strong> {bot.user}</p>
        <p><strong>Servidores:</strong> {len(bot.guilds)}</p>
        <p><strong>Uptime:</strong> {datetime.now() - bot.start_time if hasattr(bot, 'start_time') else 'Iniciando...'}</p>
        <p><strong>Status:</strong> ✅ Online</p>
        """
    else:
        return "<h1>🤖 Bot Discord</h1><p>🔄 Conectando...</p>"

@app.route('/health')
def health():
    return jsonify({
        "status": "alive",
        "bot": str(bot.user) if hasattr(bot, 'user') and bot.user else "connecting",
        "guilds": len(bot.guilds) if hasattr(bot, 'guilds') else 0,
        "uptime": str(datetime.now() - bot.start_time) if hasattr(bot, 'start_time') else None
    })

@app.route('/ping')
def ping():
    return "pong"

def run_flask():
    # Render provee el puerto en la variable PORT
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """Inicia el servidor web en un hilo separado"""
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    print(f"🌐 Servidor web iniciado en puerto {os.environ.get('PORT', 10000)}")

# ===== BOT DISCORD =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Variables globales para el timer
timer_start = None
timer_running = False
timer_paused_time = timedelta(0)

# Archivo para guardar datos
DATA_FILE = 'bot_data.json'

def load_data():
    """Cargar datos desde archivo JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"strikes": {}}

def save_data(data):
    """Guardar datos en archivo JSON"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def format_time(delta):
    """Formatear tiempo en HH:MM:SS"""
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@bot.event
async def on_ready():
    bot.start_time = datetime.now()
    print(f'✅ {bot.user} conectado exitosamente!')
    print(f'📊 Bot está en {len(bot.guilds)} servidor(es)')
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Sincronizados {len(synced)} comandos slash')
    except Exception as e:
        print(f'❌ Error sincronizando comandos: {e}')

# Comandos del Timer
@bot.tree.command(name="timer_start", description="Iniciar el cronómetro")
async def timer_start(interaction: discord.Interaction):
    global timer_start, timer_running, timer_paused_time
    
    if timer_running:
        await interaction.response.send_message("⏰ El timer ya está corriendo!", ephemeral=True)
        return
    
    timer_start = datetime.now() - timer_paused_time
    timer_running = True
    
    embed = discord.Embed(
        title="⏰ Timer Iniciado",
        description="El cronómetro ha comenzado a contar!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="timer_stop", description="Pausar el cronómetro")
async def timer_stop(interaction: discord.Interaction):
    global timer_running, timer_paused_time
    
    if not timer_running:
        await interaction.response.send_message("⏸️ El timer no está corriendo!", ephemeral=True)
        return
    
    if timer_start:
        timer_paused_time = datetime.now() - timer_start
    timer_running = False
    
    embed = discord.Embed(
        title="⏸️ Timer Pausado",
        description=f"Tiempo actual: **{format_time(timer_paused_time)}**",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="timer_reset", description="Reiniciar el cronómetro a 00:00:00")
async def timer_reset(interaction: discord.Interaction):
    global timer_start, timer_running, timer_paused_time
    
    timer_start = None
    timer_running = False
    timer_paused_time = timedelta(0)
    
    embed = discord.Embed(
        title="🔄 Timer Reiniciado",
        description="El cronómetro ha sido reiniciado a **00:00:00**",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="timer_show", description="Mostrar el tiempo actual del cronómetro")
async def timer_show(interaction: discord.Interaction):
    if timer_running and timer_start:
        current_time = datetime.now() - timer_start
    elif timer_paused_time.total_seconds() > 0:
        current_time = timer_paused_time
    else:
        current_time = timedelta(0)
    
    status = "🟢 Corriendo" if timer_running else "⏸️ Pausado" if timer_paused_time.total_seconds() > 0 else "⏹️ Detenido"
    
    embed = discord.Embed(
        title="⏰ Estado del Timer",
        description=f"**Tiempo:** {format_time(current_time)}\n**Estado:** {status}",
        color=discord.Color.green() if timer_running else discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

# Comandos de Strikes
@bot.tree.command(name="strike", description="Añadir un strike a un usuario")
async def add_strike(interaction: discord.Interaction, usuario: discord.Member):
    data = load_data()
    user_id = str(usuario.id)
    
    if user_id not in data["strikes"]:
        data["strikes"][user_id] = {"name": usuario.display_name, "count": 0}
    
    data["strikes"][user_id]["count"] += 1
    data["strikes"][user_id]["name"] = usuario.display_name
    save_data(data)
    
    embed = discord.Embed(
        title="⚠️ Strike Añadido",
        description=f"**{usuario.display_name}** ahora tiene **{data['strikes'][user_id]['count']}** strike(s)",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="strikes", description="Ver todos los strikes")
async def show_strikes(interaction: discord.Interaction):
    data = load_data()
    strikes = data["strikes"]
    
    if not strikes:
        embed = discord.Embed(
            title="📊 Tabla de Strikes",
            description="No hay strikes registrados",
            color=discord.Color.green()
        )
    else:
        sorted_strikes = sorted(strikes.items(), key=lambda x: x[1]["count"], reverse=True)
        
        description = ""
        for i, (user_id, user_data) in enumerate(sorted_strikes, 1):
            description += f"{i}. **{user_data['name']}**: {user_data['count']} strike(s)\n"
        
        embed = discord.Embed(
            title="📊 Tabla de Strikes",
            description=description,
            color=discord.Color.orange()
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="strikes_reset", description="Resetear todos los strikes")
async def reset_strikes(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden resetear strikes!", ephemeral=True)
        return
    
    data = load_data()
    data["strikes"] = {}
    save_data(data)
    
    embed = discord.Embed(
        title="🔄 Strikes Reseteados",
        description="Todos los strikes han sido eliminados",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove_strike", description="Quitar un strike a un usuario")
async def remove_strike(interaction: discord.Interaction, usuario: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo los administradores pueden quitar strikes!", ephemeral=True)
        return
    
    data = load_data()
    user_id = str(usuario.id)
    
    if user_id not in data["strikes"] or data["strikes"][user_id]["count"] <= 0:
        await interaction.response.send_message(f"❌ {usuario.display_name} no tiene strikes para quitar!", ephemeral=True)
        return
    
    data["strikes"][user_id]["count"] -= 1
    if data["strikes"][user_id]["count"] <= 0:
        del data["strikes"][user_id]
    
    save_data(data)
    
    remaining = data["strikes"].get(user_id, {}).get("count", 0)
    embed = discord.Embed(
        title="✅ Strike Removido",
        description=f"**{usuario.display_name}** ahora tiene **{remaining}** strike(s)",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help_timer", description="Ver todos los comandos disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Comandos del Bot Timer",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="⏰ Comandos de Timer",
        value="`/timer_start` - Iniciar cronómetro\n"
              "`/timer_stop` - Pausar cronómetro\n"
              "`/timer_reset` - Reiniciar a 00:00:00\n"
              "`/timer_show` - Ver tiempo actual",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Comandos de Strikes",
        value="`/strike @usuario` - Añadir strike\n"
              "`/strikes` - Ver tabla de strikes\n"
              "`/remove_strike @usuario` - Quitar strike (Admin)\n"
              "`/strikes_reset` - Resetear todos (Admin)",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="render_status", description="Ver estado del hosting en Render")
async def render_status(interaction: discord.Interaction):
    uptime = datetime.now() - bot.start_time if hasattr(bot, 'start_time') else "Desconocido"
    
    embed = discord.Embed(
        title="🌐 Estado de Render",
        color=discord.Color.green()
    )
    embed.add_field(name="Hosting", value="Render.com", inline=True)
    embed.add_field(name="Uptime", value=str(uptime).split('.')[0], inline=True)
    embed.add_field(name="Servidores", value=len(bot.guilds), inline=True)
    embed.add_field(name="Puerto Web", value=os.environ.get('PORT', '10000'), inline=True)
    
    await interaction.response.send_message(embed=embed)

# ===== EJECUCIÓN PRINCIPAL =====
if __name__ == "__main__":
    # Verificar token
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN no encontrado!")
        print("🔧 SOLUCIONES:")
        print("   - Local: Crea archivo .env con DISCORD_TOKEN=tu_token")  
        print("   - Hosting: Configura variable de entorno DISCORD_TOKEN")
        exit(1)
    
    # Iniciar servidor web (para Render)
    keep_alive()
    
    # Iniciar bot
    print("🚀 Iniciando bot...")
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token inválido! Verifica tu DISCORD_TOKEN")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")