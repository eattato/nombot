import nomUtils
import discord
from discord import app_commands

import mariadb

utils = None
guildId = 820582732219547728
class nombotClient(discord.Client):
    def __init__(self, conn, cur, **options):
        super().__init__(**options)
        self.tree = app_commands.CommandTree(self)
        self.conn = conn
        self.cur = cur

        global utils
        utils = nomUtils.utils(conn, cur)
    
    async def on_ready(self):
        print("서버 로드 중..")
        await self.tree.sync(guild=discord.Object(id=guildId))
        print("서버 로드 완료")

    @app_commands.command(name="계좌", description="현재 내 계좌의 금액과 빚을 조회합니다.")
    async def account(self, interaction):
        account = utils.getAccount(interaction.user.id)
        idk = "몰?루 "
        embed = discord.Embed(
            description=f"현금 {utils.decimalComma(account['cash'])}원\n"
                        + f"빚 {utils.decimalComma(account['debt'])}원\n"
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