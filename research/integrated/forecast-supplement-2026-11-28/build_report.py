#!/usr/bin/env python3
"""Render the dated visual research brief from the frozen supplemental packet."""
import argparse,json,math
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,Color,white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).resolve().parent
W,H=595.276,841.89
M=38
NAVY=HexColor('#142F46');TEAL=HexColor('#087F86');MUTED=HexColor('#556B7A');LIGHT=HexColor('#EDF4F6');GOLD=HexColor('#B87520');LINE=HexColor('#D4E1E6')
FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
BOLD=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
pdfmetrics.registerFont(TTFont('Body',str(FONT)))
pdfmetrics.registerFont(TTFont('Bold',str(BOLD)))
BASE='https://github.com/roylkng/market-research/blob/research/discovery-reset-20261117/research/integrated/forecast-supplement-2026-11-28/'

def para(c,text,x,y,width,size=10,color=NAVY,bold=False,leading=None):
 st=ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=size,leading=leading or size*1.43,textColor=color,spaceAfter=0)
 p=Paragraph(text,st);_,h=p.wrap(width,1000);p.drawOn(c,x,y-h);return y-h

def rule(c,y):
 c.setStrokeColor(LINE);c.setLineWidth(.6);c.line(M,y,W-M,y)

def page(c,n,title,kicker):
 c.setFillColor(NAVY);c.rect(0,H-8,W,8,fill=1,stroke=0)
 para(c,'INVESTMENT RESEARCH / 28 NOVEMBER 2026',M,H-34,W-2*M,8.2,TEAL,True)
 para(c,title,M,H-62,W-2*M,23,NAVY,True,29)
 para(c,kicker,M,H-101,W-2*M,10.3,MUTED)
 c.setFont('Body',7.4);c.setFillColor(MUTED)
 c.drawString(M,25,'December 2026 PAT experiment • Research only • No target-quarter outcomes yet')
 c.drawRightString(W-M,25,f'{n} / 3')

def num(v):
 return f'{v:,.2f}'

def bar(c,x,y,w,labels,values,max_value,color=TEAL):
 for i,(lab,v) in enumerate(zip(labels,values)):
  yy=y-i*27
  para(c,lab,x,yy+5,80,8.8,MUTED)
  c.setFillColor(LIGHT);c.roundRect(x+83,yy-10,w-129,12,3,fill=1,stroke=0)
  c.setFillColor(color);c.roundRect(x+83,yy-10,(w-129)*v/max_value,12,3,fill=1,stroke=0)
  c.setFont('Bold',8.8);c.setFillColor(NAVY);c.drawRightString(x+w,yy-7,num(v))

def box(c,x,y,w,h,title,text,color=TEAL):
 c.setFillColor(LIGHT);c.roundRect(x,y-h,w,h,8,fill=1,stroke=0)
 yy=para(c,title,x+14,y-13,w-28,11,color,True)
 return para(c,text,x+14,yy-9,w-28,9.3,NAVY)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(ROOT/'forecast-brief-2026-11-28.pdf'));a=ap.parse_args()
 packet=json.loads((ROOT/'forecast_register.json').read_text());score=json.loads((ROOT/'scorecard.json').read_text())
 cases={r['symbol']:r for r in packet['cases']};rows=score['rows'];manifest=json.loads((ROOT/'evidence_manifest.json').read_text()) if (ROOT/'evidence_manifest.json').exists() else None
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
 c=canvas.Canvas(str(path),pagesize=(W,H));c.setTitle('December 2026 earnings forecast experiment | 28 November 2026');c.setAuthor('Investment research workspace')
 page(c,1,'12 new forecasts, ready to test','A dated addition to the fixed 100-company cohort. Target: first reported quarter ending 31 December 2026.')
 y=H-160;cw=(W-2*M-20)/3
 for i,(value,label) in enumerate([('15 / 100','Company-specific forecasts now'),('12 / 12','New cases with source checks'),('0','Target-quarter outcomes scored')]):
  x=M+i*(cw+10);c.setFillColor(LIGHT);c.roundRect(x,y-67,cw,67,7,fill=1,stroke=0)
  para(c,value,x+12,y-9,cw-24,24,TEAL,True);para(c,label,x+12,y-43,cw-24,8.0,MUTED)
 top=y-94
 para(c,'Forecasts and competing seasonal estimates',M,top,W-2*M,12,NAVY,True)
 para(c,'INR crore. Company names link to the full source and assumption records.',M,top-23,W-2*M,8.5,MUTED)
 data=[['Company','Latest\nSep PAT','Raw\nseasonal','Adjusted\nseasonal','Model\nbase','Adverse to\nfavorable']]
 for r in rows:
  s=cases[r['symbol']]['scenarios'];f=r['forecasts']
  data.append([r['symbol'],num(f['latest_verified_quarter']),num(f['seasonal_additive']),num(f['normalized_seasonal_additive']),num(f['assisted_driver']),num(s['adverse']['forecast_pat_cr'])+' to '+num(s['favorable']['forecast_pat_cr'])])
 widths=[91,65,68,68,68,W-2*M-360]
 t=Table(data,colWidths=widths,rowHeights=[34]+[24]*12)
 t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,0),'Bold'),('FONTNAME',(0,1),(-1,-1),'Body'),('FONTNAME',(4,1),(4,-1),'Bold'),('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,-1),8.1),('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),white),('TEXTCOLOR',(0,1),(-1,-1),NAVY),('TEXTCOLOR',(4,1),(4,-1),TEAL),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'RIGHT'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,LIGHT]),('LINEBELOW',(0,-1),(-1,-1),.6,LINE)]))
 ty=top-47-322;t.wrapOn(c,W-2*M,322);t.drawOn(c,M,ty)
 for i,r in enumerate(rows):
  yy=ty+322-34-24*(i+1);c.linkURL(BASE+'cases/'+r['symbol']+'.md',(M,yy,M+91,yy+24),relative=0,thickness=0)
 yy=para(c,'<b>Seasonal:</b> current September + prior December − prior September. <b>Adjusted:</b> the same formula after explicitly documented historical adjustments. Some tax and owner allocations are analyst assumptions.',M,ty-12,W-2*M,8.7,MUTED)
 yy=para(c,'All targets are consolidated PAT attributable to owners, except KOTHARIPET standalone PAT. Ranges are assumption scenarios without probabilities. They are not confidence intervals.',M,yy-8,W-2*M,8.7,MUTED)
 box(c,M,yy-15,W-2*M,70,'The important result is a testable forecast, not a claim of skill.','Original forecasts remain unchanged. The added cases use newly verified information. Actual December results are needed before judging whether this research improved accuracy.')
 c.showPage()

 page(c,2,'What changes the earnings picture','Distinguish operating economics, seasonal income and accounting ownership before extrapolating profit.')
 col=(W-2*M-22)/2;x1=M;x2=M+col+22;y=H-155
 para(c,'TATA INVESTMENT',x1,y,col,10.5,TEAL,True)
 para(c,'Dividend seasonality is large',x1,y-22,col,14,NAVY,True)
 bar(c,x1,y-65,col,['Sep 2025','Dec 2025','Sep 2026'],[116.44,13.21,114.33],125)
 para(c,'Reported dividend income, INR crore',x1,y-143,col,8,MUTED)
 para(c,'Base PAT is ₹41.77cr versus ₹115.92cr in September. The model assumes ₹14cr dividends and no net P&amp;L fair-value gain. A profit decline need not imply a comparable fall in portfolio value.',x1,y-165,col,9.4)
 c.linkURL(cases['TATAINVEST']['sources'][1]['url'],(x1,y-150,x1+col,y-145+90),relative=0,thickness=0)

 para(c,'PETRONET LNG',x2,y,col,10.5,TEAL,True)
 para(c,'Variable gains drive the jump',x2,y-22,col,14,NAVY,True)
 bar(c,x2,y-65,col,['Sep 2025','Jun 2026','Sep 2026'],[41,494,658],700)
 para(c,'Issuer-stated aggregate efficiency gains, INR crore',x2,y-143,col,7.7,MUTED)
 para(c,'The model replaces ₹658cr with an assumed ₹450cr. Management did not isolate the basket’s components. The ₹625.42cr vessel-claim stress is separate. Neither persistence nor provision timing is established.',x2,y-165,col,9.4)
 c.linkURL(cases['PETRONET']['sources'][2]['url'],(x2,y-150,x2+col,y-145+90),relative=0,thickness=0)
 rule(c,400)
 box(c,x1,380,col,154,'Thomas Cook: small model distance','Model: <b>₹68.33cr</b>.<br/>Adjusted seasonal ratio: about <b>₹66.60cr</b>.<br/><br/>The source review matters, but the final estimate is close to a simple comparator. Booking growth applies to part of travel activity, not the entire group.')
 box(c,x2,380,col,154,'Kothari: almost the same estimate','Model: <b>₹18.315cr</b>.<br/>Two-quarter mean: <b>₹18.27785cr</b>.<br/><br/>The research explains the input spread. It does not yet demonstrate that a more detailed model creates a more accurate number.')
 box(c,M,216,W-2*M,112,'Accounting distinctions can reverse the interpretation','Devyani reported positive September group PAT but negative PAT attributable to owners. Sigma’s NCI sign and prior-period tax resolve a bridge mismatch without changing owner PAT. Jay Bharat Maruti’s government incentives are separated from manufacturing EBIT. These are evidence and scope checks, not proven forecasting gains.')
 para(c,'Source links: original Tata results and Petronet call are embedded in the charts. Each company row on page 1 opens its full source list, publication dates, hashes and assumptions.',M,86,W-2*M,8.5,MUTED)
 c.showPage()

 page(c,3,'The comparison is fixed before results','More detailed research earns its place only if it improves subsequent accuracy on a fair comparison.')
 y=H-155
 stages=[('1','Freeze forecasts'),('2','Review first release'),('3','Score common rows')]
 width=(W-2*M-28)/3
 for i,(n,t) in enumerate(stages):
  xx=M+i*(width+14);c.setFillColor(TEAL);c.roundRect(xx,y-48,width,48,7,fill=1,stroke=0)
  para(c,n+'  '+t,xx+10,y-15,width-20,9.1,white,True)
 y-=72
 y=para(c,'Same target. Same companies. Same error scale.',M,y,W-2*M,12,NAVY,True)
 y=para(c,'Score each forecast against the first reported December quarter at its recorded accounting scope. Error equals the absolute PAT miss divided by the original reference scale: max(₹1cr, |June PAT|, |September PAT|). Compare methods on the same issuers with available outcomes.',M,y-9,W-2*M,9.5)
 y=para(c,'The primary comparison is the adjusted additive seasonal forecast. Raw seasonality, latest quarter, two-quarter mean, damped trend and valid ratio forecasts remain visible. Normalization is not judgment-free. Comparisons with older frozen forecasts are separately labeled because the information cutoff differs.',M,y-10,W-2*M,9.5)
 y=para(c,'If a merger or demerger changes reporting scope, retain the row and flag the break. Do not silently substitute a more convenient actual. A source URL alone does not authenticate an outcome.',M,y-10,W-2*M,9.5)
 rule(c,y-15);y-=38
 y=para(c,'Audit findings preserved as dated corrections',M,y,W-2*M,12,NAVY,True)
 corrections=[('Neuland','Small Q1/Q2 extraction differences corrected from signed consolidated results.'),('Kothari','Q1 PAT changes by only ₹0.0001cr because the direct quarterly line replaces half-year subtraction.'),('Sigma','Negative NCI signs and ₹0.1167cr prior-period tax explain the bridge. Owner PAT is unchanged.'),('Outcome controls','The new scorer rejects invalid calendar dates, future evidence, wrong scope and altered frozen inputs.')]
 for title,body in corrections:
  y=para(c,'<b>'+title+'.</b> '+body,M,y-12,W-2*M,9.1)
 y-=20;rule(c,y);y-=22
 y=para(c,'Coverage and evidence',M,y,W-2*M,12,NAVY,True)
 y=para(c,'100 fixed cohort companies retain their original simple forecasts. Company-specific coverage rises from 3 to 15. This addition reviews 12 of 12 predetermined companies with no replacements. The separate four-company pilot remains separate. There are zero realized target-quarter outcomes.',M,y-10,W-2*M,9.5)
 y=para(c,'Original issuer PDFs, page locators, file hashes and a portable evidence manifest accompany the cases. The evaluator independently reproduces each base and scenario. These checks establish traceability and arithmetic consistency. They do not establish forecasting skill.',M,y-10,W-2*M,9.5)
 y=para(c,'<b>Next decisive evidence:</b> first December results, followed by additional forecast cohorts across different quarters. A single quarter in this selected universe cannot establish a persistent stock-selection advantage.',M,y-12,W-2*M,9.5)
 para(c,'<link href="'+BASE+'README.md" color="#087F86">Open the complete research packet and reproduction instructions</link>',M,75,W-2*M,9.2,TEAL,True)
 c.save();print(path)

if __name__=='__main__':main()
