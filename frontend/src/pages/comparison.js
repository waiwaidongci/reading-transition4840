import {domain} from '../constants/domain.js';
import {research} from '../stores/research.js';
import {session} from '../stores/session.js';
import {comparisonsApi} from '../api/research.js';
import {download} from '../api/client.js';
import {sourceOptions} from '../components/common/business.js';
import {status} from '../components/common/status.js';
import {esc,fmt} from '../utils/format.js';
import {action,bind,toast} from '../hooks/actions.js';

const pct=x=>(x*100).toFixed(2)+'%';
function directionBadge(d){const cls=d==='持平'?'neutral':d==='A组更高'?'dir-a':'dir-b';return '<span class="dir-badge '+cls+'">'+esc(d)+'</span>'}
function comparisonOptions(list,id){return list.map(c=>'<option value="'+c.id+'" '+(c.id==id?'selected':'')+'>'+esc(c.name)+' · #'+c.id+'</option>').join('')}

function stratumTable(row){
  return '<div class="table-wrap"><table><thead><tr><th>分层</th><th>A组人数</th><th>B组人数</th><th>A组命中</th><th>B组命中</th><th>A组比例</th><th>B组比例</th><th>该层方向</th></tr></thead><tbody>'
    +row.per_stratum.map(s=>'<tr><td>'+esc(s.stratum)+'</td><td>'+s.n_a+'</td><td>'+s.n_b+'</td><td>'+s.hits_a+'</td><td>'+s.hits_b+'</td><td>'+pct(s.rate_a)+'</td><td>'+pct(s.rate_b)+'</td><td>'+directionBadge(s.direction)+'</td></tr>').join('')
    +'</tbody></table></div>';
}

export async function comparisonPage(){
  const c=research.comparisonId?await comparisonsApi.get(research.comparisonId).catch(()=>null):null;
  research.activeComparison=c;const result=c?.result;
  return '<section class="page-heading"><p class="eyebrow">05 / STRATIFIED TWO-GROUP COMPARISON</p><h1>两组文集混看时，哪些接续在每一层都反着来。</h1>'
    +'<p>选择两个互不重叠的文集，受理时一并冻结会话与分层；每条接续在同一会话只计有无，仅用两组都有人数的层计算合并与分层比例。合并表做双侧 Fisher 精确检验，再对全部受检接续做 Holm 校正，校正齐全后才发布。</p></section>'
    +'<div class="split"><section class="config-sheet"><h2>新建分层对照</h2>'
    +(session.writable?'<form id="comparison-form"><label>对照名称<input name="name" required value="两文集分层接续对照"></label><label>A 组文集<select name="group_a_source_id">'+sourceOptions(research.sources,research.sourceId)+'</select></label><label>B 组文集（须与 A 组互不重叠）<select name="group_b_source_id">'+sourceOptions(research.sources,research.sources[1]?.id||research.sourceId)+'</select></label><p class="fine">分层口径：按会话章节路径长度（章节数）分层 · 提交即冻结两组全部会话，后续追加不混入</p><button type="submit">锁定会话与分层并执行 →</button></form>'
      :'<p>阅读者可查看已完成对照；新建对照由分析师或负责人执行。</p>')
    +'</section><aside><h2>对照任务</h2><div class="ledger">'+(research.comparisons.length?research.comparisons.slice(0,8).map(x=>'<a href="#comparison" data-comparison="'+x.id+'"><small>#'+x.id+'</small><strong>'+esc(x.name)+'</strong>'+status(x.state)+'</a>').join(''):'<div class="empty">还没有对照任务。</div>')+'</div><div class="method-note"><b>统计口径</b><p>固定各层组别人数及命中总数；双侧 Fisher 精确检验（超几何固定边际）+ Holm 校正。页面仅列合并方向与各层都相反的接续。</p></div></aside></div>'
    +(c?'<div class="run-title"><h2>'+esc(c.name)+'</h2>'+status(c.state)+'<small>#'+c.id+' · A组 #'+c.group_a_source_id+' / B组 #'+c.group_b_source_id+'</small>'+(c.state==='completed'?'<button id="export-comparison" class="secondary">下载对照 CSV（含全部受检接续）↗</button>':'')+'</div>'
      +(c.state==='failed'?'<div class="failure"><h2>本次对照未完成</h2><p>'+esc(c.error)+'</p></div>'
        :!result?'<div class="pending"><span class="spinner"></span><h2>独立 worker 正在处理</h2><p>页面自动刷新状态。</p></div>'
          :renderResult(result)):'');
}

function renderResult(result){
  const reversed=result.reversed_rows;
  let html='<p class="fine">'+esc(result.explanation)+'</p><dl class="metrics">'
    +result.summary.map(x=>'<div><dt>'+esc(x.label)+'</dt><dd>'+fmt(x.value)+'</dd></div>').join('')+'</dl>';
  html+='<h2>可比分层 <small>仅两组都有人数的层进入计算</small></h2><div class="table-wrap"><table><thead><tr><th>分层</th><th>A组人数</th><th>B组人数</th><th>该层出现过的接续</th></tr></thead><tbody>'
    +result.strata.map(s=>'<tr><td>'+esc(s.stratum)+'</td><td>'+s.n_a+'</td><td>'+s.n_b+'</td><td>'+s.edges+'</td></tr>').join('')+'</tbody></table></div>';
  if(result.excluded_strata.length){html+='<p class="fine">已剔除的不可比层（仅一组有人数）：'+result.excluded_strata.map(e=>esc(e.stratum_value+'章层(A='+e.n_a+',B='+e.n_b+')')).join('；')+'</p>'}
  html+='<h2>全层反转接续 <small>合并方向与每个可比层方向都相反；共 '+reversed.length+' 条</small></h2>';
  if(!reversed.length){html+='<div class="empty"><strong>没有满足条件的接续。</strong><p>当前冻结数据中，不存在合并方向与所有可比层方向都相反的接续。</p></div>';return html}
  html+='<div class="reversal-list">'+reversed.map(r=>'<article class="reversal-card"><header><h3>'+esc(r.from)+' → '+esc(r.to)+'</h3><div>合并方向：'+directionBadge(r.pool_direction)+'<small> 校正 p='+r.p_holm.toFixed(4)+'</small></div></header>'
    +'<p class="fine">合并：A组 '+r.pool_hits_a+'/'+r.pool_n_a+'（'+pct(r.pool_rate_a)+'） · B组 '+r.pool_hits_b+'/'+r.pool_n_b+'（'+pct(r.pool_rate_b)+'） · 原始双侧 p='+r.p_value.toFixed(4)+' · Holm 校正 p='+r.p_holm.toFixed(4)+'</p>'
    +stratumTable(r)+'</article>').join('')+'</div>';
  return html;
}

export function bindComparison(refresh){
  action('#comparison-form',async form=>{
    const data=Object.fromEntries(new FormData(form));
    if(Number(data.group_a_source_id)===Number(data.group_b_source_id)){toast('两组文集必须互不重叠，请选择不同来源',true);return}
    const r=await comparisonsApi.create({name:data.name,group_a_source_id:Number(data.group_a_source_id),group_b_source_id:Number(data.group_b_source_id)});
    research.comparisonId=r.id;await refresh();toast('对照已受理，会话与分层已冻结')
  });
  for(const a of document.querySelectorAll('[data-comparison]'))a.addEventListener('click',()=>{research.comparisonId=Number(a.dataset.comparison);refresh()});
  bind('#export-comparison','click',async()=>{try{await download('/comparisons/'+research.comparisonId+'/export','comparison-'+research.comparisonId+'.csv')}catch(e){toast(e.message,true)}});
  if(['queued','running'].includes(research.activeComparison?.state))setTimeout(refresh,1500);
}
