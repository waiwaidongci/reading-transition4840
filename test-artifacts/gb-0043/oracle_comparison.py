"""分层文集对照的独立 oracle（与产品代码完全独立的一份实现）。

仅依赖标准库，用于交叉验证 backend/src/services/comparison_algorithm.py：
- 手工枚举超几何表计算双侧 Fisher 精确概率；
- 独立实现 Holm 校正；
- 手算分层/合并命中率与全层反转判定。
运行：python3 -I test-artifacts/gb-0043/oracle_comparison.py
"""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','..','backend'))
from src.services.comparison_algorithm import compare,fisher_two_sided,holm

def comb(n,k):
    if k<0 or k>n:return 0
    import math
    return math.factorial(n)//(math.factorial(k)*math.factorial(n-k))

def oracle_fisher(a,n1,b,n2):
    K=a+b;N=n1+n2
    lo=max(0,K-n2);hi=min(n1,K)
    denom=comb(N,K);p_obs=comb(n1,a)*comb(n2,K-a)/denom
    return min(1.0,sum(comb(n1,x)*comb(n2,K-x)/denom
                       for x in range(lo,hi+1)
                       if comb(n1,x)*comb(n2,K-x)/denom<=p_obs+1e-15))

def oracle_holm(pvals):
    m=len(pvals);order=sorted(range(m),key=lambda i:pvals[i])
    out=[0.0]*m;prev=0.0
    for j,i in enumerate(order):
        prev=max(prev,(m-j)*pvals[i]);out[i]=min(1.0,prev)
    return out

def rec(sid,path):
    return {'id':abs(hash(sid))%100000,'reference':sid,
            'values':{'session':sid,'path':'>'.join(path)}}

def edge_sessions(prefix,n_hits,n_miss,edge,miss_path):
    """生成同层会话：命中会话与未命中会话的章节数必须相同（分层按路径长度）。"""
    length=len(edge)
    assert len(miss_path)==length
    out=[]
    for i in range(n_hits):out.append(rec(f'{prefix}-h{i}',list(edge)))
    for i in range(n_miss):out.append(rec(f'{prefix}-m{i}',miss_path))
    return out

EDGE=('X','Y')
def canonical_snap(include_tie_stratum=False):
    # 经典辛普森：每层 A 都高于 B，但 B 集中在高层、A 集中在低层 → 合并 B 反超。
    # 层 2章：A 5/10=.50 > B 3/10=.30
    a2=edge_sessions('A2',5,5,EDGE,['P','Q'])
    b2=edge_sessions('B2',3,7,EDGE,['P','Q'])
    # 层 3章：A 8/10=.80 > B 70/100=.70（命中用 3 章路径 X>Y>Z）
    a3=edge_sessions('A3',8,2,('X','Y','Z'),['R','S','T'])
    b3=edge_sessions('B3',70,30,('X','Y','Z'),['R','S','T'])
    a=a2+a3;b=b2+b3
    if include_tie_stratum:
        # 1章单章会话：两组都有人数但无任何边 → 该层方向持平，应阻止“全层反转”
        a+=[rec('A1-0',['Solo'])];b+=[rec('B1-0',['Solo'])]
    # 只在 A 出现的 4 章层（含重复经过 X→Y 的会话）→ 不可比，整体剔除
    a+=[rec('A4-0',['I','J','K','L']),rec('A4-1',['X','Y','X','Y'])]
    return {'group_a':{'source':{'id':1,'name':'甲组'},'records':a},
            'group_b':{'source':{'id':2,'name':'乙组'},'records':b}}

def check(name,cond,detail=''):
    print(('  PASS ' if cond else '  FAIL ')+name+(' — '+detail if detail else ''))
    if not cond:check.failures+=1
check.failures=0

def main():
    print('1) Fisher 双侧精确概率（独立枚举交叉验证）')
    cases=[(2,5,3,8),(1,2,2,5),(2,3,1,3),(0,4,4,6),(3,3,0,3),(1,10,5,10),(8,10,70,100)]
    for a,n1,b,n2 in cases:
        p1,_=fisher_two_sided(a,n1,b,n2);p2=oracle_fisher(a,n1,b,n2)
        check(f'表 a={a},n1={n1},b={b},n2={n2}',abs(p1-p2)<=1e-12,f'p={p1:.6f} oracle={p2:.6f}')
    # 手算 [[2,3],[3,5]]：观测点概率 30/1287≈.0233 为最小值 → 双侧 p=1
    p,_=fisher_two_sided(2,5,3,8)
    check('观测表为最小概率点时双侧 p=1',abs(p-1.0)<=1e-12,str(p))
    # 手算 [[0,4],[4,2]]：只有 x=0(.0762) 与 x=4(.0105) 入选 → p=.0866...
    p,_=fisher_two_sided(0,4,4,6)
    manual=(comb(4,0)*comb(6,4)+comb(4,4)*comb(6,0))/comb(10,4)
    check('[[0,4],[4,2]] 手算双侧 p',abs(p-manual)<=1e-12,f'{p:.6f} vs {manual:.6f}')

    print('2) Holm 校正（独立实现交叉验证）')
    raw=[0.01,0.04,0.03,0.9];adj=holm(raw);ref=oracle_holm(raw)
    check('Holm 与独立实现一致',all(abs(x-y)<=1e-12 for x,y in zip(adj,ref)),str(adj))
    check('Holm 校正值不小于对应原值',all(adj[i]>=raw[i]-1e-15 for i in range(4)))
    check('最小 p 校正为 m*p1=0.04',abs(adj[0]-0.04)<=1e-12)
    check('Holm 对全 1 输入保持 1',all(abs(x-1)<1e-12 for x in holm([1.0,1.0])))

    print('3) 端到端：分层口径、会话级有无、不可比层剔除、全层反转')
    result=compare(canonical_snap(),{})
    rows={(r['from'],r['to']):r for r in result['rows']}
    xy=rows[EDGE]
    check('X→Y 合并 A 命中=13 (5+8)',xy['pool_hits_a']==13,str(xy['pool_hits_a']))
    check('X→Y 合并 A 人数=20（4章层被剔除）',xy['pool_n_a']==20,str(xy['pool_n_a']))
    check('X→Y 合并 B 命中=73 (3+70)',xy['pool_hits_b']==73)
    check('X→Y 合并 B 人数=110',xy['pool_n_b']==110)
    check('合并方向 B 更高 (13/20=.65 < 73/110≈.664)',xy['pool_direction']=='B组更高',
          f"{xy['pool_rate_a']:.4f} vs {xy['pool_rate_b']:.4f}")
    strata={s['stratum_value']:s for s in xy['per_stratum']}
    check('可比层仅 2/3 章；1章未加入、4章不可比被剔除',sorted(strata)==[2,3],str(sorted(strata)))
    check('2章层 A 更高 (.5>.3)',strata[2]['direction']=='A组更高'
          and strata[2]['hits_a']==5 and strata[2]['hits_b']==3)
    check('3章层 A 更高 (.8>.7)',strata[3]['direction']=='A组更高'
          and strata[3]['hits_a']==8 and strata[3]['hits_b']==70)
    check('每个可比层方向都与合并相反 → 全层反转',xy['reversed_every_stratum'] is True)
    check('反转行进入 reversed_rows',xy in result['reversed_rows'])
    check('非反转边不被标记',all(r['reversed_every_stratum'] is False
                                for k,r in rows.items() if k!=EDGE))
    # 摘要与剔除层信息
    check('受检接续总数含其它边',result['summary'][3]['value']==len(rows))
    check('剔除层登记 4章（仅 A 有）',[e['stratum_value'] for e in result['excluded_strata']]==[4])

    print('4) 同一会话重复经过目标边只计有无')
    snap=canonical_snap()
    snap['group_a']['records']=[r for r in snap['group_a']['records'] if not r['values']['session'].startswith('A4')]
    # 3章层追加 X>Y>X：X→Y 在该会话出现两次，但只计 1 次命中
    snap['group_a']['records'].append(rec('A3-dup',['X','Y','X']))
    res=compare(snap,{});xy2={(r['from'],r['to']):r for r in res['rows']}[EDGE]
    s3={s['stratum_value']:s for s in xy2['per_stratum']}[3]
    check('3章层 A 人数 +1、命中仅 +1（重复边只计有无）',s3['n_a']==11 and s3['hits_a']==9,
          f"n={s3['n_a']} hits={s3['hits_a']}")

    print('5) 持平层阻止全层反转')
    tie=compare(canonical_snap(include_tie_stratum=True),{})
    xyt={(r['from'],r['to']):r for r in tie['rows']}[EDGE]
    vals={s['stratum_value']:s['direction'] for s in xyt['per_stratum']}
    check('可比层变为 1/2/3 章',sorted(vals)==[1,2,3],str(sorted(vals)))
    check('1章层方向持平',vals[1]=='持平')
    check('存在持平层时不标记全层反转',xyt['reversed_every_stratum'] is False)
    check('reversed_rows 为空',tie['reversed_rows']==[])

    print('6) 校正齐全才发布：每行都有 p_holm，且与独立 Holm 一致')
    ordered=sorted(result['rows'],key=lambda r:(r['from'],r['to']))
    raw_p=[r['p_value'] for r in ordered]
    check('校正数量=受检接续数量',len(result['rows'])==len(raw_p)
          and all('p_holm' in r for r in result['rows']))
    check('Holm 值与独立实现一致',
          all(abs(r['p_holm']-q)<=1e-12 for r,q in zip(ordered,oracle_holm(raw_p))))
    # X→Y 的原始 p 与 oracle 对合并表手算一致
    check('X→Y 原始双侧 p 与 oracle 一致',
          abs(xy['p_value']-oracle_fisher(13,20,73,110))<=1e-12,f"{xy['p_value']:.6f}")

    print('7) 拒绝退化输入')
    good=canonical_snap()
    for bad,msg in [
        ({'group_a':{'source':{},'records':[]},'group_b':good['group_b']},'空文集'),
        ({'group_a':good['group_a'],'group_b':{'source':{},'records':[rec('z',['K'])]}},'无可比层'),
    ]:
        try:compare(bad,{});check(msg+' 被拒绝',False)
        except ValueError:check(msg+' 被拒绝',True)
    try:
        dup=dict(good);dup['group_a']={'source':good['group_a']['source'],
            'records':good['group_a']['records']+[rec('A2-h0',['X','Y'])]}
        compare(dup,{});check('重复会话编号被拒绝',False)
    except ValueError:check('重复会话编号被拒绝',True)
    try:
        solo={'group_a':{'source':{},'records':[rec('s1',['单章'])]},
              'group_b':{'source':{},'records':[rec('s2',['单章']),rec('s3',['独章'])]}}
        compare(solo,{});check('可比层均无边时被拒绝',False)
    except ValueError:check('可比层均无边时被拒绝',True)

    print()
    print('FAILURES=%d'%check.failures)
    sys.exit(1 if check.failures else 0)

if __name__=='__main__':main()
