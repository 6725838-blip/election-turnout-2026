// Run the dashboard logic against a minimal DOM; browser QA is performed separately.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const nodes=new Map();
function element(id){
 if(!nodes.has(id))nodes.set(id,{
  value:'',textContent:'',innerHTML:'',style:{},options:[],checked:false,
  classList:{toggle(){},remove(){},add(){}},
  scrollIntoView(){},querySelector(){return null},querySelectorAll(){return []},
  dataset:{},setAttribute(){},addEventListener(){}
 });
 return nodes.get(id);
}
for(const id of ['baseline-data','embedded-demo'])element(id).textContent=html.match(new RegExp(`<script id="${id}" type="application/json">([\\s\\S]*?)<\\/script>`))[1];
element('feedUrl').value='./live-turnout.json';
element('boardSort').value='fixed';
element('filterGroup').value='';
element('sort').value='group';
element('showForecasts').checked=false;
const context=vm.createContext({
 document:{getElementById:element,querySelectorAll:()=>[]},
 location:{protocol:'file:',href:'https://example.invalid/project/',pathname:'/project/'},
 localStorage:{getItem(){},removeItem(){},setItem(){}},
 setInterval(){},setTimeout,URL,AbortSignal,console,globalThis:{}
});
context.globalThis=context;
const script=html.match(/<script>\s*([\s\S]*?)<\/script>\s*<\/body>/)[1]
 .replace(/\}\)\(\);\s*$/, 'globalThis.api={state,rows,ingest,fetchFeed,newPulseStats,nationalLive,groupStats,buildHistoricalComparison,buildHistoricalInsights,primaryGroups};})();');
vm.runInContext(script,context);
const {api}=context;
assert.equal(api.rows.length,50);assert.equal(api.state.selected.size,44);assert.equal(api.state.live.size,0);
element('scenarioDemo').onclick();
assert.equal(element('demoBanner').style.display,'block');
assert.equal(api.newPulseStats(api.rows).completeCount,44);
assert.ok(api.newPulseStats(api.rows).progress!=null);
element('loadDemo').onclick();
assert.equal(api.newPulseStats(api.rows).current,null,'partial reports cannot form complete aggregate for all-selected pulse');
const haredi=api.groupStats('haredi');
assert.ok(haredi.current!=null,'partial-group weighted turnout allowed for reported cities');
assert.equal(haredi.fullCount,5);
assert.ok(haredi.baseline!=null,'2022 baseline uses same reported cities');
const empty={format_version:1,source:'Not connected',updated_at:null,national_turnout_pct:null,records:[]};
(async()=>{
 let requests=0;
 context.fetch=async()=>{requests++;return {ok:true,json:async()=>empty}};
 await api.fetchFeed(true);
 assert.equal(requests,0,'automatic refresh must preserve an explicit local demo');
 await api.fetchFeed(false);
 assert.equal(api.state.live.size,0,'an empty cloud snapshot must clear previous data');
 assert.equal(element('demoBanner').style.display,'none');
 const fixture={source:'Unit test fixture',updated_at:'2026-10-27T12:00:00+02:00',national_turnout_pct:35.315,records:[{city:'אלעד',eligible:10000,voted:4218}]};
 context.fetch=async()=>({ok:true,json:async()=>fixture});
 await api.fetchFeed(true);
 assert.equal(api.state.live.size,1);
 const eladProgress=100*(35.315/70.63);
 assert.ok(Math.abs(api.nationalLive().value-35.315)<1e-9);
 context.fetch=async()=>({ok:true,json:async()=>({...fixture,updated_at:'2026-10-27T13:00:00+02:00',records:[{city:'אלעד',eligible:10000,voted:1000,partial:true}]})});
 await api.fetchFeed(true);
 {
  const row=[...api.state.live.values()][0];
  assert.equal(row.voted,4218,'client merge must keep full report over newer partial');
  assert.equal(row.preserved_previous,true);
 }
 context.fetch=async()=>({ok:true,json:async()=>empty});
 await api.fetchFeed(true);
 assert.equal(api.state.live.size,1,'missing snapshot cannot erase a real report');
 context.fetch=async()=>({ok:true,json:async()=>({...fixture,updated_at:'2026-10-27T11:00:00+02:00',records:[]})});
 await api.fetchFeed(true);assert.equal(api.state.live.size,1,'older snapshot cannot erase a real report');
 context.fetch=async()=>({ok:true,json:async()=>({...fixture,source:'demo',demo:true})});
 await api.fetchFeed(true);assert.equal(api.state.source,'Unit test fixture','demo feed blocked on production route');
 context.fetch=async()=>{throw Error('offline')};
 await api.fetchFeed(true);
 assert.ok(element('dataStatus').textContent.includes('הרענון נכשל') || element('dataStatus').textContent.includes('רענון הנתונים נכשל'));
 assert.equal(api.state.live.size,1,'failed fetch retains last snapshot with warning');
 let resolve;
 context.fetch=()=>new Promise(r=>{resolve=r});
 const pending=api.fetchFeed(false);
 element('scenarioDemo').onclick();
 resolve({ok:true,json:async()=>empty});await pending;
 assert.equal(api.newPulseStats(api.rows).completeCount,44,'old request cannot overwrite a newer user selection');
 const hist=api.buildHistoricalComparison(api.rows.filter(r=>r.active&&api.primaryGroups.includes(r.group)));
 assert.equal(hist.active_n,44);
 assert.equal(Object.keys(hist.groups).length,5);
 assert.ok(hist.coverage_complete);
 for(const gid of api.primaryGroups){
  assert.ok(hist.groups[gid].years[2022].turnout_pct!=null);
  assert.ok(hist.groups[gid].years[2021].turnout_pct!=null);
  assert.ok(hist.groups[gid].years[2020].turnout_pct!=null);
  assert.ok(hist.groups[gid].delta_2021_to_2022_pp!=null);
 }
 assert.ok(Math.abs(hist.groups.arab.delta_2021_to_2022_pp-8.77)<0.05);
 assert.ok(api.buildHistoricalInsights(hist).length<=3);
 console.log('Dashboard checks passed: board stats, preservation, partial coverage, demo isolation, refresh, empty snapshots, failures, races, historical panel.');
})().catch(e=>{console.error(e);process.exitCode=1});
