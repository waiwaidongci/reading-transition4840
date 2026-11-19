"""仅供集成测试使用的 pydantic 垫片：BaseModel 按类型注解强制转换并校验 Field 约束。"""
from typing import get_type_hints
class ValidationError(Exception):pass
class _FieldInfo:
    def __init__(self,default=None,min_length=None,max_length=None):
        self.default=default;self.min_length=min_length;self.max_length=max_length
def Field(default=None,**kw):
    if default is None:default=kw.pop('default_factory',None)
    return _FieldInfo(default,kw.get('min_length'),kw.get('max_length'))
class BaseModel:
    def __init__(self,**data):
        try:hints=get_type_hints(type(self))
        except Exception:hints=getattr(type(self),'__annotations__',{})
        for name,ann in hints.items():
            info=getattr(type(self),name,None)
            if name not in data:
                if isinstance(info,_FieldInfo) and not isinstance(info.default,(type(None),)):
                    data[name]=info.default
                else:continue
            value=data[name]
            if ann is int and not isinstance(value,bool):
                try:value=int(value)
                except (TypeError,ValueError):raise ValidationError(name+' 必须为整数')
            if isinstance(info,_FieldInfo):
                if isinstance(value,str):
                    if info.min_length is not None and len(value)<info.min_length:raise ValidationError(name+' 长度不足')
                    if info.max_length is not None and len(value)>info.max_length:raise ValidationError(name+' 超长')
            setattr(self,name,value)
    def model_dump(self):return {k:getattr(self,k) for k in type(self).__annotations__ if hasattr(self,k)}
