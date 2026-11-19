"""仅供集成测试使用的 FastAPI 最小垫片。"""
class HTTPException(Exception):
    def __init__(self,status_code,detail):
        super().__init__(detail);self.status_code=status_code;self.detail=detail
class APIRouter:
    def __init__(self):self.routes=[]
    def _add(self,path,fn,method):self.routes.append((method,path,fn));return fn
    def get(self,path,**kw):
        return lambda fn:self._add(path,fn,'GET')
    def post(self,path,**kw):
        return lambda fn:self._add(path,fn,'POST')
    def put(self,path,**kw):
        return lambda fn:self._add(path,fn,'PUT')
def Depends(fn=None):return ('depends',fn)
