import csv,io
from fastapi import HTTPException
from fastapi.responses import Response
from ..models.note import Note
from ..models.comparison import ComparisonRun
from .runs import get_run
from .comparisons import get_comparison
def csv_response(result,filename):
    buf=io.StringIO();fields=result['columns'];w=csv.DictWriter(buf,fieldnames=fields);w.writeheader()
    for r in result['rows']:w.writerow({k:r.get(k,'') for k in fields})
    return Response('﻿'+buf.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="'+filename+'"'})
def run_csv(db,id):
    r=get_run(db,id)
    if r.state!='completed':raise HTTPException(409,'结果尚未完成')
    return csv_response(r.result,'run-'+str(id)+'.csv')
def note_csv(db,id):
    n=db.get(Note,id)
    if not n:raise HTTPException(404,'未找到说明')
    if n.state!='approved':raise HTTPException(403,'仅批准后的业务说明可导出')
    return csv_response(n.frozen_result,'approved-'+str(id)+'.csv')
def comparison_csv(db,id):
    c=get_comparison(db,id)
    if c.state!='completed':raise HTTPException(409,'对照结果尚未完成')
    result=c.result
    fields=['from','to','pool_direction','pool_rate_a','pool_rate_b','pool_hits_a','pool_hits_b',
            'pool_n_a','pool_n_b','p_value','p_holm','reversed_every_stratum',
            'stratum','stratum_n_a','stratum_n_b','stratum_hits_a','stratum_hits_b',
            'stratum_rate_a','stratum_rate_b','stratum_direction']
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=fields);w.writeheader()
    for r in result['rows']:
        for s in r['per_stratum']:
            w.writerow({'from':r['from'],'to':r['to'],'pool_direction':r['pool_direction'],
                        'pool_rate_a':r['pool_rate_a'],'pool_rate_b':r['pool_rate_b'],
                        'pool_hits_a':r['pool_hits_a'],'pool_hits_b':r['pool_hits_b'],
                        'pool_n_a':r['pool_n_a'],'pool_n_b':r['pool_n_b'],
                        'p_value':r['p_value'],'p_holm':r['p_holm'],
                        'reversed_every_stratum':r['reversed_every_stratum'],
                        'stratum':s['stratum'],'stratum_n_a':s['n_a'],'stratum_n_b':s['n_b'],
                        'stratum_hits_a':s['hits_a'],'stratum_hits_b':s['hits_b'],
                        'stratum_rate_a':s['rate_a'],'stratum_rate_b':s['rate_b'],
                        'stratum_direction':s['direction']})
    return Response('﻿'+buf.getvalue(),media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="comparison-'+str(id)+'.csv"'})
