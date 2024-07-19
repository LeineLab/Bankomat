import user_config, uuid
from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import BinarySensor, BinarySensorInfo, Sensor, SensorInfo

class MqttNotify():
	def __init__(self):
		MAC = '%012x' % uuid.getnode()
		for i in range(1,6):
			MAC = '%s:%s' % (MAC[:i * 3 - 1], MAC[i * 3 - 1:])
		settings = Settings.MQTT(host=user_config.MQTT_HOST, username=user_config.MQTT_USERNAME, password=user_config.MQTT_PASSWORD)
		device = DeviceInfo(name='Bankomat', manufacturer='LeineLab', model='Bankomat', identifiers=MAC)
		self.stateSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='State', unique_id='bankomat_state', device=device)))
		self.stateSensor.set_state('idle')
		self.noteSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Last Note', unique_id='bankomat_note', device=device)))
		self.noteSensor.set_state(0)
		self.coinSensor = Sensor(Settings(mqtt=settings, entity=SensorInfo(name='Last Coin', unique_id='bankomat_coin', device=device)))
		self.coinSensor.set_state(0)

	def setNote(self, note):
		self.noteSensor.set_state(note)

	def setCoin(self, coin):
		self.coinSensor.set_state(coin)

	def setState(self, state):
		self.stateSensor.set_state(state)

if __name__ == '__main__':
	notify = MqttNotify()
	while True:
		pass
