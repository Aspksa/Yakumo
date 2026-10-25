"use strict";
// Optional PixiJS WebGL renderer; uses the real entity/fact graph, never sends data away.
(()=>{let current=null;
const hash=s=>{let h=2166136261;for(const c of String(s))h=Math.imul(h^c.charCodeAt(0),16777619);return(h>>>0)/4294967296};
function mount(host,data,options={}){
 if(!window.PIXI)throw Error("Не найдена локальная библиотека PixiJS");
 current?.stop();
 const P=window.PIXI,app=new P.Application(),canvas=document.createElement("div");
 canvas.className="br-pixi-canvas";host.append(canvas);
 let stopped=false,onVisibility=null;
 const profiles={eco:[450,20,.75],balanced:[1400,30,1],high:[3200,60,1.25]};
 const setting=profiles[localStorage.getItem("yakumo-pixi-quality")]||profiles.balanced;
 const entities=(data.entities||[]).slice(0,500),facts=data.facts||[];
 const ids=new Set(entities.map(e=>e.id));const connections=new Map(entities.map(e=>[e.id,new Set()]));
 for(const f of facts){const about=(f.about||[]).filter(id=>ids.has(id));for(const a of about)for(const b of about)if(a!==b)connections.get(a).add(b)}
 const positions=new Map(entities.map(e=>{const arm=Math.floor(hash(e.id+"arm")*4),radius=42+hash(e.id+"radius")*390;
 const angle=radius*.013+arm*Math.PI/2+(hash(e.id+"twist")-.5)*1.9;
 return[e.id,{x:Math.cos(angle)*radius,y:Math.sin(angle)*radius*.63,arm}]}));
 const color=[0xe9be70,0x78c5f0,0xae91e8,0x6dd7b2];
 const stop=()=>{stopped=true;if(onVisibility)document.removeEventListener("visibilitychange",onVisibility);
 try{app.destroy(true,{children:true})}catch{}canvas.remove()};
 current={stop};
 const ready=(async()=>{
 await app.init({resizeTo:canvas,background:0x0b101d,preference:"webgl",antialias:false,
  autoDensity:true,resolution:Math.min(devicePixelRatio||1,setting[2])});
 if(stopped){stop();return}
 canvas.append(app.canvas);
 const world=new P.Container(),dust=new P.Graphics(),links=new P.Graphics(),nodes=new P.Container();
 app.stage.addChild(world);world.addChild(dust,links,nodes);
 for(let i=0;i<setting[0];i++){const r=Math.sqrt(hash("dust-r"+i))*470,a=hash("dust-a"+i)*12.56+r*.012;
 dust.circle(Math.cos(a)*r,Math.sin(a)*r*.65,i%41===0?1.7:.55)
 .fill({color:i%9===0?0xe9be70:0xa7b9d3,alpha:i%9===0?.5:.22})}
 for(const e of entities){const p=positions.get(e.id);
 for(const b of connections.get(e.id))if(String(e.id)<String(b)){
 const q=positions.get(b);
 links.moveTo(p.x,p.y).quadraticCurveTo((p.x+q.x)/2,(p.y+q.y)/2-15,q.x,q.y)
 .stroke({color:0xc3a3cb,alpha:.2,width:1})}
 const group=/person|pet/.test(e.type)?1:/place/.test(e.type)?3:p.arm;
 const node=new P.Graphics();let r=Math.min(7,2.5+Math.sqrt(connections.get(e.id).size));
 node.circle(0,0,r*3).fill({color:color[group],alpha:.08});
 node.circle(0,0,r).fill({color:color[group],alpha:.91});
 node.position.set(p.x,p.y);node.eventMode="static";node.cursor="pointer";node.on("pointertap",()=>options.onPick?.(e.id));
 nodes.addChild(node)}
 const center=()=>{world.position.set(canvas.clientWidth/2,canvas.clientHeight/2);
 world.scale.set(Math.min(canvas.clientWidth/1050,canvas.clientHeight/720,1))};center();
 let drag=null;
 app.canvas.addEventListener("wheel",e=>{e.preventDefault();const rect=app.canvas.getBoundingClientRect();
 const x=e.clientX-rect.left,y=e.clientY-rect.top,k=Math.max(.3,Math.min(3,world.scale.x*(e.deltaY<0?1.12:.89)));
 const wx=(x-world.x)/world.scale.x,wy=(y-world.y)/world.scale.y;world.scale.set(k);world.position.set(x-wx*k,y-wy*k)},{passive:false});
 app.canvas.addEventListener("pointerdown",e=>{drag={x:e.clientX,y:e.clientY,wx:world.x,wy:world.y};app.canvas.setPointerCapture(e.pointerId)});
 app.canvas.addEventListener("pointermove",e=>{if(drag)world.position.set(drag.wx+e.clientX-drag.x,drag.wy+e.clientY-drag.y)});
 for(const event of ["pointerup","pointercancel","lostpointercapture"])app.canvas.addEventListener(event,()=>drag=null);
 app.ticker.maxFPS=setting[1];let t=0;
 const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
 app.ticker.add(ticker=>{if(!reduced){t+=ticker.deltaTime;world.rotation=Math.sin(t*.0015)*.013}});
 onVisibility=()=>document.hidden?app.ticker.stop():app.ticker.start();document.addEventListener("visibilitychange",onVisibility);
 return {center}
 })();
 ready.catch(err=>{stop();options.onError?.(err)});
 return {stop,ready};
}
window.YakumoPixiMap={mount};
})();