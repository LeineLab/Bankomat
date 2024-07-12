from time import sleep
import RPi.GPIO as GPIO

class CardDispenser():
	def dispense(self):
		self.servo.ChangeDutyCycle(self.activeDuty)
		sleep(.5)
		self.servo.ChangeDutyCycle(self.idleDuty)

	def check(self):
		return GPIO.input(self.detectPin)

	def __init__(self, servoPin, detectPin, idleDuty = 7, activeDuty = 12):
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(servoPin, GPIO.OUT)
		self.servo = GPIO.PWM(servoPin, 50)
		self.servo.start(idleDuty)
		self.idleDuty = idleDuty
		self.activeDuty = activeDuty
		self.detectPin = detectPin

	def __del__(self):
		self.servo.stop()

if __name__ == '__main__':
	cd = CardDispenser(4,9)
	cd.dispense()
	sleep(1)
