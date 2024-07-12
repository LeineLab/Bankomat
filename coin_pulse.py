import RPi.GPIO as GPIO
import time

class CoinPulse:
	_last_pulse = 0
	_pulses = 0
	_enabled = True
	_value_for_pulses = {}

	def intCallback(self, channel):
		self._pulses += 1
		self._last_pulse = time.time()
		self.inhibit()


	def poll(self):
		ret = None
		lp = self._last_pulse
		p = self._pulses
		if lp and lp + .25 < time.time():
			if p in self._value_for_pulses:
				ret = self._value_for_pulses[self._pulses]
			else:
				ret = -1
			self._pulses = 0
			self._last_pulse = 0
		return ret, p

	def inhibit(self):
		self._enabled = False
		GPIO.output(self._inhibit_pin, 1)

	def enable(self):
		if not self._enabled:
			self._pulses = 0
			self._last_pulse = 0
		self._enabled = True
		GPIO.output(self._inhibit_pin, 0)

	def isEnabled(self):
		return self._enabled

	def __init__(self, pulse_pin, inhibit_pin, value_for_pulses):
		self._pulse_pin = pulse_pin
		self._inhibit_pin = inhibit_pin
		self._value_for_pulses = value_for_pulses
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self._pulse_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self._inhibit_pin, GPIO.OUT)
		self.inhibit()
		GPIO.add_event_detect(self._pulse_pin, GPIO.RISING, callback=self.intCallback, bouncetime=10)

if __name__ == '__main__':
	coin = CoinPulse(17, 22, {2:0.5, 3:1, 4:2})
#	coin = CoinPulse(24, 22, {1:0.5, 2:1, 3:2})
	stored = 0
	input("Inhibited... Press Enter ")
	coin.enable()
	while True:
		m, p = coin.poll()
		if m:
			if m < 0:
				print("Coin not recognized, stored anyways")
			else:
				stored += m
				print("Received %1.2f Euro, now stored %1.2f Euro" % (m, stored))
			coin.enable()
