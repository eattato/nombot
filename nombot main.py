import discord
from discord import app_commands
from discord.ext import commands

import mariadb
import json
import pandas as pd
from datetime import datetime
from pytz import timezone

guildId = 820582732219547728
#guildId = 1044579957214556180
client = discord.Client(intents=discord.Intents.default())

tree = app_commands.CommandTree(client)
conn = None # db 연결
cur = None

# private functions
def getAccount(id):
    queryString = f"select * from nombot.members where id = {id}"
    userData = pd.read_sql(queryString, conn)
    if userData.shape[0] == 0:
        print("유저 계정을 생성했습니다!")
        userData = pd.DataFrame.from_dict({
            "id": [id],
            "cash": [0],
            "debt": [0],
            "lastseen": [None],
            "streak": [0]
        })
        queryString = f"insert into nombot.members values('{id}', 0, 0, NULL, 0)"
        cur.execute(queryString)
    userData = userData.iloc[0]
    return userData

def saveAccount(account, saves):
    queryList = []
    queryListStr = ""
    for key, val in account.iteritems():
        if key in saves:
            if val != None:
                queryList.append(f"{key} = '{val}'")
            else:
                queryList.append(f"{key} = null")
    for ind, queryData in enumerate(queryList):
        queryListStr += queryData
        if ind != len(queryList) - 1:
            queryListStr += ", "

    queryString = f"update nombot.members set {queryListStr} where id = {account['id']};"
    cur.execute(queryString)
    conn.commit()
    print("계정을 저장했습니다.")

def log(user, target, act, amount):
    queryString = f"insert into nombot.moneylog values('{user}', '{target}', {act}, {amount}, '{getCurrentTime()}')"
    cur.execute(queryString)
    conn.submit()

def getCurrentTime():
    return datetime.now()

def timeFormat(target):
    return target.strftime("%Y-%m-%d %H:%M:%S")

def stringToTime(target):
    return datetime.strptime(target, "%Y-%m-%d %H:%M:%S")

def getCurrentEconomy():
    queryString = "select * from nombot.economy"
    economyData = pd.read_sql(queryString, conn)
    return economyData.iloc[0]

# client events
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guildId))
    print("서버 로드 완료")

# slash commands
@tree.command(name="계좌", description="현재 내 계좌의 금액과 빚을 조회합니다.", guild=discord.Object(guildId))
async def account(interaction):
    account = getAccount(interaction.user.id)
    idk = "몰?루 "
    embed = discord.Embed(
        description=f"현금 {account['cash']}원\n"
                    + f"빚 {account['debt']}원\n"
                    + f"보유 주식 가치 {idk}원\n\n"
                    + f"보유 자산 {idk}원\n"
                    + f"보유 부채 {idk}원\n"
                    + f"보유 자본 {idk}원",
        color=0x00FF00,
    )
    embed.set_author(
        name=f"{interaction.user.display_name}님의 계좌",
        icon_url=interaction.user.display_avatar
    )
    await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="출근", description="하루의 출석을 인증받고 500원을 받으세요!", guild=discord.Object(guildId))
async def check(interaction):
    account = getAccount(interaction.user.id)

    # 아예 출첵 기록이 없거나 출첵 기록 하루 이후라면
    if account["lastseen"] == None or (account["lastseen"] - getCurrentTime()).days >= 1:
        earn = 500
        desc = f"오늘로 {account['streak'] + 1}일 연속으로 출석하셨습니다!\n"

        current = account['streak'] + 1
        if current % 336 == 0: # 1년 연속 출석
            earn += 100000
            desc += f"{(account['streak'] + 1) // 365}년 동안 매일 출석하셨군요! 정말 대단하네요!\n"
        elif current % 28 == 0: # 1달 연속 출석
            earn += 5000
            desc += f"{(account['streak'] + 1) // 28}달 동안 매일 출석하셨군요! 대단하네요!\n"
        elif current % 7 == 0: # 1주 연속 출석
            earn += 1000
            desc += f"{(account['streak'] + 1) // 7}주 동안 매일 출석하셨군요! 축하드립니다!\n"
        desc += f"{earn}원 적립해 {account['cash'] + earn}원이 되었습니다!\n"
        
        # 계정 정보 업데이트
        account["cash"] += earn
        account["lastseen"] = timeFormat(getCurrentTime())
        account["streak"] += 1
        saveAccount(account, ["cash", "lastseen", "streak"])

        # 메시지 포맷 & 전송
        embed = discord.Embed(
            description=desc,
            color=0x00FF00
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 출석했습니다.",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)
    else: # 이미 출석한 경우
        dateLeft = account["lastseen"] - getCurrentTime()
        hour = dateLeft.seconds // 3600
        minute = (dateLeft.seconds - 3600 * hour) // 60

        dateLeftStr = f"{hour}시간 {minute}분 {dateLeft.seconds % 60}초"
        embed = discord.Embed(
            description=f"오늘은 이미 출석하셨네요!\n"
                        + f"다음 출석까지 {dateLeftStr} 남았습니다.",
            color=0xFF0000
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님은 이미 출석했습니다.",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="송금", description="대상 유저에게 돈을 전송합니다.", guild=discord.Object(guildId))
async def send(interaction, member: discord.Member, amount: int):
    if amount > 0 and amount <= 5000:
        account = getAccount(interaction.user.id)
        targetAccount = getAccount(member.id)

        if account["cash"] >= amount:
            account["cash"] -= amount
            targetAccount["cash"] += amount
            saveAccount(account, ["cash"])
            saveAccount(targetAccount, ["cash"])

            embed = discord.Embed(
                description=f"{member.display_name}님에게 {amount}원을 송금했습니다!\n{account['cash']}원 남았습니다.",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {amount}원 송금!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
        else:
            required = -(account["cash"] - amount)
            embed = discord.Embed(
                description=f"돈이 {required}원 부족합니다..",
                color=0xFF0000
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {amount}원 송금!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            description=f"이런, 돈은 1 ~ 5000원까지만 보낼 수 있어요.",
            color=0xFF0000
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {amount}원 송금!",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="금리", description="이번 주의 금리 상황을 확인합니다.", guild=discord.Object(guildId))
async def checkRate(interaction):
    economy = getCurrentEconomy()
    currentTime = getCurrentTime()
    embed = discord.Embed(
        title="금리 상황",
        description=
            f"{currentTime.year}년 {currentTime.month}월 {currentTime.day // 7 + 1}주차, 현재 금리는 {economy['rate'] * 100}% 입니다.\n\n"
            + f"금리 변동률 : ± {economy['ratechange'] * 100}%\n"
            + f"최저 금리 : ± {economy['ratemin'] * 100}%\n"
            + f"최대 금리 : ± {economy['ratemax'] * 100}%",
        color=0x00FFFF
    )
    await interaction.response.send_message(content=None, embed=embed)

# company commands
@tree.command(name="기업설립", description="10000원을 소모해 기업을 만들고 20주를 가집니다.", guild=discord.Object(guildId))
async def createCompany(interaction, name: str):
    account = getAccount(interaction.user.id)
    if account["cash"] >= 10000:
        if len(name) > 0 and len(name) <= 50:
            cur.execute(f"insert into nombot.company(comowner, comname, stock, cash) values('{interaction.user.id}', '{name}', 500, 0)")
            #cur.execute(f"insert into nombot.stock values('{interaction.user.id}', '{name}', 500, 0)") 주식 추가, 근데 auto_increment 값 구해야함
            conn.commit()

            embed = discord.Embed(
                description=f"{interaction.user.display_name}님이 기업 {name}를 설립했습니다!",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 기업 {name}를 설립했습니다!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
        else:
            embed = discord.Embed(
                title="기업 설립",
                description="기업 이름은 최대 1 ~ 50자 입니다!",
                color=0xFF0000
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="기업 설립",
            description="기업 설립 자금이 부족합니다! 10000원 이상의 현금을 가져오세요!",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="금리설정", description="[관리자 전용] 현재 금리 값을 설정합니다.", guild=discord.Object(guildId))
async def updateRate(interaction, rate: float, rateMin: float, rateMax: float, rateChange: float):
    if interaction.user.hasPermission("ADMINISTRATOR"):
        if rate >= 0 and rate <= 1 and rateMin >= 0 and rateMin <= 1 and rateMax >= 0 and rateMax <= 1 and rateChange >= 0 and rateChange <= 1 and rateMin <= rateMax:
            queryString = f"update nombot.economy set rate = {rate}, ratemin = {rateMin}, ratemax = {rateMax}, ratechange = {rateChange}"
            cur.execute(queryString)
            conn.commit()

            embed = discord.Embed(
                title="금리 설정",
                description="금리를 성공적으로 설정하였습니다!",
                color=0x00FF00
            )
            await interaction.response.send_message(content=None, embed=embed)
        else:
            embed = discord.Embed(
                title="금리 설정",
                description="금리를 설정하는데 실패했습니다.\n모든 매개변수는 0 이상 1 이하여야 합니다.",
                color=0xFF0000
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="금리 설정",
            description="관리자 전용 기능입니다!",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

# main
try:
    # db 연결
    with open("db.json") as dbConfig:
        dbConfig = json.load(dbConfig)
        conn = mariadb.connect(**dbConfig) # 딕셔너리를 파라미터로 변환
        cur = conn.cursor()
        print("데이터 베이스 연결 완료")

    # 토큰 로드 & 실행
    with open("token.txt") as token:
        token = token.readline()
        client.run(token)
except FileNotFoundError:
    print("token.txt 파일이 존재하지 않습니다!")
except discord.LoginFailure:
    print("해당 봇 계정으로 로그인 할 수 없습니다!")
except mariadb.Error as e:
    print("데이터 베이스 연결 실패\n{}".format(e))