from pathlib import Path

from mqtt import VisioMQTTClient

_base_dir = Path.cwd()
_yaml_path = _base_dir / 'mqtt.yaml'

if __name__ == '__main__':
    visio_mqtt_client = VisioMQTTClient.from_yaml(yaml_path=_yaml_path)
    visio_mqtt_client.run()
