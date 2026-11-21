
let S=null,sel=null,lvl=.5,rip=[];const $=i=>document.getElementById(i);
const NAMES=['Sharma family','Joshi family','Khan family','Patil family','Iyer family','Deshmukh family'],KIND={'Soft municipal':'Soft tap water','Mixed supply':'Mixed water','Hard borewell':'Hard borewell water'};
const post=o=>fetch('/api/act',{method:'POST',body:JSON.stringify(o)}),a=k=>post({kind:k,id:sel}),sp=v=>post({kind:'speed',v}),rs=()=>{sel=null;post({kind:'reset'})};
const COL={HEALTHY:'#22B573',WATCH:'#F5A524','ORDER NOW':'#E8412C',FALLBACK:'#7C93A6'},LBL={HEALTHY:'Healthy',WATCH:'Change soon','ORDER NOW':'Change now',FALLBACK:'Using safe backup'};
const ADV={HEALTHY:'Nothing to do right now.',WATCH:'Plan a replacement in the coming weeks.','ORDER NOW':'Order a new filter this week.',FALLBACK:'A sensor has a problem, so the old litre counter is guiding us for safety.'};
async function poll(){try{S=await(await fetch('/api/state')).json();$('conn').textContent='Live demo';
if(sel===null)sel=S.homes.reduce((m,h)=>Math.abs(h.crul-h.rul)>Math.abs(m.crul-m.rul)?h:m).id;render()}catch(e){$('conn').textContent='Engine not running'}}
setInterval(poll,400);poll();$('dl').textContent=location.host+'/device';
setInterval(()=>fetch('/api/devices').then(r=>r.json()).then(d=>{const k=Object.keys(d);if(k.length)$('devs').innerHTML=k.map(i=>{const v=d[i];return `<div class="home"><b>${i}</b><small>${v.rul==null?'Invalid reading, safe backup':'about '+Math.round(v.rul)+' days left'}</small><span class="badge ${v.status=='ORDER NOW'?'ORDER':v.status}">${v.status}</span></div>`}).join('')}),1000);
const cls=s=>s=='ORDER NOW'?'ORDER':s;
function render(){const H=S.homes,h=H[sel];
$('homes').innerHTML=H.map(o=>`<button class="home ${o.id==sel?'on':''}" onclick="sel=${o.id};render()"><b>${NAMES[o.id]}</b><small>${KIND[o.kind]}</small><small>${o.loc}</small><span class="badge ${cls(o.status)}">${LBL[o.status]}</span></button>`).join('');
const r=h.rul;$('sent').innerHTML=h.status=='FALLBACK'?'Sensor problem. <em>Safe backup is on.</em>':r>=365?'This filter is in <em>great shape.</em>':`This filter needs changing in about <em>${r} days.</em>`;
$('badge').textContent=LBL[h.status];$('badge').className='badge '+cls(h.status);$('adv').textContent=h.sched?'A replacement is already scheduled.':ADV[h.status];
[['b1',h.crul],['b2',h.rul],['b3',h.truth]].forEach(([i,v])=>{const e=$(i);e.style.width=Math.max(12,Math.min(100,v/3.65))+'%';e.textContent=v>=365?'365+':v})
const st=h.stages;$('stages').innerHTML='<div style="font-weight:700;font-size:19px;margin-bottom:6px">The other filters in this purifier</div>'+st.list.map(x=>`<div style="display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid #CFE3E6;font-size:17px"><span>${x.name}<small style="color:#5A7384;display:block;font-size:14px">${x.basis}</small></span><b>${x.days>=365?'365+':x.days} days</b></div>`).join('')+`<div style="margin-top:10px;padding:12px 14px;background:#FFF6D6;border-radius:12px;font-weight:600">One visit, in about ${st.visit} days: change ${st.bundle.join(', ')}.</div>`;
$('log').innerHTML=S.log.map(x=>`<div>${x}</div>`).join('');['af','bf'].forEach(k=>$(k).textContent=S[k]);['aw','bw'].forEach(k=>$(k).textContent=S[k]==null?'–':S[k]+'%');chart(h);polHi()}
function chart(h){const c=$('ch'),g=c.getContext('2d'),W=c.width,Hh=c.height,N=h.hist.length,lo=.6,hi=1.4;g.clearRect(0,0,W,Hh);
const X=i=>20+i/(N+45)*(W-40),Y=v=>Hh-20-(v-lo)/(hi-lo)*(Hh-40);g.font='bold 20px sans-serif';
h.hist.forEach((p,i)=>{if(p[3]){g.fillStyle='rgba(255,201,60,.35)';g.fillRect(X(i)-1,0,X(1)-X(0)+2,Hh)}});
g.setLineDash([12,8]);g.strokeStyle='#E8412C';g.lineWidth=3;g.beginPath();g.moveTo(20,Y(.85));g.lineTo(W-10,Y(.85));g.stroke();g.setLineDash([]);g.fillStyle='#E8412C';g.fillText('Needs changing',W-190,Y(.85)+26);
const L=(k,st,w)=>{g.strokeStyle=st;g.lineWidth=w;g.lineJoin='round';g.beginPath();h.hist.forEach((p,i)=>i?g.lineTo(X(i),Y(p[k])):g.moveTo(X(i),Y(p[k])));g.stroke()};
L(0,'#9DB4C0',2);L(1,'#0B6E7F',6);
const e=h.hist[N-1][1],d=Math.min(h.rul,45);g.strokeStyle='#0B6E7F';g.lineWidth=5;g.setLineDash([3,10]);g.beginPath();g.moveTo(X(N-1),Y(e));g.lineTo(X(N-1+d),Y(e+h.slope*d));g.stroke();g.setLineDash([]);g.fillStyle='#0B2A3C';g.fillText('Forecast',X(N-1)+8,Y(e)-14)}
const T=$('drop'),G=T.getContext('2d');T.addEventListener('pointermove',e=>{const r=T.getBoundingClientRect();rip.push({x:(e.clientX-r.left)/r.width*T.width,y:(e.clientY-r.top)/r.height*T.height,t:0})});
function path(w,h){G.beginPath();G.moveTo(w/2,6);G.bezierCurveTo(w*.98,h*.45,w*.97,h*.98,w/2,h*.98);G.bezierCurveTo(w*.03,h*.98,w*.02,h*.45,w/2,6)}
function frame(t){requestAnimationFrame(frame);if(!S)return;const h=S.homes[sel],W=T.width,Hh=T.height;
const tgt=Math.max(.04,Math.min(1,(h.hist[h.hist.length-1][1]-.85)/.15));lvl+=(tgt-lvl)*.05;G.clearRect(0,0,W,Hh);
G.save();path(W,Hh);G.fillStyle='#E6F1F2';G.fill();G.clip();const top=Hh-lvl*(Hh-30)-6;
G.fillStyle=COL[h.status];G.beginPath();G.moveTo(0,Hh);for(let x=0;x<=W;x+=6)G.lineTo(x,top+Math.sin(x*.04+t*.003)*8);G.lineTo(W,Hh);G.fill();
G.fillStyle='rgba(255,255,255,.55)';for(let i=0;i<12;i++){const y=Hh-((t*.05*(.5+i%4*.3)+i*61)%(Hh-top+1))-4;if(y>top+8){G.beginPath();G.arc(60+i*23%180,y,4+i%3*2,0,7);G.fill()}}
rip=rip.filter(r=>r.t<1);rip.forEach(r=>{r.t+=.025;G.strokeStyle='#fff';G.lineWidth=5;G.globalAlpha=1-r.t;G.beginPath();G.arc(r.x,r.y,r.t*90,0,7);G.stroke();G.globalAlpha=1});G.restore();
path(W,Hh);G.strokeStyle='#0B2A3C';G.lineWidth=6;G.stroke()}
requestAnimationFrame(frame);
fetch('/api/results').then(r=>r.json()).then(d=>{RES=d;dialRender();if(!d.rows)return;const c=(v,ok)=>`<td style="padding:10px;border-bottom:1px solid #CFE3E6"><b>${v}%</b> <span class="badge ${ok?'HEALTHY':'WATCH'}" style="margin:0 0 0 6px">${ok?'Target met':'Not yet'}</span></td>`;
$('res').innerHTML='<tr style="text-align:left"><th style="padding:10px">What we measured</th><th>Our target</th><th>Normal</th><th>Harder</th><th>Real-world noise</th></tr>'+d.rows.map(r=>`<tr><td style="padding:10px;border-bottom:1px solid #CFE3E6">${r.name}</td><td style="border-bottom:1px solid #CFE3E6">${r.target}</td>${c(r.vals[0],r.ok[0])}${c(r.vals[1],r.ok[1])}${c(r.vals[2],r.ok[2])}</tr>`).join('')});
let pd=0,pf=0,tank=0,bad=0,pn=1,pst=null,pbusy=0,ptimer=null,hist=[],ordered=0;
const PC={HEALTHY:'#22B573',WATCH:'#F5A524','ORDER NOW':'#E8412C',FALLBACK:'#7C93A6'};
const g6=()=>{let s=0;for(let i=0;i<6;i++)s+=Math.random();return (s-3)/Math.sqrt(.5)},tc=x=>1+.03*(x-25),nd=x=>(6-.00075*x)/(6-.00075*500);
function toast(t){const e=$('toast');e.textContent=t;e.className='on';setTimeout(()=>e.className='',5200)}
async function pTick(){if(pbusy)return;pbusy=1;pd++;const temp=25+8*Math.sin(2*Math.PI*pd/365)+g6(),m=tank>0?1.7:1;tank=Math.max(0,tank-1);const tds=$('tds').value*m*(1+.04*g6());
pf+=.0011*tds/1000*(1+.1*g6());const flow=(1-pf)*tc(temp)*nd(tds)*(1+.04*g6());
const msg={device_id:'my-purifier-'+pn,tds_in:bad>0?9999:Math.round(tds),temp_c:+temp.toFixed(1),fill_s_per_l:+(30/flow).toFixed(2),locality:'home'};bad=Math.max(0,bad-1);
try{const r=await(await fetch('/api/telemetry',{method:'POST',body:JSON.stringify(msg)})).json();showP(r)}catch(e){$('pa').textContent='Cannot reach the server.'}pbusy=0}
function showP(r){$('pday').textContent='day '+pd;const s=r.status,col=PC[s]||'#7C93A6';
if(r.rul==null){$('pd').textContent='–';$('pu').textContent='safe backup';$('rg').style.strokeDashoffset=327*.5}
else{$('pd').textContent=r.rul>=365?'365+':Math.round(r.rul);$('pu').textContent='days left';hist.push(r.h);hist=hist.slice(-60);$('rg').style.strokeDashoffset=327*(1-Math.max(.04,Math.min(1,(r.h-.85)/.15)))}
$('rg').style.stroke=col;$('pb').textContent={HEALTHY:'Healthy','ORDER NOW':'Change now',WATCH:'Change soon',FALLBACK:'Safe backup'}[s]||s;$('pb').className='badge '+(s=='ORDER NOW'?'ORDER':s);
$('pa').textContent={HEALTHY:'Your filter is in good shape.',WATCH:'Plan ahead. Your filter is wearing.','ORDER NOW':'Order a new filter now, before it stops working.',FALLBACK:"We can't read your sensor, so we are using the safe backup."}[s]||'';
$('order').disabled=!(s=='ORDER NOW'||s=='WATCH')||ordered;if(ordered){const e=pd-ordered;$('order').textContent=e<1?'Ordered. Packing your filter':e<2?'Out for delivery':'Delivered. Time to install it'}
if(s!=pst&&pd>12){if(s=='ORDER NOW')toast('Time to order a new filter. About '+Math.round(r.rul)+' days left.');else if(s=='WATCH')toast('Your filter is starting to wear. Plan a replacement.');else if(s=='FALLBACK')toast('Sensor problem. Using the safe backup.')}
if(pd>12)pst=s;spark()}
function spark(){const c=$("spark"),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);if(hist.length<2)return;g.strokeStyle='#0B6E7F';g.lineWidth=3;g.beginPath();hist.forEach((v,i)=>{const x=i/59*(c.width-4)+2,y=c.height-4-Math.max(0,Math.min(1,(v-.82)/.2))*(c.height-8);i?g.lineTo(x,y):g.moveTo(x,y)});g.stroke()}
function orderIt(){ordered=pd;$('order').disabled=true;$('order').textContent='Ordered. Arrives in 2 days';toast('Order placed. Your new filter arrives in 2 days.')}
function newFilter(){pf=0;pn++;hist=[];pst=null;ordered=0;$('order').textContent='Order a new filter';$('rg').style.strokeDashoffset=0;toast('New filter installed. Learning your water again.')}
function spd(ms){clearInterval(ptimer);ptimer=setInterval(pTick,ms);$('pp').textContent='Pause'}
function pauseP(){if($('pp').textContent=='Pause'){clearInterval(ptimer);$('pp').textContent='Resume'}else spd(150)}
spd(150);
let RES=null;function dialRender(){if(!RES||!RES.curve)return;polBuild();const Ts=Object.keys(RES.curve).map(Number).sort((a,b)=>a-b),T=Ts[+$('dial').value],c=RES.curve[T].standard,D=RES.detail.standard,yrs=80*1100/365,f=x=>(100*x/yrs).toFixed(1);
$('dialT').textContent=T;$('dialout').innerHTML=`<div class="sc"><div class="lab">Surprise failures per 100 homes a year</div><div class="row old"><span>Old counter</span><b>${f(D.counter.fail)}</b></div><div class="row new"><span>HydroPulse</span><b>${f(c[0])}</b></div></div><div class="sc"><div class="lab">Filters bought per home a year</div><div class="row old"><span>Old counter</span><b>${((D.counter.fail+D.counter.plan)/yrs*80/80).toFixed(2)}</b></div><div class="row new"><span>HydroPulse</span><b>${(c[2]/yrs*80/80).toFixed(2)}</b></div></div><div class="sc"><div class="lab">Filter life used when changed</div><div class="row new"><span>HydroPulse</span><b>${c[1]}%</b></div></div>`}

const PRE=[[18,'Safety first','Fewest surprise failures. Best for customer trust.'],[10,'Balanced (default)','Almost no failures with sensible filter use.'],[6,'Economy','Uses the most filter life. More failures.']];
function polBuild(){if(!RES||!RES.curve)return;const yrs=80*1100/365;$('presets').innerHTML=PRE.map(([T,n,t])=>{const c=RES.curve[T].standard;return `<button class="sc pre" data-t="${T}" onclick="post({kind:'policy',v:${T}})"><div class="lab">${n}</div><b>${(100*c[0]/yrs).toFixed(1)}</b><div>failures per 100 homes a year</div><div>${c[1]}% of filter life used</div><p style="margin-top:6px;color:#5A7384;font-size:16px">${t}</p></button>`}).join('')}
function polHi(){document.querySelectorAll('.pre').forEach(b=>b.classList.toggle('sel',!!S&&+b.dataset.t==S.alert))}
const VIEWS=['home','customer','fleet','devices','policy','evidence','roadmap'];
function route(){const v=location.hash.slice(1),id=VIEWS.includes(v)?v:'home';VIEWS.forEach(x=>$('v-'+x).hidden=x!=id);document.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('on',a.dataset.v==id));scrollTo(0,0);if(id=='roadmap'&&!$('rm').innerHTML)fetch('/static/roadmap.html').then(r=>r.text()).then(t=>$('rm').innerHTML=t)}
addEventListener('hashchange',route);route();