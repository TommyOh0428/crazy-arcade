import pygame
from pygame.locals import *

class Projectile:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.radius = 5
        self.color = (255, 0, 0)  # Red color for projectiles

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

    def update(self):
        self.x += self.dx
        self.y += self.dy