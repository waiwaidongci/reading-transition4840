"""两组互不重叠阅读文集的分层接续对照。

口径（与研究约定一致，前端不做任何统计计算）：
1. 受理时冻结两个来源的全部会话快照，并按会话路径长度（章节数）确定分层；
   之后来源的并发追加不会进入本次计算。
2. 每条接续边在同一会话内只计“有无”（出现即 1，重复经过仍为 1），不重复计数。
3. 仅使用两组都至少有 1 个会话的层（可比层）；只有一个组有人数的层整体剔除。
4. 对每条在可比层出现过的接续，固定各层组别人数及命中总数，先在可比层合并出的
   2×2 表上做双侧 Fisher 精确检验（超几何分布，固定边际），再对全部受检接续做
   Holm 校正；校正未完成不发布结果。
5. 页面只列出合并方向与每一个可比层方向都相反的接续（辛普森式反转）。
"""
import hashlib,json,math
from collections import defaultdict

STRATUM_RULE='按会话章节路径长度分层（路径包含的章节数）'

def _log_combine(n,k):
    if k<0 or k>n:return float('-inf')
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)

def fisher_two_sided(a,n1,b,n2):
    """固定边际的双侧 Fisher 精确检验。

    表：组1命中 a / 人数 n1；组2命中 b / 人数 n2。
    命中总数 K=a+b、总人数 N=n1+n2 固定，组1命中数 X 服从超几何分布。
    双侧 p 值为所有概率不大于观测表概率的超几何点概率之和。
    """
    K=a+b;N=n1+n2
    if n1==0 or n2==0 or K==0 or K==N:
        return 1.0,K*n1/N
    lo=max(0,K-n2);hi=min(n1,K)
    denom=_log_combine(N,K)
    def prob(x):return math.exp(_log_combine(n1,x)+_log_combine(n2,K-x)-denom)
    p_obs=prob(a)
    p=0.0
    for x in range(lo,hi+1):
        px=prob(x)
        if px<=p_obs+1e-12:p+=px
    return min(1.0,p),K*n1/N

def holm(raw_pvalues):
    """Holm 逐步校正，返回与输入等长的校正 p 值（按原顺序）。"""
    m=len(raw_pvalues)
    if m==0:return []
    order=sorted(range(m),key=lambda i:raw_pvalues[i])
    adjusted=[0.0]*m
    running=0.0
    for rank,idx in enumerate(order):
        value=(m-rank)*raw_pvalues[idx]
        running=max(running,value)
        adjusted[idx]=min(1.0,running)
    return adjusted

def _session_index(records,group_label):
    """把冻结记录整理为 {层: {会话: 边集合}}，并做唯一性校验。"""
    strata=defaultdict(dict)
    for r in records:
        values=r['values'];sid=values['session']
        path=[s.strip() for s in values['path'].split('>')]
        if any(not x for x in path):raise ValueError('存在空章节的会话路径，无法对照')
        key=len(path)
        if sid in strata[key]:raise ValueError(group_label+'存在重复会话编号：'+sid)
        edges=set(zip(path,path[1:]))
        strata[key][sid]=edges
    return strata

def _edge_hits(sessions):
    """一层内每条边的命中会话数（每会话只计有无）。"""
    hits=defaultdict(int)
    for edges in sessions.values():
        for edge in edges:hits[edge]+=1
    return hits

def compare(snapshot,parameters=None):
    group_a=snapshot['group_a'];group_b=snapshot['group_b']
    label_a=group_a.get('source',{}).get('name','A组');label_b=group_b.get('source',{}).get('name','B组')
    idx_a=_session_index(group_a['records'],'A组（'+label_a+'）')
    idx_b=_session_index(group_b['records'],'B组（'+label_b+'）')
    if not group_a['records'] or not group_b['records']:
        raise ValueError('两个文集都必须至少包含1个会话才能对照')
    # 仅保留两组都有人数的可比层
    comparable=sorted(k for k in idx_a.keys() & idx_b.keys()
                      if len(idx_a[k])>0 and len(idx_b[k])>0)
    if not comparable:
        raise ValueError('没有两组都有人数的共同分层，无法计算合并与分层比例')

    strata_rows=[]
    for k in comparable:
        sa,sb=idx_a[k],idx_b[k]
        ha,hb=_edge_hits(sa),_edge_hits(sb)
        strata_rows.append({'stratum':'%d章会话'%k,'stratum_value':k,
                            'n_a':len(sa),'n_b':len(sb),'hits_a':ha,'hits_b':hb,
                            'edges':set(ha)|set(hb)})

    tested_edges=set().union(*(s['edges'] for s in strata_rows)) if strata_rows else set()
    if not tested_edges:
        raise ValueError('可比层内没有任何相邻章节接续，无法计算接续对照')
    rows=[]
    for edge in sorted(tested_edges,key=lambda e:(e[0],e[1])):
        per_stratum=[];A=B=N1=N2=0
        for s in strata_rows:
            n1,n2=s['n_a'],s['n_b']
            a=s['hits_a'].get(edge,0);b=s['hits_b'].get(edge,0)
            A+=a;B+=b;N1+=n1;N2+=n2
            pa,pb=a/n1,b/n2
            if pa==pb:direction='持平'
            else:direction='A组更高' if pa>pb else 'B组更高'
            per_stratum.append({'stratum':s['stratum'],'stratum_value':s['stratum_value'],
                                'n_a':n1,'n_b':n2,'hits_a':a,'hits_b':b,
                                'rate_a':pa,'rate_b':pb,'direction':direction})
        pool_na,pool_nb=A/N1,B/N2
        if pool_na==pool_nb:pool_direction='持平'
        else:pool_direction='A组更高' if pool_na>pool_nb else 'B组更高'
        p_value,expected=fisher_two_sided(A,N1,B,N2)
        rows.append({'from':edge[0],'to':edge[1],
                     'pool_hits_a':A,'pool_hits_b':B,'pool_n_a':N1,'pool_n_b':N2,
                     'pool_rate_a':pool_na,'pool_rate_b':pool_nb,
                     'pool_direction':pool_direction,'expected_hits_a':expected,
                     'p_value':p_value,'per_stratum':per_stratum})
    # 对“所有在可比层出现过的接续”一次性做 Holm 校正，齐全后才允许发布
    adjusted=holm([r['p_value'] for r in rows])
    for r,q in zip(rows,adjusted):
        r['p_holm']=q
        directions={s['direction'] for s in r['per_stratum']}
        r['reversed_every_stratum']=(r['pool_direction']!='持平'
                                     and '持平' not in directions
                                     and directions=={('B组更高' if r['pool_direction']=='A组更高' else 'A组更高')})
    rows.sort(key=lambda r:(not r['reversed_every_stratum'],r['p_holm'],r['from'],r['to']))

    stratum_summary=[{'stratum':s['stratum'],'stratum_value':s['stratum_value'],
                      'n_a':s['n_a'],'n_b':s['n_b'],
                      'edges':len(s['edges'])} for s in strata_rows]
    excluded=sorted((set(idx_a)|set(idx_b))-set(comparable))
    reversed_rows=[r for r in rows if r['reversed_every_stratum']]
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {
        'summary':[
            {'label':'A组冻结会话','value':len(group_a['records'])},
            {'label':'B组冻结会话','value':len(group_b['records'])},
            {'label':'可比分层数','value':len(comparable)},
            {'label':'受检接续总数','value':len(rows)},
            {'label':'全层反转接续','value':len(reversed_rows)},
        ],
        'strata':stratum_summary,
        'excluded_strata':[{'stratum_value':k,
                            'n_a':len(idx_a.get(k,{})),'n_b':len(idx_b.get(k,{}))} for k in excluded],
        'rows':rows,
        'reversed_rows':reversed_rows,
        'columns':['from','to','pool_direction','pool_rate_a','pool_rate_b',
                   'pool_hits_a','pool_hits_b','p_holm'],
        'explanation':('分层='+STRATUM_RULE+'。每条接续在同一会话只计有无；仅用两组都有人数的可比层。'
                       '合并表做双侧Fisher精确检验（固定各层组别人数与命中总数），再对全部受检接续做Holm校正；'
                       '仅展示合并方向与每个可比层方向都相反的接续。关联非因果。'),
        'method':{'test':'two-sided Fisher exact（超几何，固定边际）','correction':'Holm',
                  'presence':'同一会话同一边只计有无','stratum_rule':STRATUM_RULE},
        'checksum':digest,
        'seed':42,
    }
