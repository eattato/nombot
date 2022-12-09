import pandas as pd
from datetime import datetime
from pytz import timezone

class utils():
    def __init__(self, conn, cur):
        self.conn = conn
        self.cur = cur

    def getAccount(self, id):
        queryString = f"select * from nombot.members where id = {id}"
        userData = pd.read_sql(queryString, self.conn)
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
            self.cur.execute(queryString)
        userData = userData.iloc[0]
        return userData

    def saveAccount(self, account, saves):
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
        self.cur.execute(queryString)
        self.conn.commit()
        print("계정을 저장했습니다.")

    def decimalComma(self, num):
        num = str(num)
        result = ""
        for ind, char in enumerate(num[::-1]):
            result = char + result
            if (ind + 1) % 3 == 0 and ind != len(num) - 1:
                result = "," + result
        return result

    def log(self, user, target, act, amount):
        queryString = f"insert into nombot.moneylog values('{user}', '{target}', {act}, {amount}, '{self.getCurrentTime()}')"
        self.cur.execute(queryString)
        self.conn.submit()

    def getCurrentTime(self):
        return datetime.now()

    def timeFormat(self, target):
        return target.strftime("%Y-%m-%d %H:%M:%S")

    def stringToTime(self, target):
        return datetime.strptime(target, "%Y-%m-%d %H:%M:%S")

    def getCurrentEconomy(self):
        queryString = "select * from nombot.economy"
        economyData = pd.read_sql(queryString, self.conn)
        return economyData.iloc[0]