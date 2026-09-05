export type RiskLevel="Low"|"Moderate"|"High"|"Critical";
export type RiskLocation={id:string;name:string;district:string;state:string;lat:number;lng:number;score:number;level:RiskLevel;rainfall:number;soil:number;slope:number;confidence:number;road:string;population:number;hospital:string;updated:string};
export type Alert={id:string;type:string;severity:RiskLevel;location:string;time:string;description:string;people:number;action:string;resolved?:boolean;ack?:boolean};
export type Sensor={id:string;location:string;type:string;value:string;status:string;battery:number;updated:string};
export type Road={name:string;route:string;district:string;status:string;cause:string;updated:string;priority:string};
