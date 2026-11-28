#!/usr/bin/env python3
"""Read-only independent audit of frozen HG009 identities and H20 price endpoint.

Input bytes are the immutable repo snapshot identified in audit_plan, not today's
prices. No research ledger or prior decision is edited. Raw price changes only.
"""
from pathlib import Path
import argparse, csv, datetime, hashlib, io, json, math, statistics, zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT / 'repo'
OUTPUT = ROOT
ARMS = ['SELECTED', 'ONE_LANE', 'ZERO_LANE']

def read(path):
    return json.loads((REPO/path).read_text())

def bytes_checked(path, expected):
    b = (REPO/path).read_bytes()
    actual = hashlib.sha256(b).hexdigest()
    if actual != expected:
        raise ValueError(f'Original byte hash mismatch {path}: {actual} != {expected}')
    return b

def parse_udiff(path, expected, date):
    b = bytes_checked(path, expected)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        names = [n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Ambiguous original UDiFF archive')
        rows = list(csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8-sig'))))
    exact = {}
    for r in rows:
        if r['TradDt'] != date:
            raise ValueError('Original UDiFF trading date mismatch')
        if r['SctySrs'] != 'EQ':
            continue
        key = (r['TckrSymb'], r['ISIN'])
        if key in exact:
            raise ValueError(f'Duplicate EQ identity {key} on {date}')
        prices = {n:float(r[k]) for n,k in [('open','OpnPric'),('high','HghPric'),('low','LwPric'),('close','ClsPric')]}
        if not all(math.isfinite(x) and x>0 for x in prices.values()):
            continue
        if prices['low'] > min(prices['open'],prices['close']) or prices['high'] < max(prices['open'],prices['close']):
            raise ValueError('Invalid UDiFF bar extrema')
        exact[key] = prices
    return exact, len(rows)

def parse_index(path, expected, date):
    b = bytes_checked(path, expected)
    rows = list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))))
    found = [r for r in rows if r['Index Name'].strip().lower() == 'nifty 500']
    if len(found) != 1:
        raise ValueError('Nifty500 index source is not unique')
    r = found[0]
    source_date = datetime.datetime.strptime(r['Index Date'], '%d-%m-%Y').date().isoformat()
    if source_date != date:
        raise ValueError('Index date mismatch')
    return {'open':float(r['Open Index Value']), 'close':float(r['Closing Index Value'])}

def main():
    clock = read('research/hg009/hg009-p004-a1-nov08-calendar-v1.json')
    selected = read('research/hg009/hg009-d001-100-experimental-companies-v1.json')
    controls = read('research/hg009/hg009-p001-matched-300-company-controls-v1.json')
    dates = clock['amended_H20_20_exact_sessions']
    assert len(dates)==20 and len(set(dates))==20 and dates[0]=='2026-10-15' and dates[-1]=='2026-11-12'
    arms = {'SELECTED':selected['selected'], **controls['controls']}
    identifiers = [(arm,x['symbol'],x['isin']) for arm in ARMS for x in arms[arm]]
    assert all(len(arms[a])==100 for a in ARMS)
    assert len({(s,i) for a,s,i in identifiers})==300
    daymap, indexes, evidence = {}, {}, []
    packet_comparisons = 0
    for date in dates:
        if date == '2026-11-08':
            special = read('research/prospective/h021/special-sessions/2026-11-08/2026-11-08-original-ohlc-v1.json')
            mr, ir = special['original_udiff_source_receipt'], special['original_index_source_receipt']
            mp = f"research/prospective/h021/special-sessions/2026-11-08/raw/sha256/{mr['sha256']}.zip"
            ip = f"research/prospective/h021/special-sessions/2026-11-08/raw/sha256/{ir['sha256']}.csv"
            mh, ih = mr['sha256'], ir['sha256']
            mt, it = mr['captured_at_utc'], ir['captured_at_utc']
            packet = None
        else:
            packet = read(f'research/hg009/daily/{date}-v1.json')
            assert packet['date_ist'] == date
            assert packet['controls_manifest_sha256'] == controls['manifest_sha256']
            assert packet['selected_manifest_sha256'] == selected['cohort_sha256']
            assert len(packet['source_identity_rows'])==300
            assert {(r['arm'],r['symbol'],r['frozen_isin']) for r in packet['source_identity_rows']} == set(identifiers)
            mp,ip = packet['original_market_raw_path'],packet['original_index_raw_path']
            mh,ih = packet['original_market_source_sha256'],packet['original_index_source_sha256']
            mt,it = packet['original_source_market_captured_at_utc'],packet['original_source_index_captured_at_utc']
        exact,n = parse_udiff(mp,mh,date)
        idx = parse_index(ip,ih,date)
        daymap[date], indexes[date] = exact, idx
        # All source capture times must follow the official session's close.
        minimum = datetime.datetime.fromisoformat(date+'T10:45:00+00:00' if date=='2026-11-08' else date+'T10:00:00+00:00')
        assert datetime.datetime.fromisoformat(mt.replace('Z','+00:00'))>=minimum
        assert datetime.datetime.fromisoformat(it.replace('Z','+00:00'))>=minimum
        if packet:
            for r in packet['source_identity_rows']:
                key = (r['symbol'],r['frozen_isin'])
                if r['ohlcv'] is None:
                    assert key not in exact, ('Archived packet missing raw observed identity',date,key)
                else:
                    for f in ['open','high','low','close']:
                        assert abs(exact[key][f]-r['ohlcv'][f+'_inr'])<1e-10
                    packet_comparisons += 1
            assert abs(idx['open']-packet['benchmark']['open'])<1e-10
            assert abs(idx['close']-packet['benchmark']['close'])<1e-10
        evidence.append({'date':date,'stock_original_path':mp,'stock_sha256_verified':mh,'index_original_path':ip,'index_sha256_verified':ih,'original_stock_capture_utc':mt,'original_index_capture_utc':it,'raw_rows':n,'nov8_reparsed_from_archived_full_market_bytes':date=='2026-11-08'})
    rows = []
    for arm,symbol,isin in identifiers:
        key = symbol,isin
        missing = [d for d in dates if key not in daymap[d]]
        if missing:
            outcome = None
        else:
            outcome = 100*(daymap[dates[-1]][key]['close']/daymap[dates[0]][key]['open']-1)
        rows.append({'arm':arm,'symbol':symbol,'isin':isin,'missing_dates':missing,'raw_price_change_pct':outcome,'entry_open':daymap[dates[0]].get(key,{}).get('open'),'exit_close':daymap[dates[-1]].get(key,{}).get('close'),'economic_return_pct':None})
    stats = {}
    for arm in ARMS:
        rr = [r for r in rows if r['arm']==arm]
        vv = [r['raw_price_change_pct'] for r in rr if r['raw_price_change_pct'] is not None]
        stats[arm] = {'original_count':100,'observed_count':len(vv),'missing_count':100-len(vv),'mean_raw_price_change_pct':statistics.fmean(vv),'median_raw_price_change_pct':statistics.median(vv),'min_raw_price_change_pct':min(vv),'max_raw_price_change_pct':max(vv),'positive_price_changes':sum(v>0 for v in vv),'missing':[{'symbol':r['symbol'],'isin':r['isin'],'dates':r['missing_dates']} for r in rr if r['missing_dates']]}
    index_change = 100*(indexes[dates[-1]]['close']/indexes[dates[0]]['open']-1)
    # Reproduce the already frozen H1/H5 reports before relying on new H20 arithmetic.
    prior_checks = []
    for h in [1,5]:
        prior = read(f'research/hg009/price-diagnostics/HG009-P006-H{h}-20261015-v1.json')
        hd = dates[:h]
        for arm in ARMS:
            vals = [100*(daymap[hd[-1]][(s,i)]['close']/daymap[hd[0]][(s,i)]['open']-1) for a,s,i in identifiers if a==arm and all((s,i) in daymap[d] for d in hd)]
            expected = prior['arm_descriptive_statistics'][arm]['mean_price_change_pct_if_observed']
            err = abs(statistics.fmean(vals)-expected)
            assert err<0.00000051
            prior_checks.append({'horizon':h,'arm':arm,'recomputed_mean_pct':statistics.fmean(vals),'sealed_mean_pct':expected,'absolute_error_pct':err})
    # Unknown original slots are not imputed. These are algebraic thresholds only.
    reversal = {}
    for arm in ['ONE_LANE','ZERO_LANE']:
        threshold = stats[arm]['observed_count']*stats[arm]['mean_raw_price_change_pct']-stats['SELECTED']['observed_count']*stats['SELECTED']['mean_raw_price_change_pct']
        reversal[arm] = {'required_missing_selected_sum_minus_missing_control_sum_pp':threshold,'interpretation':'Sum of the two unknown selected raw price changes minus sum of the two unknown control changes must exceed this value to reverse the fixed100 mean gap. Unknown outcomes remain null. No probability or circuit bound implied.'}
    out = {'classification':'INDEPENDENT_READ_ONLY_H20_UNADJUSTED_SOURCE_PRICE_AUDIT_NOT_ECONOMIC_RETURN', 'evaluated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_commit':'1e27acfa719ee3ff4615f8c105eaa0ae870420bf','new_preregistration':False,'original_selection_changed':False,'original_holding_horizon_changed':False,'frozen_ledger_written':False,'entry_date':dates[0],'exit_date':dates[-1],'exact_holding_sessions':dates,'arm_statistics':stats,'nifty500_price_index_change_pct':index_change,'nifty500_entry_open':indexes[dates[0]]['open'],'nifty500_exit_close':indexes[dates[-1]]['close'],'conditional_mean_gaps_pp':{a:stats['SELECTED']['mean_raw_price_change_pct']-stats[a]['mean_raw_price_change_pct'] for a in ['ONE_LANE','ZERO_LANE']},'fixed100_missingness_reversal_thresholds':reversal,'source_originals_hash_checked':len(evidence)*2,'archived_packet_OHLC_rows_independently_reconciled':packet_comparisons,'h1_h5_reconciliation':prior_checks,'official_source_evidence':evidence,'rows':rows,'limitations':['Corporate actions, dividend entitlements and total returns unresolved','Open and close are source proxies, not executable fills','No fees, taxes, spreads or turnover-capacity treatment','One market entry event, not300 independent strategy trials','Controls match source turnover bands, not industry/size/beta','H1/H5/H20 overlap','No economic alpha or buy recommendation from this diagnostic'],'live_capital_allowed':False}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'hg009_h20_audit_result.json').write_text(json.dumps(out,indent=2)+'\n')
    with (OUTPUT/'hg009_h20_audit_rows.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps({k:out[k] for k in ['classification','arm_statistics','nifty500_price_index_change_pct','conditional_mean_gaps_pp','source_originals_hash_checked','archived_packet_OHLC_rows_independently_reconciled','h1_h5_reconciliation']},indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=REPO, help='Read-only original repository root at the declared source commit')
    parser.add_argument('--output', type=Path, default=OUTPUT, help='Separate output directory, never a frozen ledger')
    args = parser.parse_args()
    REPO = args.repo.resolve()
    OUTPUT = args.output.resolve()
    if OUTPUT == REPO or (REPO/'research/hg009') == OUTPUT or (REPO/'research/prospective') == OUTPUT:
        raise SystemExit('Use a separate audit output directory')
    main()
