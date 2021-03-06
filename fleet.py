from city import City
from unit import Unit
class Fleet:
    def __init__(self, n:int, city:City, id):
        self.fleet_size, self.city, self.id = n, city, id
        self.clock = 0
        self.vehicles = {}
        self.status_table = {}
        self.vehs_group = {}
        
    # status_name: dictionary of status, key is status, value is string_type name
    # status_num: initial number of status, key is status, value is int_type number
    def init_group(self, status_name:dict):
        self.status_table = status_name
        for status in status_name:
            self.vehs_group[status] = set()

    # change veh's status from status1 to status2 
    def changeVehStatus(self, status_request:tuple):
        if status_request == None:
            return 
        veh_id, status1, status2 = status_request
        if status1 == status2:
            return
        veh = self.vehicles[veh_id]
        set_out, set_in = self.vehs_group[status1], self.vehs_group[status2]
        set_out.remove(veh)
        set_in.add(veh)
        return 

    # add idle vehicle from other fleet
    def add_veh(self, vehicle:Unit):
        self.vehicles[vehicle.id] = vehicle
        self.vehs_group[vehicle.status].add(vehicle)
        self.fleet_size += 1
        return 

    # release idle vehicle to other fleet
    def release_veh(self, vehicle:Unit):
        self.vehicles.pop(vehicle.id)
        self.vehs_group[vehicle.status].remove(vehicle)
        self.fleet_size -= 1
        return 

    # function to serve the passenger at time t
    def move(self, dt):
        for id in self.vehicles:
            status_request = self.vehicles[id].move(dt)
            self.changeVehStatus(status_request)
        self.clock += dt
    
    # function for making animation
    def sketch_helper(self):
        sketch_table = []
        for status in range(len(self.status_table)):
            sketch_table.append([[], []])
            for veh in self.vehs_group[status]:
                sketch_table[status][0].append(veh.location()[0])
                sketch_table[status][1].append(veh.location()[1])
        return sketch_table