import pygame
from pygame.locals import *
from projectile import Projectile

class Cannon:
    def __init__(self, data_or_x, y=None):
        if y is None and isinstance(data_or_x, dict):
            # Initialize from server data
            data = data_or_x
            self.id = data.get('id', '')
            self.x = data.get('x', 0)
            self.y = data.get('y', 0)
            self.type = data.get('type', 'RAPID')
            self.shots_left = data.get('shots_left', 10)
            self.radius = data.get('radius', 20)
            self.color = tuple(data['color']) if isinstance(data['color'], list) else data.get('color', (128, 128, 128))
            self.controlled_by = data.get('controlled_by')
            self.use_timer = data.get('use_timer', 0)
            self.last_shot_time = data.get('last_shot_time', 0)
        else:
            self.id = ''
            self.x = data_or_x
            self.y = y
            self.type = 'RAPID'
            self.shots_left = 10
            self.radius = 20
            self.color = (128, 128, 128)
            self.controlled_by = None
            self.use_timer = 0
            self.last_shot_time = 0

    def update(self, data=None):
        """Update cannon state from server data"""
        if data:
            if 'x' in data:
                self.x = data['x']
            if 'y' in data:
                self.y = data['y']
            if 'shots_left' in data:
                self.shots_left = data['shots_left']
            if 'controlled_by' in data:
                self.controlled_by = data['controlled_by']
            if 'use_timer' in data:
                self.use_timer = data['use_timer']
            if 'last_shot_time' in data:
                self.last_shot_time = data['last_shot_time']
            if 'color' in data:
                self.color = tuple(data['color']) if isinstance(data['color'], list) else data['color']