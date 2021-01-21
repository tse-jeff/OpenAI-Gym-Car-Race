#!/usr/bin/env python

import pygame, sys, time
from math import *
import gym
from gym import spaces


class Car:
    def __init__(self, x, y, num_sensors):
        self.track = None
        self.image = pygame.image.load("Audi.png")
        self.image = pygame.transform.scale(self.image, (50, 50))        
        self.angle = 90
        self.pos = [x, y]        
        
        self.sensors = [[0, 0,  i*(180.0/num_sensors), 0] for i in range(num_sensors + 1)]
        self.center_sensors()
        self.crashed = False 
        self.speed = 0
        self.rotation = 0

        self.acceleration = .4
        self.max_speed = 10

        self.turn_rate = .2
        self.max_turn_rate = 3
        
        self.REST = 0
        self.DECELERATE = 1        
        self.ACCELERATE = 2
        self.ACCEL_LEFT = 1
        self.ACCEL_RIGHT = 2
    
        self.NEW_TILE_REWARD = 10
        self.SAME_TILE_REWARD = -1
        self.traveled = []
    
    def set_track(self, track):
        self.track = track
    
    def get_car_tip(self):
        x, y = self.pos
        return self.rotate((x+25, y), self.angle, (x+25, y+25))

    def get_car_center(self):
        x, y = self.pos
        return x+25, y+25

    def dist(self, x0, y0, x1, y1):
        return ((x0-x1)**2 + (y0-y1)**2)**.5

    def center_sensors(self):
        x, y = self.pos
        center = self.get_car_tip()
        for sensor in self.sensors:
            sensor[0], sensor[1] = center

    def update_sensors(self):
        observations = []
        self.center_sensors()
        offset = 90
        for sensor in self.sensors:
            while True:
                if self.track.colliding_with(sensor[0], sensor[1]):
                    break                
                sensor[0] += 1*cos(-radians(self.angle + sensor[2]))
                sensor[1] += 1*sin(-radians(self.angle + sensor[2]))
            x0, y0 = self.get_car_tip()
            x1, y1, = sensor[0], sensor[1]
            sensor[3] = self.dist(x0, y0, x1, y1)
            observations.append(sensor[3])
        return observations
    
    def render(self, screen):
        color = (255, 255, 0)
        self.blitRotateCenter(screen, self.image, self.pos, self.angle)
        for sensor in self.sensors:
            pygame.draw.circle(screen, (255, 0, 0), (sensor[0], sensor[1]), 5)
    
    def rotate(self, coord, angle, center):
        angle = -radians(angle+90)
        x0, y0 = center
        x1, y1 = coord    
        d = self.dist(x0, y0, x1, y1)
        return (d*cos(angle) + x0, d*sin(angle) + y0)
    
    def blitRotateCenter(self, screen, image, topleft, angle):
        rotated_image = pygame.transform.rotate(image, angle)
        new_rect = rotated_image.get_rect(center = image.get_rect(topleft = topleft).center)
        screen.blit(rotated_image, new_rect.topleft)

    def rotate_image_rect(self, image, angle, pos):
        x, y, = pos
        rotated_image = pygame.transform.rotate(image, angle)
        new_rect = rotated_image.get_rect(center = image.get_rect(center = (x, y)).center)
        return new_rect

    def has_crashed(self):
        x, y = self.get_car_tip()
        return self.track.colliding_with(x, y)
    
    def move_forward_by(self, dist):
        offset = 90
        x, y = self.pos
        rad_angle = -radians(self.angle + offset)
        return (x + dist * cos(rad_angle), y + dist * sin(rad_angle))
    
    def move(self):
        if self.crashed: return -100

        reward = 0
        self.angle += self.rotation
        self.pos = self.move_forward_by(self.speed)
        curr_tile = self.track.current_tile(self)
        
        if curr_tile not in self.traveled:
            self.traveled.append(curr_tile)
            reward = self.NEW_TILE_REWARD
        else: reward = self.SAME_TILE_REWARD
        return reward
    
    def step(self, action):
        if self.has_crashed():
            self.crashed = True
        accel, rot = action
        if accel == self.ACCELERATE and self.speed < self.max_speed:
            self.speed += self.acceleration
        elif accel == self.DECELERATE and self.speed > 0:
            self.speed -= self.acceleration
        if rot == self.ACCEL_LEFT and self.rotation < self.max_turn_rate:            
            self.rotation += self.turn_rate
        elif rot == self.ACCEL_RIGHT and self.rotation > -self.max_turn_rate:
            self.rotation -= self.turn_rate
        
        reward = self.move()
        observations = self.update_sensors()
        return observations, reward, self.crashed, {}

class TrackBorder: 
    def __init__(self, x, y, width, height, color, index):
        self.dimensions = (x, y, width, height)
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.active = True
        self.index = index
        self.mutable = True
    
    def check_state(self):
        mouse_pos = pygame.mouse.get_pos()
        pressed_state = pygame.mouse.get_pressed()
        x, y, w, h = self.dimensions
        if x+w > mouse_pos[0] > x and y + h > mouse_pos[1] > y and pressed_state[0] and self.mutable:
            self.set_active(False)            
    
    def set_active(self, state):
        self.active = state

    def render(self, screen):
        self.check_state()
        if(self.active):
            pygame.draw.rect(screen, self.color, self.rect)
            pygame.draw.rect(screen, (255, 255, 255), self.rect, 1)


class Track(gym.Env): 
    def __init__(self, num_blocks_x, num_blocks_y, block_width, block_height):        
        super(Track, self).__init__()
        pygame.init()
        self.num_blocks_x, self.num_blocks_y = num_blocks_x, num_blocks_y
        self.action_space = spaces.Tuple((spaces.Discrete(3), spaces.Discrete(3)))
        self.observation_space = spaces.Box(low=0, high=10000, shape=(1, 10))
        self.initialized = False
        
        self.clock = pygame.time.Clock()
        self.screen_width, self.screen_height = block_width * num_blocks_x, block_height * num_blocks_y
        self.screen = None
        
        self.color = (255, 0, 255)
        self.track = [[TrackBorder(x*block_width, y*block_height, block_width, block_height, self.color, (x,y)) for x in range(-1,num_blocks_x+1)] for y in range(-1, num_blocks_y+1)]
        self.cars = []
    
    def open_window(self):
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        
    def close_window(self):
        pygame.display.quit()
        self.screen = None
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.close_window()

    def reset(self):
        self.open_window()
        while self.screen:
            self.render()
        self.close_window()
        self.initialized = True
        for row in self.track:
            for border in row:
                border.mutable = False
        
    def colliding_with(self, x, y):    
        for row in self.track:
            for border in row:
                if border.rect.collidepoint(x,y) and border.active:
                    return border.index
        return False  
    
    def current_tile(self, car):
        x, y = car.get_car_center()
        for row in self.track:
            for border in row:
                if border.rect.collidepoint(x, y):
                    return border.index     

    def render(self):
        if not self.screen and self.initialized:
            self.open_window()
        self.screen.fill((30,30,30))
        self.clock.tick(60)
        for j in range(self.num_blocks_x+2):
            for k in range(self.num_blocks_y+2):
                tile = self.track[k][j]
                if(tile.active):
                    tile.render(self.screen)
        for car in self.cars:
            car.render(self.screen)        
        pygame.display.flip()
        self.handle_events()
    
    def add_car(self, car):
        self.cars.append(car)
        car.set_track(self)

    def step(self, action):
        """ for car in self.cars: """
        car = self.cars[0]
        obs, reward, done, _ = car.step(action)
        return obs, reward, done, _
