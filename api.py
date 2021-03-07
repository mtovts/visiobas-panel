from json import loads, JSONDecodeError

import paho.mqtt.client as mqtt

from i2c import I2CRWMixin
from obj_type import ObjType


class VisioMQTTApi(I2CRWMixin):

    def __init__(self, visio_mqtt_client):  # , gateway):
        self.mqtt_client = visio_mqtt_client
        # self._gateway = gateway

    def publish(self, topic: str, payload: str = None, qos: int = 0,
                retain: bool = False) -> mqtt.MQTTMessageInfo:
        return self.mqtt_client.publish(topic=topic,
                                        payload=payload,
                                        qos=qos,
                                        retain=retain
                                        )

    @staticmethod
    def decode(msg: mqtt.MQTTMessage):
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

    def rpc_value_panel(self, params: dict, topic: str) -> None:
        # todo: default value
        # todo: validate params
        publish_topic = topic.replace('Set', 'Site')

        if params['object_type'] == ObjType.BINARY_OUTPUT.id:
            _is_equal = self.write_with_check_i2c(value=params['value'],
                                                  obj_id=params['object_identifier'],
                                                  obj_type=params['object_type'],
                                                  dev_id=params['device_id']
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
                                  obj_type=params['object_type'],
                                  dev_id=params['device_id']
                                  )
            payload = '{0} {1} {2} {3}'.format(params['device_id'],
                                               params['object_type'],
                                               params['object_identifier'],
                                               value,
                                               )
        else:
            raise ValueError('Expected only BI or BO')
        self.publish(topic=publish_topic,
                     payload=payload,
                     )
