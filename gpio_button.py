import RPi.GPIO as GPIO

class GPIOButton():
	def __init__(self, button_pin, led_pin):
		self.button_pin = button_pin
		self.led_pin = led_pin
		self.triggered = False
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.led_pin, GPIO.OUT)
		GPIO.add_event_detect(
			self.button_pin,
			GPIO.FALLING,
			callback=self.trigger,
			bouncetime=100
		)

	def trigger(self, channel):
		self.triggered = True

	def check(self):
		#return not GPIO.input(self.button_pin)
		return self.triggered

	def reset(self):
		self.triggered = False

	def light(self, on_off):
		GPIO.output(self.led_pin, on_off)

if __name__ == '__main__':
	from time import sleep
	donbut = GPIOButton(11, 7)
	while not donbut.check():
		sleep(.1)
	donbut.light(1)
	sleep(1)
	donbut.light(0)
