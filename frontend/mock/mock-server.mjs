import http from 'node:http';
import { WebSocketServer } from 'ws';

const PORT = 8000;
const CATEGORIES = ['FOOTSTEPS','IMPACT','DISTRESS','ALARM','GLASS','DOOR'];
const started = Date.now();
const clients = new Set();
let mode = 'SIMULATED', risk = 'GREEN', events = [], sequences = [], counter = 0;
const now = () => (Date.now()-started)/1000;
const meta = () => ({source:'SIMULATED', t:now(), wall:new Date().toISOString()});
const send = (type, extra) => {
  const payload = JSON.stringify({type,data:{...meta(),...extra}});
  for (const client of clients) if(client.readyState===1) client.send(payload);
};
const status = () => ({...meta(),risk,latency_ms:45,device:'EchoTrace Mock (no microphone)',host_api:'SIMULATED',sample_rate:48000,channels:2,localization:'ON',model_device:'cpu',dropped_blocks:0});
const addEvent = (category,zone,confidence,angle_deg) => {
  const t=now();
  const e={...meta(),id:`mock-e${++counter}`,t_start:t-0.25,t_end:t,category,label:({GLASS:'Glass',IMPACT:'Thump, thud',ALARM:'Smoke detector, smoke alarm',FOOTSTEPS:'Walk, footsteps',DISTRESS:'Screaming',DOOR:'Door'})[category],confidence,zone,angle_deg};
  events.push(e); if(events.length>200) events.shift(); send('event',e); return e;
};
const addSequence=(pattern,newRisk,items,explanation,summary)=>{
  risk=newRisk;
  const s={...meta(),id:`mock-s${++counter}`,event_ids:items.map(e=>e.id),pattern,risk,explanation,summary,trajectory:items.map(e=>e.zone)};
  sequences.push(s); if(sequences.length>100)sequences.shift(); send('sequence',s); send('status',status());
};
const scripted = [
  {at:2,cat:'GLASS',zone:'LEFT',p:.78,angle:45,key:'glass'},
  {at:5,cat:'IMPACT',zone:'RIGHT',p:.37,angle:-45,key:'impact'},
  {at:8,cat:'ALARM',zone:'CENTRE',p:.45,angle:0,key:'alarm'},
  {at:8.5,sequence:'GLASS_IMPACT_ALARM',risk:'RED',keys:['glass','impact','alarm'],why:['Glass detected on the LEFT','Impact detected on the RIGHT shortly afterward','Alarm detected near the CENTRE'],summary:'Potentially significant sequence: glass, impact and alarm. Verify before responding.'},
  {at:14,cat:'FOOTSTEPS',zone:'LEFT',p:.57,angle:45,key:'step1'},
  {at:16,cat:'FOOTSTEPS',zone:'CENTRE',p:.63,angle:0,key:'step2'},
  {at:18,cat:'IMPACT',zone:'RIGHT',p:.39,angle:-45,key:'impact2'},
  {at:20,cat:'DISTRESS',zone:'RIGHT',p:.54,angle:-42,key:'distress'},
  {at:20.5,sequence:'MOVEMENT_IMPACT_DISTRESS',risk:'RED',keys:['step1','step2','impact2','distress'],why:['Footsteps progress from LEFT to CENTRE','An impact follows on the RIGHT','Possible distress follows on the RIGHT'],summary:'Potentially significant movement-impact-distress sequence. Verify.'},
  {at:27,cat:'IMPACT',zone:'CENTRE',p:.4,angle:0,key:'lone'},
  {at:34,cat:'GLASS',zone:'LEFT',p:.72,angle:45,key:'glass2'},
  {at:37,cat:'IMPACT',zone:'RIGHT',p:.38,angle:-45,key:'impact3'},
  {at:37.5,sequence:'GLASS_IMPACT',risk:'AMBER',keys:['glass2','impact3'],why:['Glass heard on the LEFT','Impact followed on the RIGHT'],summary:'Possible correlated glass-impact sequence. Verify.'}
];
let cycle=-1, fired=new Set(), byKey={};
setInterval(()=>{
  const t=now(), c=Math.floor(t/45), phase=t%45;
  if(c!==cycle){cycle=c;fired=new Set();byKey={};risk='GREEN';send('status',status());}
  for(const [i,step] of scripted.entries()){
    if(phase<step.at || fired.has(i))continue;
    fired.add(i);
    if(step.cat) byKey[step.key]=addEvent(step.cat,step.zone,step.p,step.angle);
    else addSequence(step.sequence,step.risk,step.keys.map(k=>byKey[k]).filter(Boolean),step.why,step.summary);
  }
},100);
setInterval(()=>{
  const phase=now()%45;
  const active=scripted.filter(s=>s.cat&&Math.abs(s.at-phase)<1.5).at(-1);
  const categories=Object.fromEntries(CATEGORIES.map(c=>[c,c===active?.cat?active.p:Math.round((.01+Math.random()*.035)*100)/100]));
  const top=Object.entries(categories).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([label,p])=>({label,p}));
  send('frame',{top,categories,rms_db:active?[-28,-31]:[-55,-57]});
},500);
setInterval(()=>send('status',status()),1000);
const json=(res,code,data)=>{res.writeHead(code,{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'});res.end(JSON.stringify(data));};
const server=http.createServer(async(req,res)=>{
  if(req.method==='OPTIONS'){res.writeHead(204,{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type'});return res.end();}
  const path=new URL(req.url,'http://localhost').pathname;
  if(req.method==='GET'&&path==='/api/status')return json(res,200,status());
  if(req.method==='GET'&&path==='/api/mode')return json(res,200,{...meta(),source:mode});
  if(req.method==='POST'&&path==='/api/mode'){
    let body='';for await(const chunk of req)body+=chunk;
    try{const data=JSON.parse(body);if(!['LIVE','RECORDED','SIMULATED'].includes(data.source))return json(res,400,{error:'Invalid source'});
      if(data.source!=='SIMULATED')return json(res,409,{error:'Mock server supports SIMULATED only; use real backend for LIVE/RECORDED'});
      mode='SIMULATED';return json(res,200,{...meta(),source:mode});
    }catch{return json(res,400,{error:'Invalid JSON'});}
  }
  if(req.method==='GET'&&path==='/api/events')return json(res,200,events);
  if(req.method==='GET'&&path==='/api/metrics')return json(res,200,{});
  if(req.method==='POST'&&path==='/api/reset'){events=[];sequences=[];risk='GREEN';fired=new Set();byKey={};send('status',status());return json(res,200,{...meta(),ok:true});}
  return json(res,404,{error:'Not found'});
});
const wss=new WebSocketServer({server,path:'/ws'});
wss.on('connection',ws=>{clients.add(ws);ws.send(JSON.stringify({type:'status',data:status()}));ws.on('close',()=>clients.delete(ws));});
server.listen(PORT,()=>console.log(`EchoTrace SIMULATED mock: http://localhost:${PORT} | ws://localhost:${PORT}/ws`));
