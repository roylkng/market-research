// Portable research-only evaluator. Node.js >=18. No network or dependencies.
import {readFileSync} from 'node:fs';
function buildForecast(x){
 const d=x.drivers;
 if(![x.oldQ3,x.oldQ2,x.newQ2,x.priorQ3Pbt,x.priorQ2Pbt].every(Number.isFinite)||x.oldQ3<=0||x.oldQ2<=0||x.priorQ3Pbt<=0||x.priorQ2Pbt<=0)throw Error("invalid history");
 const pbt=x.model==="services"?d.revenue*d.operatingMargin+d.netOtherIncome:x.model==="bank"?d.netInterestIncome+d.nonInterestIncome-d.operatingExpenses-d.provisions+d.treasury:NaN;
 const n3=x.oldQ3+x.priorQ3IdentifiedPretax-(x.priorQ3KnownTaxBenefit??x.priorQ3IdentifiedPretax*x.priorQ3Tax/x.priorQ3Pbt);
 const n2=x.oldQ2+x.priorQ2IdentifiedPretax*(1-x.priorQ2Tax/x.priorQ2Pbt);
 const forecasts={seasonal_naive:x.oldQ3,latest_quarter:x.newQ2,raw_yoy_trend:x.oldQ3*x.newQ2/x.oldQ2,adjusted_yoy_trend:n3*x.newQ2/n2,driver_based:pbt*(1-d.taxRate)-(d.nci||0)};
 if(!Object.values(forecasts).every(Number.isFinite))throw Error("invalid forecast");
 return {symbol:x.symbol,normalized_prior_Q3:n3,normalized_prior_Q2:n2,forecast_pbt:pbt,forecasts};
}
function evaluateForecasts(packet,actuals){
 if(!Array.isArray(actuals))throw Error("actuals must be array");
 const m=new Map();
 const allowed=new Map(packet.specs.map(x=>[x.symbol,x]));
 for(const a of actuals){
  const x=allowed.get(a.symbol);
  if(!x||m.has(a.symbol)||a.scope!==x.scope||a.period_end!==packet.target_period_end||!Number.isFinite(a.actual_pat_cr)||!(/^\d{4}-\d{2}-\d{2}$/.test(a.first_release_date))||a.first_release_date<=packet.target_period_end||typeof a.source_url!=="string"||!/^https:\/\//.test(a.source_url))throw Error("invalid/duplicate actual: "+a.symbol);
  m.set(a.symbol,a);
 }
 const rows=packet.specs.map(x=>{
  const f=buildForecast(x).forecasts,a=m.get(x.symbol);
  if(!a)return {symbol:x.symbol,actual:null,errors:null};
  return {symbol:x.symbol,actual:a,errors:Object.fromEntries(Object.entries(f).map(([k,v])=>[k,{signed_error_cr:v-a.actual_pat_cr,absolute_error_cr:Math.abs(v-a.actual_pat_cr),scaled_absolute_error:Math.abs(v-a.actual_pat_cr)/x.oldQ3,direction_correct:Math.sign(v-x.oldQ3)===Math.sign(a.actual_pat_cr-x.oldQ3)}]))};
 });
 const complete=rows.filter(r=>r.actual!==null),n=complete.length;
 const scores=n?Object.fromEntries(Object.keys(complete[0].errors).map(k=>[k,{mean_scaled_absolute_error:complete.reduce((s,r)=>s+r.errors[k].scaled_absolute_error,0)/n,direction_accuracy:complete.reduce((s,r)=>s+Number(r.errors[k].direction_correct),0)/n}])):null;
 const comparisons=n?Object.keys(complete[0].errors).filter(k=>k!=="driver_based").map(k=>({baseline:k,driver_wins:complete.filter(r=>r.errors.driver_based.scaled_absolute_error<r.errors[k].scaled_absolute_error-1e-12).length,ties:complete.filter(r=>Math.abs(r.errors.driver_based.scaled_absolute_error-r.errors[k].scaled_absolute_error)<=1e-12).length,driver_minus_baseline_mean_scaled_error:scores.driver_based.mean_scaled_absolute_error-scores[k].mean_scaled_absolute_error})):null;
 return {classification:"DESCRIPTIVE_PAIRED_FORECAST_ERROR_NOT_ALPHA",original_count:rows.length,observed_count:n,missing_count:rows.length-n,complete:n===rows.length,scores,comparisons,rows};
}
function selfTest(p){
 const f=p.specs.map(buildForecast);
 const eq=(a,b)=>{if(Math.abs(a-b)>1e-7)throw Error("numeric mismatch "+a+" "+b)};
 eq(f[0].forecasts.driver_based,13918.22054912);eq(f[1].forecasts.driver_based,7910.8138992);eq(f[2].forecasts.driver_based,19556.894916);eq(f[3].forecasts.driver_based,14891.8132125);eq(f[1].normalized_prior_Q3,7625);
 const zero=evaluateForecasts(p,[]);if(zero.scores!==null||zero.missing_count!==4)throw Error("missing outcome test");
 const a={symbol:p.specs[0].symbol,scope:p.specs[0].scope,period_end:p.target_period_end,first_release_date:"2027-01-15",source_url:"https://example.com/synthetic-test",actual_pat_cr:f[0].forecasts.driver_based};
 const result=evaluateForecasts(p,[a]);eq(result.scores.driver_based.mean_scaled_absolute_error,0);if(result.observed_count!==1||result.complete)throw Error("coverage test");
 for(const bad of [[a,a],[{...a,scope:"wrong"}],[{...a,period_end:"2026-09-30"}],[{...a,first_release_date:"2026-12-30"}],[{...a,actual_pat_cr:null}]]){let rejected=false;try{evaluateForecasts(p,bad)}catch{rejected=true}if(!rejected)throw Error("bad input not rejected")}
 return {forecast_arithmetic:5,missing_case:1,synthetic_partial_case:1,rejection_cases:5,actual_observations:0};
}
const packet=JSON.parse(readFileSync(new URL('./forecast_register.json',import.meta.url),'utf8'));
const tests=selfTest(packet);
const actuals=process.argv[2]?JSON.parse(readFileSync(process.argv[2],'utf8')):packet.actuals;
console.log(JSON.stringify({tests,result:evaluateForecasts(packet,actuals)},null,2));
