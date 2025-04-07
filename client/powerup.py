import pygame
from pygame.locals import *

class PowerUp:
    def __init__(self, data):
        self.id = data['id']
        self.x = data['x']
        self.y = data['y']
        self.type = data['type']
        self.radius = data.get('radius', 10)
        self.color = tuple(data['color']) if isinstance(data['color'], list) else data['color']
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)