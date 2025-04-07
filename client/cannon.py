import pygame
from pygame.locals import *
from projectile import Projectile

class Cannon:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 20
        self.color = (128, 128, 128)  # Gray color for the cannon
        self.projectiles = []

    def draw(self, surface):
        # Draw the cannon as a circle
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

        # Draw projectiles
        for projectile in self.projectiles:
            projectile.draw(surface)

    def shoot(self):
        # Add a new projectile starting from the cannon's position
        self.projectiles.append(Projectile(self.x, self.y, 0, -5))  # Shoots upward

    def update(self):
        # Update all projectiles
        for projectile in self.projectiles:
            projectile.update()

        # Remove projectiles that go off-screen
        self.projectiles = [p for p in self.projectiles if p.y > 0]