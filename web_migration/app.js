(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const state = { page: 'overview', bootstrap: null, index: [], routes: [], lead: [], audit: null, rawPage: 1, rawTotal: 0, charts: {}, filters: {} };
  const titles = {
    overview: ['Airfare Price Index', 'A live view of published airfare index artifacts and observed market coverage.'],
    analytics: ['Index Analytics', 'Explore the national index history from published statistical artifacts.'],
    routes: ['Route Intelligence', 'Compare route-level index values without recalculating the published national index.'],
    lead: ['Lead-Time Analysis', 'Explore airfare index observations by advance booking window.'],
    quality: ['Data Quality', 'Inspect quality metrics returned by the existing observation store.'],
    sources: ['Source Health', 'Understand observed contribution from the data sources feeding AirFareX.'],
    raw: ['Raw Data Explorer', 'Inspect paginated observation records from the existing observation store.'],
    audit: ['Automation & Audit', 'Review the existing publication gates and pipeline provenance.']
  };
  const esc = (v) => String(v ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, digits=2) => v == null || v === '' || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('en-IN', {maximumFractionDigits:digits, minimumFractionDigits:digits});
  const num = (v) => v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
  const dateOnly = (v) => v ? String(v).slice(0,10) : '—';
  const rowsTable = (rows, preferred=[]) => {
    if (!rows?.length) return '<div class="empty">No records available for this view.</div>';
    const keys = [...preferred.filter(k => rows.some(r => k in r)), ...Object.keys(rows[0]).filter(k => !preferred.includes(k))].slice(0,12);
    return `<table><thead><tr>${keys.map(k=>`<th>${esc(k.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${keys.map(k=>`<td>${esc(typeof r[k] === 'number' ? fmt(r[k]) : r[k])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  };
  async function api(path, opts={}) {
    const res = await fetch(path, {headers:{'Accept':'application/json'}, ...opts});
    if (!res.ok) { let message = `API request failed (${res.status})`; try { const j=await res.json(); message=j.detail||message; } catch {} throw new Error(message); }
    return res.json();
  }
  function showNotice(message, error=false) { const el=$('#notice'); el.textContent=message; el.classList.remove('hidden'); el.style.background=error?'#fff0ef':'#fff5e5'; el.style.color=error?'#963d35':'#7c5a19'; }
  function hideNotice(){ $('#notice').classList.add('hidden'); }
  function setChart(id, labels, values, label='Index') {
    if (!window.Chart) return;
    const canvas = document.getElementById(id); if (!canvas) return;
    if (state.charts[id]) state.charts[id].destroy();
    state.charts[id] = new Chart(canvas, {type:'line',data:{labels,datasets:[{label,data:values,borderColor:'#287bb2',backgroundColor:'rgba(40,123,178,.10)',borderWidth:2,fill:true,tension:.25,pointRadius:values.length>70?0:2,pointHoverRadius:4,spanGaps:true}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#102b46',padding:10}},scales:{x:{grid:{display:false},ticks:{color:'#8b99aa',maxTicksLimit:8,maxRotation:0}},y:{grid:{color:'#edf1f5'},ticks:{color:'#8b99aa'}}}}});
  }
  function renderKpis(k={}) {
    const values = [
      ['Latest index',fmt(k.latest_index),'Published value'],['Previous index',fmt(k.previous_index),'Prior observation'],['Total observations',k.observations==null?'—':Number(k.observations).toLocaleString('en-IN'),'Cloud-backed records'],['Routes',k.routes==null?'—':Number(k.routes).toLocaleString('en-IN'),'Observed routes'],['Airlines',k.airlines==null?'—':Number(k.airlines).toLocaleString('en-IN'),'Distinct airline labels'],['Sources',k.sources==null?'—':Number(k.sources).toLocaleString('en-IN'),'Observed data sources']
    ];
    $('#kpis').innerHTML = values.map(([label,value,small])=>`<article class="kpi"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(small)}</small></article>`).join('');
    $('#publication-pill').textContent = k.publication_status || 'Status unavailable';
    const good=String(k.publication_status||'').toUpperCase()==='PUBLISHABLE'; $('.status-pill i').style.background=good?'#2fa879':'#d9a144';
    $('#snapshot').innerHTML = [['Latest collection date',dateOnly(k.latest_date)],['Latest index',fmt(k.latest_index)],['Previous index',fmt(k.previous_index)],['Period change',k.change_pct==null?'—':`${Number(k.change_pct)>=0?'+':''}${fmt(k.change_pct)}%`],['Publication status',k.publication_status||'Unavailable']].map(([a,b])=>`<div class="snapshot-row"><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`).join('');
  }
  function renderIndex() {
    const rows=state.index||[]; const labels=rows.map(r=>dateOnly(r.collection_date)); const values=rows.map(r=>num(r.overall_airfare_index));
    setChart('overview-chart',labels,values,'National index'); setChart('analytics-chart',labels,values,'National index');
    $('#index-table').innerHTML=rowsTable(rows.slice(-100).reverse(),['collection_date','overall_airfare_index','daily_change_pct','coverage_status','publication_status']);
  }
  function renderRoutes() {
    const rows=state.routes||[]; const recent=rows.slice(-15); setChart('routes-chart',recent.map(r=>`${r.route||r.origin_destination||'Route'} · ${dateOnly(r.collection_date)}`),recent.map(r=>num(r.route_index)),'Route index');
    $('#routes-table').innerHTML=rowsTable(rows.slice(-150).reverse(),['collection_date','route','origin','destination','route_index','airline','source']);
    const movers=new Map(); rows.forEach(r=>{const route=r.route||`${r.origin||''}-${r.destination||''}`; if(route && num(r.route_index)!=null){const item=movers.get(route)||{route,first:num(r.route_index),latest:num(r.route_index),date:r.collection_date}; item.latest=num(r.route_index); item.date=r.collection_date; movers.set(route,item);}});
    const list=[...movers.values()].map(r=>({...r,change_pct:r.first?((r.latest/r.first)-1)*100:null})).sort((a,b)=>(b.change_pct??-Infinity)-(a.change_pct??-Infinity)).slice(0,8);
    $('#route-movers').innerHTML=rowsTable(list,['route','latest','change_pct','date']);
    const sel=$('#route-filter'); const old=sel.value; const options=[...new Set(rows.map(r=>r.route||`${r.origin||''}_${r.destination||''}`).filter(Boolean))].sort(); sel.innerHTML='<option value="">All routes</option>'+options.map(r=>`<option value="${esc(r)}">${esc(r.replaceAll('_','–'))}</option>`).join(''); if(options.includes(old))sel.value=old;
  }
  function renderLead(){const rows=state.lead||[];setChart('lead-chart',rows.slice(-100).map(r=>`${dateOnly(r.collection_date)} · ${r.advance_days??'window'}d`),rows.slice(-100).map(r=>num(r.airfare_index)),'Lead-time index');$('#lead-table').innerHTML=rowsTable(rows.slice(-150).reverse(),['collection_date','advance_days','airfare_index','mean_stratum_index','observations']);}
  function renderAudit(){const a=state.audit||{};const rows=a.data||[];const latest=[...rows].reverse().find(r=>String(r.publication_status||'').toUpperCase()==='PUBLISHABLE')||rows.at(-1)||{};const status=latest.publication_status||'Unavailable';const good=String(status).toUpperCase()==='PUBLISHABLE';$('#audit-summary').innerHTML=`<div class="audit-status"><span class="status-dot ${good?'good':status==='Unavailable'?'':'bad'}"></span><div><b>${esc(status)}</b><small>Latest ${good?'publishable audit record':'available audit record'} · ${esc(dateOnly(latest.collection_date))}</small></div></div><div class="snapshot-row"><span>Audit records</span><strong>${rows.length.toLocaleString('en-IN')}</strong></div><div class="snapshot-row"><span>Coverage report rows</span><strong>${(a.coverage||[]).length.toLocaleString('en-IN')}</strong></div>`;
    const gates=Object.entries(latest).filter(([k])=>/gate|valid|publish|status|coverage|pass|fail|audit/i.test(k));$('#audit-gates').innerHTML=gates.length?gates.map(([k,v])=>`<div class="snapshot-row"><span>${esc(k.replaceAll('_',' '))}</span><strong>${esc(v)}</strong></div>`).join(''):'<div class="empty">No gate fields found in the audit artifact.</div>';
    $('#audit-table').innerHTML=rowsTable(rows.slice(-150).reverse(),['collection_date','publication_status','coverage_status','index_status','status']);$('#pipeline-report').textContent=JSON.stringify(a.pipeline_report||{},null,2);
  }
  function renderQuality(data){const q=data?.quality||{};const entries=Object.entries(q);$('#quality-cards').innerHTML=entries.length?entries.map(([k,v])=>`<div class="quality-card"><span>${esc(k.replaceAll('_',' '))}</span><strong>${esc(typeof v==='number'?fmt(v):v)}</strong><small>Returned by observation store</small></div>`).join(''):'<div class="empty">No quality metrics returned by the observation store.</div>';}
  function renderSources(data){const sources=data?.sources||[];$('#source-table').innerHTML=rowsTable(sources,['source','observations','routes','airlines','mean_fare','median_fare']);const dims=data?.dimensions||{};const meta=data?.metadata||{};const cards=[['Total observations',meta.total_observations??meta.observations],['Configured routes',(dims.routes||[]).length],['Configured airlines',(dims.airlines||[]).length],['Configured sources',(dims.sources||[]).length]];$('#source-cards').innerHTML=cards.map(([k,v])=>`<div class="quality-card"><span>${esc(k)}</span><strong>${v==null?'—':esc(Number(v).toLocaleString('en-IN'))}</strong><small>Existing source metadata</small></div>`).join('');if(data?.warning)showNotice(`Source health query warning: ${data.warning}`,true);}
  async function loadRaw(){const size=Number($('#raw-size').value);$('#raw-table').innerHTML='<div class="loading-line"></div>';try{const p=new URLSearchParams({page:state.rawPage,page_size:size});const route=$('#route-filter').value;if(route)p.append('route',route);if($('#from-date').value)p.set('start_date',$('#from-date').value);if($('#to-date').value)p.set('end_date',$('#to-date').value);const data=await api(`/api/observations?${p}`);state.rawTotal=data.total||0;$('#raw-table').innerHTML=rowsTable(data.data||[]);const pages=Math.max(1,Math.ceil(state.rawTotal/size));$('#raw-count').textContent=`${state.rawTotal.toLocaleString('en-IN')} total records · Page ${state.rawPage} of ${pages}`;$('#raw-prev').disabled=state.rawPage<=1;$('#raw-next').disabled=state.rawPage>=pages;}catch(e){$('#raw-table').innerHTML=`<div class="empty">${esc(e.message)}</div>`;$('#raw-count').textContent='Could not load observations';}}
  async function loadPage(page){state.page=page;document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===page));document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id===`page-${page}`));$('#page-title').textContent=titles[page][0];$('#page-subtitle').textContent=titles[page][1];hideNotice();try{
    if(page==='analytics'){if(!state.index.length)state.index=(await api('/api/index?limit=1000')).data||[];renderIndex();}
    if(page==='routes'){if(!state.routes.length)state.routes=(await api('/api/routes?limit=1500')).data||[];renderRoutes();}
    if(page==='lead'){if(!state.lead.length)state.lead=(await api('/api/lead-time?limit=1500')).data||[];renderLead();}
    if(page==='audit'){if(!state.audit)state.audit=await api('/api/audit');renderAudit();}
    if(page==='quality'||page==='sources'){const d=await api('/api/source-health');if(page==='quality')renderQuality(d);else renderSources(d);}
    if(page==='raw')await loadRaw();
  }catch(e){showNotice(e.message,true);}}
  async function loadBootstrap(){try{state.bootstrap=await api('/api/bootstrap');renderKpis(state.bootstrap.kpis||{});$('#api-state').textContent='API connected';$('#updated-at').textContent=`Connected · ${new Date().toLocaleTimeString()}`;const status=state.bootstrap.kpis?.publication_status||'Unavailable';if(!state.index.length){const d=await api('/api/index?limit=365');state.index=d.data||[];renderIndex();}const k=state.bootstrap.kpis||{};if(!state.audit){state.audit={data:[]};$('#audit-summary').innerHTML=`<div class="audit-status"><span class="status-dot ${status==='PUBLISHABLE'?'good':'bad'}"></span><div><b>${esc(status)}</b><small>Latest audit-derived publication status</small></div></div>`;}
    if(state.bootstrap.dimensions?.routes){const sel=$('#route-filter');sel.innerHTML='<option value="">All routes</option>'+state.bootstrap.dimensions.routes.map(r=>`<option value="${esc(r)}">${esc(String(r).replaceAll('_','–'))}</option>`).join('');}
  }catch(e){$('#api-state').textContent='API unavailable';showNotice(`Could not load AirFareX data: ${e.message}. Confirm the API is deployed with the existing dashboard modules and data artifacts.`,true);}}
  document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',()=>loadPage(b.dataset.page)));
  $('#refresh-button').addEventListener('click',async()=>{const btn=$('#refresh-button');btn.disabled=true;btn.textContent='Refreshing…';try{await api('/api/refresh',{method:'POST'});state.bootstrap=null;state.index=[];state.routes=[];state.lead=[];state.audit=null;await loadBootstrap();if(state.page!=='overview')await loadPage(state.page);showNotice('In-process read cache cleared. Published pipeline data was not modified.');}catch(e){showNotice(e.message,true)}finally{btn.disabled=false;btn.textContent='↻ Refresh data';}});
  $('#apply-filters').addEventListener('click',()=>{state.filters={from:$('#from-date').value,to:$('#to-date').value,route:$('#route-filter').value};if(state.page==='raw'){state.rawPage=1;loadRaw();}else if(state.page==='routes')renderRoutes();else showNotice('Filter controls are ready. The national published index is unchanged; route and date filters are applied to exploratory views.');});
  $('#raw-prev').addEventListener('click',()=>{if(state.rawPage>1){state.rawPage--;loadRaw();}});$('#raw-next').addEventListener('click',()=>{state.rawPage++;loadRaw();});$('#raw-size').addEventListener('change',()=>{state.rawPage=1;loadRaw();});
  loadBootstrap();
})();
