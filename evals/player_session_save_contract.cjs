// Execute the real per-player save coordinator with controlled promises only.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web/player/player.js'),'utf8');
const start=source.indexOf('  const reportSaves ='),end=source.indexOf('  // Calculate a bounded engagement',start);
assert(start>=0&&end>start);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
  const calls=[];
  const save=vm.runInNewContext(source.slice(start,end)+'\nsaveVisit',{api:{saveSession:body=>new Promise((resolve,reject)=>calls.push({body,resolve,reject}))}});
  return{save,calls};
}
const record=()=>({id:'same-visit',ended:true,profile:{name:''},leads:[],escalations:[],transcript:[]});
const cases=[
 ['each queued revision freezes its own content',async()=>{const f=fixture(),s=record(),p=f.save(s);s.profile.name='Later';s.leads.push({phone:'9876543210'});await tick();assert.equal(f.calls[0].body.profile.name,'');assert.equal(f.calls[0].body.leads.length,0);f.calls[0].resolve();await p;}],
 ['equal pending and successful revisions use one POST',async()=>{const f=fixture(),s=record(),a=f.save(s),b=f.save(s);assert.equal(a,b);await tick();assert.equal(f.calls.length,1);f.calls[0].resolve();await a;await f.save(s);assert.equal(f.calls.length,1);}],
 ['new recap lead content saves another revision under the same visit ID',async()=>{const f=fixture(),s=record(),a=f.save(s);await tick();f.calls[0].resolve();await a;s.profile.name='Buyer';s.leads.push({phone:'9876543210'});s.escalations.push('callback requested');s.transcript.push({role:'user',text:'Please call me'});const b=f.save(s);await tick();assert.equal(f.calls.length,2);assert.equal(f.calls[1].body.id,f.calls[0].body.id);assert.equal(f.calls[1].body.profile.name,'Buyer');assert.equal(f.calls[1].body.leads.length,1);assert.equal(f.calls[1].body.escalations.length,1);assert.equal(f.calls[1].body.transcript.length,1);f.calls[1].resolve();await b;}],
 ['changed revision waits for the older save to settle',async()=>{const f=fixture(),s=record(),a=f.save(s);s.profile.name='New';const b=f.save(s);await tick();assert.equal(f.calls.length,1);f.calls[0].resolve();await a;await tick();assert.equal(f.calls.length,2);assert.equal(f.calls[1].body.profile.name,'New');f.calls[1].resolve();await b;}],
 ['failed changed revision retries its exact snapshot once',async()=>{const f=fixture(),s=record();s.profile.name='Buyer';s.leads.push({phone:'9876543210'});const frozen=JSON.parse(JSON.stringify(s)),a=f.save(frozen).catch(e=>e.message);await tick();f.calls[0].reject(new Error('fixture'));await a;s.profile.name='Unrelated later change';const b=f.save(frozen),c=f.save(frozen);assert.equal(b,c);await tick();assert.equal(JSON.stringify(f.calls[0].body),JSON.stringify(f.calls[1].body));f.calls[1].resolve();await b;}],
 ['older failure does not prevent the queued current revision from saving',async()=>{const f=fixture(),s=record(),a=f.save(s).catch(()=>{});s.profile.name='Current';const b=f.save(s);await tick();f.calls[0].reject(new Error('old failure'));await a;await tick();assert.equal(f.calls[1].body.profile.name,'Current');f.calls[1].resolve();await b;}],
 ['separate visits do not wait for each other',async()=>{const f=fixture(),a=f.save(record()),b=f.save({...record(),id:'new-visit',ended:false});await tick();assert.equal(f.calls.length,2);f.calls.forEach(c=>c.resolve());await Promise.all([a,b]);}],
];
(async()=>{let passed=0;for(const[name,test]of cases){try{await test();passed++;console.log('PASS',name);}catch(error){console.error('FAIL',name,error);}}console.log(`Player session save contracts: ${passed}/${cases.length}; no network/providers`);process.exitCode=passed===cases.length?0:1;})();
