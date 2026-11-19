from fastapi import HTTPException
class Response:
    def __init__(self,content='',media_type=None,headers=None):
        if isinstance(content,str):content=content.encode()
        self.body=content;self.media_type=media_type;self.headers=headers or {}
