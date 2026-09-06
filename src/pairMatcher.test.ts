import { describe, expect, it } from 'vitest';

type Fill={side:'UP'|'DOWN';qty:number;price:number;fee:number};
function match(fills:Fill[]){const up=fills.filter(f=>f.side==='UP').map(f=>({...f}));const down=fills.filter(f=>f.side==='DOWN').map(f=>({...f}));let i=0,j=0,edge=0,qty=0;while(i<up.length&&j<down.length){const q=Math.min(up[i].qty,down[j].qty);const fee=(up[i].fee/up[i].qty+down[j].fee/down[j].qty)*q;edge+=q-(up[i].price+down[j].price)*q-fee;qty+=q;up[i].qty-=q;down[j].qty-=q;if(up[i].qty<=1e-9)i++;if(down[j].qty<=1e-9)j++;}return{qty,edge};}

describe('FIFO pair matcher',()=>{
  it('locks 8c per 34c+58c pair before fees',()=>{const r=match([{side:'UP',qty:100,price:.34,fee:0},{side:'DOWN',qty:100,price:.58,fee:0}]);expect(r.qty).toBe(100);expect(r.edge).toBeCloseTo(8,8);});
  it('matches only min inventory',()=>{const r=match([{side:'UP',qty:120,price:.34,fee:0},{side:'DOWN',qty:80,price:.58,fee:0}]);expect(r.qty).toBe(80);expect(r.edge).toBeCloseTo(6.4,8);});
});
