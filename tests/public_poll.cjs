// Runs in GitHub Actions against the public site, with a real Chromium page.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,folder]=process.argv.slice(2);
const report={started:new Date().toISOString(),url:base,requests:[],snapshots:[]};
const mark=name=>fs.writeFileSync(path.join(folder,name),'ok');
const rows=JSON.parse(fs.readFileSync('index.html','utf8').match(/<script id="baseline-data" type="application\/json">(.*?)<\/script>/s)[1]).filter(r=>r.active);
const closeTo=(actual,expected,label)=>assert.ok(Math.abs(parseFloat(actual)-expected)<0.11,`${label}: ${actual} != ${expected.toFixed(1)}`);
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1280,height:960}});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let navigations=0;page.on('framenavigated',frame=>{if(frame===page.mainFrame())navigations++});
 page.on('request',request=>{if(request.url().includes('/test/live-turnout.json'))report.requests.push({url:request.url(),at:Date.now()})});
 const production=await context.newPage();
 await production.goto(base,{waitUntil:'networkidle'});
 assert.equal(await production.locator('#demoBanner').isVisible(),false,'production must not show a test snapshot');
 await page.goto(base+'test/',{waitUntil:'networkidle'});
 const started=await page.evaluate(()=>performance.timeOrigin);
 async function capture(stage,factor){
  await page.waitForFunction(s=>document.getElementById('sourceName').textContent.endsWith(s),stage,{timeout:360000});
  assert.equal(await page.locator('#testEnvironmentBanner').isVisible(),true);
  assert.equal(await page.locator('#demoBanner').isVisible(),true);
  const response=await fetch(base+'test/live-turnout.json?proof='+Date.now(),{cache:'no-store'});
  assert.equal(response.status,200);
  const feed=await response.json();assert.equal(feed.demo,true);assert.equal(feed.test_revision,stage);assert.equal(feed.records.length,44);
  const values=await page.locator('#pulseOverview strong').allTextContents();
  closeTo(values[0],100*factor,'national progress');
  const sum=(list,key)=>list.reduce((a,r)=>a+r[key],0);
  const historical=100*sum(rows,'voters2022')/sum(rows,'eligible2022');
  const current=100*sum(feed.records,'voted')/sum(feed.records,'eligible');
  closeTo(values[1],100*current/historical,'all localities progress');
  closeTo(values[2],100*current/historical-100*factor,'national gap');
  for(const group of [...new Set(rows.map(r=>r.group))]){
   const picked=rows.filter(r=>r.group===group),names=new Set(picked.map(r=>r.name));
   const live=feed.records.filter(r=>names.has(r.city));
   const historic=100*sum(picked,'voters2022')/sum(picked,'eligible2022');
   const pct=100*sum(live,'voted')/sum(live,'eligible');
   const groupIndex=['right','opp','haredi','arab','zionism'].indexOf(group)+2;
   closeTo(await page.locator('#pulseGroups .pulse-row').nth(groupIndex).locator('.pulse-reading strong').textContent(),100*pct/historic,'group '+group);
  }
  for(const row of rows){
   const tr=page.locator('#pulseCities tr').filter({has:page.locator('td').filter({hasText:new RegExp('^'+row.name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$')})});
   // Match city text exactly through the first cell to avoid ambiguous group text.
   const cells=await page.locator('#pulseCities tr').evaluateAll((trs,name)=>Array.from(trs).find(tr=>tr.cells[0].textContent===name)?.textContent,row.name);
   assert.ok(cells?.includes((factor*100).toFixed(1)+'%'),'city progress '+row.name);
  }
  assert.equal(await page.evaluate(()=>performance.timeOrigin),started);
  assert.equal(navigations,1,'page must not navigate or reload');
  await page.screenshot({path:path.join(folder,stage+'.png'),fullPage:false});
  report.snapshots.push({stage,source:feed.source,updated_at:feed.updated_at,records:feed.records.length,values});
  console.log(stage,JSON.stringify(report.snapshots.at(-1)));
 }
 await capture('one',.5);mark('ready');
 await capture('two',.6);
 assert.ok(report.requests.length>=2);
 assert.ok(report.requests[1].at-report.requests[0].at>=115000,'real two-minute timer must elapse');
 assert.equal(new Set(report.requests.map(r=>r.url)).size,report.requests.length,'cache-busting URL must differ');
 mark('second');
 await page.waitForFunction(()=>document.getElementById('sourceName').textContent.includes('אין נתוני הדגמה פעילים'),null,{timeout:360000});
 assert.ok((await page.locator('#pulseOverview').innerText()).includes('0/44'));
 assert.equal(await page.evaluate(()=>performance.timeOrigin),started);
 assert.equal(navigations,1);
 assert.deepEqual(errors,[]);
 report.finished=new Date().toISOString();report.navigations=navigations;report.cleanup='passed';report.errors=errors;
 await page.screenshot({path:path.join(folder,'cleared.png'),fullPage:false});
 fs.writeFileSync(path.join(folder,'report.json'),JSON.stringify(report,null,2));mark('done');
 await browser.close();
})().catch(error=>{console.error(error);fs.writeFileSync(path.join(folder,'failed'),String(error));process.exit(1)});
