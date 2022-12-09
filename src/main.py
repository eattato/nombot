import nombot
import discord
from discord import app_commands

import os
import mariadb
import json
from pytz import timezone
from PIL import ImageFont, ImageDraw, Image

tajaList = []
tajaFont = None

# main
status = 0
try:
    # db 연결
    status = 1
    with open("../config/db.json") as dbConfig:
        dbConfig = json.load(dbConfig)
        conn = mariadb.connect(**dbConfig) # 딕셔너리를 파라미터로 변환
        cur = conn.cursor()
        print("데이터 베이스 연결 완료")

    # 타자 문장 가져옴
    status = 2
    with open("../resource/taja.txt", encoding="utf8") as f:
        for line in f.readlines():
            tajaList.append(line.strip())
    print(f"타자 문장 {len(tajaList)}개 로드됨")

    # 타자용 폰트 가져옴
    tajaFont = ImageFont.truetype("../resource/Galmuri9.ttf", 20)

    # 토큰 로드 & 실행
    status = 3
    with open("../config/token.txt") as token:
        token = token.readline()
        client = nombot.nombotClient(conn, cur, intents=discord.Intents.default())
        client.run(token)
except FileNotFoundError:
    if status == 1:
        print("db.json 파일이 존재하지 않습니다!")
    elif status == 2:
        print("taja.txt 파일이 존재하지 않습니다!")
    elif status == 3:
        print("token.txt 파일이 존재하지 않습니다!")
except discord.LoginFailure:
    print("해당 봇 계정으로 로그인 할 수 없습니다!")
except mariadb.Error as e:
    print("데이터 베이스 연결 실패\n{}".format(e))