import serial, time, logging

class BillAcceptor:
	NOTE_ACCEPT1    =   1
	NOTE_ACCEPT2    =   2
	NOTE_ACCEPT3    =   3
	NOTE_ACCEPT4    =   4
	NOTE_ACCEPT5    =   5
	NOTE_ACCEPT6    =   6
	NOTE_ACCEPT7    =   7
	NOTE_ACCEPT8    =   8
	NOTE_ACCEPT9    =   9
	NOTE_ACCEPT10   =  10
	NOTE_ACCEPT11   =  11
	NOTE_ACCEPT12   =  12
	NOTE_ACCEPT13   =  13
	NOTE_ACCEPT14   =  14
	NOTE_ACCEPT15   =  15
	NOTE_ACCEPT16   =  16
	NOTE_UNKOWN     =  20
	SLOW_MECH       =  30
	STRIMMING       =  40
	FRAUD_NOTE      =  50
	STACKER_FULL    =  60
	ESCROW_ABORT    =  70 # Escrow timeout
	NOTE_TAKEN      =  80
	BUSY            = 120
	NOT_BUSY        = 121
	ERROR           = 255

	NOTE_INHIBIT1   = 131
	NOTE_INHIBIT2   = 132
	NOTE_INHIBIT3   = 133
	NOTE_INHIBIT4   = 134
	NOTE_INHIBIT5   = 135
	NOTE_INHIBIT6   = 136
	NOTE_INHIBIT7   = 137
	NOTE_INHIBIT8   = 138
	NOTE_INHIBIT9   = 139
	NOTE_INHIBIT10  = 140
	NOTE_INHIBIT11  = 141
	NOTE_INHIBIT12  = 142
	NOTE_INHIBIT13  = 143
	NOTE_INHIBIT14  = 144
	NOTE_INHIBIT15  = 145
	NOTE_INHIBIT16  = 146
	NOTE_ENABLE1    = 151
	NOTE_ENABLE2    = 152
	NOTE_ENABLE3    = 153
	NOTE_ENABLE4    = 154
	NOTE_ENABLE5    = 155
	NOTE_ENABLE6    = 156
	NOTE_ENABLE7    = 157
	NOTE_ENABLE8    = 158
	NOTE_ENABLE9    = 159
	NOTE_ENABLE10   = 160
	NOTE_ENABLE11   = 161
	NOTE_ENABLE12   = 162
	NOTE_ENABLE13   = 163
	NOTE_ENABLE14   = 164
	NOTE_ENABLE15   = 165
	NOTE_ENABLE16   = 166
	ENABLE_ESCROW   = 170 # Accept notes after escrow handshake
	DISABLE_ESCROW  = 171 # Accept notes without handshake
	ACCEPT_ESCROW   = 172 # Handshake take note
	REJECT_ESCROW   = 173 # Handshake reject note
	STATUS          = 182 # Leads to restart?
	ENABLE_ALL      = 184 # Enable device / accpt all enabled notes
	DISABLE_ALL     = 185 # Disable device / reject all enabled notes
	DISABLE_TIMEOUT = 190 # Disable 30s escrow timeout
	ENABLE_TIMEOUT  = 191 # Enable 30s escrow timeout
	REQ_FIRMWARE    = 192
	REQ_DATASET     = 193

	_last_busy      = 0
	_last_ping      = 0
	_notes          = [5,10,20,50,100,200,500]
	_enabled_notes  = [1, 1, 1, 1] + [0] * 12
	_note_state     = [0] * 16
	_escrowEnabled  = False
	_escrowVal      = 0
	_acceptedVal    = 0

	def _recentlyBusy(self):
		return self._last_busy + 2 > time.time()

	def getBillValue(self, id):
		if id < 1 or id > len(self._notes):
			return 0
		return self._notes[id - 1]

	def parse(self):
		if not self.connect():
			return
		while self.ser.in_waiting > 0:
			byteData = self.ser.read()
			b = byteData[0]
			self.logger.debug("Received %d" % b)
			if b == self.BUSY:
				self._last_busy = time.time()
				self.logger.debug('Device busy')
			elif b == self.ENABLE_ESCROW:
				self._last_ping = time.time()
				self._escrowEnabled = True
			elif b == self.DISABLE_ESCROW:
				self._escrowEnabled = False
			elif self._recentlyBusy() and b >= self.NOTE_ACCEPT1 and b <= self.NOTE_ACCEPT16:
				val = self.getBillValue(b)
				self.logger.info('Inserted %d Euro note' % val)
				if self._escrowEnabled:
					self._escrowVal += val
					self.logger.info('Escrow value currently at %d' % self._escrowVal)
				else:
					self._acceptedVal += val
					self.logger.info('Accepted value currently at %d' % self._acceptedVal)
			elif b == self.REJECT_ESCROW or b == self.ESCROW_ABORT or b == self.NOTE_TAKEN:
				self._escrowVal = 0
				self.logger.info('Escrow rejected, setting to zero')
			elif b == self.ACCEPT_ESCROW:
				self._acceptedVal += self._escrowVal
				self._escrowVal = 0
				self.logger.info('Escrow accepted, setting to zero, accepted value at %d' % self._acceptedVal)
			elif b >= self.NOTE_ENABLE1 and b <= self.NOTE_ENABLE16:
				self._note_state[b - self.NOTE_ENABLE1] = 1
			elif b >= self.NOTE_INHIBIT1 and b <= self.NOTE_INHIBIT16:
				self._note_state[b - self.NOTE_INHIBIT1] = 0

	def getEscrow(self):
		return self._escrowVal

	def getAcceptedValue(self):
		return self._acceptedVal

	def getAndClearAcceptedValue(self):
		a = self._acceptedVal
		self._acceptedVal = 0
		return a

	def send(self, b):
		if not self.ser.is_open:
			return False
		else:
			by = bytearray()
			by.append(b)
			self.logger.debug('Sending %d' % b)
			self.ser.write(by)
			self.ser.flush()
			time.sleep(0.1)
			return True

	def acceptEscrow(self):
		self.send(self.ACCEPT_ESCROW)

	def rejectEscrow(self):
		self.send(self.REJECT_ESCROW)

	def enableAcceptance(self):
		self.send(self.ENABLE_ALL)

	def disableAcceptance(self):
		self.send(self.DISABLE_ALL)

	def connect(self):
		try:
			if self.ser.is_open:
				return True
			self.ser.open()
			# Setup device
			# Disable acceptance until requested
			self.send(self.DISABLE_ALL)
			self.parse()
			# Start escrow session
			self.send(self.ENABLE_ESCROW)
			self.parse()
			# Enable selected notes
			for i in range(16):
				if i < len(self._enabled_notes) and self._enabled_notes[i]:
					self.logger.debug("Enable channel %d / %d Euro" % (i,self._notes[i]))
					self.send(self.NOTE_ENABLE1 + i)
				else:
					self.logger.debug("Disable channel %d / %d Euro" % (i,self.getBillValue(self.NOTE_ACCEPT1 + i)))
					self.send(self.NOTE_INHIBIT1 + i)
				self.parse()
			return True
		except Exception as e:
			self.logger.exception("Error while connecting")
			return False

	def __init__(self, port):
		self.logger = logging.getLogger(__name__)
		self.ser = serial.Serial()
		self.ser.baudrate = 9600
		self.ser.port = port
		self.ser.bytesize = serial.EIGHTBITS
		self.ser.parity = serial.PARITY_NONE
		self.ser.stopbits = serial.STOPBITS_TWO
		self.connect()


if __name__ == '__main__':
	acceptor = BillAcceptor('/dev/ttyACM0')
	if not acceptor.connect():
		print('Failed to open Port')
		exit(1)
	acceptor.enableAcceptance()
	curVal = 0
	escVal = 0
	while True:
		acceptor.parse()
		e = acceptor.getEscrow()
		if e and e != escVal:
			i = input('Got %d Euro, accept? [y/N]\n# ' % e)
			if i == 'y' or i == 'Y':
				acceptor.acceptEscrow()
			else:
				acceptor.rejectEscrow()
		escVal = e
		v = acceptor.getAcceptedValue()
		if v != curVal:
			curVal = v
			print('Currently %d Euro stored.' % curVal)
