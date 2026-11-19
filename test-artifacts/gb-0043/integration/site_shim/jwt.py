"""仅供集成测试使用的 PyJWT 垫片。"""
import json,base64
def encode(payload,secret,algorithms=None):
    raw=base64.urlsafe_b64encode(json.dumps(payload,sort_keys=True).encode()).decode()
    return 'token.'+raw+'.'+str(abs(hash(secret))%9999)
def decode(token,secret,algorithms=None):
    return json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'=='))
