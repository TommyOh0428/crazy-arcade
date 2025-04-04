import socket
import threading
import pickle
import time
import random
import json

# Server configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 5555
BUFFER_SIZE = 4096

# Game state constants
UPDATE_INTERVAL = 0.03  # 30 updates per second

class GameServer:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((HOST, PORT))
        self.socket.listen(5)
        print(f"Server started on {HOST}:{PORT}")
        print(f"Server IP: {self.get_ip_address()}")
        print("Run python client/client.py to connect as local client")
        print(f"Run python client/client.py {self.get_ip_address()} to connect as remote client")
        
        # Game state
        self.clients = {}  # client_id: connection
        self.players = {}  # client_id: player_state
        self.cannons = []
        self.projectiles = []
        self.powerups = []
        self.obstacles = []
        
        # Game settings
        self.map_width = 1000
        self.map_height = 700
        self.grid_size = 50
        self.running = False
        self.game_started = False
        self.sudden_death = False
        self.sudden_death_timer = 120  # 2 minutes
        
        # Generate map obstacles
        self.generate_obstacles()
    
    def get_ip_address(self):
        """Get the server's IP address"""
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

    def generate_obstacles(self):
        grid_width = self.map_width // self.grid_size
        grid_height = self.map_height // self.grid_size
        
        # Create a pattern of obstacles
        for i in range(1, grid_width - 1):
            for j in range(1, grid_height - 1):
                if (i + j) % 3 == 0:  # Create a pattern
                    self.obstacles.append({
                        'x': i * self.grid_size,
                        'y': j * self.grid_size,
                        'width': self.grid_size,
                        'height': self.grid_size
                    })
    
    def start(self):
        """Start the server and accept client connections"""
        self.running = True
        
        # Start game update thread
        update_thread = threading.Thread(target=self.game_update_loop)
        update_thread.daemon = True
        update_thread.start()
        
        # Accept client connections
        try:
            while self.running:
                client_socket, addr = self.socket.accept()
                print(f"New connection from {addr}")
                
                # Start a thread to handle this client
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.close()
    
    def handle_client(self, client_socket, addr):
        """Handle communication with a connected client"""
        try:
            # First message should be player registration
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                return
            
            # Register the player
            player_info = json.loads(data.decode('utf-8'))
            client_id = player_info.get('client_id', str(random.randint(1000, 9999)))
            
            # Assign player ID and starting position
            x = random.randint(50, self.map_width - 50)
            y = random.randint(50, self.map_height - 50)
            color = player_info.get('color', (255, 0, 0))  # Default to red if not specified
            
            # Add player to the game
            self.clients[client_id] = client_socket
            self.players[client_id] = {
                'id': client_id,
                'x': x,
                'y': y,
                'color': color,
                'health': 100,
                'alive': True,
                'has_cannon': False,
                'cannon_id': None,
                'speed': 5,
                'dash_cooldown': 0
            }
            
            # Send initial game state to client
            initial_state = {
                'type': 'init',
                'client_id': client_id,
                'map_width': self.map_width,
                'map_height': self.map_height,
                'obstacles': self.obstacles,
                'players': self.players,
                'cannons': self.cannons,
                'projectiles': self.projectiles,
                'powerups': self.powerups
            }
            client_socket.sendall(json.dumps(initial_state).encode('utf-8'))
            
            # Broadcast to all clients about new player
            self.broadcast_game_update()
            
            # If we have at least 2 players and game hasn't started yet, start it
            if len(self.players) >= 2 and not self.game_started:
                self.game_started = True
                self.broadcast_message('game_start', {'message': 'Game starting!'})
                # Spawn the first cannon
                self.spawn_cannon()
            
            # Main client communication loop
            while self.running:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                
                # Parse and handle client message
                try:
                    message = json.loads(data.decode('utf-8'))
                    self.handle_client_message(client_id, message)
                except json.JSONDecodeError:
                    print(f"Invalid JSON from client {client_id}")
                except Exception as e:
                    print(f"Error handling client message: {e}")
        
        except Exception as e:
            print(f"Client handler error: {e}")
        finally:
            # Clean up when client disconnects
            self.handle_disconnect(client_id)
    
    def handle_client_message(self, client_id, message):
        """Process messages from clients"""
        msg_type = message.get('type')
        
        if msg_type == 'player_update':
            # Update player state (position, etc.)
            player_data = message.get('data', {})
            if client_id in self.players and self.players[client_id]['alive']:
                # Update player position
                if 'x' in player_data and 'y' in player_data:
                    # Check if the move is valid (not colliding with obstacles)
                    new_x = player_data['x']
                    new_y = player_data['y']
                    
                    # Apply the update if it's valid
                    self.players[client_id]['x'] = new_x
                    self.players[client_id]['y'] = new_y
                
                # Update other player properties
                if 'dash_cooldown' in player_data:
                    self.players[client_id]['dash_cooldown'] = player_data['dash_cooldown']
        
        elif msg_type == 'cannon_pickup':
            # Player is trying to pick up a cannon
            cannon_id = message.get('cannon_id')
            self.handle_cannon_pickup(client_id, cannon_id)
        
        elif msg_type == 'cannon_shoot':
            # Player is shooting a cannon
            target_x = message.get('target_x')
            target_y = message.get('target_y')
            self.handle_cannon_shoot(client_id, target_x, target_y)
        
        elif msg_type == 'dash':
            # Player is using dash ability
            dx = message.get('dx', 0)
            dy = message.get('dy', 0)
            self.handle_player_dash(client_id, dx, dy)
    
    def handle_cannon_pickup(self, client_id, cannon_id):
        """Handle a player attempting to pick up a cannon"""
        # Find the cannon by ID
        cannon = None
        for c in self.cannons:
            if c.get('id') == cannon_id:
                cannon = c
                break
        
        if cannon and cannon.get('controlled_by') is None:
            player = self.players[client_id]
            
            # Check if player is close enough to pick up cannon
            dx = player['x'] - cannon['x']
            dy = player['y'] - cannon['y']
            distance = (dx*dx + dy*dy) ** 0.5
            
            if distance < 40:  # Player radius + cannon radius
                # Player gets control of the cannon
                cannon['controlled_by'] = client_id
                player['has_cannon'] = True
                player['cannon_id'] = cannon_id
                
                # Broadcast the cannon pickup
                self.broadcast_message('cannon_pickup', {
                    'cannon_id': cannon_id,
                    'player_id': client_id
                })
    
    def handle_cannon_shoot(self, client_id, target_x, target_y):
        """Handle a player shooting a cannon"""
        player = self.players.get(client_id)
        if not player or not player['alive'] or not player['has_cannon']:
            return
        
        # Find the player's cannon
        cannon = None
        for c in self.cannons:
            if c.get('id') == player['cannon_id']:
                cannon = c
                break
        
        if cannon and cannon.get('shots_left', 0) > 0:
            # Calculate direction
            player_x, player_y = player['x'], player['y']
            dx = target_x - player_x
            dy = target_y - player_y
            distance = max(1, (dx*dx + dy*dy) ** 0.5)
            dx /= distance
            dy /= distance
            
            # Check cooldown
            current_time = time.time()
            if current_time - cannon.get('last_shot_time', 0) < cannon.get('cooldown', 0.5):
                return  # Still on cooldown
            
            # Create new projectile
            projectile_id = f"proj_{time.time()}_{random.randint(1000, 9999)}"
            speed = cannon.get('speed', 10)
            damage = cannon.get('damage', 10)
            radius = cannon.get('radius', 5)
            can_bounce = cannon.get('type') == 'BOUNCING'
            bounces = 3 if can_bounce else 0
            
            projectile = {
                'id': projectile_id,
                'x': player_x,
                'y': player_y,
                'dx': dx * speed,
                'dy': dy * speed,
                'damage': damage,
                'radius': radius,
                'color': cannon.get('color', (255, 0, 0)),
                'owner_id': client_id,
                'can_bounce': can_bounce,
                'bounces': bounces
            }
            self.projectiles.append(projectile)
            
            # Update cannon state
            cannon['shots_left'] -= 1
            cannon['last_shot_time'] = current_time
            cannon['use_timer'] = 0  # Reset explosion timer
            
            # If cannon is out of shots, release it
            if cannon['shots_left'] <= 0:
                cannon['controlled_by'] = None
                player['has_cannon'] = False
                player['cannon_id'] = None
                
                # Remove the cannon
                self.cannons = [c for c in self.cannons if c.get('id') != cannon['id']]
                
                # Broadcast cannon depletion
                self.broadcast_message('cannon_depleted', {
                    'cannon_id': cannon['id']
                })
            
            # Broadcast the shot
            self.broadcast_message('cannon_shot', {
                'projectile': projectile
            })
    
    def handle_player_dash(self, client_id, dx, dy):
        """Handle a player using dash ability"""
        player = self.players.get(client_id)
        if not player or not player['alive']:
            return
        
        # Check if dash is on cooldown
        if player['dash_cooldown'] <= 0:
            # Apply dash
            player['dash_cooldown'] = 2  # 2 seconds cooldown
            
            # Broadcast dash effect
            self.broadcast_message('player_dash', {
                'player_id': client_id,
                'dx': dx,
                'dy': dy
            })
    
    def spawn_cannon(self):
        """Spawn a new cannon at a random location"""
        # Find a position not occupied by obstacles
        while True:
            x = random.randint(self.grid_size, self.map_width - self.grid_size)
            y = random.randint(self.grid_size, self.map_height - self.grid_size)
            
            # Check for collision with obstacles
            collision = False
            for obstacle in self.obstacles:
                ox, oy = obstacle['x'], obstacle['y']
                ow, oh = obstacle['width'], obstacle['height']
                if (ox <= x <= ox + ow and oy <= y <= oy + oh):
                    collision = True
                    break
            
            if not collision:
                # Choose a random cannon type
                cannon_types = ['RAPID', 'EXPLOSIVE', 'BOUNCING']
                cannon_type = random.choice(cannon_types)
                
                # Set properties based on type
                properties = {
                    'RAPID': {'damage': 10, 'speed': 12, 'cooldown': 0.3, 'shots': 10, 'radius': 5, 'color': (255, 0, 0)},
                    'EXPLOSIVE': {'damage': 30, 'speed': 6, 'cooldown': 1.0, 'shots': 3, 'radius': 15, 'color': (255, 255, 0)},
                    'BOUNCING': {'damage': 15, 'speed': 8, 'cooldown': 0.7, 'shots': 5, 'radius': 8, 'color': (0, 255, 0)}
                }
                
                # Create the cannon
                cannon_id = f"cannon_{time.time()}_{random.randint(1000, 9999)}"
                cannon = {
                    'id': cannon_id,
                    'x': x,
                    'y': y,
                    'type': cannon_type,
                    'shots_left': properties[cannon_type]['shots'],
                    'damage': properties[cannon_type]['damage'],
                    'speed': properties[cannon_type]['speed'],
                    'cooldown': properties[cannon_type]['cooldown'],
                    'radius': properties[cannon_type]['radius'],
                    'color': properties[cannon_type]['color'],
                    'controlled_by': None,
                    'spawn_time': time.time(),
                    'use_timer': 0,
                    'last_shot_time': 0
                }
                self.cannons.append(cannon)
                
                # Broadcast new cannon
                self.broadcast_message('cannon_spawn', {
                    'cannon': cannon
                })
                
                break
    
    def spawn_powerup(self, x, y):
        """Spawn a powerup at the specified location"""
        power_types = ['HEALTH', 'SPEED']
        power_type = random.choice(power_types)
        
        powerup_id = f"powerup_{time.time()}_{random.randint(1000, 9999)}"
        powerup = {
            'id': powerup_id,
            'x': x,
            'y': y,
            'type': power_type,
            'radius': 10,
            'color': (0, 255, 0) if power_type == 'HEALTH' else (255, 255, 0)  # Green for health, yellow for speed
        }
        self.powerups.append(powerup)
        
        # Broadcast new powerup
        self.broadcast_message('powerup_spawn', {
            'powerup': powerup
        })
    
    def update_projectiles(self, delta_time):
        """Update all projectiles and check for collisions"""
        for projectile in self.projectiles[:]:
            # Update position
            projectile['x'] += projectile['dx'] * delta_time
            projectile['y'] += projectile['dy'] * delta_time
            
            # Check if out of bounds
            x, y = projectile['x'], projectile['y']
            if x < 0 or x > self.map_width or y < 0 or y > self.map_height:
                if projectile['can_bounce'] and projectile['bounces'] > 0:
                    # Bounce off walls
                    if x < 0 or x > self.map_width:
                        projectile['dx'] = -projectile['dx']
                    if y < 0 or y > self.map_height:
                        projectile['dy'] = -projectile['dy']
                    projectile['bounces'] -= 1
                    # Adjust position to be within bounds
                    projectile['x'] = max(0, min(self.map_width, projectile['x']))
                    projectile['y'] = max(0, min(self.map_height, projectile['y']))
                else:
                    # Remove projectile
                    self.projectiles.remove(projectile)
                    continue
            
            # Check for collisions with obstacles
            for obstacle in self.obstacles:
                ox, oy = obstacle['x'], obstacle['y']
                ow, oh = obstacle['width'], obstacle['height']
                
                # Simple collision check
                if (ox - projectile['radius'] <= x <= ox + ow + projectile['radius'] and 
                    oy - projectile['radius'] <= y <= oy + oh + projectile['radius']):
                    if projectile['can_bounce'] and projectile['bounces'] > 0:
                        # Simple bounce - reverse direction
                        projectile['dx'] = -projectile['dx']
                        projectile['dy'] = -projectile['dy']
                        projectile['bounces'] -= 1
                    else:
                        # Remove projectile
                        if projectile in self.projectiles:
                            self.projectiles.remove(projectile)
                        break
            
            # Check for collisions with players
            for player_id, player in self.players.items():
                if player['alive'] and player_id != projectile.get('owner_id'):
                    px, py = player['x'], player['y']
                    dx = px - x
                    dy = py - y
                    distance = (dx*dx + dy*dy) ** 0.5
                    
                    if distance < 20 + projectile['radius']:  # Player radius + projectile radius
                        # Player is hit
                        player['health'] -= projectile['damage']
                        
                        # Check if player is eliminated
                        if player['health'] <= 0:
                            player['alive'] = False
                            player['health'] = 0
                            
                            # If player had a cannon, release it
                            if player['has_cannon']:
                                for cannon in self.cannons[:]:
                                    if cannon.get('controlled_by') == player_id:
                                        self.cannons.remove(cannon)
                                        break
                                player['has_cannon'] = False
                                player['cannon_id'] = None
                            
                            # Spawn a powerup at player's position
                            self.spawn_powerup(px, py)
                            
                            # Broadcast player elimination
                            self.broadcast_message('player_eliminated', {
                                'player_id': player_id,
                                'eliminator_id': projectile.get('owner_id')
                            })
                            
                            # Check if the game is over
                            alive_players = [p for p_id, p in self.players.items() if p['alive']]
                            if len(alive_players) <= 1:
                                # Game over - last player standing wins
                                winner_id = alive_players[0]['id'] if alive_players else None
                                self.broadcast_message('game_over', {
                                    'winner_id': winner_id
                                })
                                # Reset the game in 10 seconds
                                threading.Timer(10, self.reset_game).start()
                        
                        # Remove projectile
                        if projectile in self.projectiles:
                            self.projectiles.remove(projectile)
                        
                        # Broadcast hit
                        self.broadcast_message('player_hit', {
                            'player_id': player_id,
                            'damage': projectile['damage'],
                            'health': player['health']
                        })
                        break
    
    def update_cannons(self, delta_time):
        """Update cannons and check for explosion timers"""
        for cannon in self.cannons[:]:
            # Update explosion timer if cannon is controlled but not used
            if cannon.get('controlled_by') is not None:
                cannon['use_timer'] += delta_time
                if cannon['use_timer'] >= 10:  # 10 seconds before explosion
                    # Explode cannon and damage controlling player
                    player_id = cannon['controlled_by']
                    if player_id in self.players:
                        self.players[player_id]['health'] -= 50
                        self.players[player_id]['has_cannon'] = False
                        self.players[player_id]['cannon_id'] = None
                        
                        # Check if player is eliminated by explosion
                        if self.players[player_id]['health'] <= 0:
                            self.players[player_id]['alive'] = False
                            self.players[player_id]['health'] = 0
                            
                            # Spawn a powerup at player's position
                            self.spawn_powerup(self.players[player_id]['x'], self.players[player_id]['y'])
                            
                            # Broadcast player elimination
                            self.broadcast_message('player_eliminated', {
                                'player_id': player_id,
                                'eliminator_id': None  # Eliminated by cannon explosion
                            })
                        
                        # Broadcast hit
                        self.broadcast_message('player_hit', {
                            'player_id': player_id,
                            'damage': 50,
                            'health': self.players[player_id]['health']
                        })
                    
                    # Remove the cannon
                    self.cannons.remove(cannon)
                    
                    # Broadcast cannon explosion
                    self.broadcast_message('cannon_exploded', {
                        'cannon_id': cannon['id']
                    })
    
    def update_powerups(self, delta_time):
        """Check for powerup pickups"""
        for powerup in self.powerups[:]:
            for player_id, player in self.players.items():
                if player['alive']:
                    px, py = player['x'], player['y']
                    dx = px - powerup['x']
                    dy = py - powerup['y']
                    distance = (dx*dx + dy*dy) ** 0.5
                    
                    if distance < 20 + powerup['radius']:  # Player radius + powerup radius
                        # Apply powerup effect
                        if powerup['type'] == 'HEALTH':
                            player['health'] = min(player['health'] + 30, 100)
                        elif powerup['type'] == 'SPEED':
                            # Speed boost would need a timer in the client
                            pass
                        
                        # Remove powerup
                        self.powerups.remove(powerup)
                        
                        # Broadcast powerup pickup
                        self.broadcast_message('powerup_pickup', {
                            'powerup_id': powerup['id'],
                            'player_id': player_id,
                            'type': powerup['type']
                        })
                        break
    
    def game_update_loop(self):
        """Main game update loop"""
        last_update_time = time.time()
        last_cannon_spawn_time = last_update_time
        
        while self.running:
            current_time = time.time()
            delta_time = current_time - last_update_time
            
            if delta_time >= UPDATE_INTERVAL:
                # Update game state
                if self.game_started:
                    # Update projectiles
                    self.update_projectiles(delta_time)
                    
                    # Update cannons
                    self.update_cannons(delta_time)
                    
                    # Update powerups
                    self.update_powerups(delta_time)
                    
                    # Spawn new cannon if needed (every 5 seconds)
                    if current_time - last_cannon_spawn_time >= 5 and len(self.cannons) < 3:
                        self.spawn_cannon()
                        last_cannon_spawn_time = current_time
                    
                    # Update sudden death timer
                    if not self.sudden_death:
                        self.sudden_death_timer -= delta_time
                        if self.sudden_death_timer <= 0:
                            self.sudden_death = True
                            self.broadcast_message('sudden_death', {'message': 'Sudden Death Mode Activated!'})
                    
                    # Broadcast game state update
                    self.broadcast_game_update()
                
                last_update_time = current_time
            
            # Sleep to avoid consuming too much CPU
            time.sleep(0.01)
    
    def broadcast_game_update(self):
        """Send current game state to all clients"""
        state = {
            'type': 'game_update',
            'players': self.players,
            'cannons': self.cannons,
            'projectiles': self.projectiles,
            'powerups': self.powerups,
            'sudden_death': self.sudden_death,
            'sudden_death_timer': self.sudden_death_timer
        }
        self.broadcast_message('game_update', state)
    
    def broadcast_message(self, msg_type, data):
        """Send a message to all connected clients"""
        message = {
            'type': msg_type,
            'data': data
        }
        message_json = json.dumps(message).encode('utf-8')
        
        for client_id, client_socket in list(self.clients.items()):
            try:
                client_socket.sendall(message_json)
            except Exception as e:
                print(f"Error sending to client {client_id}: {e}")
                self.handle_disconnect(client_id)
    
    def handle_disconnect(self, client_id):
        """Handle a client disconnection"""
        if client_id in self.clients:
            try:
                self.clients[client_id].close()
            except:
                pass
            del self.clients[client_id]
        
        if client_id in self.players:
            # Release any cannon the player was holding
            if self.players[client_id].get('has_cannon'):
                for cannon in self.cannons[:]:
                    if cannon.get('controlled_by') == client_id:
                        self.cannons.remove(cannon)
                        break
            
            # Remove the player
            del self.players[client_id]
            
            # Broadcast player left
            self.broadcast_message('player_left', {'player_id': client_id})
            
            # Check if the game is over
            alive_players = [p for p_id, p in self.players.items() if p.get('alive', False)]
            if len(alive_players) <= 1 and self.game_started:
                # Game over - last player standing wins
                winner_id = alive_players[0]['id'] if alive_players else None
                self.broadcast_message('game_over', {
                    'winner_id': winner_id
                })
                # Reset the game in 10 seconds
                threading.Timer(10, self.reset_game).start()
    
    def reset_game(self):
        """Reset the game state for a new round"""
        # Clear game objects
        self.cannons = []
        self.projectiles = []
        self.powerups = []
        
        # Reset player states
        for player_id in self.players:
            self.players[player_id]['x'] = random.randint(50, self.map_width - 50)
            self.players[player_id]['y'] = random.randint(50, self.map_height - 50)
            self.players[player_id]['health'] = 100
            self.players[player_id]['alive'] = True
            self.players[player_id]['has_cannon'] = False
            self.players[player_id]['cannon_id'] = None
        
        # Reset game settings
        self.sudden_death = False
        self.sudden_death_timer = 120
        
        # Broadcast game reset
        self.broadcast_message('game_reset', {'message': 'New game starting!'})
        
        # Spawn initial cannon
        self.spawn_cannon()
    
    def close(self):
        """Close the server and all connections"""
        self.running = False
        
        # Close all client connections
        for client_id, client_socket in self.clients.items():
            try:
                client_socket.close()
            except:
                pass
        
        # Close server socket
        try:
            self.socket.close()
        except:
            pass
        
        print("Server closed")

if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("Server stopped by user")
    finally:
        server.close()