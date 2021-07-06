# %%
from abc import ABC, abstractmethod
from datetime import datetime
import requests
import json
import pandas as pd

# %%
class MoexLoader(ABC):
    def __init__(self, security, interval):
        """ 
            Отвечает за загрузку данных по акциям с Московской биржи
            security - Тикер (идентификатор финансового актива)
            interval - Интервал загружаемых данных

            .refresh() отвечает за получение актуальных данных и запись в базу данных
        """
        self.security = security # Тикер (идентификатор акции)
        self.interval = interval # Интервал (минута, 10 минут, час, день и т.д) за который будут обновляться данные


    # Метод который будет обновлять данные в базе
    def refresh(self, connection):

        self.connection = connection # Соединение с базой данных
        self.cursor = self.connection.cursor()
        
        self.target_table, self.is_active = self.__get_target_table()

        if self.is_active:
            
            self.max_date = self.__get_maximum_date()
            self.security_data  = self.__get_candles()

            if len(self.security_data) == 0:
                print('Новых данных не обнаружено')
            else:
                self.__update_candles()
        else:
            print('Загрузка данных в таблицу {} отключена'.format(self.target_table))

    
    # Получение названия таблицы в которую необходимо загрузить данные, а так же то, является ли она активная
    def __get_target_table(self):
        
        query = """
            SELECT target_table, 
                   is_active 
              FROM [MAIN].[se].[interval_target_table] 
             WHERE 1 = 1
               AND [type] = '{}'
               AND interval = {}
                    """.format(self.target_table_type, self.interval)
        
        self.cursor.execute(query)
        
        interval_target_table = self.cursor.fetchall()

        target_table, is_active = interval_target_table[0]

        return target_table, is_active

    # Получаем максимальную дату на которую есть данные
    def __get_maximum_date(self):      
        query = """
            SELECT MAX([end]) 
              FROM {}
             WHERE 1 = 1
               AND [SECID] = '{}'
                    """.format(self.target_table, self.security)
        
        self.cursor.execute(query)

        max_date = self.cursor.fetchall()[0][0]


        return max_date


    def __get_candles(self):
        # Reference: http://iss.moex.com/iss/reference/46
        # /iss/engines/[engine]/markets/[market]/boards/[board]/securities/[security]/candles

        engine = self.engine
        market = self.market
        board = self.board
        security = self.security
        date_from = self.max_date.isoformat() if self.max_date is not None else None
        date_to = datetime.now().isoformat()
        interval = self.interval
        start = 0
        
        row_count = None
        security_data = []

        while row_count != 0:
                    request = 'http://iss.moex.com/iss/engines/{}/markets/{}/boards/{}/securities/{}/candles.json?iss.meta=off&from={}&till={}&interval={}&start={}'.format(engine, market, board, security, date_from, date_to, interval, start)
                    print(request)
                    security_candles = requests.get(request)
                    security_candles = json.loads(security_candles.text)

                    data = security_candles['candles']['data']
                    row_count = len(data)
                    start = start + row_count

                    security_data.extend(data)
                    
        security_data = pd.DataFrame(data = security_data, columns = ['open','close','high','low','value','volume','begin','end'])

        return security_data

    def __update_candles(self):
        # Есть более правильный способ как это сделать, но в целях раскрытия информации показываю, что у меня был и такой код :)
        for index, row in self.security_data.iterrows():
            SECID = self.security
            BOARDID = self.board
            open_price = row['open']
            close_price = row['close']
            high_price = row['high']
            low_price = row['low']
            value = row['value']
            volume = row['volume']
            begin = row['begin']
            end = row['end']

            insert = "INSERT INTO {} VALUES ".format(self.target_table)
            values = "(N'{}',N'{}',{},{},{},{},{},{},'{}','{}')".format(SECID,BOARDID,open_price,close_price,high_price,low_price,value,volume,begin,end)
            query = insert + values

            self.cursor.execute(query) 