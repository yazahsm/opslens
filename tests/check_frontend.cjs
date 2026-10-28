// Run with Node.js. These are unit/static checks, not browser automation.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
const source=fs.readFileSync(path.join(web,'app.js'),'utf8');
const css=fs.readFileSync(path.join(web,'styles.css'),'utf8');
new vm.Script(source,{filename:'app.js'});
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]);
assert.equal(ids.length,new Set(ids).size,'HTML IDs must be unique');
const dynamic=new Set(['chart-crosshair','chart-hit','chart-tooltip']);
for(const [,id] of source.matchAll(/\$\('([^']+)'\)/g))assert.ok(ids.includes(id)||dynamic.has(id),`Missing element: ${id}`);
for(const [,asset] of html.matchAll(/(?:src|href)="(\/[^"?#]+\.(?:js|css))"/g))assert.ok(fs.existsSync(path.join(web,asset)),asset);
assert.ok(!css.includes('@import'),'The interface should work without external stylesheets');

// Exercise pure rendering functions with known data and a minimal element stub.
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:false,style:{},
  addEventListener(){},setAttribute(){},querySelectorAll(){return[];}});return elements.get(id);}
const context=vm.createContext({Intl,URLSearchParams,Date,Math,setTimeout:()=>0,
  document:{getElementById:element},window:{},console});
vm.runInContext(source.slice(0,source.indexOf("document.addEventListener('click'")),context);
assert.equal(vm.runInContext("esc('<img src=x onerror=alert(1)>')",context),'&lt;img src=x onerror=alert(1)&gt;');
assert.equal(vm.runInContext('percent(null)',context),'—');
assert.equal(vm.runInContext('percent(0)',context),'0.0%');
assert.equal(vm.runInContext("offsetDate('2026-03-01',-1)",context),'2026-02-28');
assert.ok(vm.runInContext("metricCard('Sales','0',null,'x')",context).includes('No comparison'));
const summary={period:{start:'2026-01-01',end:'2026-01-02',previous_start:'2025-12-30',previous_end:'2025-12-31',days:2,region:'',category:''},
  kpis:{sales:300,orders:4,delivered:2,processing:1,cancelled:1,on_time:50,margin:40},
  deltas:{sales:200,orders:100,on_time:-50,margin:0},
  trend:[{date:'2026-01-01',sales:100,previous:50},{date:'2026-01-02',sales:200,previous:50}],
  categories:[{category:'<script>bad</script>',sales:300,orders:2}],
  regions:[{region:'South',sales:300,on_time:50,orders:2}],anomalies:[],inventory:{low_stock:0,sku_locations:1}};
context.fixture=summary;
vm.runInContext("state.summary=fixture;state.meta={datasets:[{kind:'orders',name:'Demo orders',accepted_count:4,rejected_count:1,is_demo:true,id:'abc',created_at:'2026-01-02T00:00:00Z'}]};renderOverview();",context);
assert.ok(element('kpi-grid').innerHTML.includes('₹300'));
assert.ok(element('category-chart').innerHTML.includes('&lt;script&gt;'));
assert.ok(!element('category-chart').innerHTML.includes('<script>bad'));
assert.ok(element('sales-chart').innerHTML.includes('viewBox'));
assert.ok(element('comparison-label').textContent.includes('Daily totals'));
vm.runInContext("state.trend='weekly';renderTrend()",context);
assert.ok(element('comparison-label').textContent.includes('7-day buckets'));
summary.categories=[];summary.regions=[];summary.kpis={sales:0,orders:0,delivered:0,processing:0,cancelled:0,on_time:null,margin:null};
summary.trend=[{date:'2026-01-01',sales:0,previous:0}];
vm.runInContext("state.trend='daily';renderOverview();",context);
assert.ok(element('category-chart').innerHTML.includes('No delivered sales'));
assert.ok(!element('sales-chart').innerHTML.includes('NaN'));
assert.ok(!element('sales-chart').innerHTML.includes('undefined'));
console.log('PASS: JavaScript parses; element references/assets exist; formatting, escaping, daily/weekly charts and empty states pass.');
