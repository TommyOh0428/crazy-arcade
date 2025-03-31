import pygame
from pygame.locals import *
import sys
import random
import math
import time

# Game constants
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
GRID_SIZE = 50
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# Player constants
PLAYER_SPEED = 5
DASH_SPEED = 15
DASH_COOLDOWN = 2  # seconds
PLAYER_RADIUS = 20
PLAYER_MAX_HEALTH = 100

# Cannon constants
CANNON_TYPES = {
    "RAPID": {"damage": 10, "speed": 12, "cooldown": 0.3, "shots": 10, "radius": 5, "color": RED},
    "EXPLOSIVE": {"damage": 30, "speed": 6, "cooldown": 1.0, "shots": 3, "radius": 15, "color": YELLOW},
    "BOUNCING": {"damage": 15, "speed": 8, "cooldown": 0.7, "shots": 5, "radius": 8, "color": GREEN}
}
CANNON_USE_TIME = 10  # seconds before cannon explodes if not used

class Player:
    def __init__(self, x, y, color, player_id):
        self.x = x
        self.y = y
        self.color = color
        self.id = player_id
        self.health = PLAYER_MAX_HEALTH
        self.speed = PLAYER_SPEED
        self.dash_cooldown = 0
        self.is_dashing = False
        self.alive = True
        self.has_cannon = False
        self.cannon = None
        self.dash_direction = (0, 0)
    
    def move(self, dx, dy, obstacles):
        # Calculate new position
        new_x = self.x + dx * self.speed
        new_y = self.y + dy * self.speed
        
        # Check for collisions with walls
        if 0 <= new_x <= WINDOW_WIDTH and 0 <= new_y <= WINDOW_HEIGHT:
            # Check for collisions with obstacles
            can_move = True
            for obstacle in obstacles:
                if obstacle.collides_with_point(new_x, new_y, PLAYER_RADIUS):
                    can_move = False
                    break
            
            if can_move:
                self.x = new_x
                self.y = new_y
    
    def dash(self, dx, dy):
        if self.dash_cooldown <= 0 and (dx != 0 or dy != 0):
            self.speed = DASH_SPEED
            self.is_dashing = True
            self.dash_cooldown = DASH_COOLDOWN
            self.dash_direction = (dx, dy)
            return True
        return False
    
    def update(self, delta_time, obstacles):
        # Update dash cooldown
        if self.dash_cooldown > 0:
            self.dash_cooldown -= delta_time
        
        # Reset speed after dash
        if self.is_dashing:
            self.is_dashing = False
            self.speed = PLAYER_SPEED
        
        # Handle cannon control
        if self.has_cannon and self.cannon:
            self.cannon.x = self.x
            self.cannon.y = self.y
    
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.alive = False
            self.health = 0
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        # Draw health bar
        health_width = 40 * (self.health / PLAYER_MAX_HEALTH)
        pygame.draw.rect(surface, RED, (self.x - 20, self.y - 30, 40, 5))
        pygame.draw.rect(surface, GREEN, (self.x - 20, self.y - 30, health_width, 5))

class Cannon:
    def __init__(self, x, y, cannon_type):
        self.x = x
        self.y = y
        self.type = cannon_type
        self.properties = CANNON_TYPES[cannon_type]
        self.shots_left = self.properties["shots"]
        self.last_shot_time = 0
        self.controlled_by = None
        self.spawn_time = time.time()
        self.use_timer = 0
    
    def can_shoot(self):
        current_time = time.time()
        return (current_time - self.last_shot_time >= self.properties["cooldown"] and 
                self.shots_left > 0 and 
                self.controlled_by is not None)
    
    def shoot(self, target_x, target_y, projectiles):
        if self.can_shoot():
            # Calculate direction
            dx = target_x - self.x
            dy = target_y - self.y
            distance = max(1, math.sqrt(dx * dx + dy * dy))
            dx /= distance
            dy /= distance
            
            # Create projectile
            projectile = Projectile(
                self.x, self.y, 
                dx * self.properties["speed"], 
                dy * self.properties["speed"],
                self.properties["damage"],
                self.properties["radius"],
                self.properties["color"],
                self.type == "BOUNCING"
            )
            projectiles.append(projectile)
            
            # Update cannon state
            self.shots_left -= 1
            self.last_shot_time = time.time()
            self.use_timer = 0  # Reset explosion timer when used
            
            return True
        return False
    
    def update(self, delta_time):
        # Update explosion timer if cannon is controlled but not used
        if self.controlled_by is not None:
            self.use_timer += delta_time
            if self.use_timer >= CANNON_USE_TIME:
                # Explode cannon and damage controlling player
                if self.controlled_by:
                    self.controlled_by.take_damage(50)
                    self.controlled_by.has_cannon = False
                    self.controlled_by = None
                return True  # Cannon exploded
        
        # Check if cannon is out of shots
        if self.shots_left <= 0 and self.controlled_by:
            self.controlled_by.has_cannon = False
            self.controlled_by = None
            return True  # Cannon is depleted
        
        return False  # Cannon is still active
    
    def draw(self, surface):
        # Draw cannon
        pygame.draw.circle(surface, self.properties["color"], (int(self.x), int(self.y)), 15)
        if self.controlled_by is None:
            # Draw indicator for available cannon
            pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), 20, 2)

class Projectile:
    def __init__(self, x, y, dx, dy, damage, radius, color, can_bounce=False):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.damage = damage
        self.radius = radius
        self.color = color
        self.can_bounce = can_bounce
        self.bounces = 3 if can_bounce else 0
    
    def update(self, obstacles):
        # Update position
        self.x += self.dx
        self.y += self.dy
        
        # Check if out of bounds
        if self.x < 0 or self.x > WINDOW_WIDTH or self.y < 0 or self.y > WINDOW_HEIGHT:
            if self.can_bounce and self.bounces > 0:
                # Bounce off walls
                if self.x < 0 or self.x > WINDOW_WIDTH:
                    self.dx = -self.dx
                if self.y < 0 or self.y > WINDOW_HEIGHT:
                    self.dy = -self.dy
                self.bounces -= 1
                # Adjust position to be within bounds
                self.x = max(0, min(WINDOW_WIDTH, self.x))
                self.y = max(0, min(WINDOW_HEIGHT, self.y))
            else:
                return True  # Mark for removal
        
        # Check for collisions with obstacles
        for obstacle in obstacles:
            if obstacle.collides_with_point(self.x, self.y, self.radius):
                if self.can_bounce and self.bounces > 0:
                    # Simple bounce - reverse direction
                    self.dx = -self.dx
                    self.dy = -self.dy
                    self.bounces -= 1
                else:
                    return True  # Mark for removal
        
        return False  # Keep projectile active
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

class Obstacle:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
    
    def collides_with_point(self, x, y, radius=0):
        # Check if a point (with optional radius) collides with this obstacle
        expanded_rect = self.rect.inflate(radius*2, radius*2)
        return expanded_rect.collidepoint(x, y)
    
    def draw(self, surface):
        pygame.draw.rect(surface, BLUE, self.rect)

class PowerUp:
    def __init__(self, x, y, power_type):
        self.x = x
        self.y = y
        self.type = power_type
        self.radius = 10
        
        # Define powerup colors based on type
        self.colors = {
            "HEALTH": GREEN,
            "SPEED": YELLOW
        }
    
    def apply(self, player):
        if self.type == "HEALTH":
            player.health = min(player.health + 30, PLAYER_MAX_HEALTH)
        elif self.type == "SPEED":
            player.speed = PLAYER_SPEED * 1.5
            # This would need a timer to reset later
        return True
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.colors[self.type], (int(self.x), int(self.y)), self.radius)

class Game:
    def __init__(self):
        pygame.init()
        self.window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Cannon Chaos")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        
        # Game objects
        self.obstacles = self.generate_obstacles()
        self.player = Player(WINDOW_WIDTH//4, WINDOW_HEIGHT//2, RED, 1)
        self.players = [self.player]  # Will include network players later
        self.cannons = []
        self.projectiles = []
        self.powerups = []
        
        # Game state
        self.running = True
        self.cannon_spawn_timer = 0
        self.cannon_spawn_interval = 5  # seconds
        self.sudden_death = False
        self.sudden_death_timer = 120  # 2 minutes before sudden death
        
        # Spawn initial cannon
        self.spawn_cannon()
    
    def generate_obstacles(self):
        obstacles = []
        # Create a pattern of obstacles across the map
        for i in range(1, GRID_WIDTH-1):
            for j in range(1, GRID_HEIGHT-1):
                if (i + j) % 3 == 0:  # Create a pattern
                    obstacles.append(Obstacle(i * GRID_SIZE, j * GRID_SIZE, GRID_SIZE, GRID_SIZE))
        return obstacles
    
    def spawn_cannon(self):
        # Find a position not occupied by obstacles
        while True:
            x = random.randint(GRID_SIZE, WINDOW_WIDTH - GRID_SIZE)
            y = random.randint(GRID_SIZE, WINDOW_HEIGHT - GRID_SIZE)
            
            # Check for collision with obstacles
            collision = False
            for obstacle in self.obstacles:
                if obstacle.collides_with_point(x, y, 20):
                    collision = True
                    break
            
            if not collision:
                # Choose a random cannon type
                cannon_type = random.choice(list(CANNON_TYPES.keys()))
                self.cannons.append(Cannon(x, y, cannon_type))
                break
    
    def spawn_powerup(self, x, y):
        power_type = random.choice(["HEALTH", "SPEED"])
        self.powerups.append(PowerUp(x, y, power_type))
    
    def handle_input(self):
        keys = pygame.key.get_pressed()
        
        # Movement
        dx, dy = 0, 0
        if keys[K_LEFT] or keys[K_a]:
            dx = -1
        if keys[K_RIGHT] or keys[K_d]:
            dx = 1
        if keys[K_UP] or keys[K_w]:
            dy = -1
        if keys[K_DOWN] or keys[K_s]:
            dy = 1
        
        # Normalize diagonal movement
        if dx != 0 and dy != 0:
            dx *= 0.7071  # 1/sqrt(2)
            dy *= 0.7071
        
        # Apply movement
        self.player.move(dx, dy, self.obstacles)
        
        # Dash ability
        if keys[K_SPACE] and (dx != 0 or dy != 0):
            self.player.dash(dx, dy)
        
        # Shooting
        if pygame.mouse.get_pressed()[0] and self.player.has_cannon:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.player.cannon.shoot(mouse_x, mouse_y, self.projectiles)
    
    def check_cannon_pickup(self):
        for player in self.players:
            if not player.has_cannon:
                for cannon in self.cannons[:]:
                    if cannon.controlled_by is None:
                        # Check if player is close enough to pick up cannon
                        distance = math.sqrt((player.x - cannon.x)**2 + (player.y - cannon.y)**2)
                        if distance < PLAYER_RADIUS + 20:
                            # Player gets control of the cannon
                            cannon.controlled_by = player
                            player.has_cannon = True
                            player.cannon = cannon
    
    def check_powerup_pickup(self):
        for player in self.players:
            for powerup in self.powerups[:]:
                # Check if player is close enough to pick up powerup
                distance = math.sqrt((player.x - powerup.x)**2 + (player.y - powerup.y)**2)
                if distance < PLAYER_RADIUS + powerup.radius:
                    if powerup.apply(player):
                        self.powerups.remove(powerup)
    
    def check_projectile_hits(self):
        for projectile in self.projectiles[:]:
            # Check for collisions with players
            for player in self.players:
                if player.alive:
                    distance = math.sqrt((player.x - projectile.x)**2 + (player.y - projectile.y)**2)
                    if distance < PLAYER_RADIUS + projectile.radius:
                        player.take_damage(projectile.damage)
                        
                        # Spawn powerup if player is eliminated
                        if not player.alive:
                            self.spawn_powerup(player.x, player.y)
                        
                        # Remove projectile
                        if projectile in self.projectiles:
                            self.projectiles.remove(projectile)
                        break
    
    def update(self):
        delta_time = self.clock.get_time() / 1000.0  # Convert to seconds
        
        # Update timers
        self.cannon_spawn_timer += delta_time
        self.sudden_death_timer -= delta_time
        
        # Check for sudden death mode
        if self.sudden_death_timer <= 0 and not self.sudden_death:
            self.sudden_death = True
            # Implement sudden death effects here
        
        # Spawn new cannon if needed
        if self.cannon_spawn_timer >= self.cannon_spawn_interval:
            self.spawn_cannon()
            self.cannon_spawn_timer = 0
        
        # Update game objects
        for player in self.players:
            player.update(delta_time, self.obstacles)
        
        # Update cannons and remove depleted ones
        for cannon in self.cannons[:]:
            if cannon.update(delta_time):
                self.cannons.remove(cannon)
        
        # Update projectiles and remove those that are out of bounds
        for projectile in self.projectiles[:]:
            if projectile.update(self.obstacles):
                self.projectiles.remove(projectile)
        
        # Check for cannon pickups
        self.check_cannon_pickup()
        
        # Check for powerup pickups
        self.check_powerup_pickup()
        
        # Check for projectile hits
        self.check_projectile_hits()
        
        # Check win condition
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) <= 1 and len(self.players) > 1:
            # Game over logic here
            pass
    
    def draw(self):
        # Clear the screen
        self.window.fill(BLACK)
        
        # Draw obstacles
        for obstacle in self.obstacles:
            obstacle.draw(self.window)
        
        # Draw cannons
        for cannon in self.cannons:
            cannon.draw(self.window)
        
        # Draw projectiles
        for projectile in self.projectiles:
            projectile.draw(self.window)
        
        # Draw powerups
        for powerup in self.powerups:
            powerup.draw(self.window)
        
        # Draw players
        for player in self.players:
            if player.alive:
                player.draw(self.window)
        
        # Draw UI elements
        if self.sudden_death:
            text = self.font.render("SUDDEN DEATH", True, RED)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, 10))
        else:
            # Draw timer until sudden death
            minutes = int(self.sudden_death_timer // 60)
            seconds = int(self.sudden_death_timer % 60)
            text = self.font.render(f"Sudden Death: {minutes}:{seconds:02d}", True, WHITE)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, 10))
        
        # Update display
        pygame.display.update()
    
    def run(self):
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    sys.exit()
            
            # Handle player input
            self.handle_input()
            
            # Update game state
            self.update()
            
            # Render the game
            self.draw()
            
            # Cap the frame rate
            self.clock.tick(60)

# Start the game
if __name__ == "__main__":
    game = Game()
    game.run()