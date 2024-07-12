import RPi.GPIO as GPIO

class Keypad:
	def __init__(self, col_pins, row_pins, buttons):
		self._col_pins = col_pins
		self._row_pins = row_pins
		self._buttons = buttons
		GPIO.setmode(GPIO.BCM)
		for pin in self._col_pins:
			GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		for pin in self._row_pins:
			GPIO.setup(pin, GPIO.IN)

	def poll(self):
		key = None
		for row in range(len(self._row_pins)):
			for i in range(len(self._row_pins)):
				if i == row:
					GPIO.setup(self._row_pins[i], GPIO.OUT, initial=GPIO.LOW)
				else:
					GPIO.setup(self._row_pins[i], GPIO.IN) #Reset to input
			for col in range(len(self._col_pins)):
				if not GPIO.input(self._col_pins[col]):
					if key is None:
						key = self._buttons[row][col]
					else:
						key = -1
		if key == -1:
			key = None
		return key

if __name__ == '__main__':
	cols = [26, 19, 13,  6]
	rows = [21, 20, 16, 12]
	buttons = [
		['1',	'2',	'3',	'E'],
		['4',	'5',	'6',	'C'],
		['7',	'8',	'9',	'L'],
		['U',	'0',	'D',	'O']
	]
	keypad = Keypad(cols, rows, buttons)
	old_key = -1
	while True:
		key = keypad.poll()
		if key != old_key:
			old_key = key
			if key != None:
				print('Pressed %s' % key)
