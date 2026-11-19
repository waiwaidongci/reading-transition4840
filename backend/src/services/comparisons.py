from sqlalchemy import select
from fastapi import HTTPException
from redis import Redis
from ..config.settings import REDIS_URL
from ..models.comparison import ComparisonRun
from ..utils.serialization import row,now
from .sources import source_or_404,list_records
from .audit import log
queue=Redis.from_url(REDIS_URL)
def get_comparison(db,id):
    c=db.get(ComparisonRun,id)
    if not c:raise HTTPException(404,'未找到对照任务')
    return c
def create_comparison(db,user,data):
    if data.group_a_source_id==data.group_b_source_id:
        raise HTTPException(422,'两组文集必须互不重叠：请选择两个不同的来源')
    sa=source_or_404(db,data.group_a_source_id)
    sb=source_or_404(db,data.group_b_source_id)
    records_a=list_records(db,sa.id);records_b=list_records(db,sb.id)
    if not records_a or not records_b:
        raise HTTPException(422,'两个文集都必须至少包含1个会话才能对照')
    # 受理即冻结会话与分层输入；来源之后的并发追加不会混入本任务
    snapshot={'group_a':{'source':row(sa),'records':records_a},
              'group_b':{'source':row(sb),'records':records_b}}
    c=ComparisonRun(name=data.name,group_a_source_id=sa.id,group_b_source_id=sb.id,
                    parameters={},snapshot=snapshot,created_at=now(),state='queued')
    db.add(c);db.flush();log(db,user,'comparison.queued',c.id,data.name);db.commit()
    try:queue.rpush('comparison:queue',c.id)
    except Exception:
        c.state='failed';c.error='队列暂不可用，请重新创建对照任务';db.commit()
        raise HTTPException(503,c.error)
    return row(c)
def list_comparisons(db):
    return [{k:v for k,v in row(c).items() if k not in ('snapshot','result')}
            for c in db.scalars(select(ComparisonRun).order_by(ComparisonRun.id.desc()))]
