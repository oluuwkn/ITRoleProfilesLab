(function(){
const D=window.SURVEY_DATA;
const ROLE={fullstack:'Fullstack',backend:'Backend',frontend:'Frontend',desktop:'Desktop',mobile:'Mobile',ml_engineer:'AI/ML',embedded:'Embedded'};
const CAT={languages:'Языки',databases:'Базы данных',web:'Веб-фреймворки',cloud_tools:'Облака и инструменты'};
const METH={frequency:'p',ratio:'L',log:'Slog',sqrt:'Sroot',linear:'Slin'};
const MKEYS=['frequency','ratio','log','sqrt','linear'];
const TH=[0.01,0.025,0.04,0.05,0.10];
const $=id=>document.getElementById(id);
const fmt=(x,d=3)=>x==null||isNaN(x)?'-':x.toFixed(d).replace('.',',');
const pct=(x,d=1)=>x==null||isNaN(x)?'-':(x*100).toFixed(d).replace('.',',')+'%';
const nf=n=>n.toLocaleString('ru-RU');
function opts(sel,items,val){sel.innerHTML=items.map(([v,t])=>`<option value="${v}"${v==val?' selected':''}>${t}</option>`).join('')}
const roleItems=D.roles.map(r=>[r,ROLE[r]]);
const scopeItems=[['all_categories','Все категории (объединённый список)'],...D.cats.map(c=>[c,CAT[c]])];
const thItems=TH.map(t=>[t,pct(t,t<0.03&&t!=0.01?1:0).replace(',0%','%')]);

//facts
const A=D.audit;const resp=Object.fromEntries(D.resp.map(r=>[r.role,r]));
const roleN=D.roles.reduce((s,r)=>s+resp[r].n_total,0);
$('facts').innerHTML=[[nf(A.shape[0]),'записей в файле опроса'],[nf(roleN),'респондентов в семи ролях'],['228 → 619','пар при f ≥ 4% и p ≥ 4%'],[nf(A.complete_cases),'ответили на все четыре вопроса']].map(([n,t])=>`<div class="fact"><div class="n">${n}</div><div class="t">${t}</div></div>`).join('');

//routing
const views=['overview','profiles','thresholds','methods','stability','data'];
const names={overview:'Обзор',profiles:'Профили ролей',thresholds:'Знаменатели и пороги',methods:'Сравнение правил',stability:'Устойчивость',data:'Данные и методика'};
function route(){const h=(location.hash||'#overview').slice(1);const v=views.includes(h)?h:'overview';
  document.querySelectorAll('[data-view]').forEach(s=>s.hidden=s.id!=='v-'+v);
  document.querySelectorAll('#nav a').forEach(a=>a.toggleAttribute('aria-current',a.getAttribute('href')==='#'+v)&&a.setAttribute('aria-current','page'));
  $('crumb').textContent=names[v];window.scrollTo(0,0)}
window.addEventListener('hashchange',route);route();

//PROFILES
opts($('p-role'),roleItems,'backend');opts($('p-cat'),scopeItems.map(([v,t])=>[v,v==='all_categories'?'Все категории':t]),'databases');opts($('p-t'),thItems,0.04);
function rankMin(vals){const s=[...vals].sort((a,b)=>b-a);return vals.map(v=>1+s.findIndex(x=>x===v))}
function renderProfiles(){
  const role=$('p-role').value,cat=$('p-cat').value,den=$('p-den').value,co=$('p-co').value,t=+$('p-t').value,sort=$('p-sort').value;
  let bg=$('p-bg').value;
  const compl=co==='complete';$('p-den').disabled=compl;$('p-bg').disabled=compl;
  const key=compl?'complete|p|inclusive':`full|${den}|${bg}`;const usedDen=compl?'p':den;
  const arr=D.cond[key][role];const rows=[];
  arr.forEach((v,i)=>{if(!v)return;const [ci,name]=D.techs[i];const c=D.cats[ci];if(cat!=='all_categories'&&c!==cat)return;
    const fr=v[0],L=v[1];if(fr<t||L==null)return;
    rows.push({i,name,c,freq:fr,ratio:L,log:fr*Math.log1p(L),sqrt:fr*Math.sqrt(L),lin:fr*L})});
  const r=rankMin(rows.map(x=>x[sort]));rows.forEach((x,j)=>x.rank=r[j]);rows.sort((a,b)=>a.rank-b.rank||a.name.localeCompare(b.name));
  const bootOK=key==='full|p|inclusive'&&cat==='all_categories';const mkey={freq:'frequency',ratio:'ratio',log:'log',sqrt:'sqrt',lin:'linear'}[sort];
  const maxL=Math.max(2,...rows.map(x=>x.ratio));const sym=usedDen==='p'?'p':'f';
  const head=`<tr><th class="l">#</th><th class="l">Технология</th>${cat==='all_categories'?'<th class="l">Категория</th>':''}<th class="${sort==='freq'?'sortcol':''}">${sym}</th><th class="${sort==='ratio'?'sortcol':''}">L</th><th class="${sort==='log'?'sortcol':''}">Slog</th><th class="${sort==='sqrt'?'sortcol':''}">Sroot</th><th class="${sort==='lin'?'sortcol':''}">Slin</th>${bootOK?'<th title="Доля бутстреп-повторов, в которых технология вошла в top-10 по выбранному правилу">в top-10, бутстреп</th>':''}</tr>`;
  const body=rows.map(x=>`<tr><td class="l">${x.rank}</td><td class="name">${x.name}</td>${cat==='all_categories'?`<td class="l cat">${CAT[x.c]}</td>`:''}<td>${pct(x.freq)}<span class="ruler"><i style="width:${Math.min(100,x.freq*100)}%"></i></span></td><td>${fmt(x.ratio,2)}<span class="lmark"><span class="one" style="left:${100/maxL}%"></span><span class="pt" style="left:${Math.min(100,x.ratio/maxL*100)}%"></span></span></td><td>${fmt(x.log)}</td><td>${fmt(x.sqrt)}</td><td>${fmt(x.lin)}</td>${bootOK?`<td>${pct(D.boot_top10[role][mkey][x.i],1)}</td>`:''}</tr>`).join('');
  $('p-table').innerHTML=`<thead>${head}</thead><tbody>${body||'<tr><td class="l" colspan="9">Ни одна технология не проходит порог. Снизьте порог или выберите другую категорию.</td></tr>'}</tbody>`;
  const R=resp[role];const Ncat=cat==='all_categories'?null:(compl?null:D.eq[role][cat][0]);
  $('p-summary').innerHTML=`<span>Отобрано: <strong>${rows.length}</strong> технологий при ${sym} ≥ ${pct(t,t===0.025?1:0)}</span><span>Респондентов роли: <strong>${nf(compl?R.n_complete:R.n_total)}</strong></span>${Ncat?`<span>Ответили на вопрос: <strong>${nf(Ncat)}</strong></span>`:''}`;
  $('p-note').textContent=(cat==='all_categories'?'Объединённый список смешивает категории с разным числом вариантов ответа и служит проверкой объединения категорий, а не рейтингом важности. ':'')+'Шкала у L: вертикальная черта - значение 1 (технология встречается в роли так же часто, как у всех).'+(bootOK?' Колонка бутстрепа относится к объединённому top-10 при p ≥ 4%, фоне со всеми ответившими и полной выборке.':'');
}
['p-role','p-cat','p-den','p-bg','p-co','p-t','p-sort'].forEach(id=>$(id).addEventListener('change',renderProfiles));renderProfiles();

//THRESHOLDS
function renderThresholds(){
  const t=Math.max(0.005,(+$('t-val').value||4)/100);
  let pf=0,pp=0;D.roles.forEach(r=>{D.cond['full|f|inclusive'][r].forEach(v=>{if(v&&v[0]>=t)pf++});D.cond['full|p|inclusive'][r].forEach(v=>{if(v&&v[0]>=t)pp++})});
  $('t-summary').innerHTML=`<span>Пар при f ≥ ${fmt(t*100,1)}%: <strong>${pf}</strong></span><span>Пар при p ≥ ${fmt(t*100,1)}%: <strong>${pp}</strong></span>`;
  const rows=D.roles.map(r=>`<tr><td class="l">${ROLE[r]}</td>${D.cats.map(c=>{const [N,M]=D.eq[r][c];const m=M/N;return `<td>${fmt(m,2)} / ${pct(t*m)}</td>`}).join('')}</tr>`).join('');
  const all=`<tr><td class="l"><b>Все ответившие</b></td>${D.cats.map(c=>{const [N,M]=D.eq_all[c];const m=M/N;return `<td>${fmt(m,2)} / ${pct(t*m)}</td>`}).join('')}</tr>`;
  $('t-table').innerHTML=`<thead><tr><th class="l">Роль</th>${D.cats.map(c=>`<th>${CAT[c]}</th>`).join('')}</tr></thead><tbody>${rows}${all}</tbody>`;
}
$('t-val').addEventListener('input',renderThresholds);renderThresholds();

//METHODS
opts($('m-role'),roleItems,'backend');opts($('m-scope'),scopeItems,'languages');opts($('m-t'),thItems,0.04);
function heat(v){if(v==null)return '';const a=Math.max(0,Math.min(1,(v+1)/2));return `background:color-mix(in srgb,var(--accent) ${Math.round(a*a*70)}%,var(--heat0));color:${a>0.8?'#fff':'inherit'}`}
function renderMethods(){
  const r=$('m-role').value,sc=$('m-scope').value,t=$('m-t').value,ci=+$('m-coef').value;let n=null;
  const rows=MKEYS.map(a=>`<tr><td class="l">${METH[a]}</td>${MKEYS.map(b=>{if(a===b)return `<td class="v" style="${heat(1)}">1</td>`;
    const k1=`${r}|${sc}|${+t}|${a}|${b}`,k2=`${r}|${sc}|${+t}|${b}|${a}`;const v=D.corr[k1]||D.corr[k2];if(v)n=v[2];const x=v?v[ci]:null;return `<td class="v" style="${heat(x)}">${fmt(x,3)}</td>`}).join('')}</tr>`).join('');
  $('m-table').innerHTML=`<thead><tr><th class="l"></th>${MKEYS.map(m=>`<th>${METH[m]}</th>`).join('')}</tr></thead><tbody>${rows}</tbody>`;
  $('m-n').textContent=n!=null?`Технологий в наборе: ${n}.`:'';
  const items=(sc==='all_categories'?['all_categories',...D.cats]:[sc]).map(s=>{const v=D.vardec[`${r}|${s}`];if(!v)return '';const tot=Math.abs(v[0])+Math.abs(v[1])+Math.abs(v[2]);
    return `<div style="margin:10px 0"><div style="display:flex;justify-content:space-between;font-size:13px"><span>${s==='all_categories'?'Все категории':CAT[s]} (n=${v[3]})</span><span class="cat">p ${fmt(v[0],2)} · L ${fmt(v[1],2)} · cov ${fmt(v[2],2)}</span></div><div class="stack"><span style="width:${Math.abs(v[0])/tot*100}%;background:var(--accent)"></span><span style="width:${Math.abs(v[1])/tot*100}%;background:#14B8A6"></span><span style="width:${Math.abs(v[2])/tot*100}%;background:#F59E0B"></span></div></div>`}).join('');
  $('m-var').innerHTML=items;
}
['m-role','m-scope','m-t','m-coef'].forEach(id=>$(id).addEventListener('change',renderMethods));renderMethods();

//STABILITY
opts($('s-scope'),scopeItems,'all_categories');opts($('d-method'),MKEYS.map(m=>[m,METH[m]]),'log');opts($('d-scope'),scopeItems,'all_categories');
function heat01(v){if(v==null)return '';return `background:color-mix(in srgb,var(--accent) ${Math.round(v*v*72)}%,var(--heat0));color:${v>0.82?'#fff':'inherit'}`}
function renderStability(){
  const sc=$('s-scope').value,mi=+$('s-metric').value;
  const rows=D.roles.map(r=>`<tr><td class="l">${ROLE[r]}</td>${MKEYS.map(m=>{const v=D.retention[`${r}|${sc}|${m}`];const x=v?v[mi]:null;return `<td class="v" style="${heat01(x)}">${mi===0?pct(x,1):fmt(x,3)}</td>`}).join('')}</tr>`).join('');
  $('s-table').innerHTML=`<thead><tr><th class="l">Роль</th>${MKEYS.map(m=>`<th>${METH[m]}</th>`).join('')}</tr></thead><tbody>${rows}</tbody>`;
  const m=$('d-method').value,ds=$('d-scope').value;
  const g=(e,r)=>D.design[`${e}|${r}|${ds}|${m}`];
  const drows=D.roles.map(r=>{const b=g('background_excluded',r),c=g('complete_cases_own_sets',r);return `<tr><td class="l">${ROLE[r]}</td><td>${fmt(b&&b[0],4)}</td><td>${fmt(b&&b[1],3)}</td><td>${nf(resp[r].n_complete)}</td><td>${fmt(c&&c[0],4)}</td><td>${fmt(c&&c[1],3)}</td><td>${fmt(c&&c[2],3)}</td></tr>`}).join('');
  $('d-table').innerHTML=`<thead><tr><th class="l">Роль</th><th>Фон без роли: ρ</th><th>Фон без роли: J top-10</th><th>Полных ответов</th><th>Полные ответы: ρ</th><th>J top-10</th><th>J набора</th></tr></thead><tbody>${drows}</tbody>`;
}
['s-scope','s-metric','d-method','d-scope'].forEach(id=>$(id).addEventListener('change',renderStability));renderStability();

//AUDIT
$('audit').innerHTML=`<table><tbody>
<tr><td class="l">Файл</td><td class="l">survey_results_public.csv, ${nf(A.shape[0])} строк, ${A.shape[1]} столбцов</td></tr>
<tr><td class="l">SHA-256</td><td class="l" style="white-space:normal;word-break:break-all"><code>${A.csv_sha256}</code></td></tr>
<tr><td class="l">Уникальные ResponseId</td><td class="l">${nf(A.response_id_unique)}; полных дубликатов строк: ${A.duplicate_rows}</td></tr>
<tr><td class="l">Пропуски DevType</td><td class="l">${nf(A.devtype_missing)} (остаются в общем фоне)</td></tr>
<tr><td class="l">Расхождение с сайтом опроса</td><td class="l">в методологии указано ${nf(A.official_website_n)} ответов, в файле на ${A.website_difference} больше; строки не удалялись</td></tr>
<tr><td class="l">Воспроизведение исходной таблицы</td><td class="l">${A.legacy.computed_pairs} пар совпали полностью, макс. ошибка веса ${A.legacy.max_weight_error.toExponential(2)}</td></tr>
<tr><td class="l">Версии</td><td class="l">Python ${A.versions.python}, NumPy ${A.versions.numpy}, pandas ${A.versions.pandas}, SciPy ${A.versions.scipy}</td></tr>
</tbody></table>`;
})();
