from unified_kasse import UnifiedKasse, Transaction
import mysql.connector
import time
import user_config

class Machines(UnifiedKasse):
	def __init__(self, uid):
		super().__init__(uid, 'machines')
		self.uid = 0
		for i in uid:
			self.uid <<= 8
			self.uid += i
		self.start_time = None

	def connect(self):
		try:
			self.db = mysql.connector.connect(
				host = user_config.MACHINES_HOST,
				port = user_config.MACHINES_PORT,
				user = user_config.MACHINES_USERNAME,
				password = user_config.MACHINES_PASSWORD,
				database = user_config.MACHINES_DATABASE,
				connection_timeout = 1
			)
			self.cursor = self.db.cursor(dictionary=True)
			self.cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED')
			try:
				self.cursor.execute("SELECT uid FROM alias WHERE card_id = %s", (self.uid, ))
				result = self.cursor.fetchone()
				self.uid = result['uid']
			except mysql.connector.Error as error:
				pass
			except TypeError:
				pass #No alias
			return True
		except mysql.connector.Error as error:
			return False

	def start(self):
		self.start_time = int(time.time())
		try:
			self.cursor.execute('INSERT INTO sessions (uid, machine, start_time) VALUES(%s, "revaluator", %s)', (self.uid, self.start_time))
			self.db.commit()
		except mysql.connector.Error as error:
			print(error)
			pass

	def disconnect(self):
		if self.start_time is not None:
			try:
				self.cursor.execute('UPDATE sessions SET end_time = %s WHERE uid=%s AND machine="revaluator" AND start_time=%s', (int(time.time()), self.uid, self.start_time))
				self.db.commit()
			except mysql.connector.Error as error:
				pass
		self.cursor.close()
		self.db.close()

	def getValue(self):
		try:
			self.cursor.execute('SELECT credit FROM cards WHERE uid = %s', (self.uid, ))
			result = self.cursor.fetchone()
			return result['credit']
		except mysql.connector.Error as error:
			return None
		except TypeError:
			return None

	def addValue(self, value, pulses):
		super().addValue(value, pulses)
		try:
			self.cursor.execute('UPDATE sessions SET price=price+%s WHERE uid=%s AND machine="revaluator" AND start_time=%s', (value, self.uid, self.start_time))
			self.cursor.execute('UPDATE cards SET credit=credit+%s WHERE uid=%s', (value, self.uid))
			self.db.commit()
			return True
		except mysql.connector.Error as error:
			self.db.rollback()
		return False

	def getTransactions(self, offset = 0):
		try:
			transactions = []
			self.cursor.execute('SELECT price, machine, start_time FROM sessions WHERE uid = %s ORDER BY start_time DESC LIMIT 4 OFFSET %s', (self.uid, offset))
			while True:
				result = self.cursor.fetchone()
				if result is None:
					return transactions
				transactions.append(Transaction(result['machine'], result['price'], result['start_time']))
		except mysql.connector.Error as error:
			return []
		except TypeError:
			return []


if __name__ == '__main__':
	machines = Machines(user_config.UID_TEST)
	if machines.connect():
		val = machines.getValue()
		if val is not None:
			for t in machines.getTransactions():
				print(t.toString())
			machines.disconnect()
