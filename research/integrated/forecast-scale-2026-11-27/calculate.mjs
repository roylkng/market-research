// Research-only, Node.js >=18. No network/dependencies. Run against frozen packet.
import {readFileSync} from 'node:fs';
function selectCohort(source,config){
 function rank(s){let h=2166136261;for(const c of config.salt+s)h=Math.imul(h^c.charCodeAt(0),16777619)>>>0;return h}
 const by=new Map;for(const c of source.cards){const a=by.get(c.symbol)||[];a.push(c);by.set(c.symbol,a)}
 const eligible=[],excluded=[];
 for(const [symbol,cs] of by){const c=cs.find(c=>c.scope==="CONSOLIDATED")||cs.find(c=>c.scope==="STANDALONE");const m=c?.metrics||{},s=c?.sequential||{},key=c?.scope==="CONSOLIDATED"?"owner_pat":"reported_pat";let reasons=[];
 if(!c||!c.isin||new Set(cs.map(c=>c.isin)).size!==1)reasons.push("identity");
 if(c?.current?.selector?.period_start!=="2026-07-01"||c?.current?.selector?.period_end!=="2026-09-30"||s.selector?.period_start!=="2026-04-01"||s.selector?.period_end!=="2026-06-30"||s.selector?.scope!==c.scope)reasons.push("quarter");
 if(!c?.current?.known_at||!Number.isFinite(Date.parse(c.current.known_at))||Date.parse(c.current.known_at)>Date.parse(source.as_of)||!s.known_at||!Number.isFinite(Date.parse(s.known_at))||Date.parse(s.known_at)>Date.parse(source.as_of))reasons.push("clock");
 let keys=["reported_pat",key,...(c?.scope==="CONSOLIDATED"?["noncontrolling_pat"]:[])];
 if(!keys.every(k=>Number.isFinite(m[k]?.current)&&Number.isFinite(m[k]?.previous)))reasons.push("missing_pat");
 const tol=config.bridgeToleranceCr;
 if(c?.scope==="CONSOLIDATED"&&["current","previous"].some(k=>Math.abs(m.reported_pat?.[k]-m.owner_pat?.[k]-m.noncontrolling_pat?.[k])>tol))reasons.push("ownership_bridge");
 if(c?.scope==="STANDALONE"&&["current","previous"].some(k=>Number.isFinite(m.pbt?.[k])&&Number.isFinite(m.tax_expense?.[k])&&Math.abs(m.pbt[k]-m.tax_expense[k]-m.reported_pat[k])>tol))reasons.push("standalone_bridge");
 if(reasons.length){excluded.push({symbol,isin:c?.isin??null,scope:c?.scope??null,reasons});continue;}
 const periods={};for(const [name,k] of [["q1","previous"],["q2","current"]])periods[name]=Object.fromEntries(["revenue","pbt","tax_expense","reported_pat","owner_pat","noncontrolling_pat","pretax_exceptional_items","other_income"].map(field=>[field,Number.isFinite(m[field]?.[k])?m[field][k]:null]));
 let driverReasons=[];
 if(!["revenue","pbt","tax_expense","reported_pat",key,...(c.scope==="CONSOLIDATED"?["noncontrolling_pat"]:[])].every(k=>Number.isFinite(m[k]?.current)&&Number.isFinite(m[k]?.previous)))driverReasons.push("missing_fields");
 if(!(m.revenue?.current>0&&m.revenue?.previous>0))driverReasons.push("nonpositive_revenue");
 if(["current","previous"].some(k=>Math.abs(m.pbt?.[k]-m.tax_expense?.[k]-m.reported_pat?.[k])>tol))driverReasons.push("pbt_bridge");
 const bridgeOnlyEligible=!driverReasons.length;
 if(config.driverExclusionSymbols.includes(symbol))driverReasons.push("financial_sector_or_holding_company");
 if(!["current","previous"].every(k=>m.pbt?.[k]>0&&m.tax_expense?.[k]>=0&&m.tax_expense[k]/m.pbt[k]<=.5))driverReasons.push("unstable_effective_tax_or_loss");
 if(!["current","previous"].every(k=>m.pretax_exceptional_items?.[k]===0))driverReasons.push("exceptional_item_or_unresolved");
 eligible.push({symbol,isin:c.isin,scope:c.scope,target:c.scope==="CONSOLIDATED"?"PAT_ATTRIBUTABLE_TO_OWNERS":"STANDALONE_PAT",rank:rank(c.isin),input_status:"RETAINED_UNREVIEWED_EXTRACTION",source:c.current,sequential_source:s.evidence,sequential_method:s.method,periods,pat_key:key,bridge_only_eligible:bridgeOnlyEligible,driver_exclusions:driverReasons,prior_year_same_source:c.year_ago?.method??null});
 }
 eligible.sort((a,b)=>a.rank-b.rank||(a.isin<b.isin?-1:a.isin>b.isin?1:0));
 if(new Set(eligible.map(r=>r.isin)).size!==eligible.length)throw Error("Duplicate eligible ISIN");
 if(eligible.length<config.size)throw Error("insufficient cohort");
 return {selected:eligible.slice(0,config.size),eligible_not_selected:eligible.slice(config.size).map(r=>({symbol:r.symbol,isin:r.isin,scope:r.scope,rank:r.rank})),excluded,counts:{cards:source.cards.length,issuers:by.size,eligible:eligible.length,excluded:excluded.length,bridge_only_eligible:eligible.filter(r=>r.bridge_only_eligible).length}};
}
function predict(row,config){
 const {q1,q2}=row.periods,p1=q1[row.pat_key],p2=q2[row.pat_key];
 if(!Number.isFinite(p1)||!Number.isFinite(p2))throw Error("nonfinite PAT");
 const forecasts={latest_quarter:p2,two_quarter_mean:(p1+p2)/2,damped_sequential:p2+.25*(p2-p1),accounting_driver:null};
 let drivers=null;
 if(!row.driver_exclusions.length){
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  const growth=clamp(.5*(q2.revenue/q1.revenue-1),-.1,.1),sales=q2.revenue*(1+growth);
  const margin=(q1.pbt/q1.revenue+2*q2.pbt/q2.revenue)/3,tax=(q1.tax_expense/q1.pbt+2*q2.tax_expense/q2.pbt)/3;
  const nci=row.scope==="CONSOLIDATED"?(q1.noncontrolling_pat+2*q2.noncontrolling_pat)/3:0;
  forecasts.accounting_driver=sales*margin*(1-tax)-nci;
  drivers={sales,growth,pbt_margin:margin,tax_rate:tax,minority_pat:nci};
 }
 return {symbol:row.symbol,isin:row.isin,scope:row.scope,target:row.target,forecasts,drivers,scale_cr:Math.max(config.scaleFloorCr,Math.abs(p1),Math.abs(p2)),reference_q2_pat:p2};
}
function enhanced(spec,row){
 const d=spec.drivers,pbt=spec.model==="operating"?d.revenue*d.ebit_margin+d.other_income-d.finance_cost:d.revenue*d.pbt_margin;
 if(Math.abs(row.periods.q2[row.pat_key]-spec.source_q2_pat)>.05||Math.abs(row.periods.q1[row.pat_key]-spec.source_q1_pat)>.05)throw Error("source mismatch "+spec.symbol);
 const normalizedQ2=spec.prior_q2_pat+spec.prior_q2_adjustment,normalizedQ3=spec.prior_q3_pat+spec.prior_q3_adjustment;
 const forecasts={seasonal_naive:spec.prior_q3_pat,latest_verified_quarter:spec.source_q2_pat,seasonal_additive:spec.source_q2_pat+spec.prior_q3_pat-spec.prior_q2_pat,adjusted_seasonal_additive:spec.source_q2_pat+normalizedQ3-normalizedQ2,raw_yoy_trend:spec.prior_q2_pat>0?spec.prior_q3_pat*spec.source_q2_pat/spec.prior_q2_pat:null,adjusted_yoy_trend:spec.prior_q2_pat>0&&normalizedQ2>0?normalizedQ3*spec.source_q2_pat/normalizedQ2:null,assisted_driver:pbt*(1-d.tax_rate)-d.nci};
 return {...spec,isin:row.isin,scope:row.scope,target:row.target,source_status:"ORIGINAL_ISSUER_PDF_TEXT_CHECKED_SCREENSHOT_FAILED_NO_BYTE_ARCHIVE",forecast_pbt:pbt,forecasts};
}
function score(packet,actuals){
 const ids=new Map(packet.predictions.map(x=>[x.isin,x])),actualMap=new Map;
 if(!Array.isArray(actuals))throw Error("actuals array");
 for(const a of actuals){const x=ids.get(a.isin);if(!x||actualMap.has(a.isin)||a.symbol!==x.symbol||a.scope!==x.scope||a.target!==x.target||a.period_end!==packet.target_period_end||!Number.isFinite(a.actual_pat_cr)||!/^\d{4}-\d{2}-\d{2}$/.test(a.first_release_date)||a.first_release_date<=packet.target_period_end||!/^https:\/\//.test(a.source_url||""))throw Error("invalid/duplicate actual "+a.isin);actualMap.set(a.isin,a)}
 const rows=packet.predictions.map(x=>{const a=actualMap.get(x.isin),e=packet.assisted.find(s=>s.isin===x.isin);const forecasts={...x.forecasts,...(e?e.forecasts:{})};return {symbol:x.symbol,isin:x.isin,actual:a??null,errors:a?Object.fromEntries(Object.entries(forecasts).filter(([k,v])=>Number.isFinite(v)).map(([k,v])=>[k,{signed_cr:v-a.actual_pat_cr,scaled_abs:Math.abs(v-a.actual_pat_cr)/x.scale_cr}])):null}});
 const compare=(lhs,rhs)=>{const common=rows.filter(r=>r.errors&&r.errors[lhs]&&r.errors[rhs]);const n=common.length;if(!n)return {lhs,rhs,n,mean_lhs:null,mean_rhs:null,wins:null,ties:null,losses:null};let wins=0,ties=0;for(const r of common){const d=r.errors[lhs].scaled_abs-r.errors[rhs].scaled_abs;if(Math.abs(d)<=1e-12)ties++;else if(d<0)wins++}return {lhs,rhs,n,mean_lhs:common.reduce((s,r)=>s+r.errors[lhs].scaled_abs,0)/n,mean_rhs:common.reduce((s,r)=>s+r.errors[rhs].scaled_abs,0)/n,wins,ties,losses:n-wins-ties}};
 return {classification:"DESCRIPTIVE_FUNDAMENTAL_ERRORS_NOT_RETURNS",original_count:rows.length,observed_count:actualMap.size,missing_count:rows.length-actualMap.size,complete:actualMap.size===rows.length,comparisons:[...["two_quarter_mean","damped_sequential","accounting_driver"].map(x=>compare(x,"latest_quarter")),...["latest_quarter","two_quarter_mean","damped_sequential","accounting_driver","seasonal_naive","latest_verified_quarter","seasonal_additive","adjusted_seasonal_additive","raw_yoy_trend","adjusted_yoy_trend"].map(x=>compare("assisted_driver",x))],rows};
}
function verify(packet){
 const assert=(v,m)=>{if(!v)throw Error(m)};
 assert(packet.predictions.length===100&&new Set(packet.predictions.map(r=>r.isin)).size===100,"cohort");
 assert(packet.roster.counts.issuers===packet.roster.selected.length+packet.roster.eligible_not_selected.length+packet.roster.excluded.length,"denominator");
 for(let i=0;i<packet.predictions.length;i++)assert(JSON.stringify(predict(packet.roster.selected[i],packet.config))===JSON.stringify(packet.predictions[i]),"forecast reproducibility");
 for(const a of packet.assisted){const r=packet.roster.selected.find(r=>r.isin===a.isin);assert(JSON.stringify(enhanced(a,r))===JSON.stringify(a),"assisted reproducibility")}
 const none=score(packet,[]);assert(none.observed_count===0&&none.comparisons.every(c=>c.n===0&&c.mean_lhs===null),"no fabricated actuals");
 const p=packet.predictions[0],sample={isin:p.isin,symbol:p.symbol,scope:p.scope,target:p.target,period_end:packet.target_period_end,first_release_date:"2027-01-15",source_url:"https://example.com/synthetic-test",actual_pat_cr:p.forecasts.latest_quarter};
 const one=score(packet,[sample]);assert(one.observed_count===1&&one.missing_count===99&&one.comparisons[0].mean_rhs===0,"partial case");
 for(const bad of [[sample,sample],[{...sample,scope:"wrong"}],[{...sample,isin:"wrong"}],[{...sample,actual_pat_cr:null}],[{...sample,period_end:"2026-09-30"}],[{...sample,first_release_date:"2026-12-30"}]]){let fail=false;try{score(packet,bad)}catch{fail=true}assert(fail,"reject bad actual")}
 return {reproduced_predictions:100,reproduced_assisted:packet.assisted.length,identity_and_denominator_checks:2,missing_and_synthetic_partial_checks:2,rejection_checks:6};
}
const packet=JSON.parse(readFileSync(new URL('./forecast_register.json',import.meta.url),'utf8'));
const tests=verify(packet);
// Optional second argument: retained business-changes.json, to reproduce cohort selection.
if(process.argv[3]){const src=JSON.parse(readFileSync(process.argv[3],'utf8'));if(JSON.stringify(selectCohort(src,packet.config))!==JSON.stringify(packet.roster))throw Error('source roster mismatch')}
const actuals=process.argv[2]?JSON.parse(readFileSync(process.argv[2],'utf8')):packet.actuals;
console.log(JSON.stringify({tests,result:score(packet,actuals)},null,2));
