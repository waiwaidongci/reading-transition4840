"""端到端集成测试：真实 services/worker/export + 内存版第三方垫片。

运行：python3 -I test-artifacts/gb-0043/integration/integration_test.py
覆盖：受理冻结、并发追加不混入、队列失败 503、worker 消费与失败态、
     CSV 导出、审计事件、404/422 拒绝口径，以及结果与算法层口径一致。
"""
import os,sys,csv,io,json,tempfile,unittest
HERE=os.path.dirname(os.path.abspath(__file__))
SHIM=os.path.join(HERE,'site_shim');BACKEND=os.path.join(HERE,'..','..','..','backend')
sys.path.insert(0,SHIM);sys.path.insert(0,BACKEND)
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['REDIS_URL']='redis://shim/0'
ART=tempfile.mkdtemp(prefix='cmp-artifacts-');os.environ['ARTIFACT_DIR']=ART

from src.config.database import Session
from sqlalchemy import REGISTRY
from src.models.source import Source
from src.models.record import Record
from src.models.comparison import ComparisonRun
from src.schemas.comparison import ComparisonInput
from src.services import comparisons,export
from src.services.comparison_algorithm import compare
from src import worker
from fastapi import HTTPException

def edge_sessions(prefix,n_hits,n_miss,edge,miss_path):
    out=[]
    for i in range(n_hits):out.append((f'{prefix}-h{i}',list(edge)))
    for i in range(n_miss):out.append((f'{prefix}-m{i}',list(miss_path)))
    return out

def seed_sources(db):
    sa=Source(key='SY-A',name='秋季常规组',filename='a.csv',description='A');db.add(sa);db.flush()
    sb=Source(key='SY-B',name='复测对照组',filename='b.csv',description='B');db.add(sb);db.flush()
    # 辛普森构造：每层 A 更高，合并 B 反超
    a=[('A2',p) for _,p in edge_sessions('A2',5,5,('X','Y'),('P','Q'))]
    a+= [('A3',p) for _,p in edge_sessions('A3',8,2,('X','Y','Z'),('R','S','T'))]
    a+=[('A1',['Solo']),('A4',['I','J','K','L'])]
    b=[('B2',p) for _,p in edge_sessions('B2',3,7,('X','Y'),('P','Q'))]
    b+=[('B3',p) for _,p in edge_sessions('B3',70,30,('X','Y','Z'),('R','S','T'))]
    for i,(g,path) in enumerate(a):db.add(Record(source_id=sa.id,reference=f'A-{i:03}',values={'session':g+'-'+str(i),'path':'>'.join(path)}))
    for i,(g,path) in enumerate(b):db.add(Record(source_id=sb.id,reference=f'B-{i:03}',values={'session':g+'-'+str(i),'path':'>'.join(path)}))
    db.commit();return sa,sb

class Actor:
    email='analyst@reading-transition.demo';role='analyst'

class IntegrationTest(unittest.TestCase):
    def setUp(self):
        for rows in REGISTRY.tables.values():rows.clear()
        with Session() as db:self.sa,self.sb=seed_sources(db)

    def _create(self,db=None,**over):
        data=ComparisonInput(name='分层对照',group_a_source_id=self.sa.id,group_b_source_id=self.sb.id,**over)
        with db or Session() as s:return comparisons.create_comparison(s,Actor(),data)

    def test_01_create_freezes_snapshot_and_enqueues(self):
        row=self._create()
        self.assertEqual(row['state'],'queued')
        with Session() as db:
            c=comparisons.get_comparison(db,row['id'])
            self.assertEqual(len(c.snapshot['group_a']['records']),22)
            self.assertEqual(len(c.snapshot['group_b']['records']),110)
            self.assertEqual(comparisons.queue.pushed[-1],('comparison:queue',row['id']))
            # 审计事件
            from src.models.audit import Audit
            ev=[r for r in REGISTRY.tables['audit_events'] if r.action=='comparison.queued']
            self.assertEqual(len(ev),1);self.assertEqual(ev[0].actor,Actor.email)

    def test_02_concurrent_appends_do_not_mix_into_locked_task(self):
        row=self._create()
        with Session() as db:
            db.add(Record(source_id=self.sa.id,reference='LATE',values={'session':'LATE-1','path':'X>Y'}));db.commit()
            c=comparisons.get_comparison(db,row['id'])
            self.assertEqual(len(c.snapshot['group_a']['records']),22)  # 仍是冻结时的 22 条
            live=comparisons.list_records(db,self.sa.id)
            self.assertEqual(len(live),23)  # 来源本身已含新追加

    def test_03_worker_completes_and_writes_csv_audit(self):
        row=self._create()
        worker.execute_comparison(row['id'])
        with Session() as db:
            c=comparisons.get_comparison(db,row['id'])
            self.assertEqual(c.state,'completed');self.assertEqual(c.error,'')
            res=c.result
            json.dumps(res,allow_nan=False)  # 可序列化、无 NaN
            xy={ (r['from'],r['to']):r for r in res['rows'] }[('X','Y')]
            self.assertTrue(xy['reversed_every_stratum'])
            self.assertEqual(xy['pool_hits_a'],13);self.assertEqual(xy['pool_n_a'],20)
            self.assertEqual(xy['pool_hits_b'],73);self.assertEqual(xy['pool_n_b'],110)
            self.assertEqual(xy['pool_direction'],'B组更高')
            for s in xy['per_stratum']:self.assertEqual(s['direction'],'A组更高')
            self.assertIn('p_holm',xy)
            # 工件 CSV
            path=os.path.join(ART,f'comparison-{c.id}.csv')
            self.assertTrue(os.path.exists(path));raw=open(path,'rb').read()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            text=raw.decode('utf-8-sig');reader=list(csv.DictReader(io.StringIO(text)))
            self.assertIn('stratum_direction',reader[0])
            xy_csv=[r for r in reader if r['from']=='X' and r['to']=='Y']
            self.assertEqual(len(xy_csv),2)  # 两个可比层各一行
            # 导出接口返回同样内容
            resp=export.comparison_csv(db,c.id);self.assertEqual(resp.body,raw)
            # 审计
            done=[r for r in REGISTRY.tables['audit_events'] if r.action=='comparison.completed']
            self.assertEqual(len(done),1)

    def test_04_stale_and_running_tasks_are_not_reprocessed(self):
        row=self._create()
        with Session() as db:
            c=comparisons.get_comparison(db,row['id']);c.state='running';db.commit()
        worker.execute_comparison(row['id'])  # 应直接返回
        with Session() as db:
            c=comparisons.get_comparison(db,row['id']);self.assertEqual(c.state,'running');self.assertIsNone(c.result)

    def test_05_worker_records_failed_state(self):
        row=self._create()
        with Session() as db:
            c=comparisons.get_comparison(db,row['id']);c.snapshot['group_b']['records']=[];db.commit()
        worker.execute_comparison(row['id'])
        with Session() as db:
            c=comparisons.get_comparison(db,row['id'])
            self.assertEqual(c.state,'failed');self.assertIn('会话',c.error)
            failed=[r for r in REGISTRY.tables['audit_events'] if r.action=='comparison.failed']
            self.assertEqual(len(failed),1)

    def test_06_reject_overlap_empty_missing_and_queue_outage(self):
        with Session() as db:
            with self.assertRaises(HTTPException) as cm:
                comparisons.create_comparison(db,Actor(),ComparisonInput(name='重叠拒绝',group_a_source_id=self.sa.id,group_b_source_id=self.sa.id))
            self.assertEqual(cm.exception.status_code,422)
            with self.assertRaises(HTTPException) as cm:
                comparisons.create_comparison(db,Actor(),ComparisonInput(name='缺来源',group_a_source_id=999,group_b_source_id=self.sb.id))
            self.assertEqual(cm.exception.status_code,404)
        empty=Source(key='SY-EMPTY',name='空文集',filename='e.csv',description='')
        with Session() as db:db.add(empty);db.commit()
        with Session() as db:
            with self.assertRaises(HTTPException) as cm:
                comparisons.create_comparison(db,Actor(),ComparisonInput(name='空文集对照',group_a_source_id=empty.id,group_b_source_id=self.sb.id))
            self.assertEqual(cm.exception.status_code,422)
        # 队列不可用 → 503 且任务落 failed
        comparisons.queue.available=False
        try:
            with Session() as db:
                with self.assertRaises(HTTPException) as cm:
                    comparisons.create_comparison(db,Actor(),ComparisonInput(name='队列中断',group_a_source_id=self.sa.id,group_b_source_id=self.sb.id))
                self.assertEqual(cm.exception.status_code,503)
                bad=REGISTRY.tables[ComparisonRun.__tablename__][-1]
                self.assertEqual(bad.state,'failed')
        finally:
            comparisons.queue.available=True

    def test_07_list_and_404_and_export_guard(self):
        with Session() as db:self.assertEqual(comparisons.list_comparisons(db),[])
        with self.assertRaises(HTTPException) as cm:
            with Session() as db:comparisons.get_comparison(db,12345)
        self.assertEqual(cm.exception.status_code,404)
        row=self._create()
        with Session() as db:
            with self.assertRaises(HTTPException) as cm:export.comparison_csv(db,row['id'])
            self.assertEqual(cm.exception.status_code,409)
            lst=comparisons.list_comparisons(db)
            self.assertEqual(len(lst),1);self.assertNotIn('snapshot',lst[0]);self.assertNotIn('result',lst[0])

    def test_08_algorithm_matches_frozen_snapshot_directly(self):
        row=self._create()
        with Session() as db:
            c=comparisons.get_comparison(db,row['id']);direct=compare(c.snapshot,{})
        worker.execute_comparison(row['id'])
        with Session() as db:
            stored=comparisons.get_comparison(db,row['id']).result
        self.assertEqual([ (r['from'],r['to']) for r in stored['rows'] ],
                         [ (r['from'],r['to']) for r in direct['rows'] ])
        self.assertEqual(stored['checksum'],direct['checksum'])

    def test_09_queue_routing_through_worker_main(self):
        row=self._create()
        item=worker.queue.blpop(['analysis:queue','comparison:queue'],timeout=2)
        self.assertEqual(item,('comparison:queue',row['id']))
        # 重新入队，由 main 循环消费一次后退出
        worker.queue.rpush('comparison:queue',row['id'])
        orig=worker.execute_comparison
        def stop_after(id):
            orig(id);raise SystemExit
        worker.execute_comparison=stop_after
        try:
            with self.assertRaises(SystemExit):worker.main()
        finally:
            worker.execute_comparison=orig
        with Session() as db:
            self.assertEqual(comparisons.get_comparison(db,row['id']).state,'completed')

if __name__=='__main__':
    unittest.main(verbosity=2)
