"""仅供集成测试使用的内存版 Redis 垫片。"""
_CLIENTS={}
class Redis:
    def __init__(self,url):self.url=url;self.lists={};self.available=True;self.pushed=[]
    @classmethod
    def from_url(cls,url):
        if url not in _CLIENTS:_CLIENTS[url]=cls(url)
        return _CLIENTS[url]
    def rpush(self,key,value):
        if not self.available:raise ConnectionError('queue unavailable')
        self.lists.setdefault(key,[]).append(value);self.pushed.append((key,value));return len(self.lists[key])
    def blpop(self,keys,timeout=0):
        for k in keys:
            if self.lists.get(k):return (k,self.lists[k].pop(0))
        return None
    def ping(self):
        if not self.available:raise ConnectionError('down')
        return True
