"""仅供集成测试使用的内存版 SQLAlchemy 垫片，不进入应用导入路径。"""
class _Type:
    def __init__(self,*a,**k):self.args=a
class Integer(_Type):pass
class String(_Type):pass
class Text(_Type):pass
class JSON(_Type):pass
class ForeignKey:
    def __init__(self,target):self.target=target
class UniqueConstraint:
    def __init__(self,*cols,**kw):self.cols=cols
class Column:
    def __init__(self,type_,*args,primary_key=False,unique=False,nullable=True,default=None,**kw):
        self.type=type_;self.primary_key=primary_key;self.unique=unique
        self.nullable=nullable;self.default=default;self.name=None;self.table=None
    def desc(self):return _Order(self,'desc')
    def asc(self):return _Order(self,'asc')
class _Order:
    def __init__(self,col,dir):self.col=col;self.dir=dir
class _Condition:
    def __init__(self,col,op,value):self.col=col;self.op=op;self.value=value
def _bind(col,op,value):return _Condition(col,op,value)
Column.__eq__=lambda self,other:_bind(self,'==',other)
Column.__ne__=lambda self,other:_bind(self,'!=',other)
Column.__gt__=lambda self,other:_bind(self,'>',other)
Column.__lt__=lambda self,other:_bind(self,'<',other)
class _ColumnMap(dict):
    def __iter__(self):return iter(self.values())
class Table:
    def __init__(self,name,columns):self.name=name;self.columns=_ColumnMap(columns)
class _Registry:
    def __init__(self):self.tables={}
REGISTRY=_Registry()
class _Meta(type):
    def __new__(mcs,name,bases,ns):
        cls=super().__new__(mcs,name,bases,ns)
        tablename=ns.get('__tablename__')
        if not tablename:return cls
        columns={}
        for attr,val in list(ns.items()):
            if isinstance(val,Column):
                val.name=attr;val.table=tablename;columns[attr]=val
        cls.__table__=Table(tablename,columns)
        REGISTRY.tables.setdefault(tablename,[])
        return cls
class DeclarativeBase(metaclass=_Meta):
    def __init__(self,**kw):
        for name,col in self.__table__.columns.items():
            if name in kw:setattr(self,name,kw.pop(name))
            elif col.default is not None:setattr(self,name,col.default)
            else:setattr(self,name,None)
        for k,v in kw.items():setattr(self,k,v)
class _Func:
    def count(self):return _Aggregate('count')
func=_Func()
class _Aggregate:
    def __init__(self,name):self.name=name
def text(s):return s
class _Select:
    def __init__(self,target):
        self.target=target;self.conds=[];self.orders=[];self.limit_v=None;self.entity=None
    def where(self,*c):self.conds.extend(c);return self
    def order_by(self,*c):self.orders.extend(c);return self
    def limit(self,n):self.limit_v=n;return self
    def select_from(self,e):self.entity=e;return self
def select(target):return _Select(target)
class _Result:
    def __init__(self,items):self.items=items
    def all(self):return self.items
    def first(self):return self.items[0] if self.items else None
    def __iter__(self):return iter(self.items)
class _Engine:
    def __init__(self,url,**kw):self.url=url
    def connect(self):
        class _Conn:
            def __enter__(s):return s
            def __exit__(s,*a):return False
            def execute(s,stmt):return None
        return _Conn()
def create_engine(url,**kw):return _Engine(url)
class Session:
    def __init__(self):self.pending=[]
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def add(self,obj):self.pending.append(obj)
    def add_all(self,objs):self.pending.extend(objs)
    def flush(self):
        for obj in self.pending:
            table=obj.__table__.name;rows=REGISTRY.tables[table]
            pk=next((c for c in obj.__table__.columns.values() if c.primary_key),None)
            if pk is not None and getattr(obj,pk.name,None) is None:
                setattr(obj,pk.name,max([getattr(r,pk.name) for r in rows if getattr(r,pk.name,None) is not None]+[0])+1)
            if obj not in rows:rows.append(obj)
        self.pending.clear()
    def commit(self):self.flush()
    def get(self,model,pk):
        pkcol=next(c for c in model.__table__.columns.values() if c.primary_key)
        for row in REGISTRY.tables.get(model.__tablename__,[]):
            if getattr(row,pkcol.name)==pk:return row
        return None
    def _target_table(self,stmt):
        t=stmt.target
        if isinstance(t,Column):return t.table
        if isinstance(t,_Aggregate):return stmt.entity.__tablename__
        return t.__tablename__
    def _match(self,row,stmt):
        for cond in stmt.conds:
            if getattr(row,cond.col.name)!=cond.value:return False
        return True
    def scalars(self,stmt):
        rows=[r for r in REGISTRY.tables.get(self._target_table(stmt),[]) if self._match(r,stmt)]
        for o in stmt.orders:
            col=o.col if isinstance(o,_Order) else o
            reverse=isinstance(o,_Order) and o.dir=='desc'
            rows.sort(key=lambda r:getattr(r,col.name),reverse=reverse)
        if stmt.limit_v is not None:rows=rows[:stmt.limit_v]
        if isinstance(stmt.target,_Aggregate):return _Result([len(rows)])
        if isinstance(stmt.target,Column):return _Result([getattr(r,stmt.target.name) for r in rows])
        return _Result(rows)
    def scalar(self,stmt):
        res=self.scalars(stmt).all()
        return res[0] if res else None
def sessionmaker(bind=None,**kw):
    def factory():return Session()
    return factory
