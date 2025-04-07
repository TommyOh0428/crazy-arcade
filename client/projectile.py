import pygame
from pygame.locals import *

class Projectile:
    def __init__(self, data_or_x, y=None, dx=None, dy=None):
        # Handle both initialization methods: with data dict or with coordinates
        if y is None and isinstance(data_or_x, dict):
            # Initialize from server data
            data = data_or_x
            self.id = data.get('id', '')
            self.x = data.get('x', 0)
            self.y = data.get('y', 0)
            self.dx = data.get('dx', 0)
            self.dy = data.get('dy', 0)
            self.radius = data.get('radius', 5)
            self.color = tuple(data['color']) if isinstance(data['color'], list) else data.get('color', (255, 0, 0))
            self.damage = data.get('damage', 10)
            self.owner_id = data.get('owner_id')
            self.can_bounce = data.get('can_bounce', False)
            self.bounces = data.get('bounces', 0)
        else:
            # Initialize with coordinates
            self.id = ''
            self.x = data_or_x
            self.y = y
            self.dx = dx if dx is not None else 0
            self.dy = dy if dy is not None else 0
            self.radius = 5
            self.color = (255, 0, 0)  # Red color for projectiles
            self.damage = 10
            self.owner_id = None
            self.can_bounce = False
            self.bounces = 0

    def update(self, data=None):
        if data:
            # Update from server data
            if 'x' in data:
                self.x = data['x']
            if 'y' in data:
                self.y = data['y']
            if 'dx' in data:
                self.dx = data['dx']
            if 'dy' in data:
                self.dy = data['dy']
        else:
            # Update position with current velocity
            self.x += self.dx
            self.y += self.dy

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)