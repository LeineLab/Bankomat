import user_config, uuid
from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import BinarySensor, BinarySensorInfo, Sensor, SensorInfo
from datetime import datetime
import pytz

class MqttNotify():
	instance = None

	def getInstance():
		if MqttNotify.instance is None:
			MqttNotify.instance = MqttNotify()
		return MqttNotify.instance

	def __init__(self):
		MAC = '%012x' % uuid.getnode()
		for i in range(1,6):
			MAC = '%s:%s' % (MAC[:i * 3 - 1], MAC[i * 3 - 1:])
		settings = Settings.MQTT(host=user_config.MQTT_HOST, username=user_config.MQTT_USERNAME, password=user_config.MQTT_PASSWORD)
		device = DeviceInfo(name='Bankomat', manufacturer='LeineLab', model='Bankomat', identifiers=MAC)
		self.stateSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='State', unique_id='bankomat_state', device=device)))
		self.stateSensor.set_state('idle')
		dateSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Starttime', unique_id='bankomat_restart', device=device, device_class="timestamp")))
		dateSensor.set_state(datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat())
		self.noteSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Last Note', unique_id='bankomat_note', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.noteSensor.set_state(0)
		self.coinSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Last Coin', unique_id='bankomat_coin', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.coinSensor.set_state(0)
		self.nfckasseTotalSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='NFCKasse Total', unique_id='bankomat_nfckasse_total', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.nfckasseTotalSensor.set_state(None)
		self.machineTotalSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Machine Total', unique_id='bankomat_machine_total', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.machineTotalSensor.set_state(None)
		self.donationsTotalSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Dontaions Total', unique_id='bankomat_donations_total', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.donationsTotalSensor.set_state(None)
		self.cardsTotalSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Cards Total', unique_id='bankomat_cards_total', device=device, device_class="monetary", unit_of_measurement="EUR")))
		self.cardsTotalSensor.set_state(None)

	def setNote(self, note):
		self.noteSensor.set_state(note)

	def setCoin(self, coin):
		self.coinSensor.set_state(coin)

	def setState(self, state):
		self.stateSensor.set_state(state)

	def setKasseTotal(self, kasse, total):
		if kasse == 'nfckasse':
			self.nfckasseTotalSensor.set_state(total)
		elif kasse == 'machines':
			self.machineTotalSensor.set_state(total)
		elif kasse == 'donations':
			self.donationsTotalSensor.set_state(total)
		elif kasse == 'cards':
			self.cardsTotalSensor.set_state(total)

if __name__ == '__main__':
	notify = MqttNotify.getInstance()
	while True:
		pass
