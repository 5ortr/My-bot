import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os

# إعدادات البوت والـ Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قائمة حفظ المشتركين في Broadcast (في بيئة الإنتاج يفضل استخدام قاعدة بيانات)
subscribed_users = set()

# إعدادات ثابتة (قم بتغيير ID الرتبة التلقائية)
AUTO_ROLE_ID = 123456789012345678  # استبدل هذا بـ ID الرتبة للـ Auto Role

@bot.event
async def on_ready():
    print(f'تم تسجيل الدخول بنجاح باسم: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"تم مزامنة {len(synced)} أمر slash.")
    except Exception as e:
        print(f"خطأ في مزامنة الأوامر: {e}")

# ================= 1. AUTO ROLE & WELCOME =================
@bot.event
async def on_member_join(member):
    # إعطاء رتبة تلقائية
    role = member.guild.get_role(AUTO_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"تعذر إعطاء الرتبة: {e}")

    # إرسال رسالة ترحيب في القناة المخصصة (أو أول قناة نصية)
    welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome") or member.guild.system_channel
    if welcome_channel:
        embed = discord.Embed(
            title="أهلاً بك في السيرفر! 🎉",
            description=f"مرحباً بك {member.mention}، يسعدنا انضمامك إلينا!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await welcome_channel.send(embed=embed)

# ================= 2. MODERATION COMMANDS =================
@bot.tree.command(name="kick", description="طرد عضو من السيرفر")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"✅ تم طرد {member.mention} | السبب: {reason}")

@bot.tree.command(name="ban", description="حظر عضو من السيرفر")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚫 تم حظر {member.mention} | السبب: {reason}")

@bot.tree.command(name="mute", description="كتم عضو لفترة معينة (بالدقائق)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "لا يوجد سبب"):
    duration = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 تم ميوت {member.mention} لمدة {minutes} دقيقة.")

# ================= 3. EMBED MAKER =================
@bot.tree.command(name="embed", description="إنشاء رسالة إعلانية بتصميم مرتب")
@app_commands.checks.has_permissions(manage_messages=True)
async def create_embed(interaction: discord.Interaction, title: str, description: str, color_hex: str = "3498db"):
    color = int(color_hex.replace("#", ""), 16)
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=f"أُرسلت بواسطة {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

# ================= 4. BROADCAST SYSTEM =================
@bot.tree.command(name="subscribe_broadcast", description="الاشتراك في تلقي الإعلانات بالخاص")
async def subscribe(interaction: discord.Interaction):
    subscribed_users.add(interaction.user.id)
    await interaction.response.send_message("✅ تم إضافتك لقائمة استلام الإعلانات بالخاص!", ephemeral=True)

@bot.tree.command(name="broadcast", description="إرسال إعلان لجميع المشتركين")
@app_commands.checks.has_permissions(administrator=True)
async def broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    count = 0
    for user_id in subscribed_users:
        user = await bot.fetch_user(user_id)
        if user:
            try:
                await user.send(f"📢 **إعلان هام:**\n{message}")
                count += 1
            except:
                pass
    await interaction.followup.send(f"📬 تم إرسال الإعلان إلى {count} مشترك بنجاح!")

# ================= 5. TICKETS SYSTEM =================
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="فتح تكت دعم 📩", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", overwrites=overwrites)
        
        embed = discord.Embed(title="تكت الدعم الفني", description="يرجى كتابة مشكلتك وسيقوم فريق الدعم بالرد عليك.", color=discord.Color.blue())
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"تم فتح التكت: {channel.mention}", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التكت 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التكت خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="setup_tickets", description="نشر لوحة التكتات")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(title="مركز الدعم الفني", description="اضغط على الزر أدناه لفتح تكت دعم جديد.", color=discord.Color.gold())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("تم إرسال لوحة التكتات!", ephemeral=True)

# تشغيل البوت عبر التوكن المأخوذ من متغيرات البيئة
bot.run(os.getenv("DISCORD_TOKEN"))
