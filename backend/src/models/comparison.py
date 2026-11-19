from sqlalchemy import Column,Integer,String,JSON,Text,ForeignKey
from ..config.database import Base
from ..config.settings import CONFIG
class ComparisonRun(Base):
    __tablename__='transition_comparisons'
    id=Column(Integer,primary_key=True)
    name=Column(String(160),nullable=False)
    group_a_source_id=Column(Integer,ForeignKey(CONFIG['source_table']+'.id'),nullable=False)
    group_b_source_id=Column(Integer,ForeignKey(CONFIG['source_table']+'.id'),nullable=False)
    state=Column(String(20),default='queued')
    snapshot=Column(JSON,nullable=False)
    result=Column(JSON,nullable=True)
    error=Column(Text,default='')
    created_at=Column(String(40),nullable=False)
