import pygame
from pygame.locals import *

# Colors
RED = (255, 0, 0)
GREEN = (0, 255, 0)

# Constants
PLAYER_RADIUS = 20
PLAYER_MAX_HEALTH = 100

class Player:
    def __init__(self, x, y, color, player_id):
        self.x = x
        self.y = y
        self.color = color
        self.id = player_id
        self.health = PLAYER_MAX_HEALTH
        self.speed = 5
        self.alive = True
        self.has_cannon = False
        self.cannon_id = None
    
    def update(self, data):
        """Update player state from server data"""
        if 'x' in data:
            self.x = data['x']
        if 'y' in data:
            self.y = data['y']
        if 'health' in data:
            self.health = data['health']
        if 'alive' in data:
            self.alive = data['alive']
        if 'has_cannon' in data:
            self.has_cannon = data['has_cannon']
        if 'cannon_id' in data:
            self.cannon_id = data['cannon_id']
    
    def draw(self, surface):
        if not self.alive:
            return
            
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        # Draw health bar
        health_width = 40 * (self.health / PLAYER_MAX_HEALTH)
        pygame.draw.rect(surface, RED, (self.x - 20, self.y - 30, 40, 5))
        pygame.draw.rect(surface, GREEN, (self.x - 20, self.y - 30, health_width, 5))