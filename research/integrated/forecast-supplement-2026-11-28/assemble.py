#!/usr/bin/env python3
"""Assemble additive case records, validate against the pinned original, emit comparison."""
import argparse,csv,hashlib,json
from pathlib import Path
from calculate import score,validate_baseline_bytes
ROOT=Path(__file__).resolve().parent

def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cutoff',help='Required for first assembly, explicit UTC evidence cutoff');a=ap.parse_args()
 existing=ROOT/'forecast_register.json'
 cutoff=a.cutoff or (json.loads(existing.read_text())['evidence_cutoff_utc'] if existing.exists() else None)
 if not cutoff:raise SystemExit('First assembly requires --cutoff. Reproduction reuses the recorded cutoff.')
 selection=json.loads((ROOT/'selection.json').read_text());cases=[json.loads((ROOT/'cases'/f'{r["symbol"]}.json').read_text()) for r in selection['attempted']]
 original_path=ROOT/'../forecast-scale-2026-11-27/forecast_register.json';ob=original_path.read_bytes();original=json.loads(ob)
 packet={'classification':'PROSPECTIVE_ADDITIVE_WITHIN_QUARTER_FORECAST_SUPPLEMENT_NOT_INVESTMENT_RECOMMENDATIONS','research_date_ist':'2026-11-28','evidence_cutoff_utc':cutoff,'target_period_end':'2026-12-31','unit':'INR_CRORE','original_register':'../forecast-scale-2026-11-27/forecast_register.json','original_register_sha256':selection['baseline_sha256'],'original_register_git_blob_sha1':selection.get('baseline_git_blob_sha1'),'selection_file':'selection.json','ratio_denominator_floor_cr':1.0,'attempted_cohort_size':12,'source_policy':'Critical financial tables from signed issuer results visually reviewed. Management outlook is an issuer claim, not a verified future result. Original bytes, hashes and publication dates retained separately.','forecast_target':'First reported December 2026 quarterly PAT at the selected issuer identity and consolidated/standalone scope, including the explicitly recorded owner attribution. No substitute EPS, total group PAT, adjusted PAT or annualized number.','outcome_policy':{'first_release':'Read and capture the first quarterly release, not a later restatement. Record release date, review timestamp, original source URL, unit and identity.','perimeter_changes':'If the same selected issuer identity and accounting target still report a first-release figure, score that reported figure and flag the merger/demerger or other perimeter change separately. Do not use it for a post-hoc favorable exclusion. If no matching issuer/target genuinely exists, retain the attempted row as unavailable with an explicit reason. No silent pro-forma substitution.','actuals_after_review_only':True,'future_actuals':None},'comparison_policy':{'primary':'assisted_driver versus normalized_seasonal_additive on identical observed rows','mandatory_raw_check':'Also report raw seasonal_additive. Normalized input adjustments may contain analyst tax or owner-allocation assumptions.','additional_same_information_methods':['latest_verified_quarter','verified_two_quarter_mean','verified_damped_sequential','seasonal_naive','raw_yoy_trend','normalized_yoy_trend'],'older_frozen_comparisons':'Separate diagnostics because information dates differ. Do not call the difference pure model/reasoning skill.','error_scale':'Original frozen max(1,abs(Q1 PAT),abs(Q2 PAT)), unchanged even where extraction was corrected.','missingness':'Every attempt is retained. Pairwise comparisons report available, observed and missing counts. No best-method selection after results.','scenario_policy':'Three explicit assumptions, no probabilities and no prediction-interval claim.','cohort_limit':'First twelve remaining original hash-ranked names, from a selected source-acquisition universe. Not a random sample of the Indian market.','within_quarter':'Recorded with the target quarter already in progress, not a quarter-start forecast.'},'cases':cases,'actuals':[]}
 digest=validate_baseline_bytes(ob,packet,selection)
 result=score(packet,original,selection);result['original_register_sha256_verified']=digest
 dump(existing,packet);dump(ROOT/'scorecard.json',result)
 fields=['symbol','scope','target','latest_verified_pat_cr','raw_seasonal_pat_cr','normalized_seasonal_pat_cr','assisted_pat_cr','adverse_pat_cr','favorable_pat_cr','original_error_scale_cr','actual_pat_cr']
 with (ROOT/'forecasts.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r,c in zip(result['rows'],cases):
   s=c['scenarios'];v=r['forecasts']
   w.writerow(dict(zip(fields,[r['symbol'],r['scope'],r['target'],v['latest_verified_quarter'],v['seasonal_additive'],v['normalized_seasonal_additive'],v['assisted_driver'],s['adverse']['forecast_pat_cr'],s['favorable']['forecast_pat_cr'],r['original_scale_cr'],None])))
 print(json.dumps({'cutoff':cutoff,'coverage':result['coverage'],'primary_comparison':result['primary_comparison'],'original_sha256':digest},indent=2))

if __name__=='__main__':main()
