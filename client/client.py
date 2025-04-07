import socket
import threading
import json
import time
import pygame
from pygame.locals import *
import sys
import random
import math

# Game constants
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
GRID_SIZE = 50
PLAYER_RADIUS = 20
PLAYER_MAX_HEALTH = 100

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# Network settings
DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 5555
BUFFER_SIZE = 4096

class Player:
    def __init__(self, x, y, color, player_id):
        self.x = x
        self.y = y
        self.color = color
        self.id = player_id
        self.health = PLAYER_MAX_HEALTH
        self.speed = 5
        self.dash_cooldown = 0
        self.is_dashing = False
        self.alive = True
        self.has_cannon = False
        self.cannon_id = None
        self.dash_direction = (0, 0)
    
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
        if 'dash_cooldown' in data:
            self.dash_cooldown = data['dash_cooldown']
    
    def draw(self, surface):
        if not self.alive:
            return
            
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        # Draw health bar
        health_width = 40 * (self.health / PLAYER_MAX_HEALTH)
        pygame.draw.rect(surface, RED, (self.x - 20, self.y - 30, 40, 5))
        pygame.draw.rect(surface, GREEN, (self.x - 20, self.y - 30, health_width, 5))

class Cannon:
    def __init__(self, data):
        self.id = data['id']
        self.x = data['x']
        self.y = data['y']
        self.type = data['type']
        self.shots_left = data['shots_left']
        self.controlled_by = data.get('controlled_by')
        self.color = tuple(data['color']) if isinstance(data['color'], list) else data['color']
    
    def update(self, data):
        """Update cannon state from server data"""
        if 'x' in data:
            self.x = data['x']
        if 'y' in data:
            self.y = data['y']
        if 'shots_left' in data:
            self.shots_left = data['shots_left']
        if 'controlled_by' in data:
            self.controlled_by = data['controlled_by']
    
    def draw(self, surface):
        # Draw cannon
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), 15)
        if self.controlled_by is None:
            # Draw indicator for available cannon
            pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), 20, 2)
        
        # Draw shots left if cannon is being used
        if self.controlled_by is not None:
            font = pygame.font.SysFont(None, 24)
            text = font.render(str(self.shots_left), True, WHITE)
            surface.blit(text, (self.x - text.get_width() // 2, self.y - text.get_height() // 2))

class Projectile:
    def __init__(self, data):
        self.id = data['id']
        self.x = data['x']
        self.y = data['y']
        self.dx = data['dx']
        self.dy = data['dy']
        self.radius = data['radius']
        self.color = tuple(data['color']) if isinstance(data['color'], list) else data['color']
    
    def update(self, data):
        """Update projectile state from server data"""
        if 'x' in data:
            self.x = data['x']
        if 'y' in data:
            self.y = data['y']
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

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

class Obstacle:
    def __init__(self, data):
        self.x = data['x']
        self.y = data['y']
        self.width = data['width']
        self.height = data['height']
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
    
    def draw(self, surface):
        pygame.draw.rect(surface, BLUE, self.rect)

class GameClient:
    def __init__(self, server_address=DEFAULT_SERVER, port=DEFAULT_PORT):
        self.last_ping_time = 0
        self.ping_interval = 5  # seconds
        self.ping_sent_time = 0
        self.latency_ms = None
        # Initialize pygame
        pygame.init()
        self.window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Cannon Chaos - Client")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        self.small_font = pygame.font.SysFont(None, 24)
        
        # Network settings
        self.server_address = server_address
        self.port = port
        self.socket = None
        self.connected = False
        self.client_id = None
        
        # Game state
        self.players = {}
        self.local_player = None
        self.cannons = {}
        self.projectiles = {}
        self.powerups = {}
        self.obstacles = []
        
        # Game settings
        self.running = False
        self.game_started = False
        self.sudden_death = False
        self.sudden_death_timer = 120
        self.last_update_time = 0
        self.game_over = False
        self.winner_id = None
        self.messages = []
        self.message_timeout = 3  # seconds
        
        # Player input state
        self.input_x = 0
        self.input_y = 0
        self.last_send_time = 0
        self.input_update_rate = 0.05  # 20 updates per second
    
    def connect_to_server(self):
        """Connect to the game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_address, self.port))
            
            # Generate a random color for this player
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            
            # Send player registration
            registration = {
                'client_id': f"player_{random.randint(1000, 9999)}",
                'color': color
            }
            self.socket.sendall(json.dumps(registration).encode('utf-8'))
            
            # Start listening for server messages
            self.connected = True
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return False
    
    def receive_messages(self):
        """Listen for messages from the server"""
        while self.connected:
            try:
                data = self.socket.recv(BUFFER_SIZE)
                if not data:
                    self.disconnect()
                    break
                
                try:
                    message = json.loads(data.decode('utf-8'))
                    self.handle_server_message(message)
                except json.JSONDecodeError:
                    print("Invalid JSON received from server")
                except Exception as e:
                    print(f"Error processing server message: {e}")
            
            except ConnectionError:
                self.disconnect()
                break
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.disconnect()
                break
    
    def handle_server_message(self, message):
        """Process messages from the server"""
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'init':
            # Initial game state
            self.client_id = data.get('client_id')
            
            # Process players
            for player_id, player_data in data.get('players', {}).items():
                if player_id not in self.players:
                    color = tuple(player_data['color']) if isinstance(player_data['color'], list) else player_data['color']
                    self.players[player_id] = Player(player_data['x'], player_data['y'], color, player_id)
                    if player_id == self.client_id:
                        self.local_player = self.players[player_id]
                else:
                    self.players[player_id].update(player_data)
            
            # Process obstacles
            for obstacle_data in data.get('obstacles', []):
                self.obstacles.append(Obstacle(obstacle_data))
        
        elif msg_type == 'game_update':
            # Update game state
            
            # Update players
            for player_id, player_data in data.get('players', {}).items():
                if player_id not in self.players:
                    color = tuple(player_data['color']) if isinstance(player_data['color'], list) else player_data['color']
                    self.players[player_id] = Player(player_data['x'], player_data['y'], color, player_id)
                    if player_id == self.client_id:
                        self.local_player = self.players[player_id]
                else:
                    self.players[player_id].update(player_data)
            
            # Update cannons
            current_cannons = set()
            for cannon_data in data.get('cannons', []):
                cannon_id = cannon_data['id']
                current_cannons.add(cannon_id)
                
                if cannon_id not in self.cannons:
                    self.cannons[cannon_id] = Cannon(cannon_data)
                else:
                    self.cannons[cannon_id].update(cannon_data)
            
            # Remove cannons that no longer exist
            for cannon_id in list(self.cannons.keys()):
                if cannon_id not in current_cannons:
                    del self.cannons[cannon_id]
            
            # Update projectiles
            current_projectiles = set()
            for projectile_data in data.get('projectiles', []):
                projectile_id = projectile_data['id']
                current_projectiles.add(projectile_id)
                
                if projectile_id not in self.projectiles:
                    self.projectiles[projectile_id] = Projectile(projectile_data)
                else:
                    self.projectiles[projectile_id].update(projectile_data)
            
            # Remove projectiles that no longer exist
            for projectile_id in list(self.projectiles.keys()):
                if projectile_id not in current_projectiles:
                    del self.projectiles[projectile_id]
            
            # Update powerups
            current_powerups = set()
            for powerup_data in data.get('powerups', []):
                powerup_id = powerup_data['id']
                current_powerups.add(powerup_id)
                
                if powerup_id not in self.powerups:
                    self.powerups[powerup_id] = PowerUp(powerup_data)
            
            # Remove powerups that no longer exist
            for powerup_id in list(self.powerups.keys()):
                if powerup_id not in current_powerups:
                    del self.powerups[powerup_id]
            
            # Update game settings
            if 'sudden_death' in data:
                self.sudden_death = data['sudden_death']
            if 'sudden_death_timer' in data:
                self.sudden_death_timer = data['sudden_death_timer']
        
        elif msg_type == 'game_start':
            self.game_started = True
            self.add_message("Game starting!")
        
        elif msg_type == 'cannon_spawn':
            cannon_data = data.get('cannon')
            if cannon_data:
                cannon_id = cannon_data['id']
                self.cannons[cannon_id] = Cannon(cannon_data)
                self.add_message(f"New {cannon_data['type']} cannon spawned!")
        
        elif msg_type == 'cannon_pickup':
            cannon_id = data.get('cannon_id')
            player_id = data.get('player_id')
            
            if cannon_id in self.cannons and player_id in self.players:
                self.cannons[cannon_id].controlled_by = player_id
                if player_id == self.client_id:
                    self.add_message("You picked up a cannon!")
                else:
                    self.add_message(f"Player grabbed a cannon!")
        
        elif msg_type == 'cannon_shot':
            projectile_data = data.get('projectile')
            if projectile_data:
                projectile_id = projectile_data['id']
                self.projectiles[projectile_id] = Projectile(projectile_data)
        
        elif msg_type == 'player_hit':
            player_id = data.get('player_id')
            damage = data.get('damage')
            
            if player_id == self.client_id:
                self.add_message(f"You took {damage} damage!")
        
        elif msg_type == 'player_eliminated':
            player_id = data.get('player_id')
            eliminator_id = data.get('eliminator_id')
            
            if player_id in self.players:
                if player_id == self.client_id:
                    self.add_message("You were eliminated!")
                elif eliminator_id == self.client_id:
                    self.add_message("You eliminated a player!")
                else:
                    self.add_message("A player was eliminated!")
        
        elif msg_type == 'powerup_spawn':
            powerup_data = data.get('powerup')
            if powerup_data:
                powerup_id = powerup_data['id']
                self.powerups[powerup_id] = PowerUp(powerup_data)
        
        elif msg_type == 'powerup_pickup':
            powerup_id = data.get('powerup_id')
            player_id = data.get('player_id')
            powerup_type = data.get('type')
            
            if powerup_id in self.powerups and player_id in self.players:
                if player_id == self.client_id:
                    if powerup_type == 'HEALTH':
                        self.add_message("You picked up a health boost!")
                    elif powerup_type == 'SPEED':
                        self.add_message("You picked up a speed boost!")
                
                # Remove powerup
                if powerup_id in self.powerups:
                    del self.powerups[powerup_id]
        
        elif msg_type == 'sudden_death':
            self.sudden_death = True
            self.add_message("SUDDEN DEATH MODE ACTIVATED!")
        
        elif msg_type == 'game_over':
            self.game_over = True
            self.winner_id = data.get('winner_id')
            
            if self.winner_id == self.client_id:
                self.add_message("You won the game!")
            else:
                self.add_message("Game over!")
        
        elif msg_type == 'game_reset':
            self.game_over = False
            self.winner_id = None
            self.sudden_death = False
            self.add_message("New game starting!")
        
        elif msg_type == 'player_left':
            player_id = data.get('player_id')
            
            if player_id in self.players:
                del self.players[player_id]
                self.add_message("A player left the game.")

        elif msg_type == 'pong':
            now = time.time()
            rtt = (now - self.ping_sent_time) * 1000  # Round-trip time in ms
            self.latency_ms = int(rtt)
    
    def send_update(self):
        """Send player update to server"""
        if not self.connected or not self.local_player or not self.local_player.alive:
            return
        
        current_time = time.time()
        if current_time - self.last_send_time < self.input_update_rate:
            return  # Throttle updates
        
        # Calculate new position
        player_x = self.local_player.x + self.input_x * self.local_player.speed
        player_y = self.local_player.y + self.input_y * self.local_player.speed
        
        # Check for collisions with walls
        player_x = max(PLAYER_RADIUS, min(WINDOW_WIDTH - PLAYER_RADIUS, player_x))
        player_y = max(PLAYER_RADIUS, min(WINDOW_HEIGHT - PLAYER_RADIUS, player_y))
        
        # Check for collisions with obstacles
        collision = False
        for obstacle in self.obstacles:
            if (obstacle.x - PLAYER_RADIUS <= player_x <= obstacle.x + obstacle.width + PLAYER_RADIUS and
                obstacle.y - PLAYER_RADIUS <= player_y <= obstacle.y + obstacle.height + PLAYER_RADIUS):
                collision = True
                break
        
        if not collision and (self.input_x != 0 or self.input_y != 0):
            # Send update to server
            update = {
                'type': 'player_update',
                'data': {
                    'x': player_x,
                    'y': player_y,
                    'dash_cooldown': self.local_player.dash_cooldown
                }
            }
            
            try:
                self.socket.sendall(json.dumps(update).encode('utf-8'))
                self.last_send_time = current_time
            except Exception as e:
                print(f"Error sending update: {e}")
                self.disconnect()
    
    def try_pickup_cannon(self):
        """Attempt to pick up a nearby cannon"""
        if not self.connected or not self.local_player or not self.local_player.alive or self.local_player.has_cannon:
            return
        
        for cannon_id, cannon in self.cannons.items():
            if cannon.controlled_by is None:
                # Check if player is close enough to pick up cannon
                dx = self.local_player.x - cannon.x
                dy = self.local_player.y - cannon.y
                distance = (dx*dx + dy*dy) ** 0.5
                
                if distance < PLAYER_RADIUS + 20:
                    # Send pickup request to server
                    message = {
                        'type': 'cannon_pickup',
                        'cannon_id': cannon_id
                    }
                    
                    try:
                        self.socket.sendall(json.dumps(message).encode('utf-8'))
                    except Exception as e:
                        print(f"Error sending pickup request: {e}")
                        self.disconnect()
                    
                    return
    
    def try_shoot_cannon(self, target_x, target_y):
        """Attempt to shoot with the equipped cannon"""
        if (not self.connected or not self.local_player or 
            not self.local_player.alive or not self.local_player.has_cannon):
            return
        
        # Send shoot request to server
        message = {
            'type': 'cannon_shoot',
            'target_x': target_x,
            'target_y': target_y
        }
        
        try:
            self.socket.sendall(json.dumps(message).encode('utf-8'))
        except Exception as e:
            print(f"Error sending shoot request: {e}")
            self.disconnect()
    
    def try_dash(self):
        """Attempt to use dash ability"""
        if (not self.connected or not self.local_player or 
            not self.local_player.alive or self.local_player.dash_cooldown > 0 or
            (self.input_x == 0 and self.input_y == 0)):
            return
        
        # Send dash request to server
        message = {
            'type': 'dash',
            'dx': self.input_x,
            'dy': self.input_y
        }
        
        try:
            self.socket.sendall(json.dumps(message).encode('utf-8'))
            self.local_player.dash_cooldown = 2  # Local prediction
        except Exception as e:
            print(f"Error sending dash request: {e}")
            self.disconnect()
    
    def add_message(self, text):
        """Add a message to the message queue"""
        self.messages.append({
            'text': text,
            'time': time.time()
        })
    
    def update_messages(self):
        """Update message display times and remove old messages"""
        current_time = time.time()
        self.messages = [msg for msg in self.messages if current_time - msg['time'] < self.message_timeout]
    
    def handle_input(self):
        """Handle user input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            
            # Mouse clicks for shooting
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
                mouse_x, mouse_y = pygame.mouse.get_pos()
                self.try_shoot_cannon(mouse_x, mouse_y)
            
            # Space for dash
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.try_dash()
            
            # E for picking up cannons
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self.try_pickup_cannon()
        
        # Handle continuous movement inputs
        keys = pygame.key.get_pressed()
        self.input_x = 0
        self.input_y = 0
        
        if keys[K_LEFT] or keys[K_a]:
            self.input_x = -1
        if keys[K_RIGHT] or keys[K_d]:
            self.input_x = 1
        if keys[K_UP] or keys[K_w]:
            self.input_y = -1
        if keys[K_DOWN] or keys[K_s]:
            self.input_y = 1
        
        # Normalize diagonal movement
        if self.input_x != 0 and self.input_y != 0:
            self.input_x *= 0.7071  # 1/sqrt(2)
            self.input_y *= 0.7071
    
    def draw(self):
        """Render the game state"""
        # Clear the screen
        self.window.fill(BLACK)
        
        # Draw obstacles
        for obstacle in self.obstacles:
            obstacle.draw(self.window)
        
        # Draw powerups
        for powerup_id, powerup in self.powerups.items():
            powerup.draw(self.window)
        
        # Draw cannons
        for cannon_id, cannon in self.cannons.items():
            cannon.draw(self.window)
        
        # Draw players
        for player_id, player in self.players.items():
            player.draw(self.window)
        
        # Draw projectiles
        for projectile_id, projectile in self.projectiles.items():
            projectile.draw(self.window)
        
        # Ensure the local player is initialized for testing
        if not self.local_player:
            self.local_player = Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2, (255, 0, 0), "test_player")

        # Draw the local player
        if self.local_player:
            self.local_player.draw(self.window)
        
        # Draw UI elements
        if self.sudden_death:
            text = self.font.render("SUDDEN DEATH", True, RED)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, 10))
        else:
            # Draw timer until sudden death
            minutes = max(0, int(self.sudden_death_timer // 60))
            seconds = max(0, int(self.sudden_death_timer % 60))
            text = self.font.render(f"Sudden Death: {minutes}:{seconds:02d}", True, WHITE)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, 10))
        
        # Draw player count
        max_players = 4  
        alive_players = sum(1 for player in self.players.values() if player.alive)
        text = self.small_font.render(f"Players: {alive_players}/{max_players}", True, WHITE)
        self.window.blit(text, (10, 10))

        if self.latency_ms is not None:
            text = self.small_font.render(f"Ping: {self.latency_ms} ms", True, WHITE)
            self.window.blit(text, (10, 30))
        
        # Draw controls help
        text = self.small_font.render("WASD: Move | E: Pick up cannon | SPACE: Dash | Click: Shoot", True, WHITE)
        self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, WINDOW_HEIGHT - 30))
        
        # Draw messages
        message_y = 50
        for message in self.messages:
            text = self.small_font.render(message['text'], True, WHITE)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, message_y))
            message_y += 25
        
        # Draw game over screen
        if self.game_over:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))  # Semi-transparent black
            self.window.blit(overlay, (0, 0))
            
            if self.winner_id == self.client_id:
                text = self.font.render("YOU WIN!", True, GREEN)
            else:
                text = self.font.render("GAME OVER", True, RED)
            
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, WINDOW_HEIGHT//2 - text.get_height()//2))
            
            text = self.small_font.render("New game starting soon...", True, WHITE)
            self.window.blit(text, (WINDOW_WIDTH//2 - text.get_width()//2, WINDOW_HEIGHT//2 + 50))
        
        # Update display
        pygame.display.update()
    
    def update(self):
        """Update game state"""
        delta_time = self.clock.get_time() / 1000.0  # Convert to seconds
        
        # Update messages
        self.update_messages()
        
        # Update player if we're still playing
        if self.connected and self.local_player and self.local_player.alive:
            # Update dash cooldown
            if self.local_player.dash_cooldown > 0:
                self.local_player.dash_cooldown = max(0, self.local_player.dash_cooldown - delta_time)
            
            # Send position updates to server
            self.send_update()

        # Simplify game logic to focus on player loading and movement
        if self.local_player and self.local_player.alive:
            self.local_player.x += self.input_x * self.local_player.speed
            self.local_player.y += self.input_y * self.local_player.speed

            # Ensure the player stays within the window bounds
            self.local_player.x = max(PLAYER_RADIUS, min(WINDOW_WIDTH - PLAYER_RADIUS, self.local_player.x))
            self.local_player.y = max(PLAYER_RADIUS, min(WINDOW_HEIGHT - PLAYER_RADIUS, self.local_player.y))

        current_time = time.time()
        if current_time - self.last_ping_time > self.ping_interval:
            self.last_ping_time = current_time
            self.ping_sent_time = current_time
            try:
                self.socket.sendall(json.dumps({'type': 'ping'}).encode('utf-8'))
            except Exception as e:
                print(f"Error sending ping: {e}")

        # Start sudden death timer countdown
        if self.sudden_death_timer > 0:
            self.sudden_death_timer -= delta_time

        # Ensure sudden death mode activates when timer reaches zero
        if self.sudden_death_timer <= 0 and not self.sudden_death:
            self.sudden_death = True
    
    def disconnect(self):
        """Disconnect from the server"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        self.add_message("Disconnected from server.")
    
    def run(self):
        """Main game loop"""
        # Connect to the server
        if not self.connect_to_server():
            print("Failed to connect to server.")
            return
        
        self.running = True
        while self.running:
            # Handle user input
            self.handle_input()
            
            # Update game state
            self.update()
            
            # Render the game
            self.draw()
            
            # Cap the frame rate
            self.clock.tick(60)
        
        # Clean up
        self.disconnect()
        pygame.quit()

if __name__ == "__main__":
    # Get server address from command line args if provided
    server_address = DEFAULT_SERVER
    if len(sys.argv) > 1:
        server_address = sys.argv[1]
    
    client = GameClient(server_address)
    client.run()