#!bankomat/venv/bin/python
import time
from RPLCD import i2c
from keypad import Keypad
from sio_acceptor import BillAcceptor
from coin_pulse import CoinPulse
from machines import Machines
from nfckasse import NFCKasse
from unified_kasse import UnifiedKasse
from door import Door
from card_dispenser import CardDispenser
from gpio_button import GPIOButton
from mqtt_notify import MqttNotify
from pn532pi import Pn532I2c, Pn532, pn532

import logging

import user_config

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

lcd = i2c.CharLCD('PCF8574', 0x27, port=1, charmap='A00', cols=20, rows=4)
lcd.create_char(1, [0x11,0x00,0x11,0x11,0x11,0x11,0x0E,0x00]) #Ü
lcd.create_char(2, [0x06,0x09,0x09,0x0E,0x09,0x09,0x16,0x00]) #ß
lcd.create_char(3, [0x07,0x08,0x1E,0x08,0x1E,0x08,0x07,0x00]) #€

lcd.clear()
lcd.write_string('Booting...')

coin = CoinPulse(17, 22, {2:0.5, 3:1, 4:2})
cols = [26, 19, 13,  6]
rows = [21, 20, 16, 12]
buttons = [
        ['1',   '2',    '3',    'E'],
        ['4',   '5',    '6',    'C'],
        ['7',   '8',    '9',    'L'],
        ['U',   '0',    'D',    'O']
]
keypad = Keypad(cols, rows, buttons)

bills = BillAcceptor(user_config.NV9_10_USBPORT)
lcd.cursor_pos = (1, 0)
lcd.write_string('Notes init')
logger.debug('Initializing bill acceptor')
if not bills.connect():
	logger.error('Starting bill acceptor failed')
	lcd.write_string('    [fail]')
else:
	lcd.write_string('      [OK]')
door = Door(23, 18)
cardDispenser = CardDispenser(4, 5)

donationButton = GPIOButton(11, 7)
guestButton = GPIOButton(9, 8)
buyButton = GPIOButton(10, 25)

lcd.cursor_pos = (2, 0)
lcd.write_string('NFC Init')

try:
	logger.debug('Initializing NFC reader')
	pni2c = Pn532I2c(1)
	nfc = Pn532(pni2c)

	nfc.begin()
	nfc.setPassiveActivationRetries(0xFF)
	nfc.SAMConfig()
	lcd.write_string('        [OK]')
	logger.debug('NFC init succeeded')
except Exception:
	lcd.write_string('      [fail]')
	logger.exception('NFC init failed')
	exit(1)

UnifiedKasse([0], 'nfckasse') #init

def wait_for_tag():
	try:
		MqttNotify.getInstance().setState('idle')
	except:
		pass
	logger.debug('Starting NFC read loop')
	donationButton.light(1)
	buyButton.light(cardDispenser.check())
	guestButton.light(1)
	donationButton.reset()
	buyButton.reset()
	guestButton.reset()
	lcd.backlight_enabled = False
	lcd.clear()
	lcd.cursor_pos = (0, 0)
	#                 12345678901234567890
	lcd.write_string(' Karte an NFC-Leser ')
	lcd.cursor_pos = (1, 0)
	lcd.write_string(' halten, alternativ ')
	lcd.cursor_pos = (2, 0)
	if user_config.GUEST_UID is not None:
		lcd.write_string(' Spenden, Gast oder ')
		lcd.cursor_pos = (3, 0)
		lcd.write_string('Karte kaufen drücken')
	else:
		lcd.write_string(' Spenden oder Karte ')
		lcd.cursor_pos = (3, 0)
		lcd.write_string('   kaufen drücken')
	while True:
		try:
			success, uid = nfc.readPassiveTargetID(pn532.PN532_MIFARE_ISO14443A_106KBPS)
			if not success:
				uid = None
		except:
			logger.exception('NFC read failed')
			uid = None
		light = int(time.time()) % 3
		donationButton.light(light == 0)
		buyButton.light(light == 1 and cardDispenser.check())
		guestButton.light(light == 2)
		if user_config.GUEST_UID is not None and uid is None and guestButton.check():
			logger.debug('Guest button pressed')
			uid = user_config.GUEST_UID
		if uid is not None:
			logger.debug('Got UID %s', uid.hex())
			donationButton.light(0)
			guestButton.light(uid == user_config.GUEST_UID)
			buyButton.light(0)
			return uid
		elif donationButton.check():
			logger.debug('Donation button pressed')
			buyButton.light(0)
			guestButton.light(0)
			donate()
			return
		elif keypad.poll() == 'L' or buyButton.check():
			logger.debug('Buy button pressed')
			guestButton.light(0)
			donationButton.light(0)
			buyCard()
			return

def waitForTransferTag():
	logger.debug('Starting NFC read loop for transfer')
	lcd.clear()
	lcd.cursor_pos = (1, 0)
	#                 12345678901234567890
	lcd.write_string('Karte zum \x01berweisen')
	lcd.cursor_pos = (2, 0)
	lcd.write_string('     anhalten...    ')
	timeout = time.time() + 30
	while keypad.poll() != 'E' and timeout > time.time():
		try:
			success, uid = nfc.readPassiveTargetID(pn532.PN532_MIFARE_ISO14443A_106KBPS)
			if not success:
				uid = None
		except:
			logger.exception('NFC read failed')
			uid = None
		if uid is not None:
			return uid
	return None

def buyCard():
	logger.debug('Starting buying card loop')
	buyButton.light(1)
	lcd.backlight_enabled = True
	if not cardDispenser.check():
		logger.error('No more cards available in stacker')
		lcd.clear()
		#                 12345678901234567890
		lcd.cursor_pos = (1, 0)
		lcd.write_string('Derzeit keine Karten')
		lcd.cursor_pos = (2, 0)
		lcd.write_string('     verfügbar.')
		time.sleep(5)
		return
	try:
		MqttNotify.getInstance().setState('buying')
	except:
		pass
	lcd.clear()
	lcd.write_string('Neue Karte: 50ct')
	lcd.cursor_pos = (1, 0)
	lcd.write_string('Kein Wechselgeld!')
	timeout = time.time() + 30
	coin.enable()
	while timeout > time.time() and keypad.poll() != 'E':
		if time.time() > timeout - 2:
			coin.inhibit()
		c, p = coin.poll()
		if c is not None:
			ukasse = UnifiedKasse([0], 'cards')
			ukasse.addValue(c, p)
			if c >= 0.5:
				logger.info('Inserted %.2f, dispensing card', c)
				cardDispenser.dispense()
				lcd.clear()
				lcd.cursor_pos = (2, 0)
				lcd.write_string('Danke!')
				time.sleep(5)
				return
		time.sleep(.1)
	coin.inhibit()
	lcd.clear()
	lcd.cursor_pos = (2, 0)
	lcd.write_string('Abgebrochen')
	logger.debug('Buying card stopped due to user cancellation or timeout')
	time.sleep(5)

def chargeKonto(konto):
	logger.debug('Starting account charging for %s', konto.getSource())
	inserted = 0
	oldVal = None
	lastInserted = 0
	val = konto.getValue()
	coin.enable()
	bills.enableAcceptance()
	konto.start()
	try:
		MqttNotify.getInstance().setState('charging')
	except:
		pass
	timeout = time.time() + 30
	while timeout > time.time():
		if oldVal != val or lastInserted != inserted:
			lcd.cursor_pos = (0, 0)
			if isinstance(konto, NFCKasse):
				lcd.write_string('   Getränkekonto:   ')
			else:
				lcd.write_string('     Laserkonto:    ')
			lcd.cursor_pos = (1, 0)
			lcd.write_string('Guthaben:% 9.2f \x03' % val)
			lcd.cursor_pos = (2, 0)
			lcd.write_string('Zuletzt: % 9.2f \x03' % inserted)
			lcd.cursor_pos = (3, 0)
			lcd.write_string('Mit OK beenden ')
			oldVal = val
			lastInserted = inserted
		key = keypad.poll()
		if key == 'O' or (lastInserted == 0 and key == 'E'):
			break
		if not konto.ping():
			logger.error('Lost connection to database')
			lcd.clear()
			#                 12345678901234567890
			lcd.write_string('Verbindung zur')
			lcd.cursor_pos = (1, 0)
			lcd.write_string('Datenbank verloren.')
			lcd.cursor_pos = (2, 0)
			lcd.write_string('Vorgang abgebrochen')
			time.sleep(5)
			break
		c, p = coin.poll()
		if c is not None:
			timeout = time.time() + 30
			if c > 0:
				logger.info('Inserted coin value %.2f', c)
				inserted = c
				konto.addValue(c, p)
				try:
					MqttNotify.getInstance().setCoin(c)
				except:
					pass
			else:
				logger.error('Inserted unknown coin with %d pulses', p)
				konto.addValue(0, p)
			coin.enable()
			val = konto.getValue()
		bills.parse()
		if bills.getEscrow():
			logger.info('Inserted bill value %d, accepting', bills.getEscrow())
			timeout = time.time() + 30
			bills.acceptEscrow()
		b = bills.getAndClearAcceptedValue()
		if b:
			logger.info('Stored bill value %d', b)
			timeout = time.time() + 30
			inserted = b
			try:
				MqttNotify.getInstance().setNote(b)
			except:
				pass
			logger.info('Adding value to account')
			konto.addValue(b, None)
			logger.info('Fetching new value')
			val = konto.getValue()
		time.sleep(.1)
	bills.disableAcceptance()
	coin.inhibit()
	time.sleep(1)
	c, p = coin.poll() # If not fast enough disabled
	if c is not None:
		if c > 0:
			logger.info('Inserted coin value %.2f after closing', c)
			konto.addValue(c, p)
		else:
			logger.error('Inserted unknown coin with %d pulses after closing', p)
			konto.addValue(0, p)
	konto.disconnect()

def donate():
	logger.debug('Starting donation')
	inserted = 0
	oldVal = None
	lastInserted = 0
	konto = UnifiedKasse([0], 'donations')
	coin.enable()
	bills.enableAcceptance()
	val = 0
	lcd.backlight_enabled = True
	try:
		MqttNotify.getInstance().setState('donating')
	except:
		pass
	timeout = time.time() + 30
	while timeout > time.time():
		if oldVal != val or lastInserted != inserted:
			lcd.cursor_pos = (0, 0)
			#                 12345678901234567890
			lcd.write_string('Spende:             ')
			lcd.cursor_pos = (1, 0)
			lcd.write_string('Bisher:  % 9.2f \x03' % val)
			lcd.cursor_pos = (2, 0)
			lcd.write_string('Zuletzt: % 9.2f \x03' % inserted)
			lcd.cursor_pos = (3, 0)
			lcd.write_string('Mit OK beenden      ')
			oldVal = val
			lastInserted = inserted
		key = keypad.poll()
		if key == 'O' or (lastInserted == 0 and key == 'E'):
			break
		if not konto.ping():
			logger.error('Lost connection to database')
			lcd.clear()
			#                 12345678901234567890
			lcd.write_string('Verbindung zur')
			lcd.cursor_pos = (1, 0)
			lcd.write_string('Datenbank verloren.')
			lcd.cursor_pos = (2, 0)
			lcd.write_string('Vorgang abgebrochen')
			time.sleep(5)
			break
		c, p = coin.poll()
		if c is not None:
			timeout = time.time() + 30
			if c > 0:
				logger.info('Inserted coin value %.2f', c)
				inserted = c
				try:
					MqttNotify.getInstance().setCoin(c)
				except:
					pass
				konto.addValue(c, p)
				val += c
			else:
				logger.error('Inserted unknown coin with %d pulses after closing', p)
				konto.addValue(0, p)
				pass #unknown coin?
			coin.enable()
		bills.parse()
		if bills.getEscrow():
			logger.info('Inserted bill value %d, accepting', bills.getEscrow())
			timeout = time.time() + 30
			bills.acceptEscrow()
		b = bills.getAndClearAcceptedValue()
		if b:
			logger.info('Stored bill value %d', b)
			timeout = time.time() + 30
			inserted = b
			try:
				MqttNotify.getInstance().setNote(b)
			except:
				pass
			val += b
			konto.addValue(b, None)
		time.sleep(.1)
	bills.disableAcceptance()
	coin.inhibit()
	time.sleep(1)
	c, p = coin.poll() # If not fast enough disabled
	if c is not None:
		if c > 0:
			logger.info('Inserted coin value %.2f after closing', c)
			val += c
			konto.addValue(c, p)
		else:
			logger.error('Inserted unknown coin with %d pulses after closing', p)
			konto.addValue(0, p)
	lcd.clear()
	lcd.cursor_pos = (2, 0)
	if val == 0:
		#                 12345678901234567890
		lcd.write_string("      Schade...")
	elif val >= 20:
		#                 12345678901234567890
		lcd.write_string("  Sehr gro\x02zügig!")
	elif val >= 5:
		#                 12345678901234567890
		lcd.write_string("    Vielen Dank!")
	else:
		#                 12345678901234567890
		lcd.write_string("       Danke!")
	time.sleep(3)


def showTransactionDetails(t):
	logger.debug('Showing transaction details')
	lcd.clear()
	lcd.write_string("%s" % t.getDate().strftime('%d.%m.%y %H:%M'))
	lcd.cursor_pos = (1, 0)
	lcd.write_string("%40s" % t.getDesc()[:40])
	lcd.cursor_pos = (3, 0)
	lcd.write_string("%18.2f \x03" % t.getValue())
	timeout = time.time() + 30
	while keypad.poll() != 'E' and timeout > time.time():
		time.sleep(.1)

def historyKonto(konto):
	logger.debug('Showing transaction list')
	offset = 0
	cursor = 0
	oldKey = keypad.poll()
	transactions = konto.getTransactions()
	numTransactions = len(transactions)
	oldTransactions = None
	timeout = time.time() + 30
	try:
		MqttNotify.getInstance().setState('history')
	except:
		pass
	while timeout > time.time():
		if transactions != oldTransactions:
			oldTransactions = transactions
			for i in range(len(transactions)):
				lcd.cursor_pos = (i, 2)
				lcd.write_string('%18s' % transactions[i].getDesc()[:18])
			for i in range(len(transactions), 4):
				lcd.cursor_pos = (i, 2)
				lcd.write_string(' ' * 18)
			for i in range(4):
				lcd.cursor_pos = (i, 0)
				lcd.write_string('* ' if i == cursor else '  ')
		key = keypad.poll()
		if key != oldKey:
			oldKey = key
			if key == 'E':
				return
			elif key == 'O':
				showTransactionDetails(transactions[cursor])
				oldKey = keypad.poll()
				oldTransactions = None
				timeout = time.time() + 30
			elif key == 'U':
				if cursor > 0:
					lcd.cursor_pos = (cursor, 0)
					lcd.write_string(' ')
					cursor -= 1
					lcd.cursor_pos = (cursor, 0)
					lcd.write_string('*')
				elif offset > 0:
					offset -= 1
					transactions = konto.getTransactions(offset)
				timeout = time.time() + 30
			elif key == 'D':
				if cursor < numTransactions - 1:
					lcd.cursor_pos = (cursor, 0)
					lcd.write_string(' ')
					cursor += 1
					lcd.cursor_pos = (cursor, 0)
					lcd.write_string('*')
				elif cursor == 3:
					tmp = konto.getTransactions(offset + 1)
					if len(tmp) == 4:
						offset += 1
						transactions = tmp
				timeout = time.time() + 30
		else:
			time.sleep(.1)

def enterAmount(maxVal):
	logger.debug('Requesting input of value, max: %.2f', maxVal)
	lcd.clear()
	lcd.write_string('Verfügbar:')
	lcd.cursor_pos = (1, 0)
	lcd.write_string('%18.2f \x03' % maxVal)
	lcd.cursor_pos = (2, 0)
	lcd.write_string('Betrag:')
	lcd.cursor_pos = (3, 0)
	val = '0'
	oldVal = None
	oldKey = keypad.poll()
	while True:
		key = keypad.poll()
		if key is not None and oldKey != key:
			if key >= '0' and key <= '9':
				if round(float(val + key) / 100.0, 2) <= maxVal:
					val += key
			elif key == 'C':
				val = val[:-1]
				if not len(val):
					val = '0'
			elif key == 'E':
				logger.debug('Cancelled')
				return None
			elif key == 'O':
				logger.debug('Input %.2f', float(val) / 100.0)
				return round(float(val) / 100.0, 2)
		if val != oldVal:
			oldVal = val
			lcd.cursor_pos = (3, 0)
			lcd.write_string('%18.2f \x03' % (float(val) / 100.0))
		oldKey = key

def transferKonto(konto):
	try:
		MqttNotify.getInstance().setState('transfer')
	except:
		pass
	amount = enterAmount(konto.getValue())
	if amount is None:
		return False
	else:
		tag = waitForTransferTag()
		if tag is None:
			lcd.clear()
			lcd.cursor_pos = (2, 0)
			#                 12345678901234567890
			lcd.write_string('    Abgebrochen')
			time.sleep(5)
			return False
		else:
			ret = konto.transfer(amount, tag)
			lcd.clear()
			if ret == 0:
				logger.info('Transfer successful')
				#                 12345678901234567890
				lcd.write_string('    \x01berweisung')
				lcd.cursor_pos = (1, 0)
				lcd.write_string('    erfolgreich')
			elif ret == -1:
				logger.error('Tried to transfer more, than available')
				lcd.write_string('Fehler')
				lcd.cursor_pos = (1, 0)
				lcd.write_string('Guthaben nicht')
				lcd.cursor_pos = (2, 0)
				lcd.write_string('ausreichend')
			elif ret == 1:
				logger.error('Tried to transfer to same account')
				lcd.write_string('Fehler')
				lcd.cursor_pos = (1, 0)
				lcd.write_string('Gleiches Konto')
			elif ret == 2:
				logger.error('Receiving account not registered')
				lcd.write_string('Fehler')
				lcd.cursor_pos = (1, 0)
				lcd.write_string('Gegenkonto fehlt')
				lcd.cursor_pos = (2, 0)
				lcd.write_string('Erst registrieren')
			elif ret == 3:
				logger.debug('Cancelled')
				lcd.write_string('Fehler')
				lcd.cursor_pos = (1, 0)
				lcd.write_string('\x01berweisung abgebrochen')
			konto.disconnect()
			time.sleep(5)
			return ret == 0

def inputPin():
	logger.debug('Requesting pin')
	lcd.clear()
	lcd.cursor_pos = (1, 0)
	#                 12345678901234567890
	lcd.write_string('   Pin eingeben:    ')
	pin = ''
	oldPin = ''
	oldKey = keypad.poll()
	while True:
		key = keypad.poll()
		if key is not None and oldKey != key:
			if key >= '0' and key <= '9' and len(pin) < 4:
				pin += key
			if key == 'C':
				pin = pin[:-1]
			if key == 'E':
				return None
			if key == 'O' and len(pin) == 4:
				return pin
			if pin != oldPin:
				oldPin = pin
				lcd.cursor_pos = (2, 8)
				lcd.write_string(('*' * len(pin))+(' ' * (4 - len(pin))))
		oldKey = key


def mopupKonto(konto):
	logger.debug('Starting account mopup, disconnecting remote database')
	konto.disconnect()
	try:
		MqttNotify.getInstance().setState('mopup')
	except:
		pass
	conf = False
	for i in range(3):
		pin = inputPin()
		if pin is None:
			return
		if konto.checkPin(pin):
			conf = True
			break
	if not conf:
		return
	total = konto.getTotal()
	if total == 0 and False:
		logger.error('Trying to mopup empty account')
		lcd.clear()
		lcd.write_string('Dieses Konto ist')
		lcd.cursor_pos = (1, 0)
		lcd.write_string(' leer.')
		time.sleep(5)
		return
	door.open()
	amount = enterAmount(total)
	if amount is None or amount == 0:
		lcd.clear()
		lcd.write_string('Abgebrochen')
		time.sleep(5)
	elif konto.mopupValue(amount):
		lcd.clear()
		lcd.write_string('Abschöpfung von')
		lcd.cursor_pos = (1, 0)
		lcd.write_string('%18.2f \x03' % amount)
		lcd.cursor_pos = (2, 0)
		lcd.write_string('erfolgreich')
	else:
		lcd.clear()
		lcd.write_string('Abschöpfung')
		lcd.cursor_pos = (1, 0)
		lcd.write_string('fehlgeschlagen')
	time.sleep(5)
	if door.isOpen():
		lcd.clear()
		lcd.write_string('Tür schlie\x02en!')
		while door.isOpen():
			time.sleep(1)
			while door.isOpen():
				time.sleep(.5)

def subMenu(konto):
	logger.debug('Submenu for %s', konto.getSource())
	timeout = time.time() + 30
	while timeout > time.time():
		lcd.clear()
		lcd.write_string('5 Einzahlung')
		lcd.cursor_pos = (1, 0)
		lcd.write_string('6 Transaktionen')
		if isinstance(konto, NFCKasse):
			lcd.cursor_pos = (2, 0)
			lcd.write_string('7 \x01berweisung')
		if konto.isAdmin():
			lcd.cursor_pos = (3, 0)
			lcd.write_string('8 Abschöpfung')
		timeout = time.time() + 30
		while True:
			key = keypad.poll()
			if key == '5':
				chargeKonto(konto)
				return
			elif key == '6':
				historyKonto(konto)
				timeout = time.time() + 30
				break
			elif key == '7' and isinstance(konto, NFCKasse):
				transferKonto(konto)
				return
			elif key == '8' and konto.isAdmin():
				mopupKonto(konto)
				return
			elif time.time() > timeout or key == 'E':
				konto.disconnect()
				return

def mainMenu(tag):
	logger.debug('Main menu showing')
	try:
		MqttNotify.getInstance().setState('menu')
	except:
		pass
	gval = None
	mval = None
	kasse = NFCKasse(tag)
	if not kasse.connect():
		kasse = None
	else:
		gval = kasse.getValue()
		if user_config.GUEST_UID is not None and tag == user_config.GUEST_UID:
			chargeKonto(kasse)
			return
	machine = Machines(tag)
	if not machine.connect():
		machine = None
	else:
		mval = machine.getValue()
	timeout = time.time() + 30
	while timeout > time.time():
		timeout = time.time() + 30
		lcd.clear()
		lcd.cursor_pos = (0, 0)
		if kasse is None:
			#                12345678901234567890
			lcd.write_string('x Getränkekasse N/A')
		elif gval is not None:
			print("Getränkekonto gefunden %.2f" % gval)
			lcd.write_string('1 Getränkekonto')
		else:
			lcd.write_string('x Kein Getränkekonto')

		lcd.cursor_pos = (1, 0)
		if machine is None:
			lcd.write_string('x Laserkasse N/A')
		elif mval is not None:
			lcd.write_string('2 Laserkonto')
			print("Maschinenkonto gefunden %.2f" % mval)
		else:
			lcd.write_string('x Kein Laserkonto')
		donations = UnifiedKasse(tag, 'donations')
		lcd.cursor_pos = (2, 0)
		if donations.isAdmin():
			lcd.write_string('3 Spenden entnehmen')
		cards = UnifiedKasse(tag, 'cards')
		lcd.cursor_pos = (3, 0)
		if cards.isAdmin():
			lcd.write_string('4 Kartenkäufe entn.')
		while True:
			key = keypad.poll()
			if key == '1':
				if kasse is None:
					logger.error('Remote database for nfckasse not available')
					lcd.clear()
					#                 12345678901234567890
					lcd.write_string('Getränkekasse nicht')
					lcd.cursor_pos = (1, 0)
					lcd.write_string('verfügbar. Bitte')
					lcd.cursor_pos = (2, 0)
					lcd.write_string('später noch einmal')
					lcd.cursor_pos = (3, 0)
					lcd.write_string('versuchen.')
					time.sleep(5)
					break
				elif gval is None:
					logger.info('Trying to access nfckasse, not registered')
					lcd.clear()
					lcd.write_string('Kein Getränkekassen-')
					lcd.cursor_pos = (1, 0)
					lcd.write_string('Konto. Erst dort')
					lcd.cursor_pos = (2, 0)
					lcd.write_string('registrieren!')
					time.sleep(5)
					break
				else:
					if machine is not None:
						machine.disconnect()
					if key == '1':
						subMenu(kasse)
					return
			elif key == '2':
				if machine is None:
					logger.error('Remote database for machines not available')
					lcd.clear()
					lcd.write_string('Laserkonto nicht')
					lcd.cursor_pos = (1, 0)
					lcd.write_string('verfügbar. Bitte')
					lcd.cursor_pos = (2, 0)
					lcd.write_string('später noch einmal')
					lcd.cursor_pos = (3, 0)
					lcd.write_string('versuchen.')
					time.sleep(5)
					break
				elif mval is None:
					logger.info('Trying to access nfckasse, not registered')
					lcd.clear()
					lcd.write_string('Laserkonto nicht')
					lcd.cursor_pos = (1, 0)
					lcd.write_string('existent. Bitte')
					lcd.cursor_pos = (2, 0)
					lcd.write_string('an Luca wenden.')
					time.sleep(5)
					break
				else:
					if kasse is not None:
						kasse.disconnect()
					subMenu(machine)
					return
			elif key == '3' and donations.isAdmin():
				if kasse is not None:
					kasse.disconnect()
				if machine is not None:
					machine.disconnect()
				mopupKonto(donations)
				return
			elif key == '4' and cards.isAdmin():
				if kasse is not None:
					kasse.disconnect()
				if machine is not None:
					machine.disconnect()
				mopupKonto(cards)
				return
			elif key == 'E' or time.time() > timeout:
				if kasse is not None:
					kasse.disconnect()
				if machine is not None:
					machine.disconnect()
				return

time.sleep(1)
while True:
	tag = wait_for_tag()
	if tag is not None:
		lcd.clear()
		lcd.backlight_enabled = True
		lcd.write_string('Einen Moment...')
		mainMenu(tag)

