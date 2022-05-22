import utils 
from passenger import Passenger
from city import City
from city import CityLink
import math
class Vehicle:
    def __init__(self, vehicle_id:int, city:City):
        self.city = city
        self.id = vehicle_id
        self.clock = 0
        if self.city.type_name == "Euclidean" or self.city.type_name == "Manhattan":    
            self.x, self.y = utils.generate_location(city)
        if self.city.type_name == "real-world":
            self.link, self.len = utils.generate_location(city)
        # around 30 mph
        self.speed = 0.3
        self.load = 0
        self.status = "idle"
        self.passenger = None
        # ordered list of passed nodes [..., cityNode1, cityNode2, cityNode3, ...]
        self.path1 = [] 
        self.path2 = []  
        # determine whether the pre-assigned route is finished
        self.start1 = True
        # distance of assigned
        self.dist_a = 0
        # distance of service
        self.dist_s = 0
        # assigned time 
        self.ta = 0 
        # inservice time
        self.ts = 0
        # frequency of being called
        self.freq = 0


    def assign(self, passenger:Passenger):
        if self.city.type_name == "Euclidean" or self.city.type_name == "Manhattan": 
            self.path1 = [[self.x, self.y], [passenger.ox, passenger.oy]]
            self.path2 = [[passenger.ox, passenger.oy], [passenger.dx, passenger.dy]]

        if self.city.type_name == "real-world":  
            dist1, path1 = self.city.dijkstra(self.link.origin.id, passenger.o_link.origin.id)
            dist2, path2 = self.city.dijkstra(passenger.o_link.origin.id, passenger.d_link.origin.id)
            if (dist1 == -1 or dist2 == -1):
                return False
            # assign current location to passenger and passenger origin to destination
            self.path1 = path1 
            self.path2 = path2
            self.start1 = True
        self.load += 1
        self.freq += 1
        self.passenger = passenger
        self.status = "assigned"
        return True
    
    def location(self):
        if self.city.type_name == "Euclidean" or self.city.type_name == "Manhattan":  
            return (self.x, self.y)

        if self.city.type_name == "real-world":
            x1, y1 = self.link.origin.x, self.link.origin.y
            x2, y2 = self.link.destination.x, self.link.destination.y
            x3, y3 = None, None
            if (x1 == x2):
                x3 = x1
                if (y1 < y2):
                    y3 = y1 + self.len
                else:
                    y3 = y1 - self.len
                return (x3, y3)
            k = (y2 - y1)/(x2 - x1)
            if (x1 < x2):
                x3 = x1 + self.len / self.link.length * abs(x2 - x1)
                y3 = y1 + k*(x3 - x1)
            if (x1 > x2):
                x3 = x1 - self.len / self.link.length * abs(x2 - x1)
                y3 = y1 + k*(x3 - x1)   
            return (x3, y3)

    # move from current position to destination [x, y] using Euclidean space
    # return true if the goal is reached
    def move_Euclidean(self, dt:float, dxy:list):
        dx, dy = dxy[0], dxy[1]
        if (self.x == dx and self.y == dy):
            return True
        if (self.x == dx):
            ydir = (dy-self.y) / abs(dy-self.y)
            self.y += ydir * dt * self.speed
            self.y = ydir*min(ydir*self.y, ydir*dy)
            if (self.y == dy):
                return True
        else:
            xdir = (dx-self.x) / abs(dx-self.x)
            if (self.y != dy):
                ydir = (dy-self.y) / abs(dy-self.y)
                alpha = math.atan(abs(self.y-dy)/abs(self.x-dx))            
                self.x += xdir*self.speed*dt*math.cos(alpha) 
                self.y += ydir*self.speed*dt*math.sin(alpha)
                self.x = xdir*min(xdir*self.x, xdir*dx)
                self.y = ydir*min(ydir*self.y, ydir*dy)
            else:
                return True
        return False

    # move from origin (x, y) to destination (x, y) using Manhattan space
    def move_Manhattan(self, dt:float, dxy:list):
            dx, dy = dxy[0], dxy[1]
            if (self.x != dx):
                xdir = (dx-self.x) / abs(dx-self.x)
                self.x += xdir * dt * self.speed
                self.x = xdir*min(xdir*self.x, xdir*dx)
            else:
                if (self.y != dy):
                    ydir = (dy-self.y) / abs(dy-self.y)
                    self.y += ydir * dt * self.speed
                    self.y = ydir*min(ydir*self.y, ydir*dy)
                else:
                    return True 
            return False

    def move_real_world(self, dt, path:list, dlink:CityLink, dlen:float):
        """
        Let the status of vehicle changed as time goes
        `dt`: time gap
        `path`: list of CityNodes
        `dlink`: the Citylink where destination is on  
        `dlen`: distance from destination Citylink 
        `return`: True if the goal is reached
        """
        # edge case last citylink
        if len(path) == 0:
            return True
        if len(path) == 1:
            temp = self.len + dt * self.speed
            # driving over destination
            if (temp >= dlen):
                path.pop(0)
                self.len = dlen
                return True
            else:
                self.len = temp
        else:
            self.len += dt * self.speed
            if (self.len > self.link.length):
                path.pop(0)
                if (len(path) == 1):
                    self.link = dlink
                    self.len = 0
                # id of next link  
                else:
                    next_id = self.city.map[path[0], path[1]]
                    self.link = self.city.links[next_id]
                    self.len = 0
                return True
        return False

    # move along the path and update the location of vehicle
    def move(self, dt):
        if (self.status == "assigned"):
            self.ta += dt
            self.dist_a += dt * self.speed 
        elif (self.status == "in_service"):
            self.ts += dt
            self.dist_s += dt * self.speed 

        # Eulidean movement
        if self.city.type_name == "Euclidean":
            if self.status == "assigned":
                reached = self.move_Euclidean(dt, self.path1[1])
                if (reached):
                    self.passenger.status = "picked up"
                    self.status = "in_service"
            elif self.status == "in_service":
                reached = self.move_Euclidean(dt, self.path2[1])
                if (reached):
                    self.status = "idle"

        elif self.city.type_name == "Manhattan":  
            if self.status == "assigned":
                reached = self.move_Manhattan(dt, self.path1[1])
                if (reached):
                    self.passenger.status = "picked up"
                    self.status = "in_service"
            elif self.status == "in_service":
                reached = self.move_Manhattan(dt, self.path2[1])
                if (reached):   
                    self.status = "idle"

        elif self.city.type_name == "real-world":
            # determine the movement of first path
            if (len(self.path1) == 0 and len(self.path2) == 0):
                self.status = "idle"
                return 
            
            if (self.start1):
                # edge case path1 length is 1
                if (len(self.path1) == 1):
                    # different direction 
                    if (self.link.id != self.passenger.o_link.id):
                        self.len -= dt * self.speed
                        if (self.len < 0):
                            self.len = 0
                            self.link = self.passenger.o_link
                            self.start1 = False
                    else: 
                        self.start1 = False
                    return
                # general case same direction
                elif (self.link.id == self.city.map[self.path1[0], self.path1[1]]):
                    self.start1 = False
                    return 
                # general case different direction 
                else:
                    self.len -= dt * self.speed
                    if (self.len < 0):
                        self.len = 0
                        self.link = self.city.links[self.city.map[self.path1[0], self.path1[1]]]
                        self.start1 = False
                    return 

            if len(self.path1) != 0:
                self.move_real_world(dt, self.path1, self.passenger.o_link, self.passenger.o_len)
                self.clock += dt
                return 
            
            if len(self.path2) != 0:
                self.status = "in_service"
                self.passenger.status = "picked up"
                if (len(self.path2) >= 2 and self.link.id != self.city.map[self.path2[0], self.path2[1]]):
                    self.len -= dt * self.speed
                    if (self.len < 0):
                        self.len = 0
                        self.link = self.city.links[self.city.map[self.path2[0], self.path2[1]]]
                else:   
                    self.move_real_world(dt, self.path2, self.passenger.d_link, self.passenger.d_len)
                    self.clock += dt
                    return 
            self.status = "idle"
            return 