from unified_kasse import UnifiedKasse, Transaction
import mysql.connector
from hashlib import md5
import user_config

class NFCKasse(UnifiedKasse):
	def uidToHash(self, uid):
		return md5(uid).hexdigest()

	def __init__(self, uid):
		super().__init__(uid, 'nfckasse')
		self.uid = self.uidToHash(bytearray(uid))

	def connect(self):
		try:
			self.db = mysql.connector.connect(
				host = user_config.NFCKASSE_HOST,
				port = user_config.NFCKASSE_PORT,
				user = user_config.NFCKASSE_USERNAME,
				password = user_config.NFCKASSE_PASSWORD,
				database = user_config.NFCKASSE_DATABASE,
				connection_timeout = 1
			)
			self.cursor = self.db.cursor(dictionary=True)
			self.cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITED')
			return True
		except mysql.connector.Error as error:
			return False

	def disconnect(self):
		self.cursor.close()
		self.db.close()

	def getValue(self):
		try:
			self.cursor.execute('SELECT value FROM cards WHERE uid = %s', (self.uid, ))
			result = self.cursor.fetchone()
			return result['value']
		except mysql.connector.Error as error:
			return None
		except TypeError:
			return None

	def addValue(self, value, pulses):
		super().addValue(value, pulses)
		try:
			self.cursor.execute('INSERT INTO transactions (uid, value, tdate) VALUES (%s, %s, NOW())', (self.uid, value))
			self.cursor.execute('UPDATE cards SET value = value + %s WHERE uid = %s', (value, self.uid))
			self.db.commit()
			return True
		except mysql.connector.Error as error:
			return False

	def transfer(self, value, destcard):
		if value > self.getValue():
			return -1
		dest = self.uidToHash(bytearray(destcard))
		if dest == self.uid:
			return 1
		try:
			self.cursor.execute('SELECT value FROM cards WHERE uid = %s', (dest, ))
			result = self.cursor.fetchone()
			result['value']
		except mysql.connector.Error:
			return 2
		except TypeError:
			return 2
		try:
			self.cursor.execute('INSERT INTO transactions (uid, value, exchange_with_uid, tdate) VALUES (%s, %s, %s, NOW())', (self.uid, -value, dest))
			self.cursor.execute('INSERT INTO transactions (uid, value, exchange_with_uid, tdate) VALUES (%s, %s, %s, NOW())', (dest, value, self.uid))
			self.cursor.execute('UPDATE cards SET value = value - %s WHERE uid = %s', (value, self.uid))
			self.cursor.execute('UPDATE cards SET value = value + %s WHERE uid = %s', (value, dest))
			self.db.commit()
			return 0
		except mysql.connector.Error:
			self.db.rollback()
			return 3

	def getTransactions(self, offset = 0):
		try:
			transactions = []
			self.cursor.execute('SELECT t.value, p.name, t.topupcode, t.exchange_with_uid, UNIX_TIMESTAMP(t.tdate) as tdate FROM transactions t LEFT JOIN products p ON t.ean = p.ean WHERE t.uid = %s ORDER BY tdate DESC LIMIT 4 OFFSET %s', (self.uid, offset))
			while True:
				result = self.cursor.fetchone()
				print(result)
				if result is None:
					return transactions
				if result['name'] is not None:
					desc = result['name']
				elif result['topupcode'] is not None:
					desc = 'QR-Aufladung'
				elif result['exchange_with_uid'] is not None:
					desc = 'überweisung'
				else:
					desc = 'Unbekannt'
				transactions.append(Transaction(desc, result['value'], result['tdate']))
		except mysql.connector.Error:
			return []
		except TypeError:
			return []


if __name__ == '__main__':
	kasse = NFCKasse(user_config.UID_TEST)
	if kasse.connect():
		val = kasse.getValue()
		if val is not None:
			print("Aktuelles Guthaben: %.2f" % val)
		for transaction in kasse.getTransactions():
			print(transaction.toString())
