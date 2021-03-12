import logging
import time
from json import loads, JSONDecodeError
from pathlib import Path

import busio
import digitalio
from adafruit_mcp230xx.mcp23008 import MCP23008

from obj_type import ObjType

_log = logging.getLogger(__name__)

try:
    import board
except NotImplementedError as e:
    _log.critical(e)


class VisioMQTTI2CApi:

    def __init__(self, visio_mqtt_client, config: dict):  # , gateway):
        self.mqtt_client = visio_mqtt_client

        self._config = config

        self.i2c = busio.I2C(board.SCL, board.SDA)

        # init i2c buses
        self.bi_busses = [MCP23008(self.i2c, address=addr)
                          for addr in self._config.get('bi_buses', [])]
        self.bo_busses = [MCP23008(self.i2c, address=addr)
                          for addr in self._config.get('bo_buses', {}).keys()]
        _log.debug(f'bo={self.bo_busses} bi={self.bi_busses}')

        # init pins
        self.bi_pins = {}
        for bus, bus_addr in zip(self.bi_busses, self._config.get('bi_buses', [])):
            pins = []
            for i in range(8):
                pin = bus.get_pin(i)
                pin.direction = digitalio.Direction.INPUT
                pin.pull = digitalio.Pull.UP
                pins.append(pin)

            self.bi_pins[bus_addr] = pins

        self.bo_pins = {}
        for bus, bus_addr in zip(self.bo_busses, self._config.get('bo_buses', [])):
            pins = []
            for i in range(8):
                pin = bus.get_pin(i)
                pin.switch_to_output()
                pins.append(pin)

            self.bo_pins[bus_addr] = pins

    @property
    def buses(self) -> dict:
        return {**self.bo_busses, **self.bi_busses}

    @property
    def pins(self):  # -> dict[int, list]:
        return {**self.bi_pins, **self.bo_pins}

    def _publish(self, topic, payload=None, qos=0, retain=True):
        # topic: str, payload: str = None, qos: int = 0,
        # retain: bool = True) -> mqtt.MQTTMessageInfo:
        return self.mqtt_client.publish(topic=topic,
                                        payload=payload,
                                        qos=qos,
                                        retain=retain
                                        )

    @classmethod
    def from_yaml(cls, visio_mqtt_client, yaml_path: Path):
        import yaml

        with yaml_path.open() as cfg_file:
            i2c_cfg = yaml.load(cfg_file, Loader=yaml.FullLoader)
            _log.info(f'Creating {cls.__name__} from {yaml_path} ... {i2c_cfg}')
        return cls(visio_mqtt_client=visio_mqtt_client,
                   config=i2c_cfg
                   )

    @staticmethod
    def decode(msg):  # mqtt.MQTTMessage):
        try:
            if isinstance(msg.payload, bytes):
                content = loads(msg.payload.decode("utf-8", "ignore"))
            else:
                content = loads(msg.payload)
        except JSONDecodeError:
            if isinstance(msg.payload, bytes):
                content = msg.payload.decode("utf-8", "ignore")
            else:
                content = msg.payload
        return content

    def rpc_value_panel(self, params, topic):
        # params: dict, topic: str) -> None:
        # todo: default value
        # todo: validate params

        _log.debug(f'Processing \'value\' method with params: {params}')

        publish_topic = topic.replace('Set', 'Site')

        if params['object_type'] == ObjType.BINARY_OUTPUT.id:
            _is_equal = self.write_with_check_i2c(value=bool(params['value']),
                                                  obj_id=params['object_identifier'],
                                                  # obj_type=params['object_type'],
                                                  # dev_id=params['device_id']
                                                  )
            if not _is_equal:
                return None
            payload = '{0} {1} {2} {3}'.format(params['device_id'],
                                               params['object_type'],
                                               params['object_identifier'],
                                               params['value'],
                                               )

        elif params['object_type'] == ObjType.BINARY_INPUT.id:
            value = self.read_i2c(obj_id=params['object_identifier'],
                                  # obj_type=params['object_type'],
                                  # dev_id=params['device_id']
                                  )
            payload = '{0} {1} {2} {3}'.format(params['device_id'],
                                               params['object_type'],
                                               params['object_identifier'],
                                               value,
                                               )
        else:
            raise ValueError(
                f'Expected only {ObjType.BINARY_INPUT} or {ObjType.BINARY_OUTPUT}')
        self._publish(topic=publish_topic,
                      payload=payload,
                      )

    def read_i2c(self, obj_id):  #: int):  # , obj_type: int, dev_id: int) -> bool:
        """
        :param obj_id: first two numbers contains bus address. Then going pin number.
                Example: obj_id=3701 -> bus_address=37, pin=01
        """
        bus_addr = int(str(obj_id)[:2])  # fixme
        pin_id = int(str(obj_id)[2:])

        try:
            # inverting because False=turn on, True=turn off
            v = not self.pins[bus_addr][pin_id].value

            _log.debug(f'Read: bus={bus_addr} pin={pin_id} value={v}')
            return v
        except LookupError as e:
            _log.warning(e,
                         exc_info=True
                         )

    def write_i2c(self, value, obj_id):
        # value: bool, obj_id: int) -> None:  # , obj_type: int, dev_id: int):
        """
        :param obj_id: first two numbers contains bus address. Then going pin number.
                Example: obj_id=3701 -> bus_address=37, pin=01
        """
        try:
            value = not value

            bus_addr = int(str(obj_id)[:2])  # fixme
            pin_id = int(str(obj_id)[2:])

            _log.debug(f'Write bus={bus_addr}, pin={pin_id} value={value}')

            self.bo_pins[bus_addr][pin_id].value = value

            # block for non-pulse relays
            if self._config['bo_buses'][bus_addr]['delay'][pin_id]:
                time.sleep(self._config['bo_buses'][bus_addr]['delay'][pin_id])
                self.bo_pins[bus_addr][pin_id].value = not value

        except LookupError as e:
            _log.warning(e,
                         exc_info=True
                         )

    def write_with_check_i2c(self, value, obj_id):
        # value: bool, obj_id: int  # , obj_type: int, dev_id: int
        # ) -> bool:
        """
        :param obj_id: first two numbers contains bus address. Then going pin number.
                Example: obj_id=3701 -> bus_address=37, pin=01
        :return: the read value is equal to the written value
        """
        self.write_i2c(value=value,
                       obj_id=obj_id,
                       # obj_type=obj_type,
                       # dev_id=dev_id
                       )
        rvalue = self.read_i2c(obj_id=obj_id,
                               # obj_type=obj_type,
                               # dev_id=dev_id
                               )
        res = not value == rvalue  # because inverting value in read\write
        _log.debug(f'Write with check result={res}')
        return res
