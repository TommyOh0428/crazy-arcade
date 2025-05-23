import pygame
from pygame.locals import *
import time

# Colors
RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
ORANGE = (255, 165, 0) 

# Constants
PLAYER_RADIUS = 20
PLAYER_MAX_HEALTH = 100
PLAYER_NORMAL_SPEED = 5
PLAYER_BOOST_SPEED = 7.5 

class Player:
    def __init__(self, x, y, color, player_id, name="Player"):
        self.x = x
        self.y = y
        self.color = color
        self.id = player_id
        self.name = name  
        self.health = PLAYER_MAX_HEALTH
        self.speed = PLAYER_NORMAL_SPEED
        self.alive = True
        self.has_cannon = False
        self.cannon_id = None
        self.cannon_use_timer = 0 
        self.speed_boosted = False
        self.speed_boost_end_time = 0
        self.boost_particles = []
        self.font = pygame.font.SysFont(None, 24)
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
        if 'name' in data:
            self.name = data['name']
        
        # check for speed boost timeout
        current_time = time.time()
        if self.speed_boosted and current_time > self.speed_boost_end_time:
            self.speed_boosted = False
            self.speed = PLAYER_NORMAL_SPEED
        
        # reset cannon timer if player no longer has a cannon
        if not self.has_cannon:
            self.cannon_use_timer = 0
    
    def apply_speed_boost(self):
        """Apply speed boost for 10 seconds"""
        self.speed_boosted = True
        self.speed = PLAYER_BOOST_SPEED
        self.speed_boost_end_time = time.time() + 10 
    def draw(self, surface):
        if not self.alive:
            return
        
        # Draw player
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        
        # Draw name above health bar
        name_text = self.font.render(self.name, True, WHITE)
        name_width = name_text.get_width()
        surface.blit(name_text, (self.x - name_width // 2, self.y - 50))
        
        # Draw health bar
        health_width = 40 * (self.health / PLAYER_MAX_HEALTH)
        pygame.draw.rect(surface, RED, (self.x - 20, self.y - 30, 40, 5))
        pygame.draw.rect(surface, GREEN, (self.x - 20, self.y - 30, health_width, 5))
          # Draw speed boost indicator if active
        if self.speed_boosted:
            time_remaining = self.speed_boost_end_time - time.time()
            if time_remaining > 0:
                # Draw a yellow ring around the player
                pygame.draw.circle(surface, YELLOW, (int(self.x), int(self.y)), PLAYER_RADIUS + 3, 2)
                
                # Draw boost timer indicator
                boost_width = 40 * (time_remaining / 10)
                pygame.draw.rect(surface, YELLOW, (self.x - 20, self.y - 25, boost_width, 3))
        
        # Draw cannon timer indicator if player has a cannon
        if self.has_cannon and hasattr(self, 'cannon_use_timer'):
            # Calculate remaining time (10 seconds max before explosion)
            time_remaining = 10 - self.cannon_use_timer
            if time_remaining > 0:
                # Draw an orange ring around the player
                pygame.draw.circle(surface, ORANGE, (int(self.x), int(self.y)), PLAYER_RADIUS + 6, 2)
                
                # Draw cannon timer indicator
                # If speed boost is active, position the cannon timer below it
                y_offset = -20 if self.speed_boosted else -25
                cannon_width = 40 * (time_remaining / 10)
                pygame.draw.rect(surface, ORANGE, (self.x - 20, self.y + y_offset, cannon_width, 3))