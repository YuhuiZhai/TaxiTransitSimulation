from cv2 import threshold
import numpy as np
import math
import utils
from city import City
from fleet import Fleet
from eventQueue import EventQueue
from tqdm import tqdm
from animation import Animation
import pandas as pd
import pulp
class Simulation:
    def __init__(self, city:City, T:float, lmd=200, fleet_size=None, simul_type="",
                inter = True, lmd_map=None, fleet_map=None, threshold_map = None, realloc_decision  = True):
        self.clock = 0
        self.T = T
        self.fleet = {}
        self.events = {}
        self.realloc_decision = realloc_decision 
        self.simu_type = simul_type if simul_type in ["homogeneous", "heterogeneous"] else "homogeneous" 
        if self.simu_type == "homogeneous":
            self.city = city
            self.lmd = lmd
            self.fleet_size = fleet_size if fleet_size != None else 1.5*utils.optimal(self.city, self.lmd)[4]
            self.fleet[0] = Fleet(fleet_size, city, 0)
            self.events[0] = EventQueue(city, T, lmd, 0)
        elif self.simu_type == "heterogeneous":
            self.lmd_map, self.fleet_map, self.inter, self.threshold_map = lmd_map, fleet_map, inter, threshold_map
            self.city = City(city.type_name, length=city.length*len(self.lmd_map), origin=(0, 0))
            self.temp = city        
            self.hetero_init()    
        # na, ns, ni, p vs t
        self.timeline = None
        self.na, self.ns, self.ni, self.p = [], [], [], []
        # list of [ax, ay], [sx, sy], [ix, iy]
        self.fleet_info = []
        # list of [px, py]
        self.passenger_info = []
    
    def hetero_init(self):
        num_per_line = len(self.lmd_map)
        for i in range(num_per_line):
            for j in range(num_per_line):
                subcity = City(self.temp.type_name, length=self.temp.length, origin=(i*self.temp.length, (num_per_line-1-j)*self.temp.length))
                subfleet = Fleet(self.fleet_map[i][j], subcity, str(i*num_per_line+j))
                subevents = EventQueue(subcity, self.T, self.lmd_map[i][j], str(i*num_per_line+j))
                self.fleet[subfleet.id] = subfleet
                self.events[subevents.id] = subevents

    def move(self, res:float):
        self.clock += res
        for key in self.fleet:
            self.fleet[key].move(res)
            self.events[key].move(res)

    def update(self, res):
        if self.simu_type == "heterogeneous" and self.inter and int(self.clock/res) % 200 == 0:
            self.global_reallocation()
        total_na, total_ns, total_ni = 0, 0, 0
        total_ax, total_ay = [], []
        total_sx, total_sy = [], []
        total_ix, total_iy = [], []
        total_interx, total_intery = [], []
        total_px, total_py = [], []
        for key in self.fleet:
            total_na += self.fleet[key].assigned_num 
            total_ns += self.fleet[key].inservice_num
            total_ni += self.fleet[key].idle_num
            [ax, ay], [sx, sy], [ix, iy], [interx, intery] = self.fleet[key].sketch_helper()
            [px, py] = self.events[key].sketch_helper()
            total_ax += ax; total_ay += ay; total_sx += sx; total_sy += sy
            total_ix += ix; total_iy += iy; total_interx += interx; total_intery += intery; 
            total_px += px; total_py += py
            self.fleet[key].local_reallocation(self.realloc_decision)
        self.na.append(total_na)
        self.ns.append(total_ns)
        self.ni.append(total_ni)
        self.fleet_info.append([[total_ax, total_ay], [total_sx, total_sy], [total_ix, total_iy], [total_interx, total_intery]])
        self.passenger_info.append([total_px, total_py])
        
    # def reset(self):
    #     self.timeline = None
    #     self.na, self.ns, self.ni, self.p = [], [], [], []
    #     self.fleet_info, self.passenger_info = [], []
    #     if self.simu_type == "homogeneous":
    #         self.fleet = [Fleet(self.fleet_size, self.city)]
    #         self.events = [EventQueue(self.city, self.T, self.lmd)]
    #     elif self.simu_type == "heterogeneous":
    #         self.hetero_init()

    def global_reallocation(self):
        if self.simu_type == "homogeneous":
            return 
        # key is id, value is (free veh number, idx in list)
        supply_fleet, demand_fleet = {}, {}
        supply_name, demand_name = [], []
        supply_sum, demand_sum = 0, 0
        for key in self.fleet:
            subfleet, subevent = self.fleet[key], self.events[key]
            ni, lmdR = subfleet.idle_num, subevent.lmd 
            if self.threshold_map != None: 
                opt_ni = self.threshold_map[int(int(key)/len(self.threshold_map))][int(int(key)%len(self.threshold_map))]
            else: opt_ni = math.ceil(utils.optimal(subfleet.city, lmdR)[1])
            if (ni > opt_ni):
                supply_fleet[subfleet.id] = ni - opt_ni
                supply_name.append(subfleet.id)
                supply_sum += ni - opt_ni
            elif (ni < opt_ni):
                demand_fleet[subfleet.id] = opt_ni - ni
                demand_name.append(subfleet.id) 
                demand_sum += opt_ni - ni
        if (len(supply_fleet) == 0 or len(demand_fleet) == 0):
            return 
        supply_name.append("D")
        demand_name.append("D")
        supply_fleet["D"], demand_fleet["D"] = 0, 0 
        costs = np.zeros((len(supply_fleet), len(demand_fleet)))
        if (supply_sum < demand_sum): supply_fleet["D"] = demand_sum - supply_sum
        elif (supply_sum > demand_sum): demand_fleet["D"] = supply_sum - demand_sum
        inf = 1000  
        row_idx = 0      
        for s_id in supply_fleet:
            if s_id == "D": continue
            s = self.fleet[s_id]
            col_idx = 0
            for d_id in demand_fleet:
                if d_id == "D": continue
                d = self.fleet[d_id]
                if abs(sum(s.city.origin)/s.city.length-sum(d.city.origin)/d.city.length) != 1:
                    costs[row_idx][col_idx] = inf
                else: costs[row_idx][col_idx] = 1/demand_fleet[d_id]
                col_idx += 1
            row_idx += 1
        prob = pulp.LpProblem("transproblem", pulp.LpMinimize)
        Routes = [(s_id,d_id) for s_id in supply_name for d_id in demand_name]
        pulp_costs = pulp.makeDict([supply_name, demand_name], costs, 0)
        vars = pulp.LpVariable.dicts("Route", (supply_name, demand_name), 0, None, pulp.LpInteger)
        prob += pulp.lpSum([vars[s_id][d_id]*pulp_costs[s_id][d_id] for (s_id, d_id) in Routes])
        for s_id in supply_name:
            prob += pulp.lpSum([vars[s_id][d_id] for d_id in demand_name]) <= supply_fleet[s_id]
        for d_id in demand_name:
            prob += pulp.lpSum([vars[s_id][d_id] for s_id in supply_name]) >= demand_fleet[d_id]
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        for v in prob.variables():
            s_id, d_id = v.name.split("_")[1], v.name.split("_")[2]
            if s_id == "D" or d_id == "D" or pulp_costs[s_id][d_id] == inf:
                continue
            self.fleet[s_id].global_reallocation(self.fleet[d_id], v.varValue)
        return 

    def simple_serve(self, res:float):
        prev = 0
        self.timeline = np.arange(0, self.T, res)
        for t in tqdm(self.timeline, desc="simple_serve loading"):
            self.update(res)
            for key in self.fleet:
                head_time, head = self.events[key].head()
                while (not self.events[key].empty() and head_time < t):
                    prev += 1
                    self.fleet[key].simple_serve(head.passenger)
                    self.events[key].dequeue()
                    head_time, head = self.events[key].head()
            self.p.append(prev)
            self.move(res)
        return 

    def sharing_serve(self, res:float, detour_percentage:float):
        prev = 0
        self.timeline = np.arange(0, self.T, res)
        for t in tqdm(self.timeline, desc="sharing_serve loading"):
            for key in self.fleet:
                self.update(res)
                head_time, head = self.events[key].head()
                while (not self.events[key].empty() and head_time < t):
                    self.fleet[key].sharing_serve(head.passenger, detour_percentage)
                    prev += 1
                    self.events[key].dequeue()
                    head_time, head = self.events[key].head()
            self.move(res)
            self.p.append(prev)
        return

    def batch_serve(self, res:float, dt:float):
        self.timeline = np.arange(0, self.T, res)
        batch_timeline = np.arange(0, self.T, dt)
        batch_idx = 0
        prev = 0
        
        for t in tqdm(self.timeline, desc="batch_serve loading"):
            self.update(res)
            # when it is batching time, starts serving
            if (batch_idx >= len(batch_timeline)):
                batch_time = self.timeline[-1]
            else:
                batch_time = batch_timeline[batch_idx] 
            if batch_time <= t:
                for key in self.fleet:
                    passengers = []
                    head_time, head = self.events[key].head()
                    while (not self.events[key].empty() and head_time < batch_time):
                        prev += 1
                        passengers.append(head.passenger)
                        self.events[key].dequeue()
                        head_time, head = self.events[key].head()
                    if len(passengers) != 0:
                        self.fleet[key].batch_serve(passengers)
                    batch_idx += 1
            self.move(res)
            self.p.append(prev)     
        return   

    # def sharing_serve(self, res:float, detour_dist=0, detour_percent=0):
    def export(self, name=""):
        name_ = name
        if (name_ != ""):
            name_ += "_"
        veh_num = {
            'time': self.timeline, 
            'passenger' : self.p,
            'na': self.na, 
            'ns': self.ns, 
            'ni': self.ni 
        }
        output_1 = pd.DataFrame(veh_num)
        output_1.to_csv(name_ + 'veh_num_M_' + str(self.fleet_size) + '_lambda_' + str(self.lmd) + '.csv')
        if (self.simu_type == "heterogeneous"):
            return 
        elif (self.simu_type == "homogeneous"):
            dist_a, dist_s, ta, ts, freq, unserved = self.fleet[0].info()
            fleet_info = {
                'dist_a' : dist_a,
                'dist_s' : dist_s,
                'total_ta' : ta,
                'total_ts' : ts,
                'total_ti' : self.T - np.array(ta) - np.array(ts), 
                'freq' : freq
            }
            output_2 = pd.DataFrame(fleet_info)
            output_2.to_csv(name_ + 'fleet_info_M_' + str(self.fleet_size) + '_lambda_' + str(self.lmd) + '.csv')
            print("unserved number: ", unserved)
        return 

    def make_animation(self, compression = 100, fps=15):
            print("animation plotting")
            animation = Animation(self.city, self.fleet_info, self.passenger_info)
            animation.plot(compression, fps)
    
