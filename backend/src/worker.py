import json,time,logging
from redis import Redis
from sqlalchemy import select
from .config.database import Session
from .config.settings import REDIS_URL,ARTIFACT_DIR
from .models.run import Run
from .models.comparison import ComparisonRun
from .models import source,record,user,note,audit
from .services.algorithm import calculate
from .services.comparison_algorithm import compare
from .services.audit import log
from .services.export import csv_response,comparison_csv
queue=Redis.from_url(REDIS_URL)
ARTIFACT_DIR.mkdir(parents=True,exist_ok=True)
def execute(id):
    with Session() as db:
        r=db.get(Run,id)
        if not r or r.state!='queued':return
        r.state='running';db.commit()
        try:
            result=calculate(r.snapshot['records'],r.parameters)
            json.dumps(result,allow_nan=False)
            r.result=result;r.state='completed'
            response=csv_response(result,'run.csv')
            (ARTIFACT_DIR/f'run-{r.id}.csv').write_bytes(response.body)
            log(db,'worker','run.completed',r.id)
        except Exception as e:
            logging.exception('analysis failed');r.state='failed';r.error=str(e)[:2000]
            log(db,'worker','run.failed',r.id,r.error)
        db.commit()
def execute_comparison(id):
    with Session() as db:
        c=db.get(ComparisonRun,id)
        if not c or c.state!='queued':return
        c.state='running';db.commit()
        try:
            result=compare(c.snapshot,c.parameters)
            json.dumps(result,allow_nan=False)
            c.result=result;c.state='completed'
            (ARTIFACT_DIR/f'comparison-{c.id}.csv').write_bytes(comparison_csv(db,c.id).body)
            log(db,'worker','comparison.completed',c.id)
        except Exception as e:
            logging.exception('comparison failed');c.state='failed';c.error=str(e)[:2000]
            log(db,'worker','comparison.failed',c.id,c.error)
        db.commit()
def main():
    while True:
        (ARTIFACT_DIR/'heartbeat').write_text(str(time.time()))
        item=queue.blpop(['analysis:queue','comparison:queue'],timeout=2)
        if not item:continue
        name,value=item
        if name=='comparison:queue':execute_comparison(int(value))
        else:execute(int(value))
if __name__=='__main__':main()
