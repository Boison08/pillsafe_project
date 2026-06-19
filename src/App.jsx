import { useState, useEffect, useCallback, useRef } from "react";

/* ─── API Service ───────────────────────────────────────────────────────────── */
const BASE_URL = "http://192.168.4.1:5000";
const api = {
  async get(p){const r=await fetch(`${BASE_URL}${p}`);if(!r.ok)throw new Error(r.status);return r.json();},
  async post(p,b){const r=await fetch(`${BASE_URL}${p}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)});if(!r.ok)throw new Error(r.status);return r.json();},
  async del(p){const r=await fetch(`${BASE_URL}${p}`,{method:"DELETE"});if(!r.ok)throw new Error(r.status);return r.json();},
  async patch(p){const r=await fetch(`${BASE_URL}${p}`,{method:"PATCH"});if(!r.ok)throw new Error(r.status);return r.json();},
  getUsers:()=>api.get("/users"),
  createUser:u=>api.post("/users",u),
  getSlots:()=>api.get("/slots"),
  startEnrolment:id=>api.post("/enrol/start",{user_id:id}),
  getEnrolmentProgress:id=>api.get(`/enrol/progress?user_id=${id}`),
  finaliseEnrolment:id=>api.post("/enrol/finalise",{user_id:id}),
  verify:()=>api.post("/verify",{}),
  login:credentials=>api.post("/auth/login",credentials),
  getSchedules:id=>api.get(`/schedules?user_id=${id}`),
  createSchedule:s=>api.post("/schedules",s),
  deleteSchedule:id=>api.del(`/schedules/${id}`),
  getAdherence:(id,days=7)=>api.get(`/adherence?user_id=${id}&days=${days}`),
  getNotifications:id=>api.get(`/notifications?user_id=${id}`),
  markRead:id=>api.patch(`/notifications/read?user_id=${id}`),
  getDeviceStatus:()=>api.get("/device/status"),
};

/* ─── Mock data ─────────────────────────────────────────────────────────────── */
const MOCK = {
  user:{id:1,fullName:"Maxwell Donkor",caregiverPhone:"+233 24 000 0001",compartmentIndex:0,enrolled:true},
  schedules:[
    {id:1,medicationName:"Lisinopril 10mg",dosage:"1 tablet",dispenseTimes:["07:00"],repeatDays:[1,1,1,1,1,1,1],gracePeriodMinutes:15},
    {id:2,medicationName:"Atorvastatin 20mg",dosage:"1 tablet",dispenseTimes:["08:00"],repeatDays:[1,1,1,1,1,1,1],gracePeriodMinutes:15},
    {id:3,medicationName:"Metformin 500mg",dosage:"1 tablet",dispenseTimes:["13:00","23:00"],repeatDays:[1,1,1,1,1,1,1],gracePeriodMinutes:15},
    {id:4,medicationName:"Aspirin 81mg",dosage:"1 tablet",dispenseTimes:["20:00"],repeatDays:[1,1,1,1,1,1,1],gracePeriodMinutes:15},
  ],
  adherence:[
    {medicationName:"Lisinopril 10mg",scheduledAt:new Date(Date.now()-3600000*3).toISOString(),status:"taken"},
    {medicationName:"Metformin 500mg",scheduledAt:new Date(Date.now()-3600000*13).toISOString(),status:"missed"},
    {medicationName:"Aspirin 81mg",scheduledAt:new Date(Date.now()-3600000*30).toISOString(),status:"taken"},
    {medicationName:"Lisinopril 10mg",scheduledAt:new Date(Date.now()-3600000*27).toISOString(),status:"taken"},
    {medicationName:"Atorvastatin 20mg",scheduledAt:new Date(Date.now()-3600000*26).toISOString(),status:"taken"},
  ],
  notifications:[
    {id:1,type:"dispensed",title:"Dose dispensed",detail:"Lisinopril 10mg · Slot A — Pickup confirmed by IR sensor",timestamp:new Date(Date.now()-3600000*3).toISOString(),read:false},
    {id:2,type:"missed",title:"Missed dose",detail:"Metformin 500mg · Slot C — Grace period expired. SMS sent.",timestamp:new Date(Date.now()-3600000*13).toISOString(),read:false},
    {id:3,type:"failedVerification",title:"Verification failed",detail:"3 attempts exceeded. Dispense blocked. Caregiver notified.",timestamp:new Date(Date.now()-3600000*14).toISOString(),read:true},
    {id:4,type:"dispensed",title:"Dose dispensed",detail:"Aspirin 81mg · Slot D — Pickup confirmed",timestamp:new Date(Date.now()-3600000*30).toISOString(),read:true},
    {id:5,type:"deviceAlert",title:"Device reconnected",detail:"PillSafe hotspot re-established after 4 min offline",timestamp:new Date(Date.now()-3600000*32).toISOString(),read:true},
  ],
  slots:[false,false,true,true,false,false],
  device:{connected:true,rtcTime:"09:41:02",gsmSignal:"Strong",slotsLoaded:4,faceModel:"MobileFaceNet TFLite",lastDispense:"07:00 · Slot A"},
};

/* ─── Helpers ────────────────────────────────────────────────────────────────── */
const slotLabel = i => String.fromCharCode(65+i);
const pad = n => String(n).padStart(2,"0");
const fmtRelTime = iso => {
  const d = Math.floor((Date.now()-new Date(iso))/86400000);
  const t = new Date(iso).toLocaleTimeString("en",{hour:"numeric",minute:"2-digit"});
  return d===0?`Today, ${t}`:d===1?`Yesterday, ${t}`:`${new Date(iso).toLocaleDateString("en",{weekday:"short",day:"numeric",month:"short"})}, ${t}`;
};
const greeting = () => { const h=new Date().getHours(); return h<12?"Good morning":h<17?"Good afternoon":"Good evening"; };
const MED_COLORS = ["#1D6FE8","#0EA472","#F59E0B","#EF4444","#8B5CF6","#06B6D4"];

const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const query = "(max-width:768px)";
    const mql = window.matchMedia(query);
    const update = () => setIsMobile(mql.matches);
    update();
    if (mql.addEventListener) mql.addEventListener("change", update);
    else mql.addListener(update);
    return () => {
      if (mql.removeEventListener) mql.removeEventListener("change", update);
      else mql.removeListener(update);
    };
  }, []);
  return isMobile;
};

/* ─── Shared UI atoms ─────────────────────────────────────────────────────────── */
const Spinner = ({size=16,color="#1D6FE8"}) => (
  <span style={{display:"inline-block",width:size,height:size,border:`2px solid ${color}33`,borderTopColor:color,borderRadius:"50%",animation:"spin .7s linear infinite"}} />
);

const Badge = ({children, color="#1D6FE8", bg}) => (
  <span style={{display:"inline-flex",alignItems:"center",fontSize:11,fontWeight:600,padding:"2px 8px",borderRadius:20,background:bg||color+"18",color,letterSpacing:.2}}>{children}</span>
);

const PrimaryBtn = ({children,onClick,disabled,loading,icon,variant="primary"}) => {
  const styles = {
    primary:{background:"#1D6FE8",color:"#fff",border:"none"},
    outline:{background:"transparent",color:"#1D6FE8",border:"1.5px solid #1D6FE8"},
    ghost:{background:"transparent",color:"#64748B",border:"1px solid #E2E8F0"},
    danger:{background:"#EF4444",color:"#fff",border:"none"},
  };
  const s = styles[variant]||styles.primary;
  return (
    <button onClick={onClick} disabled={disabled||loading}
      style={{...s,width:"100%",borderRadius:10,padding:"11px 16px",fontSize:14,fontWeight:600,fontFamily:"inherit",cursor:disabled||loading?"not-allowed":"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:8,opacity:disabled||loading?.5:1,transition:"all .15s",boxShadow:variant==="primary"?"0 2px 8px #1D6FE830":"none"}}>
      {loading?<Spinner size={16} color={variant==="primary"?"#fff":"#1D6FE8"} />:<>{icon&&<span style={{fontSize:16}}>{icon}</span>}{children}</>}
    </button>
  );
};

const Card = ({children,style={}}) => (
  <div style={{background:"#fff",border:"1px solid #E8EEF8",borderRadius:14,padding:"18px 20px",...style}}>{children}</div>
);

const StatCard = ({icon,value,label,color="#1D6FE8",trend}) => (
  <Card style={{padding:"18px 20px",position:"relative",overflow:"hidden"}}>
    <div style={{position:"absolute",top:-12,right:-12,width:64,height:64,borderRadius:"50%",background:color+"0D"}} />
    <div style={{width:36,height:36,borderRadius:10,background:color+"18",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,marginBottom:12}}>{icon}</div>
    <div style={{fontSize:26,fontWeight:700,color:"#0F172A",letterSpacing:-.5}}>{value}</div>
    <div style={{fontSize:13,color:"#64748B",marginTop:3}}>{label}</div>
    {trend&&<div style={{fontSize:11,color:trend>0?"#0EA472":"#EF4444",marginTop:6,fontWeight:600}}>{trend>0?"↑":"↓"} {Math.abs(trend)}% this week</div>}
  </Card>
);

const SectionHead = ({title,action}) => (
  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16}}>
    <h3 style={{fontSize:15,fontWeight:700,color:"#0F172A",margin:0,letterSpacing:-.2}}>{title}</h3>
    {action}
  </div>
);

const FieldLabel = ({children}) => (
  <div style={{fontSize:11,fontWeight:700,color:"#64748B",textTransform:"uppercase",letterSpacing:.8,marginBottom:6}}>{children}</div>
);

const TextInput = ({value,onChange,placeholder,type="text",style={}}) => (
  <input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
    style={{width:"100%",background:"#F8FAFD",border:"1.5px solid #E2E8F0",borderRadius:10,padding:"10px 14px",fontSize:14,color:"#0F172A",fontFamily:"inherit",outline:"none",boxSizing:"border-box",transition:"border-color .15s",...style}}
    onFocus={e=>{e.target.style.borderColor="#1D6FE8";e.target.style.background="#fff";}}
    onBlur={e=>{e.target.style.borderColor="#E2E8F0";e.target.style.background="#F8FAFD";}} />
);

const LoginScreen = ({ email, setEmail, password, setPassword, onLogin, onDemo, error, loading }) => (
  <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: '#F0F5FF' }}>
    <div style={{ width: '100%', maxWidth: 420, background: '#fff', borderRadius: 24, boxShadow: '0 28px 80px rgba(15,23,42,0.12)', padding: '36px 30px', fontFamily: 'inherit' }}>
      <div style={{ marginBottom: 26 }}>
        <div style={{ width: 54, height: 54, borderRadius: 18, background: '#1D6FE8', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, color: '#fff', marginBottom: 16 }}>
          💊
        </div>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#0F172A', marginBottom: 8 }}>Welcome to PillSafe</h1>
        <p style={{ fontSize: 14, color: '#64748B', lineHeight: 1.7 }}>Secure patient registration, face enrollment, and verification in one professional app.</p>
      </div>
      <div style={{ display: 'grid', gap: 18 }}>
        <div>
          <FieldLabel>Email address</FieldLabel>
          <TextInput value={email} onChange={setEmail} placeholder="john@example.com" type="email" />
        </div>
        <div>
          <FieldLabel>Password</FieldLabel>
          <TextInput value={password} onChange={setPassword} placeholder="Enter your password" type="password" />
        </div>
        {error && <div style={{ color: '#EF4444', fontSize: 13, fontWeight: 600 }}>{error}</div>}
        <PrimaryBtn onClick={onLogin} loading={loading} disabled={loading || !email || !password}>Log in</PrimaryBtn>
        <button onClick={onDemo} style={{ width: '100%', padding: '12px 16px', borderRadius: 10, border: '1.5px solid #E2E8F0', background: '#fff', color: '#64748B', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
          Continue with demo account
        </button>
      </div>
    </div>
  </div>
);

const SlotGrid = ({occupancy,selected,onSelect}) => (
  <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginTop:6}}>
    {occupancy.map((occ,i) => {
      const sel = selected===i;
      return (
        <div key={i} onClick={()=>!occ&&onSelect(i)}
          style={{background:sel?"#EBF2FD":occ?"#F8FAFD":"#F8FAFD",border:`${sel?"2px":"1.5px"} solid ${sel?"#1D6FE8":occ?"#E2E8F0":"#E2E8F0"}`,borderRadius:10,padding:"12px 8px",textAlign:"center",cursor:occ?"not-allowed":"pointer",opacity:occ?.45:1,transition:"all .15s"}}>
          <div style={{fontSize:20,fontWeight:800,color:sel?"#1D6FE8":"#0F172A"}}>{slotLabel(i)}</div>
          <div style={{fontSize:11,fontWeight:600,color:sel?"#1D6FE8":occ?"#94A3B8":"#10B981",marginTop:2}}>{occ?"In use":"Free"}</div>
        </div>
      );
    })}
  </div>
);

/* ─── Stepper ─────────────────────────────────────────────────────────────────── */
const Stepper = ({steps,current}) => (
  <div style={{display:"flex",alignItems:"center",marginBottom:28}}>
    {steps.map((s,i) => (
      <div key={i} style={{display:"flex",alignItems:"center",flex:i<steps.length-1?1:"none"}}>
        <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:4}}>
          <div style={{width:32,height:32,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:700,background:i<current?"#1D6FE8":i===current?"#1D6FE8":"#F1F5F9",color:i<=current?"#fff":"#94A3B8",border:i===current?"2px solid #93C5FD":"none",boxShadow:i===current?"0 0 0 4px #EBF2FD":"none",transition:"all .25s"}}>
            {i<current?"✓":i+1}
          </div>
          <div style={{fontSize:11,fontWeight:i===current?700:500,color:i===current?"#1D6FE8":i<current?"#0F172A":"#94A3B8",whiteSpace:"nowrap"}}>{s}</div>
        </div>
        {i<steps.length-1&&<div style={{flex:1,height:2,background:i<current?"#1D6FE8":"#E2E8F0",margin:"0 8px",marginBottom:20,transition:"background .25s"}} />}
      </div>
    ))}
  </div>
);

/* ══════════════════════════════════════════════════════════════════════════════
   SCREENS
═══════════════════════════════════════════════════════════════════════════════ */

/* ─── Home ──────────────────────────────────────────────────────────────────── */
function HomeScreen({user,schedules,adherence,device,isMobile}) {
  const now = new Date();
  const todayIdx = (now.getDay()+6)%7;
  const todaySch = schedules.filter(s=>s.repeatDays[todayIdx]);
  const taken = adherence.filter(l=>l.status==="taken").length;
  const missed = adherence.filter(l=>l.status==="missed").length;
  const rate = adherence.length ? Math.round(taken/adherence.length*100) : 0;

  const nextItem = (() => {
    for(const s of todaySch) for(const t of s.dispenseTimes) {
      const [h,m]=t.split(":").map(Number);
      if(h>now.getHours()||(h===now.getHours()&&m>now.getMinutes())) return {s,t};
    }
    return todaySch.length?{s:todaySch[0],t:todaySch[0].dispenseTimes[0]}:null;
  })();

  const lastMissed = [...adherence].reverse().find(l=>l.status==="missed");
  const days = ["M","T","W","T","F","S","S"];
  const daysFull = ["Mo","Tu","We","Th","Fr","Sa","Su"];

  const statusFor = (s,t) => {
    const [h,m]=t.split(":").map(Number);
    const sched=new Date(now); sched.setHours(h,m,0,0);
    const match=adherence.find(l=>l.medicationName===s.medicationName);
    if(match?.status==="taken") return "taken";
    if(match?.status==="missed") return "missed";
    if(sched<now) return "missed";
    return "pending";
  };

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",overflowY:"auto",height:"100%",boxSizing:"border-box",maxWidth:isMobile?"100%":"1400px",margin:"0 auto"}}>
      {/* Header */}
      <div style={{marginBottom:28}}>
        <div style={{fontSize:13,fontWeight:500,color:"#64748B",marginBottom:4}}>{greeting()},</div>
        <h1 style={{fontSize:28,fontWeight:800,color:"#0F172A",margin:0,letterSpacing:-.7}}>{user.fullName.split(" ")[0]}</h1>
      </div>

      {/* Missed alert */}
      {lastMissed&&(
        <div style={{background:"#FFF5F5",border:"1.5px solid #FCA5A5",borderRadius:12,padding:"12px 16px",marginBottom:24,display:"flex",alignItems:"flex-start",gap:12}}>
          <div style={{width:32,height:32,borderRadius:8,background:"#FEE2E2",display:"flex",alignItems:"center",justifyContent:"center",fontSize:16,flexShrink:0}}>⚠</div>
          <div>
            <div style={{fontSize:13,fontWeight:700,color:"#DC2626"}}>Missed dose alert</div>
            <div style={{fontSize:12,color:"#EF4444",marginTop:2}}>{lastMissed.medicationName} — SMS sent to caregiver at {user.caregiverPhone}</div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div style={{display:"grid",gridTemplateColumns:isMobile?"repeat(2,1fr)":"repeat(4,1fr)",gap:14,marginBottom:28}}>
        <StatCard icon="💊" value={todaySch.length} label="Today's doses" color="#1D6FE8" />
        <StatCard icon="✅" value={`${rate}%`} label="Adherence rate" color="#10B981" trend={4} />
        <StatCard icon="⚠️" value={missed} label="Missed this week" color="#F59E0B" />
        <StatCard icon={device.connected?"🟢":"🔴"} value={device.connected?"Online":"Offline"} label="Device status" color={device.connected?"#10B981":"#EF4444"} />
      </div>

      <div style={{display:"grid",gridTemplateColumns:isMobile?"1fr":"1fr 1fr",gap:20}}>
        {/* Next dose */}
        <Card style={{background:"linear-gradient(135deg,#1D6FE8 0%,#2563EB 100%)",border:"none"}}>
          <div style={{fontSize:12,fontWeight:600,color:"#93C5FD",textTransform:"uppercase",letterSpacing:.8,marginBottom:8}}>Next dispense</div>
          <div style={{fontSize:36,fontWeight:800,color:"#fff",letterSpacing:-1,fontFamily:"'DM Mono',monospace"}}>{nextItem?.t||"--:--"}</div>
          <div style={{fontSize:14,color:"#BFDBFE",marginTop:6,fontWeight:500}}>{nextItem?.s.medicationName||"No more doses today"}</div>
          <div style={{marginTop:16,display:"flex",alignItems:"center",gap:8}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:device.connected?"#4ADE80":"#FCA5A5",boxShadow:device.connected?"0 0 0 3px #4ADE8030":"none"}} />
            <div style={{fontSize:12,color:device.connected?"#A7F3D0":"#FCA5A5",fontWeight:500}}>{device.connected?"Device connected":"Device offline"}</div>
          </div>
        </Card>

        {/* Weekly adherence */}
        <Card>
          <SectionHead title="Weekly adherence" />
          <div style={{display:"flex",gap:6}}>
            {days.map((d,i) => {
              const isT=i===todayIdx, isF=i>todayIdx;
              const dl=adherence.filter(l=>(new Date(l.scheduledAt).getDay()+6)%7===i);
              const hasMissed=dl.some(l=>l.status==="missed"),allTaken=dl.length>0&&dl.every(l=>l.status==="taken");
              const bg=isT?"#1D6FE8":isF?"#F1F5F9":hasMissed?"#FEE2E2":allTaken?"#D1FAE5":"#F1F5F9";
              const fg=isT?"#fff":isF?"#CBD5E1":hasMissed?"#EF4444":allTaken?"#059669":"#94A3B8";
              return (
                <div key={i} style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",gap:4}}>
                  <div style={{width:32,height:32,borderRadius:8,background:bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:12,fontWeight:isT?800:600,color:fg}}>{d}</div>
                  <div style={{fontSize:10,color:"#94A3B8",fontWeight:600}}>{daysFull[i]}</div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Today's schedule */}
        <Card style={{gridColumn:isMobile?"1/-1":"1/-1"}}>
          <SectionHead title={`Today — ${now.toLocaleDateString("en",{weekday:"long",day:"numeric",month:"long"})}`} />
          {todaySch.length===0?<div style={{textAlign:"center",color:"#94A3B8",fontSize:14,padding:"20px 0"}}>No medications scheduled today</div>:
          <div style={{display:"flex",flexDirection:"column",gap:8}}>
            {todaySch.flatMap((s,si)=>s.dispenseTimes.map((t,ti) => {
              const status=statusFor(s,t);
              const col=MED_COLORS[si%MED_COLORS.length];
              const statusCfg={taken:{bg:"#D1FAE5",color:"#059669",label:"Taken",icon:"✓"},missed:{bg:"#FEE2E2",color:"#EF4444",label:"Missed",icon:"✕"},pending:{bg:"#EFF6FF",color:"#1D6FE8",label:"Pending",icon:"○"}};
              const sc=statusCfg[status];
              return (
                <div key={`${si}-${ti}`} style={{display:"flex",alignItems:"center",gap:12,padding:"12px 14px",background:"#F8FAFD",borderRadius:10,border:"1px solid #E8EEF8"}}>
                  <div style={{width:38,height:38,borderRadius:10,background:col+"18",border:`1px solid ${col}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>💊</div>
                  <div style={{flex:1}}>
                    <div style={{fontSize:14,fontWeight:700,color:"#0F172A"}}>{s.medicationName}</div>
                    <div style={{fontSize:12,color:"#64748B",marginTop:2}}>Slot {slotLabel(si)} · {s.dosage}</div>
                  </div>
                  <div style={{textAlign:"right"}}>
                    <div style={{fontSize:15,fontWeight:700,color:"#0F172A",fontFamily:"'DM Mono',monospace"}}>{t}</div>
                    <div style={{marginTop:4}}><Badge color={sc.color} bg={sc.bg}>{sc.icon} {sc.label}</Badge></div>
                  </div>
                </div>
              );
            }))}
          </div>}
        </Card>
      </div>
    </div>
  );
}

/* ─── Register ──────────────────────────────────────────────────────────────── */
function RegisterScreen({onRegistered,isMobile}) {
  const [step,setStep]=useState(0);
  const [name,setName]=useState("");
  const [phone,setPhone]=useState("");
  const [selSlot,setSelSlot]=useState(-1);
  const [slots,setSlots]=useState(MOCK.slots);
  const [createdUser,setCreatedUser]=useState(null);
  const [captures,setCaptures]=useState(0);
  const [enrolling,setEnrolling]=useState(false);
  const [enrolled,setEnrolled]=useState(false);
  const [saving,setSaving]=useState(false);
  const iRef=useRef(null);

  useEffect(()=>{api.getSlots().then(setSlots).catch(()=>setSlots(MOCK.slots));},[]);
  useEffect(()=>()=>clearInterval(iRef.current),[]);

  const startMockEnrol=()=>{
    setEnrolling(true);let c=0;
    iRef.current=setInterval(()=>{c++;setCaptures(c);if(c>=10){clearInterval(iRef.current);setEnrolled(true);setEnrolling(false);}},700);
  };

  const goSlot=()=>{if(name.trim()&&phone.trim())setStep(1);};
  const goEnrol=async()=>{
    if(selSlot<0)return;setSaving(true);
    try{const u=await api.createUser({full_name:name,caregiver_phone:phone,compartment_index:selSlot,enrolment_status:0});setCreatedUser(u);}
    catch{setCreatedUser({...MOCK.user,fullName:name,caregiverPhone:phone,compartmentIndex:selSlot});}
    setSaving(false);setStep(2);startMockEnrol();
  };
  const finish=()=>{
    clearInterval(iRef.current);
    setStep(0);setName("");setPhone("");setSelSlot(-1);setCaptures(0);setEnrolled(false);
    if(onRegistered)onRegistered({id:Date.now(),fullName:name,caregiverPhone:phone,compartmentIndex:selSlot,enrolled:true});
  };

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",overflowY:"auto",height:"100%",boxSizing:"border-box",maxWidth:isMobile?"100%":"640px",margin:"0 auto"}}>
      <h1 style={{fontSize:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>User registration</h1>
      <p style={{fontSize:14,color:"#64748B",margin:"0 0 28px"}}>Register a new patient and enrol their face for pill dispense verification.</p>
      <Stepper steps={["Personal details","Slot assignment","Face enrolment"]} current={step} />

      {step===0&&(
        <Card>
          <h3 style={{fontSize:16,fontWeight:700,color:"#0F172A",margin:"0 0 20px"}}>Personal details</h3>
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <div><FieldLabel>Full name</FieldLabel><TextInput value={name} onChange={setName} placeholder="e.g. Maxwell Donkor" /></div>
            <div><FieldLabel>Caregiver phone</FieldLabel><TextInput value={phone} onChange={setPhone} placeholder="+233 24 000 0000" type="tel" /></div>
            <PrimaryBtn onClick={goSlot} disabled={!name.trim()||!phone.trim()} icon="→">Continue to slot assignment</PrimaryBtn>
          </div>
        </Card>
      )}

      {step===1&&(
        <Card>
          <h3 style={{fontSize:16,fontWeight:700,color:"#0F172A",margin:"0 0 6px"}}>Assign carousel slot</h3>
          <p style={{fontSize:13,color:"#64748B",margin:"0 0 16px"}}>Select a free compartment in the PillSafe carousel for this patient.</p>
          <SlotGrid occupancy={slots} selected={selSlot} onSelect={setSelSlot} />
          <div style={{marginTop:20,display:"flex",gap:10}}>
            <PrimaryBtn onClick={()=>setStep(0)} variant="ghost" icon="←">Back</PrimaryBtn>
            <PrimaryBtn onClick={goEnrol} disabled={selSlot<0} loading={saving} icon="→">Continue to enrolment</PrimaryBtn>
          </div>
        </Card>
      )}

      {step===2&&(
        <Card>
          <h3 style={{fontSize:16,fontWeight:700,color:"#0F172A",margin:"0 0 6px"}}>Face enrolment</h3>
          <p style={{fontSize:13,color:"#64748B",margin:"0 0 20px"}}>The PillSafe device camera is capturing facial embeddings using MobileFaceNet.</p>
          <div style={{background:"#F8FAFD",border:"1.5px solid #E2E8F0",borderRadius:12,padding:24,display:"flex",flexDirection:"column",alignItems:"center",gap:16,marginBottom:20}}>
            <div style={{width:96,height:96,borderRadius:"50%",background:enrolled?"#D1FAE5":"#EFF6FF",border:`2px solid ${enrolled?"#10B981":"#1D6FE8"}`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:40,position:"relative",overflow:"hidden"}}>
              {enrolled?"✓":"📷"}
              {enrolling&&!enrolled&&<div style={{position:"absolute",left:0,right:0,height:2,background:"#1D6FE8",animation:"scanDown 1.5s ease-in-out infinite"}} />}
            </div>
            <div style={{fontSize:14,fontWeight:600,color:enrolled?"#059669":"#1D6FE8"}}>{enrolled?"Enrolment complete!":enrolling?"Capturing samples...":"Waiting to start"}</div>
            <div style={{width:"100%"}}>
              <div style={{display:"flex",justifyContent:"space-between",fontSize:12,color:"#64748B",marginBottom:6,fontWeight:600}}>
                <span>Progress</span><span style={{color:"#1D6FE8",fontFamily:"'DM Mono',monospace"}}>{captures} / 10 samples</span>
              </div>
              <div style={{background:"#E2E8F0",borderRadius:6,height:6,overflow:"hidden"}}>
                <div style={{height:"100%",width:`${captures*10}%`,background:"linear-gradient(90deg,#1D6FE8,#3B82F6)",borderRadius:6,transition:"width .3s"}} />
              </div>
            </div>
          </div>
          <Card style={{background:"#F8FAFD",border:"1px solid #E2E8F0",padding:"14px 16px",marginBottom:20}}>
            <div style={{fontSize:11,fontWeight:700,color:"#94A3B8",textTransform:"uppercase",letterSpacing:.8,marginBottom:8}}>Embedding log</div>
            <div style={{display:"flex",flexDirection:"column",gap:4,maxHeight:140,overflowY:"auto"}}>
              {Array.from({length:captures},(_,i)=>(
                <div key={i} style={{display:"flex",alignItems:"center",gap:8,fontSize:12,color:"#059669",fontFamily:"'DM Mono',monospace"}}>
                  <span style={{color:"#10B981"}}>✓</span> sample_{pad(i+1)}.emb — dist: {(0.18+i*0.01).toFixed(3)}
                </div>
              ))}
              {captures<10&&<div style={{display:"flex",alignItems:"center",gap:8,fontSize:12,color:"#64748B"}}><Spinner size={12} color="#64748B" /> Capturing sample {captures+1}...</div>}
            </div>
          </Card>
          <div style={{display:"flex",gap:10}}>
            <PrimaryBtn onClick={()=>{clearInterval(iRef.current);setStep(1);setCaptures(0);setEnrolled(false);}} variant="ghost" icon="←">Back</PrimaryBtn>
            <PrimaryBtn onClick={finish} disabled={!enrolled} icon="✓">Complete registration</PrimaryBtn>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ─── Verify ────────────────────────────────────────────────────────────────── */
function VerifyScreen({isMobile}) {
  const [vState,setVState]=useState("idle");
  const [completedSteps,setCompletedSteps]=useState(0);
  const [result,setResult]=useState(null);
  const STEPS=[{p:"Scanning face...",d:"Face matched · Euclidean dist: 0.21"},{p:"Matching embeddings...",d:"Embedding verified against stored model"},{p:"Rotating carousel...",d:"Carousel at 120° · Slot B aligned"},{p:"Waiting for pickup...",d:"Pickup confirmed — dose logged"}];

  const begin=async()=>{
    setVState("scanning");setCompletedSteps(0);
    let res;
    try{res=await api.verify();}catch{res={success:true,user_name:"Maxwell Donkor",distance:0.21};}
    if(!res.success){setVState("failed");return;}
    setResult(res);
    for(let i=0;i<STEPS.length;i++){await new Promise(r=>setTimeout(r,1100));setCompletedSteps(i+1);}
    setVState("success");
  };
  const reset=()=>{setVState("idle");setCompletedSteps(0);setResult(null);};

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",height:"100%",boxSizing:"border-box",display:"flex",flexDirection:"column",maxWidth:isMobile?"100%":"560px",margin:"0 auto"}}>
      <h1 style={{fontSize:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>Facial verification</h1>
      <p style={{fontSize:14,color:"#64748B",margin:"0 0 28px"}}>Authenticate patient identity before dispensing medication.</p>

      {vState==="idle"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16,flex:1}}>
          <Card style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:20,minHeight:280}}>
            <div style={{width:140,height:140,borderRadius:"50%",background:"#EFF6FF",border:"3px solid #BFDBFE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:60,position:"relative"}}>
              🪪
              <div style={{position:"absolute",inset:-8,borderRadius:"50%",border:"1.5px dashed #93C5FD",animation:"rotateSlow 8s linear infinite"}} />
            </div>
            <div style={{textAlign:"center"}}>
              <div style={{fontSize:17,fontWeight:700,color:"#0F172A"}}>Ready to verify</div>
              <div style={{fontSize:13,color:"#64748B",marginTop:4,lineHeight:1.5}}>Look directly at the PillSafe device camera<br/>and press the button below</div>
            </div>
          </Card>
          <PrimaryBtn onClick={begin} icon="⊙">Begin facial verification</PrimaryBtn>
          <PrimaryBtn variant="ghost" icon="⏱">Waiting for scheduled dose time</PrimaryBtn>
        </div>
      )}

      {vState==="scanning"&&(
        <Card style={{flex:1,display:"flex",flexDirection:"column",gap:20}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"center",padding:"24px 0"}}>
            <div style={{width:120,height:120,borderRadius:"50%",background:"#EFF6FF",border:"3px solid #1D6FE8",display:"flex",alignItems:"center",justifyContent:"center",fontSize:50,position:"relative",overflow:"hidden"}}>
              🪪
              <div style={{position:"absolute",left:0,right:0,height:3,background:"linear-gradient(90deg,transparent,#1D6FE8,transparent)",animation:"scanDown 1.8s ease-in-out infinite"}} />
            </div>
          </div>
          <div style={{textAlign:"center",marginBottom:8}}>
            <div style={{fontSize:16,fontWeight:700,color:"#1D6FE8"}}>Verifying identity...</div>
            <div style={{fontSize:13,color:"#64748B",marginTop:4}}>Please hold still and face the camera</div>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:10}}>
            {STEPS.map((s,i)=>{
              const done=i<completedSteps,active=i===completedSteps;
              return (
                <div key={i} style={{display:"flex",alignItems:"center",gap:12,padding:"10px 14px",background:done?"#F0FDF4":active?"#EFF6FF":"#F8FAFD",borderRadius:10,border:`1px solid ${done?"#BBF7D0":active?"#BFDBFE":"#E2E8F0"}`}}>
                  <div style={{width:24,height:24,borderRadius:"50%",background:done?"#10B981":active?"#1D6FE8":"#E2E8F0",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                    {done?<span style={{color:"#fff",fontSize:12}}>✓</span>:active?<Spinner size={12} color="#fff"/>:<span style={{fontSize:11,color:"#94A3B8"}}>{i+1}</span>}
                  </div>
                  <div style={{fontSize:13,fontWeight:500,color:done?"#059669":active?"#1D6FE8":"#94A3B8"}}>{done?s.d:s.p}</div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {vState==="success"&&(
        <Card style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:18}}>
          <div style={{width:100,height:100,borderRadius:"50%",background:"#D1FAE5",border:"3px solid #10B981",display:"flex",alignItems:"center",justifyContent:"center",fontSize:44,color:"#059669"}}>✓</div>
          <div style={{textAlign:"center"}}>
            <div style={{fontSize:20,fontWeight:800,color:"#059669"}}>Identity confirmed</div>
            {result?.user_name&&<div style={{fontSize:14,color:"#64748B",marginTop:4}}>Welcome, {result.user_name}</div>}
            {result?.distance&&<div style={{fontSize:12,color:"#94A3B8",marginTop:4,fontFamily:"'DM Mono',monospace"}}>distance: {result.distance.toFixed(2)}</div>}
          </div>
          <Card style={{width:"100%",background:"#F8FAFD",border:"1px solid #E2E8F0",padding:"14px 16px"}}>
            {STEPS.map((s,i)=>(
              <div key={i} style={{display:"flex",alignItems:"center",gap:10,fontSize:13,color:"#059669",marginBottom:i<3?8:0,fontWeight:500}}>
                <span style={{color:"#10B981",fontSize:14}}>✓</span>{s.d}
              </div>
            ))}
          </Card>
          <PrimaryBtn onClick={reset} icon="↺">Verify another patient</PrimaryBtn>
        </Card>
      )}

      {vState==="failed"&&(
        <Card style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:18}}>
          <div style={{width:100,height:100,borderRadius:"50%",background:"#FEE2E2",border:"3px solid #EF4444",display:"flex",alignItems:"center",justifyContent:"center",fontSize:44}}>✕</div>
          <div style={{textAlign:"center"}}>
            <div style={{fontSize:20,fontWeight:800,color:"#EF4444"}}>Verification failed</div>
            <div style={{fontSize:14,color:"#64748B",marginTop:6,lineHeight:1.6}}>Face not recognised. Dispense blocked.<br/>Caregiver has been notified via SMS.</div>
          </div>
          <PrimaryBtn onClick={reset} variant="danger" icon="↺">Try again</PrimaryBtn>
        </Card>
      )}
    </div>
  );
}

/* ─── Schedule ──────────────────────────────────────────────────────────────── */
function ScheduleScreen({user,schedules,onAdd,onDelete,isMobile}) {
  const [showAdd,setShowAdd]=useState(false);
  const [amName,setAmName]=useState("");
  const [amDose,setAmDose]=useState("");
  const [amSlot,setAmSlot]=useState(-1);
  const [amDays,setAmDays]=useState([1,1,1,1,1,1,1]);
  const [amTimes,setAmTimes]=useState(["08:00"]);
  const [amGrace,setAmGrace]=useState("15");
  const [slots,setSlots]=useState(MOCK.slots);
  const [saving,setSaving]=useState(false);

  useEffect(()=>{api.getSlots().then(setSlots).catch(()=>{});},[]);

  const DAYS=["Mo","Tu","We","Th","Fr","Sa","Su"];
  const grouped={Morning:[],Afternoon:[],Evening:[]};
  schedules.forEach((s,si)=>{s.dispenseTimes.forEach(t=>{const h=parseInt(t);grouped[h<12?"Morning":h<17?"Afternoon":"Evening"].push({s,t,si});});});
  Object.values(grouped).forEach(g=>g.sort((a,b)=>a.t.localeCompare(b.t)));

  const saveMed=async()=>{
    if(!amName.trim()||!amDose.trim()||amSlot<0)return;setSaving(true);
    const payload={user_id:user.id,medication_name:amName,dosage:amDose,dispense_times:amTimes,repeat_days:amDays,grace_period_minutes:parseInt(amGrace)||15};
    try{const s=await api.createSchedule(payload);onAdd(s);}
    catch{onAdd({...payload,id:Date.now(),medicationName:amName,dispenseTimes:amTimes});}
    setSaving(false);setShowAdd(false);setAmName("");setAmDose("");setAmSlot(-1);setAmTimes(["08:00"]);
  };

  if(showAdd) return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",overflowY:"auto",height:"100%",boxSizing:"border-box",maxWidth:isMobile?"100%":"580px",margin:"0 auto"}}>
      <button onClick={()=>setShowAdd(false)} style={{background:"none",border:"none",color:"#64748B",cursor:"pointer",display:"flex",alignItems:"center",gap:6,fontSize:13,fontWeight:600,padding:0,marginBottom:20,fontFamily:"inherit"}}>← Back to schedule</button>
      <h1 style={{fontSize:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>Add medication</h1>
      <p style={{fontSize:14,color:"#64748B",margin:"0 0 24px"}}>Add a new medication to the dispense schedule.</p>
      <Card style={{display:"flex",flexDirection:"column",gap:18}}>
        <div><FieldLabel>Medication name</FieldLabel><TextInput value={amName} onChange={setAmName} placeholder="e.g. Metoprolol 25mg"/></div>
        <div><FieldLabel>Dosage</FieldLabel><TextInput value={amDose} onChange={setAmDose} placeholder="e.g. 1 tablet"/></div>
        <div><FieldLabel>Carousel slot</FieldLabel><SlotGrid occupancy={slots} selected={amSlot} onSelect={setAmSlot}/></div>
        <div>
          <FieldLabel>Repeat days</FieldLabel>
          <div style={{display:"flex",gap:8}}>
            {DAYS.map((d,i)=>(
              <div key={i} onClick={()=>{const n=[...amDays];n[i]=n[i]?0:1;setAmDays(n);}}
                style={{width:38,height:38,borderRadius:10,display:"flex",alignItems:"center",justifyContent:"center",fontSize:12,fontWeight:700,cursor:"pointer",background:amDays[i]?"#1D6FE8":"#F1F5F9",color:amDays[i]?"#fff":"#94A3B8",border:`1.5px solid ${amDays[i]?"#1D6FE8":"#E2E8F0"}`,transition:"all .15s"}}>{d}</div>
            ))}
          </div>
        </div>
        <div>
          <FieldLabel>Dispense times</FieldLabel>
          {amTimes.map((t,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
              <input type="time" value={t} onChange={e=>{const n=[...amTimes];n[i]=e.target.value;setAmTimes(n);}}
                style={{flex:1,background:"#F8FAFD",border:"1.5px solid #E2E8F0",borderRadius:10,padding:"10px 14px",fontSize:14,color:"#0F172A",fontFamily:"'DM Mono',monospace",outline:"none"}}/>
              {amTimes.length>1&&<button onClick={()=>setAmTimes(amTimes.filter((_,j)=>j!==i))} style={{background:"none",border:"none",color:"#EF4444",cursor:"pointer",fontSize:18,padding:"4px 8px"}}>×</button>}
            </div>
          ))}
          <button onClick={()=>setAmTimes([...amTimes,"12:00"])} style={{background:"none",border:"none",color:"#1D6FE8",cursor:"pointer",fontSize:13,fontWeight:600,padding:0,fontFamily:"inherit",display:"flex",alignItems:"center",gap:6}}>+ Add another time</button>
        </div>
        <div><FieldLabel>Grace period (minutes)</FieldLabel><TextInput value={amGrace} onChange={setAmGrace} type="number"/></div>
        <div style={{display:"flex",gap:10,marginTop:4}}>
          <PrimaryBtn onClick={()=>setShowAdd(false)} variant="ghost">Cancel</PrimaryBtn>
          <PrimaryBtn onClick={saveMed} disabled={!amName.trim()||!amDose.trim()||amSlot<0} loading={saving} icon="✓">Save medication</PrimaryBtn>
        </div>
      </Card>
    </div>
  );

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",overflowY:"auto",height:"100%",boxSizing:"border-box",maxWidth:isMobile?"100%":"1000px",margin:"0 auto"}}>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:28,flexDirection:isMobile?"column":"row",gap:isMobile?14:0}}>
        <div>
          <h1 style={{fontSize:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>Medication schedule</h1>
          <p style={{fontSize:14,color:"#64748B",margin:0}}>{schedules.length} medication{schedules.length!==1?"s":""} configured</p>
        </div>
        <button onClick={()=>setShowAdd(true)} style={{background:"#1D6FE8",color:"#fff",border:"none",borderRadius:10,padding:"10px 18px",fontSize:14,fontWeight:600,cursor:"pointer",fontFamily:"inherit",display:"flex",alignItems:"center",gap:8,boxShadow:"0 2px 8px #1D6FE830"}}>+ Add medication</button>
      </div>
      {schedules.length===0?(
        <Card style={{textAlign:"center",padding:"60px 40px"}}>
          <div style={{fontSize:48,marginBottom:16}}>💊</div>
          <div style={{fontSize:16,fontWeight:700,color:"#0F172A",marginBottom:8}}>No medications yet</div>
          <div style={{fontSize:14,color:"#64748B",marginBottom:24}}>Add your first medication to get started</div>
          <div style={{maxWidth:200,margin:"0 auto"}}><PrimaryBtn onClick={()=>setShowAdd(true)} icon="+">Add medication</PrimaryBtn></div>
        </Card>
      ):(
        <div style={{display:"flex",flexDirection:"column",gap:12}}>
          {Object.entries(grouped).map(([bucket,items])=>items.length>0&&(
            <div key={bucket}>
              <div style={{fontSize:11,fontWeight:800,color:"#94A3B8",textTransform:"uppercase",letterSpacing:1,marginBottom:10,display:"flex",alignItems:"center",gap:10}}>
                {bucket}<div style={{flex:1,height:1,background:"#E2E8F0"}}/>
              </div>
              <div style={{display:"flex",flexDirection:"column",gap:8}}>
                {items.map(({s,t,si})=>{
                  const col=MED_COLORS[si%MED_COLORS.length];
                  return (
                    <Card key={`${s.id}-${t}`} style={{display:"flex",alignItems:"center",gap:14,padding:"14px 18px"}}>
                      <div style={{width:44,height:44,borderRadius:12,background:col+"18",border:`1px solid ${col}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>💊</div>
                      <div style={{flex:1}}>
                        <div style={{fontSize:15,fontWeight:700,color:"#0F172A"}}>{s.medicationName}</div>
                        <div style={{fontSize:13,color:"#64748B",marginTop:3}}>{s.dosage} · {s.repeatDays.every(Boolean)?"Daily":"Custom"}</div>
                        <div style={{marginTop:5}}><Badge color="#1D6FE8">SLOT-{slotLabel(si)} · {t}</Badge></div>
                      </div>
                      <button onClick={()=>onDelete(s.id)} style={{background:"#FEE2E2",border:"none",borderRadius:8,width:32,height:32,display:"flex",alignItems:"center",justifyContent:"center",cursor:"pointer",color:"#EF4444",fontSize:16}}>×</button>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Monitor ───────────────────────────────────────────────────────────────── */
function MonitorScreen({user,adherence,device,isMobile}) {
  const taken=adherence.filter(l=>l.status==="taken").length;
  const missed=adherence.filter(l=>l.status==="missed").length;
  const failed=adherence.filter(l=>l.status==="failed").length;
  const rate=adherence.length?Math.round(taken/adherence.length*100):0;

  const devRows=[
    ["Connection",device.connected,device.connected?"Hotspot online":"Offline"],
    ["RTC time",null,device.rtcTime],
    ["GSM signal",null,device.gsmSignal],
    ["Slots loaded",device.slotsLoaded>=3,`${device.slotsLoaded}/6 occupied`],
    ["Face model",null,device.faceModel],
    ["Last dispense",null,device.lastDispense],
  ];

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",overflowY:"auto",height:"100%",boxSizing:"border-box",maxWidth:isMobile?"100%":"1400px",margin:"0 auto"}}>
      <h1 style={{fontSize:isMobile?22:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>Caregiver monitor</h1>
      <p style={{fontSize:14,color:"#64748B",margin:"0 0 28px"}}>Real-time adherence tracking and device telemetry.</p>

      <div style={{display:"grid",gridTemplateColumns:isMobile?"repeat(2,1fr)":"repeat(4,1fr)",gap:14,marginBottom:28}}>
        <StatCard icon="📊" value={`${rate}%`} label="Adherence rate" color="#1D6FE8" />
        <StatCard icon="✅" value={taken} label="Doses taken" color="#10B981" />
        <StatCard icon="⚠️" value={missed} label="Doses missed" color="#F59E0B" />
        <StatCard icon="🚫" value={failed} label="Failed verifications" color="#EF4444" />
      </div>

      <div style={{display:"grid",gridTemplateColumns:isMobile?"1fr":"1fr 1fr",gap:20}}>
        <Card>
          <SectionHead title="Caregiver contact" />
          <div style={{display:"flex",alignItems:"center",gap:14,marginBottom:16}}>
            <div style={{width:44,height:44,borderRadius:"50%",background:"#EFF6FF",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}>👤</div>
            <div>
              <div style={{fontSize:15,fontWeight:700,color:"#0F172A"}}>Primary Caregiver</div>
              <div style={{fontSize:13,color:"#64748B",marginTop:2}}>{user.caregiverPhone}</div>
            </div>
            <div style={{marginLeft:"auto"}}><Badge color="#10B981">Active</Badge></div>
          </div>
          <div style={{background:"#F8FAFD",border:"1px solid #E2E8F0",borderRadius:10,padding:"12px 14px"}}>
            <div style={{fontSize:11,fontWeight:700,color:"#94A3B8",textTransform:"uppercase",letterSpacing:.8,marginBottom:10}}>SMS alert log</div>
            <div style={{display:"flex",flexDirection:"column",gap:7}}>
              {[...adherence.filter(l=>l.status==="taken").slice(0,2).map(l=>({ok:true,txt:`Dose taken — ${l.medicationName}`})),
                ...adherence.filter(l=>l.status==="missed").slice(0,2).map(l=>({ok:false,txt:`Missed — ${l.medicationName}`}))].map((e,i)=>(
                <div key={i} style={{display:"flex",alignItems:"center",gap:8,fontSize:13}}>
                  <div style={{width:20,height:20,borderRadius:"50%",background:e.ok?"#D1FAE5":"#FEE2E2",display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,flexShrink:0,color:e.ok?"#059669":"#EF4444"}}>{e.ok?"✓":"✕"}</div>
                  <span style={{color:"#374151"}}>{e.txt}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <SectionHead title="Device telemetry" action={<Badge color={device.connected?"#10B981":"#EF4444"} bg={device.connected?"#D1FAE5":"#FEE2E2"}>{device.connected?"● Online":"● Offline"}</Badge>} />
          <div style={{display:"flex",flexDirection:"column",gap:0}}>
            {devRows.map(([k,isOk,v],i)=>(
              <div key={k} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"10px 0",borderBottom:i<devRows.length-1?"1px solid #F1F5F9":"none"}}>
                <div style={{fontSize:13,color:"#64748B",fontWeight:500}}>{k}</div>
                <div style={{fontSize:13,fontWeight:600,color:isOk===true?"#059669":isOk===false?"#EF4444":"#0F172A",fontFamily:k==="RTC time"||k==="Last dispense"?"'DM Mono',monospace":"inherit"}}>{v}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ─── Notifications ─────────────────────────────────────────────────────────── */
function NotificationsScreen({user,notifications,onMarkRead,isMobile}) {
  const [filter,setFilter]=useState(null);
  const FILTERS=[[null,"All"],[" dispensed","Dispensed"],["missed","Missed"],["failedVerification","Verification"],["deviceAlert","Device"]];
  const ICONCFG={dispensed:{icon:"✓",bg:"#D1FAE5",color:"#059669"},missed:{icon:"⚠",bg:"#FEE2E2",color:"#EF4444"},failedVerification:{icon:"🪪",bg:"#FEF3C7",color:"#D97706"},deviceAlert:{icon:"⚡",bg:"#EFF6FF",color:"#1D6FE8"}};
  const filtered=filter?notifications.filter(n=>n.type===filter.trim()):notifications;
  const unread=notifications.filter(n=>!n.read).length;

  return (
    <div style={{padding:isMobile?"16px 14px":"32px 36px",height:"100%",boxSizing:"border-box",display:"flex",flexDirection:"column",maxWidth:isMobile?"100%":"1000px",margin:"0 auto"}}>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:20,flexDirection:isMobile?"column":"row",gap:isMobile?12:0}}>
        <div>
          <h1 style={{fontSize:26,fontWeight:800,color:"#0F172A",margin:"0 0 6px",letterSpacing:-.5}}>Alerts & notifications</h1>
          <p style={{fontSize:14,color:"#64748B",margin:0}}>{unread} unread notification{unread!==1?"s":""}</p>
        </div>
        {unread>0&&<button onClick={onMarkRead} style={{background:"none",border:"1.5px solid #E2E8F0",borderRadius:8,padding:"8px 14px",fontSize:13,fontWeight:600,color:"#64748B",cursor:"pointer",fontFamily:"inherit"}}>Mark all read</button>}
      </div>
      <div style={{display:"flex",gap:8,marginBottom:20,flexWrap:"wrap"}}>
        {FILTERS.map(([f,lbl])=>(
          <button key={String(f)} onClick={()=>setFilter(f)}
            style={{padding:"6px 14px",borderRadius:20,border:`1.5px solid ${filter===f?"#1D6FE8":"#E2E8F0"}`,background:filter===f?"#EFF6FF":"#fff",color:filter===f?"#1D6FE8":"#64748B",fontSize:13,fontWeight:600,cursor:"pointer",fontFamily:"inherit",transition:"all .15s"}}>{lbl}</button>
        ))}
      </div>
      <div style={{overflowY:"auto",flex:1}}>
        {filtered.length===0?(
          <Card style={{textAlign:"center",padding:"60px 40px"}}>
            <div style={{fontSize:40,marginBottom:12}}>🔔</div>
            <div style={{fontSize:15,fontWeight:700,color:"#0F172A"}}>No notifications</div>
          </Card>
        ):(
          <div style={{display:"flex",flexDirection:"column",gap:10}}>
            {filtered.map(n=>{
              const cfg=ICONCFG[n.type]||{icon:"•",bg:"#F1F5F9",color:"#64748B"};
              return (
                <Card key={n.id} style={{display:"flex",gap:14,padding:"16px 18px",border:`1.5px solid ${n.read?"#E8EEF8":"#BFDBFE"}`,background:n.read?"#fff":"#F0F6FF"}}>
                  <div style={{width:40,height:40,borderRadius:12,background:cfg.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0,color:cfg.color}}>{cfg.icon}</div>
                  <div style={{flex:1}}>
                    <div style={{fontSize:14,fontWeight:700,color:"#0F172A"}}>{n.title}</div>
                    <div style={{fontSize:13,color:"#64748B",marginTop:3,lineHeight:1.5}}>{n.detail}</div>
                    <div style={{fontSize:11,color:"#94A3B8",marginTop:6,fontFamily:"'DM Mono',monospace",fontWeight:500}}>{fmtRelTime(n.timestamp)}</div>
                  </div>
                  {!n.read&&<div style={{width:8,height:8,borderRadius:"50%",background:"#1D6FE8",marginTop:4,flexShrink:0}} />}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════════
   ROOT APP
═══════════════════════════════════════════════════════════════════════════════ */
export default function App() {
  const [user,setUser]=useState(null);
  const [loading,setLoading]=useState(true);
  const [offline,setOffline]=useState(false);
  const [loginEmail,setLoginEmail]=useState("");
  const [loginPassword,setLoginPassword]=useState("");
  const [authError,setAuthError]=useState("");
  const [tab,setTab]=useState("home");
  const [schedules,setSchedules]=useState([]);
  const [adherence,setAdherence]=useState([]);
  const [notifications,setNotifications]=useState([]);
  const [device,setDevice]=useState(MOCK.device);
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false);
  const isMobile = useIsMobile();

  const loadAppData = async (activeUser) => {
    try {
      const [s,a,n,d] = await Promise.all([
        api.getSchedules(activeUser.id),
        api.getAdherence(activeUser.id),
        api.getNotifications(activeUser.id),
        api.getDeviceStatus(),
      ]);
      setSchedules(s);
      setAdherence(a);
      setNotifications(n);
      setDevice(d);
      setOffline(false);
    } catch {
      setSchedules(MOCK.schedules);
      setAdherence(MOCK.adherence);
      setNotifications(MOCK.notifications);
      setDevice(MOCK.device);
      setOffline(true);
    }
  };

  useEffect(()=>{
    const init=async()=>{
      let storedUser = null;
      try { storedUser = JSON.parse(window.localStorage.getItem('pillSafeUser')); } catch {}
      if (storedUser) {
        setUser(storedUser);
        await loadAppData(storedUser);
      }
      setLoading(false);
    };
    init();
  },[]);

  const handleLogin = async () => {
    setAuthError("");
    setLoading(true);
    try {
      const logged = await api.login({ email: loginEmail, password: loginPassword });
      setUser(logged);
      window.localStorage.setItem('pillSafeUser', JSON.stringify(logged));
      await loadAppData(logged);
      setTab('home');
    } catch (error) {
      setAuthError(error?.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setAuthError("");
    setLoading(true);
    try {
      const demoUser = MOCK.user;
      setUser(demoUser);
      window.localStorage.setItem('pillSafeUser', JSON.stringify(demoUser));
      await loadAppData(demoUser);
      setTab('home');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    window.localStorage.removeItem('pillSafeUser');
    setUser(null);
    setTab('home');
    setSchedules([]);
    setAdherence([]);
    setNotifications([]);
    setDevice(MOCK.device);
  };

  useEffect(() => {
    if (isMobile) setSidebarCollapsed(true);
  }, [isMobile]);

  const unread=notifications.filter(n=>!n.read).length;

  const NAV=[
    {id:"home",icon:"🏠",label:"Dashboard"},
    {id:"register",icon:"👤",label:"Register patient"},
    {id:"verify",icon:"🪪",label:"Verify & dispense"},
    {id:"schedule",icon:"📅",label:"Schedule"},
    {id:"monitor",icon:"📊",label:"Monitor"},
    {id:"notifications",icon:"🔔",label:"Alerts",badge:unread},
  ];

  const mainUser=user||MOCK.user;

  if(loading) return (
    <div style={{height:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#F0F5FF",fontFamily:"'DM Sans','Inter',sans-serif"}}>
      <div style={{textAlign:"center",display:"flex",flexDirection:"column",alignItems:"center",gap:20}}>
        <div style={{width:72,height:72,borderRadius:20,background:"#1D6FE8",display:"flex",alignItems:"center",justifyContent:"center",fontSize:34,boxShadow:"0 8px 24px #1D6FE840"}}>💊</div>
        <div style={{fontSize:24,fontWeight:800,color:"#0F172A",letterSpacing:-.5}}>PillSafe</div>
        <Spinner size={24} />
      </div>
    </div>
  );

  if (!loading && !user) return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#F0F5FF;font-family:'DM Sans',sans-serif;min-height:100vh}
      `}</style>
      <LoginScreen
        email={loginEmail}
        setEmail={setLoginEmail}
        password={loginPassword}
        setPassword={setLoginPassword}
        onLogin={handleLogin}
        onDemo={handleDemo}
        error={authError}
        loading={loading}
      />
    </>
  );

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#F0F5FF;font-family:'DM Sans',sans-serif;min-height:100vh}
        @keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
        @keyframes scanDown{0%,100%{top:10%;opacity:.4}50%{top:85%;opacity:1}}
        @keyframes rotateSlow{from{transform:rotate(0)}to{transform:rotate(360deg)}}
        @keyframes fadeSlide{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:translateX(0)}}
        input[type=time]::-webkit-calendar-picker-indicator{filter:invert(.4)}
        input::placeholder{color:#CBD5E1}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:#E2E8F0;border-radius:4px}
      `}</style>

      <div style={{display:"flex",height:"100vh",overflow:"hidden",position:"relative"}}>
        {isMobile && !sidebarCollapsed && (
          <div onClick={()=>setSidebarCollapsed(true)} style={{position:"fixed",inset:0,background:"rgba(15,23,42,.22)",zIndex:15}} />
        )}

        {/* ── Sidebar ─────────────────────────────────────────────────────── */}
        <aside style={{
          width:isMobile?240:(sidebarCollapsed?72:240),background:"#fff",borderRight:"1px solid #E2EEF8",
          display:"flex",flexDirection:"column",flexShrink:0,transition:"transform .25s ease,width .25s ease",
          boxShadow:isMobile?"4px 0 20px rgba(15,23,42,.12)":"2px 0 12px #0F172A08",position:isMobile?"fixed":"relative",top:0,left:0,bottom:isMobile?0:"auto",zIndex:20,
          transform:isMobile && sidebarCollapsed ? "translateX(-100%)" : "none",
        }}>
          {/* Logo */}
          <div style={{padding:sidebarCollapsed?"20px 0":"24px 20px",display:"flex",alignItems:"center",gap:12,borderBottom:"1px solid #F1F5F9",justifyContent:sidebarCollapsed?"center":"flex-start"}}>
            <div style={{width:38,height:38,borderRadius:11,background:"#1D6FE8",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0,boxShadow:"0 4px 12px #1D6FE830"}}>💊</div>
            {!sidebarCollapsed&&<div><div style={{fontSize:16,fontWeight:800,color:"#0F172A",letterSpacing:-.3}}>PillSafe</div><div style={{fontSize:11,color:"#94A3B8",fontWeight:500}}>Smart dispenser</div></div>}
          </div>

          {/* Offline badge */}
          {offline&&!sidebarCollapsed&&(
            <div style={{margin:"10px 14px 0",background:"#FFFBEB",border:"1px solid #FDE68A",borderRadius:8,padding:"6px 10px",fontSize:11,fontWeight:600,color:"#D97706",textAlign:"center"}}>⚡ Demo mode</div>
          )}

          {/* Nav items */}
          <nav style={{flex:1,padding:"12px 10px",display:"flex",flexDirection:"column",gap:2}}>
            {NAV.map(({id,icon,label,badge})=>{
              const active=tab===id||(tab==="add-med"&&id==="schedule");
              return (
                <button key={id} onClick={()=>setTab(id)}
                  style={{
                    display:"flex",alignItems:"center",gap:12,
                    padding:sidebarCollapsed?"10px 0":"10px 12px",
                    borderRadius:10,border:"none",cursor:"pointer",fontFamily:"inherit",
                    background:active?"#EFF6FF":"transparent",
                    color:active?"#1D6FE8":"#64748B",
                    fontSize:14,fontWeight:active?700:500,
                    transition:"all .15s",
                    width:"100%",justifyContent:sidebarCollapsed?"center":"flex-start",
                    position:"relative",
                  }}>
                  <span style={{fontSize:18,flexShrink:0,filter:active?"none":"grayscale(.3)"}}>{icon}</span>
                  {!sidebarCollapsed&&<span style={{flex:1,textAlign:"left"}}>{label}</span>}
                  {!sidebarCollapsed&&badge>0&&<span style={{background:"#1D6FE8",color:"#fff",fontSize:11,fontWeight:700,minWidth:20,height:20,borderRadius:20,display:"flex",alignItems:"center",justifyContent:"center",padding:"0 5px"}}>{badge}</span>}
                  {sidebarCollapsed&&badge>0&&<span style={{position:"absolute",top:6,right:10,width:8,height:8,borderRadius:"50%",background:"#1D6FE8"}} />}
                  {active&&<div style={{position:"absolute",left:0,top:"50%",transform:"translateY(-50%)",width:3,height:20,borderRadius:"0 4px 4px 0",background:"#1D6FE8"}} />}
                </button>
              );
            })}
          </nav>

          {/* User + collapse */}
          <div style={{borderTop:"1px solid #F1F5F9",padding:sidebarCollapsed?"16px 0":"16px 14px",display:"flex",flexDirection:"column",gap:10}}>
            {!sidebarCollapsed&&(
              <div style={{display:"flex",alignItems:"center",gap:10,padding:"8px 10px",borderRadius:10,background:"#F8FAFD"}}>
                <div style={{width:34,height:34,borderRadius:10,background:"#EFF6FF",border:"1.5px solid #BFDBFE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:800,color:"#1D6FE8",flexShrink:0}}>
                  {mainUser.fullName.split(" ").map(n=>n[0]).slice(0,2).join("")}
                </div>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontSize:13,fontWeight:700,color:"#0F172A",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{mainUser.fullName}</div>
                  <div style={{fontSize:11,color:"#94A3B8"}}>Patient</div>
                </div>
              </div>
            )}
            <button onClick={()=>setSidebarCollapsed(c=>!c)}
              style={{display:"flex",alignItems:"center",justifyContent:"center",gap:8,background:"none",border:"1px solid #E2E8F0",borderRadius:8,padding:"7px 0",cursor:"pointer",color:"#94A3B8",fontSize:12,fontWeight:600,fontFamily:"inherit",width:"100%"}}>
              {sidebarCollapsed?"→":"← Collapse"}
            </button>
          </div>
        </aside>

        {/* ── Main content ─────────────────────────────────────────────────── */}
        <main style={{flex:1,overflow:"hidden",display:"flex",flexDirection:"column",background:"#F8FAFD"}}>
          {/* Top bar */}
          <header style={{height:isMobile?56:58,background:"#fff",borderBottom:"1px solid #E2EEF8",display:"flex",alignItems:"center",padding:isMobile?"0 16px":"0 28px",gap:16,flexShrink:0,boxShadow:"0 1px 4px #0F172A06"}}>
            {isMobile&&(
              <button onClick={()=>setSidebarCollapsed(c=>!c)} style={{background:"none",border:"none",fontSize:22,display:"flex",alignItems:"center",justifyContent:"center",width:44,height:44,cursor:"pointer",color:"#1D4ED8"}}>
                {sidebarCollapsed?"☰":"✕"}
              </button>
            )}
            <div style={{flex:1}}>
              <div style={{fontSize:13,fontWeight:700,color:"#0F172A"}}>
                {NAV.find(n=>n.id===tab||n.id==="schedule"&&tab==="add-med")?.label||"Dashboard"}
              </div>
              {!isMobile&&<div style={{fontSize:11,color:"#94A3B8",marginTop:1}}>
                {new Date().toLocaleDateString("en",{weekday:"long",day:"numeric",month:"long",year:"numeric"})}
              </div>}
            </div>
            <div style={{display:"flex",alignItems:"center",gap:isMobile?8:14}}>
              {!isMobile&&offline&&<Badge color="#D97706" bg="#FEF3C7">Demo mode</Badge>}
              {!isMobile&&<div style={{display:"flex",alignItems:"center",gap:6}}>
                <div style={{width:8,height:8,borderRadius:"50%",background:device.connected?"#10B981":"#EF4444",boxShadow:device.connected?"0 0 0 3px #D1FAE5":"none"}} />
                <span style={{fontSize:12,fontWeight:600,color:device.connected?"#059669":"#EF4444"}}>{device.connected?"Device online":"Device offline"}</span>
              </div>}
              {!isMobile&&(
                <button onClick={handleLogout} style={{padding:"8px 14px",borderRadius:10,border:"1.5px solid #E2E8F0",background:"#EFF6FF",color:"#1D4ED8",fontSize:13,fontWeight:600,cursor:"pointer",fontFamily:"inherit"}}>
                  Logout
                </button>
              )}
              {isMobile&&<div style={{width:6,height:6,borderRadius:"50%",background:device.connected?"#10B981":"#EF4444",boxShadow:device.connected?"0 0 0 2px #D1FAE5":"none"}} />}
              <div style={{width:isMobile?32:34,height:isMobile?32:34,borderRadius:10,background:"#EFF6FF",border:"1.5px solid #BFDBFE",display:"flex",alignItems:"center",justifyContent:"center",fontSize:isMobile?12:13,fontWeight:800,color:"#1D6FE8"}}>
                {mainUser.fullName.split(" ").map(n=>n[0]).slice(0,2).join("")}
              </div>
            </div>
          </header>

          {/* Screen content */}
          <div style={{flex:1,overflow:"hidden"}}>
            <div key={tab} style={{height:"100%",animation:"fadeSlide .2s ease-out"}}>
              {tab==="home"&&<HomeScreen user={mainUser} schedules={schedules} adherence={adherence} device={device} isMobile={isMobile}/>}
              {tab==="register"&&<RegisterScreen onRegistered={u=>{setUser(u);setTab("home");}} isMobile={isMobile}/>}
              {tab==="verify"&&<VerifyScreen isMobile={isMobile}/>}
              {tab==="schedule"&&<ScheduleScreen user={mainUser} schedules={schedules}
                onAdd={s=>setSchedules(p=>[...p,{...s,medicationName:s.medication_name||s.medicationName,dispenseTimes:s.dispense_times||s.dispenseTimes}])}
                onDelete={id=>setSchedules(p=>p.filter(s=>s.id!==id))} isMobile={isMobile}/>}
              {tab==="monitor"&&<MonitorScreen user={mainUser} adherence={adherence} device={device} isMobile={isMobile}/>}
              {tab==="notifications"&&<NotificationsScreen user={mainUser} notifications={notifications} onMarkRead={()=>{api.markRead(mainUser.id).catch(()=>{});setNotifications(ns=>ns.map(n=>({...n,read:true})));}} isMobile={isMobile}/>}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
