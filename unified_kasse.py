import mysql.connector
from hashlib import sha256
from datetime import datetime
from email_sender import emailSender
import user_config
from mqtt_notify import MqttNotify

import logging

logger = logging.getLogger(__name__)

class Transaction:
	def __init__(self, desc, value, date):
		self.desc = desc
		self.value = value
		self.date = datetime.fromtimestamp(date)

	def getDate(self):
		return self.date
	def getValue(self):
		return self.value
	def getDesc(self):
		return self.desc
	def toString(self):
		return "%s  %s  %6.2f" % (self.date.strftime('%d.%m.%y %H:%M'), self.desc, self.value)

class UnifiedKasse:
	_bankomatDB = None
	_cursor = None

	def _connect(self):
		logger.debug('Tring to connect to internal database')
		try:
			UnifiedKasse._bankomatDB = mysql.connector.connect(
				host = user_config.LOCALDB_HOST,
				port = user_config.LOCALDB_PORT,
				user = user_config.LOCALDB_USERNAME,
				password = user_config.LOCALDB_PASSWORD,
				database = user_config.LOCALDB_DATABASE
			)
			UnifiedKasse._cursor = UnifiedKasse._bankomatDB.cursor(dictionary=True)
			UnifiedKasse._cursor.execute('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED')
			for k in ['nfckasse', 'machines', 'donations', 'cards']:
				# Updating MQTT values
				UnifiedKasse([0], k).getTotal()
			return True
		except mysql.connector.Error:
			logger.exception('Could not connect to internal database')
			return False

	def __init__(self, uid, source):
		self.source = source
		self._uid = 0
		for i in uid:
			self._uid <<= 8
			self._uid += i
		if UnifiedKasse._bankomatDB is None:
			if not self._connect():
				raise Exception('UnifiedKasse DB Connection failed')
		logger.debug('Initialized UnifiedKasse for uid %08x', uid)
		try:
			self.ping()
		except:
			pass

	def getSource(self):
		return self.source

	def isAdmin(self):
		logger.debug('Checking if user is admin')
		try:
			UnifiedKasse._cursor.execute('SELECT uid FROM admins WHERE uid = %s', (self._uid,))
			result = self._cursor.fetchone()
			return 'uid' in result
		except mysql.connector.Error as error:
			return False
		except TypeError as error:
			return False

	def getAdminName(self):
		logger.debug('Resolving user name')
		try:
			UnifiedKasse._cursor.execute('SELECT name FROM admins WHERE uid = %s', (self._uid,))
			result = self._cursor.fetchone()
			return result['name']
		except mysql.connector.Error as error:
			return None
		except TypeError:
			return None

	def generatePin(pin):
		return sha256(pin.encode('utf-8')).hexdigest()

	def checkPin(self, pin):
		logger.debug('Checking pin')
		try:
			UnifiedKasse._cursor.execute('SELECT uid FROM admins WHERE uid = %s AND pin = %s', (self._uid, UnifiedKasse.generatePin(pin)))
			result = self._cursor.fetchone()
			return 'uid' in result
		except mysql.connector.Error as error:
			logger.exception()
			return False
		except TypeError as error:
			logger.exception('Possibly entered wrong pin')
			return False

	def getTotal(self):
		try:
			UnifiedKasse._cursor.execute('SELECT value FROM targets WHERE tname = %s', (self.source,))
			result = self._cursor.fetchone()
			try:
				MqttNotify.getInstance().setKasseTotal(self.source, result['value'])
			except:
				pass # No connection
			return result['value']
		except mysql.connector.Error as error:
			logger.exception()
			return 0
		except TypeError:
			logger.exception()
			return 0

	def addValue(self, value, pulses):
		try:
			UnifiedKasse._cursor.execute('INSERT INTO transactions (uid, value, pulses, sourcedest, dt) VALUES (%s, %s, %s, %s, NOW())', (self._uid, value, pulses, self.source))
			UnifiedKasse._cursor.execute('UPDATE targets SET value = value + %s WHERE tname = %s', (value, self.source))
			UnifiedKasse._bankomatDB.commit()
			total = self.getTotal()
			if float(total) > 500 and float(total) - float(value) < 500:
				try:
					email = emailSender()
					email.report('Einzahlungen über 500 Euro', 'Die Einzahlungen für %s liegen über 500 Euro' % (self.source,))
				except:
					pass
			return True
		except mysql.connector.Error as error:
			logger.exception('Add value for source %s failed: %08x, value %.2f', self.source, self._uid, value)
			return False

	def mopupValue(self, value):
		try:
			UnifiedKasse._cursor.execute('INSERT INTO transactions (uid, value, sourcedest, dt) VALUES (%s, %s, %s, NOW())', (self._uid, -value, self.source))
			UnifiedKasse._cursor.execute('UPDATE targets SET value = value - %s WHERE tname = %s', (value, self.source))
			UnifiedKasse._bankomatDB.commit()
			try:
				email = emailSender()
				email.report('Abschöpfung %s' % (self.source,), "Soeben hat %s eine Abschöpfung in Höhe von %.2f Euro vorgenommen" % (self.getAdminName(), value))
			except:
				pass
			self.getTotal() # update MQTT sensors
			return True
		except mysql.connector.Error as error:
			logger.exception('Mopup failed')
			return False

	def start(self):
		pass

	def disconnect(self):
		pass

	def ping(self):
		try:
			UnifiedKasse._bankomatDB.ping(True)
			return True
		except mysql.connector.errors.OperationalError: # lost connection
			return self._connect()
		except mysql.connector.errors.InterfaceError: # lost connection
			return self._connect()


if __name__ == '__main__':
	ukasse = UnifiedKasse(user_config.UID_TEST, 'donations')
	print('User is admin: %d' % (ukasse.isAdmin(), ))
	print('Total value: %.2f' % (ukasse.getTotal(), ))
	print(ukasse.ping())
	import getpass
	pin = getpass.getpass('Generate pin hash (4 digits): ')
	print(UnifiedKasse.generatePin(pin))
