import discord
from discord import app_commands

import mariadb

class nombotClient(discord.Client):
    def __init__(self, conn, cur, **options):
        super().__init__(**options)

        # db
        self.conn = conn
        self.cur = cur
    
    async def on_ready(self):
        print("서버 로드 완료")

    @app_commands.command()
    async def sync(self, interaction):
        await interaction.client.tree.sync()
        #await interaction.client.tree.sync(guild=interaction.guild_id)
        await interaction.response.send_message("슬래시 커맨드를 연결했습니다!")