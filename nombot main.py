import discord
from discord import app_commands
import mariadb

guildId = 820582732219547728
#guildId = 1044579957214556180
client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)

# client events
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guildId))
    print("서버 로드 완료")

# slash commands
@tree.command(name="출첵", description="하루의 출석을 인증받고 500원을 받으세요!", guild=discord.Object(guildId))
async def check(interaction):

    print(interaction.user.id)
    await interaction.response.send_message("출첵")

# main
try:
    conn = mariadb.connect(
        user="jm-han",
        password="jm-han",
        host="34.64.154.53",
        port=3306,
        database="real_estate"
    )

    with open("token.txt") as token:
        token = token.readline()
        client.run(token)
except FileNotFoundError:
    print("token.txt 파일이 존재하지 않습니다!")
except discord.LoginFailure:
    print("해당 봇 계정으로 로그인 할 수 없습니다!")
except mariadb.Error as e:
    print("데이터 베이스 연결 실패\n{}".format(e))