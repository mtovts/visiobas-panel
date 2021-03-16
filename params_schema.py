from typing import Optional

from pydantic import BaseModel


class ParamsModel(BaseModel):
    device_id: int
    object_identifier: int
    object_type: int
    priority: int
    value: Optional[float] = 1.0

# class RPCValueModel(BaseModel):
#     jsonrpc = '2.0'
#     method = 'value'
#     params: ParamsModel
