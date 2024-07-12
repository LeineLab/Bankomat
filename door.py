import RPi.GPIO as GPIO
from time import sleep

class Door:
	def isOpen(self):
		return GPIO.input(self._door_pin)

	def open(self):
		GPIO.output(self._open_pin, 1)
		sleep(.2)
		GPIO.output(self._open_pin, 0)

	def __init__(self, open_pin, door_pin):
		self._open_pin = open_pin
		self._door_pin = door_pin
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self._door_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self._open_pin, GPIO.OUT)

if __name__ == '__main__':
	door = Door(23, 18)
	while True:
		if not door.isOpen():
			print("closed")
			sleep(1)
			print("opening...")
			door.open()
		sleep(.2)
