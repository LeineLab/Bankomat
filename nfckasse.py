from unified_kasse import UnifiedKasse, Transaction
import mysql.connector
from hashlib import md5
import user_config

import logging

logger = logging.getLogger(__name__)

class NFCKasse(UnifiedKasse):
	def uidToHash(self, uid):
		return md5(uid).hexdigest()

	def __init__(self, uid):
		super().__init__(uid, 'nfckasse')
		self.uid = self.uidToHash(bytearray(uid))

	def connect(self):
		logger.debug('Connecting to database')
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
			self.cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED')
			return True
		except mysql.connector.Error as error:
			logger.exception('No connection to database')
			return False

	def disconnect(self):
		logger.debug('Closing connection to database')
		self.cursor.close()
		self.db.close()

	def getValue(self):
		try:
			self.cursor.execute('SELECT value FROM cards WHERE uid = %s', (self.uid, ))
			result = self.cursor.fetchone()
			return result['value']
		except mysql.connector.Error as error:
			logger.exception()
			return None
		except TypeError:
			#logger.exception('Probably no account')
			return None

	def addValue(self, value, pulses):
		logger.info('Adding %.2f to account', value)
		super().addValue(value, pulses)
		try:
			self.cursor.execute('INSERT INTO transactions (uid, value, tdate) VALUES (%s, %s, NOW())', (self.uid, value))
			self.cursor.execute('UPDATE cards SET value = value + %s WHERE uid = %s', (value, self.uid))
			self.db.commit()
			return True
		except mysql.connector.Error as error:
			logger.exception('Add value failed: %08x, value %.2f, rolling back', self._uid, value)
			return False

	def transfer(self, value, destcard):
		if value > self.getValue():
			return -1
		dest = self.uidToHash(bytearray(destcard))
		if dest == self.uid:
			logger.info('Transfer to same account stopped')
			return 1
		try:
			self.cursor.execute('SELECT value FROM cards WHERE uid = %s', (dest, ))
			result = self.cursor.fetchone()
			result['value']
		except mysql.connector.Error:
			logger.exception('Account check failed')
			return 2
		except TypeError:
			logger.info('No account registered for receiver')
			return 2
		try:
			self.cursor.execute('INSERT INTO transactions (uid, value, exchange_with_uid, tdate) VALUES (%s, %s, %s, NOW())', (self.uid, -value, dest))
			self.cursor.execute('INSERT INTO transactions (uid, value, exchange_with_uid, tdate) VALUES (%s, %s, %s, NOW())', (dest, value, self.uid))
			self.cursor.execute('UPDATE cards SET value = value - %s WHERE uid = %s', (value, self.uid))
			self.cursor.execute('UPDATE cards SET value = value + %s WHERE uid = %s', (value, dest))
			self.db.commit()
			logger.info('Transfer successful')
			return 0
		except mysql.connector.Error:
			logger.exception('Transfer failed, maybe too low credit after check')
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
			logger.exception()
			return []
		except TypeError:
			logger.exception('Probably no account')
			return []

	def ping(self):
		try:
			self.db.ping(True)
			return super().ping()
		except mysql.connector.errors.OperationalError:
			logger.exception('Connection to database lost, reconnecting failed')
			return False

if __name__ == '__main__':
	kasse = NFCKasse(user_config.UID_TEST)
	if kasse.connect():
		val = kasse.getValue()
		if val is not None:
			print("Aktuelles Guthaben: %.2f" % val)
		for transaction in kasse.getTransactions():
			print(transaction.toString())
