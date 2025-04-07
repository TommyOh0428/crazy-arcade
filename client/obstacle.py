import pygame
from pygame.locals import *

# Colors
BLUE = (0, 0, 255)

class Obstacle:
    def __init__(self, data):
        self.x = data['x']
        self.y = data['y']
        self.width = data['width']
        self.height = data['height']
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
    
    def draw(self, surface):
        pygame.draw.rect(surface, BLUE, self.rect)