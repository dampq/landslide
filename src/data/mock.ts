import {Alert,RiskLocation,Road,Sensor} from "../types";
export const risks:RiskLocation[]=[
{id:"r1",name:"Mawsynram Hills",district:"East Khasi Hills",state:"Meghalaya",lat:25.297,lng:91.582,score:91,level:"Critical",rainfall:186,soil:88,slope:42,confidence:94,road:"Partially Blocked",population:2450,hospital:"Mawsynram CHC · 7.8 km",updated:"2 mins ago"},
{id:"r2",name:"Sohra Ridge",district:"East Khasi Hills",state:"Meghalaya",lat:25.270,lng:91.730,score:84,level:"High",rainfall:164,soil:82,slope:39,confidence:92,road:"Open / monitored",population:1780,hospital:"Sohra CHC · 5.1 km",updated:"4 mins ago"},
{id:"r3",name:"Aizawl South",district:"Aizawl",state:"Mizoram",lat:23.705,lng:92.717,score:87,level:"High",rainfall:128,soil:81,slope:36,confidence:91,road:"Restricted",population:3120,hospital:"Civil Hospital · 8.4 km",updated:"5 mins ago"},
{id:"r4",name:"Kohima Ridge",district:"Kohima",state:"Nagaland",lat:25.675,lng:94.108,score:72,level:"High",rainfall:112,soil:74,slope:34,confidence:89,road:"Open",population:2140,hospital:"Naga Hospital · 6.2 km",updated:"8 mins ago"},
{id:"r5",name:"Gangtok East",district:"Gangtok",state:"Sikkim",lat:27.338,lng:88.607,score:65,level:"Moderate",rainfall:96,soil:69,slope:31,confidence:86,road:"NH-10 Blocked",population:1680,hospital:"STNM Hospital · 9.1 km",updated:"7 mins ago"},
{id:"r6",name:"Itanagar Hills",district:"Papum Pare",state:"Arunachal Pradesh",lat:27.084,lng:93.605,score:58,level:"Moderate",rainfall:88,soil:64,slope:28,confidence:84,road:"Open",population:920,hospital:"TRIHMS · 12 km",updated:"11 mins ago"},
{id:"r7",name:"Imphal West",district:"Imphal West",state:"Manipur",lat:24.817,lng:93.936,score:34,level:"Low",rainfall:42,soil:48,slope:12,confidence:88,road:"Open",population:740,hospital:"RIMS · 4.5 km",updated:"9 mins ago"},
{id:"r8",name:"Guwahati Foothills",district:"Kamrup Metro",state:"Assam",lat:26.144,lng:91.736,score:49,level:"Moderate",rainfall:76,soil:61,slope:24,confidence:90,road:"Open",population:4100,hospital:"GMCH · 10 km",updated:"6 mins ago"}];
export const alerts:Alert[]=[
{id:"a1",type:"CRITICAL LANDSLIDE WARNING",severity:"Critical",location:"Mawsynram, East Khasi Hills",time:"2 min ago",description:"AI model predicts a 91% probability of landslide activity within the next 6 hours.",people:2450,action:"Restrict road movement and deploy field response team."},
{id:"a2",type:"HEAVY RAIN WARNING",severity:"High",location:"Sohra, Meghalaya",time:"8 min ago",description:"Rainfall intensity has exceeded the district warning threshold.",people:1780,action:"Activate local watch posts and monitor drainage."},
{id:"a3",type:"ROAD BLOCKAGE",severity:"Critical",location:"NH-10, Sikkim",time:"18 min ago",description:"Slope failure has blocked both lanes on a monitored section.",people:3600,action:"Divert traffic and dispatch PWD road crew."},
{id:"a4",type:"SLOPE MOVEMENT DETECTED",severity:"High",location:"Aizawl South, Mizoram",time:"26 min ago",description:"Ground movement sensor recorded abnormal displacement.",people:3120,action:"Verify movement and prepare evacuation advisory."}];
export const sensors:Sensor[]=[
{id:"SM-1023",location:"Mawsynram",type:"Soil Moisture",value:"88%",status:"Critical",battery:76,updated:"2 mins ago"},
{id:"RG-0881",location:"Mawsynram",type:"Rain Gauge",value:"186 mm",status:"Warning",battery:91,updated:"1 min ago"},
{id:"GM-2041",location:"Sohra",type:"Ground Movement",value:"7.2 mm/h",status:"Critical",battery:68,updated:"4 mins ago"},
{id:"TL-1190",location:"Aizawl",type:"Tilt Sensor",value:"2.8°",status:"Warning",battery:84,updated:"5 mins ago"},
{id:"VB-0912",location:"Kohima",type:"Vibration Sensor",value:"0.42 g",status:"Online",battery:63,updated:"7 mins ago"},
{id:"TH-2214",location:"Gangtok",type:"Temperature/Humidity",value:"19°C / 92%",status:"Online",battery:88,updated:"6 mins ago"},
{id:"SM-1442",location:"Itanagar",type:"Soil Moisture",value:"64%",status:"Online",battery:79,updated:"11 mins ago"},
{id:"RG-0544",location:"Imphal",type:"Rain Gauge",value:"42 mm",status:"Offline",battery:12,updated:"1 hr ago"}];
export const roads:Road[]=[
{name:"NH-6",route:"Shillong – Silchar",district:"East Khasi Hills",status:"Partially Blocked",cause:"Landslide debris",updated:"10 min ago",priority:"HIGH"},
{name:"NH-10",route:"Gangtok – Siliguri",district:"Gangtok",status:"Blocked",cause:"Slope failure",updated:"18 min ago",priority:"CRITICAL"},
{name:"NH-2",route:"Kohima – Imphal",district:"Kohima",status:"Open",cause:"—",updated:"6 min ago",priority:"LOW"},
{name:"NH-44",route:"Shillong – Tripura",district:"Ri-Bhoi",status:"Under Verification",cause:"Debris report",updated:"23 min ago",priority:"MODERATE"}];
export const rainfall=[{t:"00h",rain:42,soil:62,risk:48},{t:"06h",rain:72,soil:68,risk:57},{t:"12h",rain:118,soil:77,risk:73},{t:"18h",rain:148,soil:84,risk:84},{t:"24h",rain:210,soil:91,risk:94}];
export const monthly=[{m:"Jan",v:7},{m:"Feb",v:8},{m:"Mar",v:12},{m:"Apr",v:18},{m:"May",v:34},{m:"Jun",v:62},{m:"Jul",v:79},{m:"Aug",v:71},{m:"Sep",v:48},{m:"Oct",v:23},{m:"Nov",v:11},{m:"Dec",v:6}];
export const states=[{name:"Meghalaya",risk:91,events:58},{name:"Mizoram",risk:87,events:42},{name:"Nagaland",risk:72,events:31},{name:"Sikkim",risk:65,events:39},{name:"Arunachal",risk:58,events:27},{name:"Assam",risk:49,events:22},{name:"Manipur",risk:34,events:18},{name:"Tripura",risk:29,events:11}];
