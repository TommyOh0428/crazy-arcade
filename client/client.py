import socket
import threading
import json
import time
import pygame
from pygame.locals import *
import sys
import random
import math
from player import Player
from cannon import Cannon
from projectile import Projectile
from obstacle import Obstacle
from powerup import PowerUp
from text_input import TextInput

# Constants we need 
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
GRID_SIZE = 50
PLAYER_RADIUS = 20
PLAYER_MAX_HEALTH = 100

# colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# network config
DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 5555
BUFFER_SIZE = 4096

class GameClient:
    def __init__(self, server_address=DEFAULT_SERVER, port=DEFAULT_PORT):
        self.last_ping_time = 0
        self.ping_interval = 5  # seconds
        self.ping_sent_time = 0
        self.latency_ms = None
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
        self.player_name = self.get_player_name()  # Get player name before connecting
        
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
    
    def get_player_name(self):
        text_input = TextInput(max_length=15)
        background = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        background.fill(BLACK)
        
        title_font = pygame.font.SysFont(None, 48)
        title_text = title_font.render("Enter Your Name:", True, WHITE)
        title_rect = title_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 60))
        
        instruction_font = pygame.font.SysFont(None, 24)
        instruction_text = instruction_font.render("Press ENTER when done", True, WHITE)
        instruction_rect = instruction_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 40))
        
        name_entered = False
        default_name = f"Player_{random.randint(100, 999)}"
        
        while not name_entered:
            dt = self.clock.tick(30) / 1000.0 
            
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # Use default name if user presses escape
                    return default_name
            
            # Update text input and check if Enter was pressed
            if text_input.update(events, dt):
                name = text_input.get_text().strip() or default_name
                return name
            
            # background
            self.window.blit(background, (0, 0))
            # title
            self.window.blit(title_text, title_rect)
            # text box
            text_surface = text_input.get_surface()
            text_rect = text_surface.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2))
            
            # box around text input
            input_box_rect = pygame.Rect(text_rect)
            input_box_rect.inflate_ip(20, 10)
            pygame.draw.rect(self.window, WHITE, input_box_rect, 2)
            
            self.window.blit(text_surface, text_rect)
            self.window.blit(instruction_text, instruction_rect)
            
            pygame.display.update()
        
        return default_name
    
    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_address, self.port))
            
            # generate random client ID and remember it
            self.client_id = f"player_{random.randint(1000, 9999)}"
            
            # Generate random player color 
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            
            # Send player reg
            registration = {
                'client_id': self.client_id,  # Use our saved client_id
                'color': color,
                'name': self.player_name      # Send player name with registration
            }
            self.socket.sendall(json.dumps(registration).encode('utf-8'))
            
            # Pre-make our local player with the ID we've chosen
            # have a player to move regardless of server behavior
            print(f"PRE-CREATING local player with ID: {self.client_id}")
            x = random.randint(50, WINDOW_WIDTH - 50)
            y = random.randint(50, WINDOW_HEIGHT - 50)
            self.local_player = Player(x, y, color, self.client_id, self.player_name)
            self.players[self.client_id] = self.local_player
            
            # listening server messages
            self.connected = True
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return False
    
    def receive_messages(self):
        buffer = ""  # incomplete messages
        
        while self.connected:
            try:
                data = self.socket.recv(BUFFER_SIZE)
                if not data:
                    self.disconnect()
                    break
                
                buffer += data.decode('utf-8')
                
                while True:
                    try:
                        # try to parse a complete JSON message
                        message, buffer = self.extract_json(buffer)
                        if not message:
                            break  
                        
                        # Process the message
                        self.handle_server_message(message)
                    except json.JSONDecodeError:
                        break
                    except Exception as e:
                        print(f"Error processing server message: {e}")
                        break
            
            except ConnectionError:
                self.disconnect()
                break
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.disconnect()
                break
    
    def extract_json(self, buffer):
        try:
            # try to find a complete JSON object with proper message bound handling
            json_start = buffer.find('{')
            if json_start == -1:
                return None, buffer  # none found
            
            # where json object ends
            depth = 0
            for i in range(json_start, len(buffer)):
                if buffer[i] == '{':
                    depth += 1
                elif buffer[i] == '}':
                    depth -= 1
                    if depth == 0:
                        # found a complete JSON object
                        try:
                            obj = json.loads(buffer[json_start:i+1])
                            return obj, buffer[i+1:]  
                        except json.JSONDecodeError:
                            pass 
            
            # no complete JSON found
            return None, buffer
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return None, buffer
    
    def handle_server_message(self, message):
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'init':
            # initial game state
            self.client_id = data.get('client_id')
            print(f"Received init message with client_id: {self.client_id}")
            
            # Process players
            for player_id, player_data in data.get('players', {}).items():
                if player_id not in self.players:
                    color = tuple(player_data['color']) if isinstance(player_data['color'], list) else player_data['color']
                    self.players[player_id] = Player(player_data['x'], player_data['y'], color, player_id)
                    if player_id == self.client_id:
                        self.local_player = self.players[player_id]
                        print(f"LOCAL PLAYER SET: id={player_id}, pos=({self.local_player.x}, {self.local_player.y})")
                else:
                    self.players[player_id].update(player_data)
            
            # Check if local_player was set, if not this is a critical error
            if not self.local_player and self.client_id:
                print(f"CRITICAL ERROR: Local player not set despite having client_id={self.client_id}")
                print(f"Available players: {list(self.players.keys())}")
                
                # Force create local player if it doesn't exist but should
                if self.client_id not in self.players:
                    print(f"Creating local player manually with client_id={self.client_id}")
                    x = random.randint(50, WINDOW_WIDTH - 50)
                    y = random.randint(50, WINDOW_HEIGHT - 50)
                    color = (255, 0, 0)  # Bright red for visibility
                    self.players[self.client_id] = Player(x, y, color, self.client_id)
                    self.local_player = self.players[self.client_id]
                    
                    # Send this player to the server
                    self.send_update()
            
            # Process obstacles
            for obstacle_data in data.get('obstacles', []):
                self.obstacles.append(Obstacle(obstacle_data))
                
            # Process initial cannons if any
            for cannon_data in data.get('cannons', []):
                cannon_id = cannon_data.get('id', 'unknown')
                self.cannons[cannon_id] = Cannon(cannon_data)
                
        elif msg_type == 'game_update':
            # update game state and players
            for player_id, player_data in data.get('players', {}).items():
                if player_id not in self.players:
                    color = tuple(player_data['color']) if isinstance(player_data['color'], list) else player_data['color']
                    self.players[player_id] = Player(player_data['x'], player_data['y'], color, player_id)
                    if player_id == self.client_id:
                        self.local_player = self.players[player_id]
                else:
                    if player_id != self.client_id:
                        if hasattr(self.players[player_id], 'x') and hasattr(self.players[player_id], 'y'):
                            self.players[player_id].prev_x = self.players[player_id].x
                            self.players[player_id].prev_y = self.players[player_id].y
                            self.players[player_id].interp_start_time = time.time()
                        else:
                            self.players[player_id].prev_x = player_data['x']
                            self.players[player_id].prev_y = player_data['y']
                            self.players[player_id].interp_start_time = time.time()
                            
                        # Set target position from server
                        self.players[player_id].target_x = player_data['x']
                        self.players[player_id].target_y = player_data['y']
                        
                        # Update other properties immediately
                        player_copy = player_data.copy()
                        if 'x' in player_copy: del player_copy['x']
                        if 'y' in player_copy: del player_copy['y']
                        self.players[player_id].update(player_copy)
                    else:
                        # For local player, only update non-position properties
                        local_data = player_data.copy()
                        if 'x' in local_data: del local_data['x']
                        if 'y' in local_data: del local_data['y']
                        self.local_player.update(local_data)
              # Update cannons
            current_cannons = set()
            for cannon_data in data.get('cannons', []):
                cannon_id = cannon_data.get('id', 'unknown')
                current_cannons.add(cannon_id)
                
                if cannon_id not in self.cannons:
                    self.cannons[cannon_id] = Cannon(cannon_data)
                else:
                    self.cannons[cannon_id].update(cannon_data)
                    
                # If this cannon is controlled by a player, update the player's cannon timer
                controlled_by = cannon_data.get('controlled_by')
                if controlled_by and controlled_by in self.players:
                    self.players[controlled_by].cannon_use_timer = cannon_data.get('use_timer', 0)
            
            # Remove cannons that no longer exist
            for cannon_id in list(self.cannons.keys()):
                if cannon_id not in current_cannons:
                    del self.cannons[cannon_id]
            
            # Update projectiles, powerups and other state
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
                cannon_id = cannon_data.get('id', 'unknown')
                try:
                    self.cannons[cannon_id] = Cannon(cannon_data)
                    self.add_message(f"New {cannon_data.get('type', 'unknown')} cannon spawned!")
                except Exception as e:
                    pass 
        
        elif msg_type == 'cannon_pickup':
            cannon_id = data.get('cannon_id')
            player_id = data.get('player_id')
            
            if cannon_id in self.cannons and player_id in self.players:
                self.cannons[cannon_id].controlled_by = player_id
                
                # explicitly set the has_cannon flag on the player
                if player_id == self.client_id:
                    self.local_player.has_cannon = True
                    self.local_player.cannon_id = cannon_id
                    self.add_message("You picked up a cannon!")
                else:
                    self.players[player_id].has_cannon = True
                    self.players[player_id].cannon_id = cannon_id
                    self.add_message(f"Player grabbed a cannon!")
        
        elif msg_type == 'cannon_shot':
            projectile_data = data.get('projectile')
            if projectile_data:
                projectile_id = projectile_data['id']
                self.projectiles[projectile_id] = Projectile(projectile_data)

        elif msg_type == 'player_hit':
            player_id = data.get('player_id')
            damage = data.get('damage')
            is_sudden_death_kill = data.get('sudden_death_kill', False)
            
            if player_id == self.client_id:
                if is_sudden_death_kill:
                    self.add_message("You got one-shotted in SUDDEN DEATH!")
                else:
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
                        self.local_player.apply_speed_boost()
                        self.add_message("You picked up a speed boost! Moving 1.5x faster for 10 seconds!")
                else:
                    # apply speed boost to other players too so their movement is consistent
                    if powerup_type == 'SPEED':
                        self.players[player_id].apply_speed_boost()
                
                # remove powerup
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
            # Round-trip time in ms
            rtt = (now - self.ping_sent_time) * 1000  
            self.latency_ms = int(rtt)
    
    def send_update(self):
        if not self.connected or not self.local_player or not self.local_player.alive:
            return
        
        # Send current position to server
        update = {
            'type': 'player_update',
            'data': {
                'x': self.local_player.x,
                'y': self.local_player.y,
            }
        }
        
        try:
            self.socket.sendall(json.dumps(update).encode('utf-8'))
        except Exception as e:
            print(f"Error sending update: {e}")
            self.disconnect()
    
    def try_pickup_cannon(self):
        if not self.connected or not self.local_player or not self.local_player.alive or self.local_player.has_cannon:
            return
        
        for cannon_id, cannon in self.cannons.items():
            if cannon.controlled_by is None:
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
        if not self.connected or not self.local_player:
            print("DEBUG: Cannot shoot - not connected or no local player")
            return
            
        if not self.local_player.alive:
            print("DEBUG: Cannot shoot - player not alive")
            return
            
        if not self.local_player.has_cannon:
            print("DEBUG: Cannot shoot - player doesn't have a cannon")
            return
                    
        # Send shoot request to server
        message = {
            'type': 'cannon_shoot',
            'target_x': target_x,
            'target_y': target_y
        }
        
        try:
            self.socket.sendall(json.dumps(message).encode('utf-8'))
            print("DEBUG: Shoot request sent successfully")
        except Exception as e:
            print(f"Error sending shoot request: {e}")
            self.disconnect()

    def add_message(self, text):
        self.messages.append({
            'text': text,
            'time': time.time()
        })
    
    def update_messages(self):
        current_time = time.time()
        self.messages = [msg for msg in self.messages if current_time - msg['time'] < self.message_timeout]
    
    def handle_input(self):
        # Process one-time events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            
            # E for picking up cannons
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self.try_pickup_cannon()
                
            # Space to shoot cannon
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if self.local_player and self.local_player.has_cannon:
                    # Get mouse position for aiming direction
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    self.try_shoot_cannon(mouse_x, mouse_y)
                
            # DEBUG: Force teleport player with T key
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_t and self.local_player:
                self.local_player.x = 500
                self.local_player.y = 500
                self.send_update()
        
        # Check if local player exists
        if not self.local_player:
            print("WARNING: No local player to control")
            return
        
        if not self.local_player.alive:
            return

        # Process continuous keyboard input - only if player doesn't have a cannon
        if not self.local_player.has_cannon:
            keys = pygame.key.get_pressed()
            dx = 0
            dy = 0
            
            if keys[K_LEFT] or keys[K_a]:
                dx -= 1
            if keys[K_RIGHT] or keys[K_d]:
                dx += 1 
            if keys[K_UP] or keys[K_w]:
                dy -= 1
            if keys[K_DOWN] or keys[K_s]:
                dy += 1
            
            # diagonal movement
            if dx != 0 and dy != 0:
                dx *= 0.7071  # 1/sqrt(2)
                dy *= 0.7071
            
            # Store input values for other functions to use
            self.input_x = dx
            self.input_y = dy
            
            # FORCE PLAYER MOVEMENT regardless of network conditions
            if dx != 0 or dy != 0:
                old_x = self.local_player.x
                old_y = self.local_player.y
                
                # Force movement with speed factor
                speed = self.local_player.speed
                new_x = old_x + dx * speed
                new_y = old_y + dy * speed
                
                # Wall collision - keep player within bounds
                new_x = max(PLAYER_RADIUS+50, min(WINDOW_WIDTH-50 - PLAYER_RADIUS, new_x))
                new_y = max(PLAYER_RADIUS+50, min(WINDOW_HEIGHT-50 - PLAYER_RADIUS, new_y))
                
                # Directly update player position
                self.local_player.x = new_x
                self.local_player.y = new_y
                
                # Send update to server
                self.send_update()
        else:
            # Reset input values when player has a cannon (can't move)
            self.input_x = 0
            self.input_y = 0
    
    def draw(self):
        # Clear the screen
        self.window.fill(BLACK)
        
        # Draw obstacles
        for obstacle in self.obstacles:
            obstacle.draw(self.window)
        
        # Draw powerups
        for powerup_id, powerup in self.powerups.items():
            powerup.draw(self.window)        
        for cannon_id, cannon in self.cannons.items():
            try:
                standard_radius = 15
                
                # Set cannon color based on type
                if cannon.type == "EXPLOSIVE":
                    cannon_color = (255, 255, 0)  
                elif cannon.type == "BOUNCING":
                    cannon_color = (0, 255, 0)   
                elif cannon.type == "RAPID":
                    cannon_color = (255, 0, 0)    
                else:
                    cannon_color = (255, 255, 0)
                
                # Draw the cannon base circle with type-specific color
                pygame.draw.circle(self.window, cannon_color, (int(cannon.x), int(cannon.y)), standard_radius)
                
                if cannon.type == "EXPLOSIVE":
                    # explosion-like icon (asterisk shape)
                    for angle in range(0, 360, 45):
                        rad_angle = math.radians(angle)
                        start_x = int(cannon.x + (standard_radius * 0.4 * math.cos(rad_angle)))
                        start_y = int(cannon.y + (standard_radius * 0.4 * math.sin(rad_angle)))
                        end_x = int(cannon.x + (standard_radius * 0.9 * math.cos(rad_angle)))
                        end_y = int(cannon.y + (standard_radius * 0.9 * math.sin(rad_angle)))
                        pygame.draw.line(self.window, (0, 0, 0), (start_x, start_y), (end_x, end_y), 2)
                
                elif cannon.type == "BOUNCING":
                    # bounce icon (zigzag line)
                    points = [
                        (int(cannon.x - standard_radius * 0.7), int(cannon.y)),
                        (int(cannon.x - standard_radius * 0.35), int(cannon.y - standard_radius * 0.5)),
                        (int(cannon.x + standard_radius * 0.35), int(cannon.y + standard_radius * 0.5)),
                        (int(cannon.x + standard_radius * 0.7), int(cannon.y))
                    ]
                    pygame.draw.lines(self.window, (0, 0, 0), False, points, 2)
                
                elif cannon.type == "RAPID":
                    # rapid fire icon (three parallel lines)
                    line_length = standard_radius * 0.8
                    for i in range(-1, 2):
                        offset = i * 4
                        pygame.draw.line(
                            self.window,
                            (0, 0, 0),
                            (int(cannon.x - line_length/2), int(cannon.y + offset)),
                            (int(cannon.x + line_length/2), int(cannon.y + offset)),
                            2
                        )
                
                # white outline around free cannons
                if cannon.controlled_by is None:
                    pygame.draw.circle(self.window, (255, 255, 255), (int(cannon.x), int(cannon.y)), standard_radius + 2, 2)
            except Exception as e:
                print(f"Error drawing cannon {cannon_id}: {e}")
        
        # Draw players
        for player_id, player in self.players.items():
            player.draw(self.window)
        
        # Draw projectiles
        for projectile_id, projectile in self.projectiles.items():
            projectile.draw(self.window)
        
        # Draw aiming crosshair when player has a cannon
        if self.local_player and self.local_player.has_cannon:
            # Draw aiming line from the player's position to the mouse position
            mouse_x, mouse_y = pygame.mouse.get_pos()
            player_x, player_y = int(self.local_player.x), int(self.local_player.y)
            
            # Draw a line from player to mouse cursor
            pygame.draw.line(self.window, (255, 255, 255), (player_x, player_y), (mouse_x, mouse_y), 2)
            
            # Draw crosshair at mouse position for aiming
            pygame.draw.circle(self.window, (255, 0, 0), (mouse_x, mouse_y), 10, 2)
            pygame.draw.line(self.window, (255, 0, 0), (mouse_x - 15, mouse_y), (mouse_x + 15, mouse_y), 2)
            pygame.draw.line(self.window, (255, 0, 0), (mouse_x, mouse_y - 15), (mouse_x, mouse_y + 15), 2)
        
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
        
        # Draw controls help - updated to reflect the new Space key shooting
        text = self.small_font.render("WASD: Move | E: Pick up cannon | SPACE: Shoot", True, WHITE)
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
            overlay.fill((0, 0, 0, 128))
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
        delta_time = self.clock.get_time() / 1000.0
        
        # Update messages
        self.update_messages()
        
        current_time = time.time()
        for player_id, player in self.players.items():
            if player_id == self.client_id:
                continue
            if not hasattr(player, 'interp_start_time') or not hasattr(player, 'target_x'):
                continue
            interp_duration = 0.1
            time_since_update = current_time - player.interp_start_time
            progress = min(time_since_update / interp_duration, 1.0)
            
            if hasattr(player, 'prev_x') and hasattr(player, 'prev_y'):
                player.x = player.prev_x + (player.target_x - player.prev_x) * progress
                player.y = player.prev_y + (player.target_y - player.prev_y) * progress
        
        # Send periodic ping for latency measurement
        if self.connected and current_time - self.last_ping_time > self.ping_interval:
            self.last_ping_time = current_time
            self.ping_sent_time = current_time
            try:
                self.socket.sendall(json.dumps({'type': 'ping'}).encode('utf-8'))
            except Exception as e:
                pass
        
        # Update cannon objects
        for cannon_id, cannon in self.cannons.items():
            cannon.update()
    
    def disconnect(self):
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        self.add_message("Disconnected from server.")
    
    def run(self):
        # Connect to server
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