import oracledb as cx_Oracle
import json
from datetime import datetime

class DBLibrary:
    def __init__(self, username, password, hostname, port, servicename):
        self.username = username
        self.password = password
        self.hostname = hostname
        self.port = port
        self.servicename = servicename
        self.conn = None
        self.cur = None
        self.connection = None
        self.json_obj = None  # Initialize json_obj attribute

    def establishConnection(self):
        # Establish a connection to the Oracle database
        try:
            self.conn = cx_Oracle.connect(self.username+'/'+self.password+'@'+self.hostname+':'+self.port+'/'+self.servicename)
            self.cur = self.conn.cursor()
            print(cx_Oracle.version)
            print(self.conn.version)
            print("Connected to DB: ", self.conn)
        except Exception as err:
            print('Error while connecting to DB', err)

    def execute_sql_query(self, query):
        try:
            self.cur.execute(query)
            columns = [desc[0] for desc in self.cur.description]  # Get column names
            results = self.cur.fetchall()
            print(results)
            data = {}
            for row in results:
                for column, value in zip(columns, row):
                    if isinstance(value, datetime):
                        value = str(value)  # Convert datetime to string
                    if column not in data:
                        data[column] = []
                    data[column].append(value)  # Group values with same key
            json_data = json.dumps(data)  # Convert data to JSON string

            # Print value by JSON path
            self.json_obj = json.loads(json_data)
            # Convert JSON string to Python object
            print(self.json_obj)
            # return self.json_obj  # Example JSON path

        except Exception as e:
            print(f"Error executing SQL query: {e}")

    def closeConnection(self):
        if self.conn:
            self.cur.close()
            self.conn.close()

    def ExecuteDB(self, query):
        try:
            self.establishConnection()
            self.execute_sql_query(query)
            self.closeConnection()
            return self.json_obj

        except Exception as e:
            return f"An error occurred: {str(e)}"


# conStr = 'OPS$SVWDEV/manager@10.61.1.213:1521/SVWDEV'
# username = 'OPS$SVWDEV'
# password = 'manager'
# hostname = '10.61.1.94'
# port = '1521'
# servicename = 'SVWDEV'
# query = """select * from PERSON_HISTORY where person_type_id='254001'"""
#
# DBAutomation = DBLibrary(username, password, hostname, port, servicename)
# result1 = DBAutomation.ExecuteDB(query)
# print(result1)