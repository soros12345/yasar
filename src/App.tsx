import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, Pause, Play, RefreshCw, ShieldCheck, Zap } from 'lucide-react';

type Market = {
  id: string;
  question: string;
  endDate?: string;
  outcomes: string[];
  prices: number[];
  tokenIds: string[];
};

type Fill = {
  id: string;
  side: 'UP' | 'DOWN';
  qty: number;
  price: number;
  fee: number;
  ts: string;
};

type Pair = { qty: number; upCost: number; downCost: number; fee: number; totalCost: number; edge: number };

const GAMMA = 'https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200';
const CLOB = 'https://clob.polymarket.com/book?token_id=';
const START_BALANCE = 10000;

function safeJson<T>(v: unknown, fallback: T): T {
  try {
    if (Array.isArray(v)) return v as T;
    if (typeof v === 'string') return JSON.parse(v) as T;
    return fallback;
  } catch { return fallback; }
}

function matchFifo(fills: Fill[]): Pair[] {
  const up = fills.filter(f => f.side === 'UP').map(f => ({ ...f }));
  const down = fills.filter(f => f.side === 'DOWN').map(f => ({ ...f }));
  const pairs: Pair[] = [];
  let i = 0, j = 0;
  while (i < up.length && j < down.length) {
    const q = Math.min(up[i].qty, down[j].qty);
    const fee = (up[i].fee / up[i].qty + down[j].fee / down[j].qty) * q;
    const upCost = up[i].price * q;
    const downCost = down[j].price * q;
    const totalCost = upCost + downCost + fee;
    pairs.push({ qty: q, upCost, downCost, fee, totalCost, edge: q - totalCost });
    up[i].qty -= q; down[j].qty -= q;
    if (up[i].qty <= 1e-9) i++;
    if (down[j].qty <= 1e-9) j++;
  }
  return pairs;
}

async function fetchBook(tokenId: string) {
  const r = await fetch(CLOB + encodeURIComponent(tokenId));
  if (!r.ok) throw new Error(`CLOB ${r.status}`);
  const j = await r.json();
  const asks = Array.isArray(j.asks) ? j.asks.map((x: any) => ({ price: Number(x.price), size: Number(x.size) })).filter((x:any)=>Number.isFinite(x.price)) : [];
  const bids = Array.isArray(j.bids) ? j.bids.map((x: any) => ({ price: Number(x.price), size: Number(x.size) })).filter((x:any)=>Number.isFinite(x.price)) : [];
  asks.sort((a:any,b:any)=>a.price-b.price); bids.sort((a:any,b:any)=>b.price-a.price);
  return { asks, bids };
}

export default function App() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [selected, setSelected] = useState<Market | null>(null);
  const [books, setBooks] = useState<any[]>([]);
  const [fills, setFills] = useState<Fill[]>(() => safeJson(localStorage.getItem('polyarb:fills'), []));
  const [paused, setPaused] = useState(false);
  const [status, setStatus] = useState('Bağlanıyor…');
  const [lastUpdate, setLastUpdate] = useState<string>('—');
  const [error, setError] = useState<string>('');
  const [qty, setQty] = useState(10);
  const [maxPairCost, setMaxPairCost] = useState(0.95);
  const [maxUnmatched, setMaxUnmatched] = useState(250);
  const [feeBps, setFeeBps] = useState(0);

  useEffect(() => { localStorage.setItem('polyarb:fills', JSON.stringify(fills)); }, [fills]);

  async function loadMarkets() {
    setError(''); setStatus('Piyasa verisi alınıyor…');
    try {
      const r = await fetch(GAMMA);
      if (!r.ok) throw new Error(`Gamma ${r.status}`);
      const raw = await r.json();
      const parsed: Market[] = (Array.isArray(raw) ? raw : []).map((m:any) => ({
        id: String(m.id ?? m.conditionId ?? ''),
        question: String(m.question ?? ''),
        endDate: m.endDate ?? m.end_date_iso,
        outcomes: safeJson<string[]>(m.outcomes, []),
        prices: safeJson<any[]>(m.outcomePrices, []).map(Number),
        tokenIds: safeJson<string[]>(m.clobTokenIds, []),
      })).filter((m:any) => m.question && /btc|bitcoin/i.test(m.question) && m.tokenIds.length >= 2);
      setMarkets(parsed);
      setSelected(s => s && parsed.some(m=>m.id===s.id) ? s : parsed[0] ?? null);
      setStatus(parsed.length ? 'Polymarket bağlı' : 'BTC piyasası bulunamadı');
      setLastUpdate(new Date().toLocaleTimeString('tr-TR'));
    } catch (e:any) {
      setStatus('Veri bağlantısı yok'); setError(e.message ?? 'Bilinmeyen hata');
    }
  }

  async function loadBooks() {
    if (!selected) return;
    try {
      const b = await Promise.all(selected.tokenIds.slice(0,2).map(fetchBook));
      setBooks(b); setLastUpdate(new Date().toLocaleTimeString('tr-TR')); setError('');
    } catch (e:any) { setError(e.message ?? 'Order book alınamadı'); }
  }

  useEffect(() => { loadMarkets(); }, []);
  useEffect(() => { loadBooks(); const id = setInterval(loadBooks, 5000); return () => clearInterval(id); }, [selected?.id]);

  const upAsk = books[0]?.asks?.[0]?.price ?? selected?.prices?.[0] ?? null;
  const downAsk = books[1]?.asks?.[0]?.price ?? selected?.prices?.[1] ?? null;
  const pairCost = upAsk != null && downAsk != null ? upAsk + downAsk : null;
  const arbEdge = pairCost != null ? 1 - pairCost : null;
  const pairs = useMemo(() => matchFifo(fills), [fills]);
  const upQty = fills.filter(f=>f.side==='UP').reduce((a,f)=>a+f.qty,0);
  const downQty = fills.filter(f=>f.side==='DOWN').reduce((a,f)=>a+f.qty,0);
  const unmatched = Math.abs(upQty-downQty);
  const spent = fills.reduce((a,f)=>a + f.qty*f.price + f.fee, 0);
  const lockedEdge = pairs.reduce((a,p)=>a+p.edge,0);
  const balance = START_BALANCE - spent;
  const riskBlocked = paused || unmatched >= maxUnmatched;

  function paperBuy(side:'UP'|'DOWN') {
    const price = side==='UP' ? upAsk : downAsk;
    if (price == null || !Number.isFinite(price)) return setError('Geçerli fiyat yok');
    const projected = Math.abs((side==='UP'?upQty+qty:upQty) - (side==='DOWN'?downQty+qty:downQty));
    if (paused) return setError('Bot duraklatıldı');
    if (projected > maxUnmatched) return setError('Risk motoru: maksimum eşleşmemiş envanter aşılıyor');
    const fee = qty * price * feeBps / 10000;
    setFills(v => [...v, { id: crypto.randomUUID(), side, qty, price, fee, ts: new Date().toISOString() }]);
    setError('');
  }

  const pairSafe = pairCost != null && pairCost <= maxPairCost;

  return <div className="app">
    <aside className="side">
      <div className="brand"><Zap size={24}/> PolyArb Bot</div>
      <div className="muted">BTC Up/Down • Paper Trading</div>
      <nav>{['Dashboard','Piyasalar','İşlemler','Envanter','Strateji','Risk Yönetimi','Analiz','Raporlar','Ayarlar'].map((x,i)=><button key={x} className={i===0?'active':''}>{x}</button>)}</nav>
      <div className="system"><b>Sistem Durumu</b><span>● {status}</span><span>Son güncelleme: {lastUpdate}</span><span>Mod: Paper</span></div>
    </aside>

    <main>
      <header>
        <div><h1>{selected?.question ?? 'BTC Up/Down piyasası aranıyor'}</h1><p>Gerçek Polymarket verisi + yerel paper-trading motoru</p></div>
        <div className="actions"><button onClick={loadMarkets}><RefreshCw size={16}/> Yenile</button><button className={paused?'green':'danger'} onClick={()=>setPaused(!paused)}>{paused?<><Play size={16}/> Devam</>:<><Pause size={16}/> Duraklat</>}</button></div>
      </header>

      {error && <div className="alert"><AlertTriangle size={18}/>{error}</div>}

      <section className="cards">
        <Card label="Paper Bakiye" value={`$${balance.toFixed(2)}`} />
        <Card label="Kilitli Pair Edge" value={`$${lockedEdge.toFixed(2)}`} good={lockedEdge>=0}/>
        <Card label="UP / DOWN" value={`${upQty.toFixed(0)} / ${downQty.toFixed(0)}`} />
        <Card label="Eşleşmemiş" value={unmatched.toFixed(0)} warn={unmatched>maxUnmatched*0.7}/>
        <Card label="Anlık Pair Cost" value={pairCost==null?'—':`$${pairCost.toFixed(3)}`} good={pairSafe}/>
        <Card label="Anlık Edge" value={arbEdge==null?'—':`${(arbEdge*100).toFixed(2)}%`} good={(arbEdge??0)>0}/>
      </section>

      <section className="grid2">
        <div className="panel">
          <div className="panelHead"><h2>Piyasa</h2><select value={selected?.id??''} onChange={e=>setSelected(markets.find(m=>m.id===e.target.value)??null)}>{markets.map(m=><option key={m.id} value={m.id}>{m.question}</option>)}</select></div>
          <div className="quotes"><Quote side="UP" price={upAsk}/><Quote side="DOWN" price={downAsk}/></div>
          <div className="opportunity"><Activity size={20}/><div><b>{pairSafe?'Eşik içinde fırsat':'Eşik dışında'}</b><p>{pairCost==null?'Fiyat bekleniyor':`UP + DOWN = $${pairCost.toFixed(3)} • brüt edge $${(1-pairCost).toFixed(3)}`}</p></div></div>
          <div className="controls"><label>Lot<input type="number" min="1" value={qty} onChange={e=>setQty(Math.max(1,Number(e.target.value)||1))}/></label><button disabled={riskBlocked} onClick={()=>paperBuy('UP')}>Paper UP Al</button><button disabled={riskBlocked} onClick={()=>paperBuy('DOWN')}>Paper DOWN Al</button></div>
        </div>

        <div className="panel">
          <h2>Risk Motoru</h2>
          <label>Maks. pair maliyeti <input type="number" step="0.001" value={maxPairCost} onChange={e=>setMaxPairCost(Number(e.target.value))}/></label>
          <label>Maks. eşleşmemiş lot <input type="number" value={maxUnmatched} onChange={e=>setMaxUnmatched(Number(e.target.value))}/></label>
          <label>Fee varsayımı (bps) <input type="number" value={feeBps} onChange={e=>setFeeBps(Number(e.target.value))}/></label>
          <div className={riskBlocked?'risk bad':'risk good'}><ShieldCheck size={20}/>{riskBlocked?'Yeni emirler bloklu':'Risk limitleri içinde'}</div>
          <button className="danger wide" onClick={()=>{setPaused(true);}}>KILL SWITCH</button>
        </div>
      </section>

      <section className="grid2">
        <Book title="UP Order Book" book={books[0]}/><Book title="DOWN Order Book" book={books[1]}/>
      </section>

      <section className="panel">
        <div className="panelHead"><h2>Paper Fill Kayıtları</h2><button onClick={()=>setFills([])}>Kayıtları Temizle</button></div>
        <table><thead><tr><th>Zaman</th><th>Taraf</th><th>Lot</th><th>Fiyat</th><th>Fee</th><th>Maliyet</th></tr></thead><tbody>{[...fills].reverse().map(f=><tr key={f.id}><td>{new Date(f.ts).toLocaleTimeString('tr-TR')}</td><td className={f.side==='UP'?'up':'down'}>{f.side}</td><td>{f.qty}</td><td>${f.price.toFixed(3)}</td><td>${f.fee.toFixed(4)}</td><td>${(f.qty*f.price+f.fee).toFixed(2)}</td></tr>)}</tbody></table>
        {!fills.length && <div className="empty">Henüz paper işlem yok.</div>}
      </section>

      <footer>Canlı para işlemi yoktur. Bu sürüm gerçek halka açık piyasa verisini izler ve işlemleri yalnızca paper modunda simüle eder.</footer>
    </main>
  </div>
}

function Card({label,value,good,warn}:{label:string,value:string,good?:boolean,warn?:boolean}) { return <div className={`card ${good?'goodCard':''} ${warn?'warnCard':''}`}><span>{label}</span><strong>{value}</strong></div> }
function Quote({side,price}:{side:string,price:number|null}) { return <div className="quote"><span className={side==='UP'?'up':'down'}>{side}</span><strong>{price==null?'—':`$${price.toFixed(3)}`}</strong></div> }
function Book({title,book}:{title:string,book:any}) { const rows=[...(book?.asks??[])].slice(0,5); return <div className="panel"><h2>{title}</h2><table><thead><tr><th>Ask</th><th>Size</th></tr></thead><tbody>{rows.map((r:any,i:number)=><tr key={i}><td>${r.price.toFixed(3)}</td><td>{r.size.toFixed(2)}</td></tr>)}</tbody></table>{!rows.length&&<div className="empty">Order book verisi bekleniyor.</div>}</div> }
