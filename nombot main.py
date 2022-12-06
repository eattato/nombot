import discord
from discord import app_commands

import mariadb
import json
import pandas as pd
import numpy as np
from datetime import datetime
from pytz import timezone
import random
import asyncio
import math
import cv2
from PIL import ImageFont, ImageDraw, Image
import io

guildId = 820582732219547728
#guildId = 1044579957214556180
client = discord.Client(intents=discord.Intents.default())

tree = app_commands.CommandTree(client)
conn = None # db 연결
cur = None
tajaList = []
tajaFont = None

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
    for key, val in account.items():
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

def decimalComma(num):
    num = str(num)
    result = ""
    for ind, char in enumerate(num[::-1]):
        result = char + result
        if (ind + 1) % 3 == 0 and ind != len(num) - 1:
            result = "," + result
    return result

def log(user, target, act, amount):
    queryString = f"insert into nombot.moneylog values('{user}', '{target}', {act}, {amount}, '{getCurrentTime()}')"
    cur.execute(queryString)
    conn.submit()

def getCurrentTime():
    return datetime.now()
    target.seconds = 0
    return target

def timeFormat(target):
    return target.strftime("%Y-%m-%d %H:%M:%S")

def stringToTime(target):
    return datetime.strptime(target, "%Y-%m-%d %H:%M:%S")

def getCurrentEconomy():
    queryString = "select * from nombot.economy"
    economyData = pd.read_sql(queryString, conn)
    return economyData.iloc[0]

async def gamble(interaction, name, stake, callback, stakeLimitMin=None, stakeLimitMax=None):
    if (stakeLimitMin == None and stakeLimitMax == None) or (stakeLimitMin <= stake <= stakeLimitMax):
        account = getAccount(interaction.user.id)
        if account["cash"] >= stake:
            await callback(account, stake)
        else: # 돈이 없음
            embed = discord.Embed(
                title=name,
                description=f"가지고 있는 돈이 제시한 판돈보다 적습니다!\n"
                            + f"현재 소지금 : {decimalComma(account['cash'])}원\n판돈 : {decimalComma(stake)}원",
                color=0xFF0000
            )
            await interaction.response.send_message(content=None, embed=embed)
    else: # 판돈 파라미터 에러
        embed = discord.Embed(
            title=name,
            description=f"판돈은 최대 {decimalComma(stakeLimitMin)} ~ {decimalComma(stakeLimitMax)}원 입니다.",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

def clearWork(id):
    cur.execute(f"delete from nombot.workdata where worker = {id}")
    conn.commit()

def setWork(id, worktype, question, answer, reward):
    cur.execute(f"insert into nombot.workdata values('{id}', '{worktype}', '{question}', '{answer}', {reward})")
    conn.commit()

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
        description=f"현금 {decimalComma(account['cash'])}원\n"
                    + f"빚 {decimalComma(account['debt'])}원\n"
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
    if account["lastseen"] == None or (getCurrentTime() - account["lastseen"].replace(hour=0, minute=0, second=0)).days >= 1:
        earn = 500
        desc = f"오늘로 {decimalComma(account['streak'] + 1)}일 연속으로 출석하셨습니다!\n"

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
        desc += f"{decimalComma(earn)}원 적립해 {decimalComma(account['cash'] + earn)}원이 되었습니다!\n"
        
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
        dateLeft = account["lastseen"].replace(hour=0, minute=0, second=0) - getCurrentTime()
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
                description=f"{member.display_name}님에게 {decimalComma(amount)}원을 송금했습니다!\n"
                            + f"{decimalComma(account['cash'])}원 남았습니다.",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {decimalComma(amount)}원 송금!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
        else:
            required = -(account["cash"] - amount)
            embed = discord.Embed(
                description=f"돈이 {decimalComma(required)}원 부족합니다..",
                color=0xFF0000
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {decimalComma(amount)}원 송금!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            description=f"이런, 돈은 1 ~ 5000원까지만 보낼 수 있어요.",
            color=0xFF0000
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 {member.display_name}님에게 {decimalComma(amount)}원 송금!",
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
async def updateRate(interaction, rate: float, ratemin: float, ratemax: float, ratechange: float):
    if interaction.user.hasPermission("ADMINISTRATOR"):
        if rate >= 0 and rate <= 1 and ratemin >= 0 and ratemin <= 1 and ratemax >= 0 and ratemax <= 1 and ratechange >= 0 and ratechange <= 1 and ratemin <= ratemax:
            queryString = f"update nombot.economy set rate = {rate}, ratemin = {ratemin}, ratemax = {ratemax}, ratechange = {ratechange}"
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

@tree.command(name="돈복사", description="디버깅용 돈 복사기", guild=discord.Object(guildId))
async def addMoney(interaction, amount: int):
    account = getAccount(interaction.user.id)
    account["cash"] += amount
    saveAccount(account, ["cash"])
    await interaction.response.send_message("ㅇㅋ")

# gamble
@tree.command(name="반반도박", description="500 ~ 3000원을 소모해 50% 확률로 판돈의 절반을 잃거나 얻습니다.", guild=discord.Object(guildId))
async def gambleHalf(interaction, stake: int):
    async def callback(account, stake):
        result = random.randint(0, 1)
        if result == 0:
            account["cash"] += stake // 2
            embed = discord.Embed(
                description=f"반반 도박 성공!\n"
                            + f"판돈 {decimalComma(stake)}원을 걸어 {decimalComma(stake // 2)}원을 벌었습니다.\n"
                            + f"현재 소지금 : {decimalComma(account['cash'])}원",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 반반 도박 성공!",
                icon_url=interaction.user.display_avatar
            )
        else:
            account["cash"] -= stake // 2
            embed = discord.Embed(
                description=f"반반 도박 실패..\n"
                            + f"판돈 {decimalComma(stake)}원을 걸어 {decimalComma(stake // 2)}원을 잃었습니다.\n"
                            + f"현재 소지금 : {decimalComma(account['cash'])}원",
                color=0xFF0000
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 반반 도박 실패..",
                icon_url=interaction.user.display_avatar
            )
        saveAccount(account, ["cash"])
        await interaction.response.send_message(content=None, embed=embed)
    await gamble(interaction, "반반 도박", stake, stakeLimitMin=500, stakeLimitMax=3000, callback=callback)

@tree.command(name="주사위", description="500 ~ 3000원을 소모해 봇 보다 높은 주사위 합이 나오면 돈을 얻습니다.", guild=discord.Object(guildId))
async def gambleDice(interaction, stake: int):
    async def callback(account, stake):
        playerDice = [random.randint(1, 6), random.randint(1, 6)]
        enemyDice = [random.randint(1, 6), random.randint(1, 6)]
        result = 0
        if sum(playerDice) > sum(enemyDice):
            result = 1
            account["cash"] += stake
            saveAccount(account, ["cash"])
        elif sum(playerDice) < sum(enemyDice):
            result = -1
            account["cash"] -= stake
            saveAccount(account, ["cash"])
        else:
            result = 0

        embed = discord.Embed(
            description=f"주사위를 굴려라!\n"
                        + f"내 주사위 : {playerDice[0]}\n"
                        + f"봇 주사위 : {enemyDice[0]}\n\n"
                        + f"판돈 : {decimalComma(stake)}원",
            color = 0xAAAAAA
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 주사위 도박 중 입니다..",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)
        await asyncio.sleep(0.5)

        embed.description="주사위를 굴려라!\n"
        + f"내 주사위 : {playerDice[0]} + {playerDice[1]}\n"
        + f"봇 주사위 : {enemyDice[0]} + {enemyDice[1]}\n\n"
        + f"판돈 : {decimalComma(stake)}원"
        await interaction.edit_original_response(content=None, embed=embed)
        await asyncio.sleep(0.5)

        embed.description = (
            f"주사위를 굴려라!\n"
            + f"내 주사위 : {playerDice[0]} + {playerDice[1]} = {sum(playerDice)}\n"
            + f"봇 주사위 : {enemyDice[0]} + {enemyDice[1]} = {sum(enemyDice)}\n\n"
        )
        if result == 0:
            embed.description += f"무승부!\n현재 소지금 : {decimalComma(account['cash'])}원"
            embed.set_author(
                name=f"{interaction.user.display_name}님이 주사위 도박 무승부",
                icon_url=interaction.user.display_avatar
            )
        elif result == 1:
            embed.description += f"주사위 도박 성공!\n"
            + f"판돈 {decimalComma(stake)}원을 벌었습니다.\n"
            + f"현재 소지금 : {decimalComma(account['cash'])}원"
            embed.color = 0x00FF00
            embed.set_author(
                name=f"{interaction.user.display_name}님이 주사위 도박 성공",
                icon_url=interaction.user.display_avatar
            )
        elif result == -1:
            embed.description += f"주사위 도박 실패..\n판돈 {decimalComma(stake)}원을 잃었습니다.\n현재 소지금 : {decimalComma(account['cash'])}원"
            embed.color = 0xFF0000
            embed.set_author(
                name=f"{interaction.user.display_name}님이 주사위 도박 실패",
                icon_url=interaction.user.display_avatar
            )
        await interaction.edit_original_response(content=None, embed=embed)
        
    await gamble(interaction, "주사위 도박", stake, stakeLimitMin=500, stakeLimitMax=3000, callback=callback)

@tree.command(name="슬롯머신", description="100원을 소모해 슬롯 머신을 돌려 777을 만들면 누적된 돈을 모두 얻습니다.", guild=discord.Object(guildId))
async def gambleSlot(interaction):
    async def callback(account, stake):
        economy = getCurrentEconomy()
        slot = [random.randint(1, 9), random.randint(1, 9), random.randint(1, 9)]
        slotSpeed = [random.randint(1, 5), random.randint(1, 5), random.randint(1, 5)]
        slotSaves = []
        economy["jackpot"] += 100

        for roll in range(3):
            slotSave = []
            for ind, val in enumerate(slot):
                slot[ind] += slotSpeed[ind]
                if slot[ind] > 9:
                    slot[ind] = slot[ind] - 9
                slotSave.append(slot[ind])
            slotSaves.append(slotSave)

        if slot[0] == 7 and slot[1] == 7 and slot[2] == 7:
            cur.execute("update nombot.economy set jackpot = 0")
            account["cash"] += economy["jackpot"] - 100
        else:
            cur.execute("update nombot.economy set jackpot = jackpot + 100")
            account["cash"] -= 100
        saveAccount(account, ["cash"]) # save account 하면서 자동 커밋, 위의 execute도 커밋됨

        embed = discord.Embed(
            description=f"슬롯 머신을 돌려라!\n\n"
                        + f"{slotSaves[0][0]} {slotSaves[0][1]} {slotSaves[0][2]}\n\n"
                        + f"현재 누적금 : {decimalComma(economy['jackpot'])}원",
            color = 0xAAAAAA
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 슬롯 머신을 돌리는 중 입니다..",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)

        for i in range(1, 2 + 1):
            await asyncio.sleep(0.5)
            embed.description = (
                f"슬롯 머신을 돌려라!\n\n"
                + f"{slotSaves[i][0]} {slotSaves[i][1]} {slotSaves[i][2]}\n\n"
                + f"현재 누적금 : {decimalComma(economy['jackpot'])}원"
            )
            await interaction.edit_original_response(content=None, embed=embed)
        if slot[0] == 7 and slot[1] == 7 and slot[2] == 7:
            await asyncio.sleep(1)
            embed.description = (
                f"슬롯 머신을 돌려라!\n\n"
                + f"{slotSaves[i][0]} {slotSaves[i][1]} {slotSaves[i][2]}\n\n"
                + f"잭팟!\n{decimalComma(economy['jackpot'])}원을 받아 {decimalComma(account['cash'])}원이 되었습니다!"
            )
            embed.color = 0x00FF00
            embed.set_author(
                name=f"{interaction.user.display_name}님이 잭팟을 터트렸습니다!",
                icon_url=interaction.user.display_avatar
            )
        else:
            embed.description = (
                f"슬롯 머신을 돌려라!\n\n"
                + f"{slotSaves[i][0]} {slotSaves[i][1]} {slotSaves[i][2]}\n\n"
                + f"실패!\n현재 누적금 : {decimalComma(economy['jackpot'])}원"
            )
            embed.color = 0xFF0000
            embed.set_author(
                name=f"{interaction.user.display_name}님이 슬롯 머신을 돌렸습니다.",
                icon_url=interaction.user.display_avatar
            )
        await interaction.edit_original_response(content=None, embed=embed)
        
    await gamble(interaction, "슬롯 머신", 100, callback=callback)

@tree.command(name="차용증", description="대상에게 차용증을 써 돈을 빌려줍니다. 매주 설정한 이자율만큼 대상의 빚이 늘어납니다.", guild=discord.Object(guildId))
async def privateDebt(interaction, member: discord.Member, amount: int, rate: float):
    account = getAccount(interaction.user.id)
    if amount > 0 and rate > 0 and rate <= 100:
        if account["cash"] >= amount:
            embed = discord.Embed(
                description="차용증을 DM으로 전송했습니다.",
                color=0x00FFFF
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 차용증 전송",
                icon_url=interaction.user.display_avatar
            )

            accept = discord.ui.Button(label="수락", style=discord.ButtonStyle.success)
            decline = discord.ui.Button(label="거절", style=discord.ButtonStyle.danger)
            async def accept_callback(interaction):
                accept.disabled = True
                decline.disabled = True
                account["cash"] += amount
                await dm.reply(
                    f"해당 차용증을 수락하였습니다.\n"
                    + f"매주 이자 {decimalComma(math.floor(amount * (rate / 100)))}원을 채무자에게 주어야합니다.\n"
                    + f"현재 소지금 : {decimalComma(account['cash'])}원"
                )
                await interaction.response.defer()
            async def decline_callback(interaction):
                accept.disabled = True
                decline.disabled = True
                await dm.reply("해당 차용증을 거절하였습니다.")
                await interaction.response.defer()

            accept.callback = accept_callback
            decline.callback = decline_callback
            view = discord.ui.View()
            view.add_item(accept)
            view.add_item(decline)

            await interaction.response.send_message(content=None, embed=embed)
            embed.description = (
                f"채권자 {interaction.user.display_name}\n"
                + f"채무자 {member.display_name}\n\n"
                + f"금액 {amount}원\n이자율 {rate}%\n\n"
                + f"해당 차용증 수락 시 채무자는 채권자에게 매주 이자로 {decimalComma(math.floor(amount * (rate / 100)))}원을 주어야하며, 원금 {decimalComma(amount)}원을 갚아야합니다.\n"
                + f"해당 차용증을 수락하시겠습니까?"
            )
            dm = await member.send(content=None, embed=embed, view=view)
        else:
            embed = discord.Embed(
                description=f"현금이 {decimalComma(-(amount - account['cash']))}원 부족합니다..",
                color=0xFF0000
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {member.display_name}님에게 차용증 전송",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            description=f"차용증 금액은 0원 이상, 이자율은 최대 0 ~ 100이여야 합니다.",
            color=0xFF0000
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 {member.display_name}님에게 차용증 전송",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)

# works
@tree.command(name="작업포기", description="지금 하고 있는 작업을 포기합니다.", guild=discord.Object(guildId))
async def giveup(interaction):
    data = pd.read_sql(f"select * from nombot.workdata where worker = {interaction.user.id}", conn)
    if data.shape[0] != 0:
        clearWork(interaction.user.id)

        embed = discord.Embed(
            description=f"{data.iloc[0]['worktype']} 작업을 포기했습니다.",
            color=0x00FF00
        )
        embed.set_author(
            name=f"{interaction.user.display_name}님이 작업을 포기했습니다.",
            icon_url=interaction.user.display_avatar
        )
        await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="작업 포기",
            description="현재 진행 중인 작업이 없습니다.",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="작업", description="작업을 선택해 완료하면 보수를 지급합니다. 작업포기를 사용해 취소할 수 있습니다.", guild=discord.Object(guildId))
async def giveup(interaction, work: str):
    data = pd.read_sql(f"select * from nombot.workdata where worker = {interaction.user.id}", conn)
    if data.shape[0] == 0:
        availableWorks = ["수학", "타자"]
        if work in availableWorks:
            embed = discord.Embed(
                description=f"```/작업제출```을 사용해 정답을 제출하세요!\n{work} 작업 중..\n\n",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {work} 작업을 하는 중 입니다..",
                icon_url=interaction.user.display_avatar
            )

            if work == "수학":
                operator = random.randint(1, 3)
                num1 = random.randint(1, 100)
                num2 = random.randint(1, 100)
                answer = ""
                if operator == 1:
                    operator = "+"
                    answer = f"{num1 + num2}"
                elif operator == 2:
                    operator = "-"
                    answer = f"{num1 - num2}"
                else:
                    operator = "x"
                    answer = f"{num1 * num2}"
                question = f"{num1} {operator} {num2} = ?"
                setWork(interaction.user.id, "수학", question, answer, 50)
                embed.description += f"밑의 수학 문제를 풀고 50원을 받으세요!\n{question}"
                await interaction.response.send_message(content=None, embed=embed)
            elif work == "타자":
                question = tajaList[random.randint(0, len(tajaList) - 1)]
                answer = question
                setWork(interaction.user.id, "타자", question, answer, 50)
                embed.description += f"밑의 문장을 그대로 입력하고 50원을 받으세요!"

                w,h,b,g,r,a = 20 * len(question),50,255,255,255,0
                img = np.zeros((h, w, 3), np.uint8) # 빈 RGB 채널 이미지 생성
                img[:] = (54, 57, 63) # 모든 픽셀 컬러 변경
                img = Image.fromarray(img) # PIL 이미지로 변경
                draw = ImageDraw.Draw(img)
                _, _, wt, ht = draw.textbbox((0, 0), question, font=tajaFont)
                draw.text(((w - wt) / 2, (h - ht) / 2), question, font=tajaFont, fill=(b, g, r, a)) # 텍스트 작성
                img = np.array(img) # cv2 포맷(numpy 배열)으로 변환
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                successed, buffer = cv2.imencode(".png", img)
                bytes = io.BytesIO(buffer) # BytesIO 스트림

                embed.set_image(url="attachment://taja.png")
                await interaction.response.send_message(content=None, embed=embed, file=discord.File(bytes, "taja.png"))
        else:
            embed = discord.Embed(
                title="작업",
                description=f"해당 작업이 존재하지 않습니다.",
                color=0xFF0000
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="작업",
            description=f"현재 {data.iloc[0]['worktype']} 작업을 진행하고 있어 다른 작업을 진행할 수 없습니다.",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

@tree.command(name="작업제출", description="작업을 선택해 완료하면 보수를 지급합니다. 작업포기를 사용해 취소할 수 있습니다.", guild=discord.Object(guildId))
async def giveup(interaction, answer: str):
    data = pd.read_sql(f"select * from nombot.workdata where worker = {interaction.user.id}", conn)
    if data.shape[0] != 0:
        workData = data.iloc[0]
        if answer == workData["answer"]:
            clearWork(interaction.user.id)
            account = getAccount(interaction.user.id)
            account["cash"] += workData["reward"]
            saveAccount(account, ["cash"])

            embed = discord.Embed(
                description=f"[{workData['worktype']}] {workData['question']}\n\n제출 : {answer}\n정답입니다!\n보상으로 {decimalComma(workData['reward'])}원을 받아 {decimalComma(account['cash'])}원이 되었습니다.",
                color=0x00FF00
            )
            embed.set_author(
                name=f"{interaction.user.display_name}님이 {workData['worktype']} 작업 성공!",
                icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(content=None, embed=embed)
        else:
            embed = discord.Embed(
                title="작업 제출",
                description=f"[{workData['worktype']}] {workData['question']}\n\n제출 : {answer}\n정답이 틀렸습니다!",
                color=0xFF0000
            )
            await interaction.response.send_message(content=None, embed=embed)
    else:
        embed = discord.Embed(
            title="작업 제출",
            description="현재 진행 중인 작업이 없습니다.",
            color=0xFF0000
        )
        await interaction.response.send_message(content=None, embed=embed)

# main
try:
    # db 연결
    with open("config/db.json") as dbConfig:
        dbConfig = json.load(dbConfig)
        conn = mariadb.connect(**dbConfig) # 딕셔너리를 파라미터로 변환
        cur = conn.cursor()
        print("데이터 베이스 연결 완료")

    # 타자 문장 가져옴
    with open("resource/taja.txt", encoding="utf8") as f:
        for line in f.readlines():
            tajaList.append(line.strip())
    print(f"타자 문장 {len(tajaList)}개 로드됨")

    # 타자용 폰트 가져옴
    tajaFont = ImageFont.truetype("resource/Galmuri9.ttf", 20)

    # 토큰 로드 & 실행
    with open("config/token.txt") as token:
        token = token.readline()
        client.run(token)
except FileNotFoundError:
    print("token.txt 파일이 존재하지 않습니다!")
except discord.LoginFailure:
    print("해당 봇 계정으로 로그인 할 수 없습니다!")
except mariadb.Error as e:
    print("데이터 베이스 연결 실패\n{}".format(e))