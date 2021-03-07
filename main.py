import logging
import os
import sys
from pathlib import Path

from mqtt import VisioMQTTClient

_base_dir = Path.cwd()
_yaml_path = _base_dir / 'mqtt.yaml'

if __name__ == '__main__':
    # Set logging
    _log_fmt = ('%(levelname)-8s [%(asctime)s] [%(threadName)s] %(name)s'
                '.%(funcName)s(%(lineno)d): %(message)s'
                )
    _log_level = os.environ.get('LOG_LEVEL', 'DEBUG')
    _log = logging.getLogger(__name__)

    logging.basicConfig(format=_log_fmt,
                        level=_log_level,
                        stream=sys.stderr,
                        )

    visio_mqtt_client = VisioMQTTClient.from_yaml(yaml_path=_yaml_path)
    visio_mqtt_client.run()
