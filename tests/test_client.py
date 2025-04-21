"""
Unit tests for the client component of Cannon Chaos game.
This module tests client functionality including server communication,
game state synchronization, and input handling.
"""
print("--- test_client.py: Module level execution ---")

import unittest
import socket
import threading
import json
import time
import sys
import os
import pygame
from unittest.mock import MagicMock, patch

print("--- test_client.py: Imported modules ---")

# Add parent directory to path to import client modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client.client import GameClient
from client.player import Player
from client.cannon import Cannon
from client.projectile import Projectile
from client.powerup import PowerUp

class MockServer:
    """A mock server for testing client interactions"""
    def __init__(self, port=5557):
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('127.0.0.1', self.port))
        self.socket.listen(5)
        
        self.running = False
        self.clients = {}
        self.server_thread = None
        self.game_state = {
            'players': {},
            'cannons': {},
            'projectiles': {},
            'powerups': {},
            'obstacles': []
        }
    
    def start(self):
        """Start the mock server"""
        self.running = True
        self.server_thread = threading.Thread(target=self._accept_clients)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def _accept_clients(self):
        """Accept client connections"""
        self.socket.settimeout(0.5)
        while self.running:
            try:
                client_socket, addr = self.socket.accept()
                print(f"Mock server: Client connected from {addr}")
                
                # Handle client in a new thread
                client_thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Mock server accept error: {e}")
        
    def _handle_client(self, client_socket, addr):
        """Handle client communication"""
        client_id = None
        
        try:
            # Get initial registration message
            data = client_socket.recv(4096)
            if not data:
                return
            
            # Process registration
            try:
                message = json.loads(data.decode('utf-8'))
                client_id = message.get('client_id')
                
                # Store client socket
                if client_id:
                    self.clients[client_id] = client_socket
                    
                    # Create player in game state
                    self.game_state['players'][client_id] = {
                        'id': client_id,
                        'x': 100,
                        'y': 100,
                        'color': message.get('color', (255, 0, 0)),
                        'name': message.get('name', f"Player_{client_id}"),
                        'health': 100,
                        'alive': True,
                        'has_cannon': False,
                        'cannon_id': None
                    }
                    
                    # Send initial game state
                    self.send_init_message(client_id)
            except json.JSONDecodeError:
                print(f"Mock server: Invalid JSON in registration")
                return
            
            # Main client message handling loop
            while self.running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    # Process message
                    message = json.loads(data.decode('utf-8'))
                    self._process_client_message(client_id, message)
                except Exception as e:
                    print(f"Mock server client handler error: {e}")
                    break
        except Exception as e:
            print(f"Mock server client thread error: {e}")
        finally:
            # Clean up
            if client_id and client_id in self.clients:
                del self.clients[client_id]
                if client_id in self.game_state['players']:
                    del self.game_state['players'][client_id]
    
    def _process_client_message(self, client_id, message):
        """Process messages from clients"""
        msg_type = message.get('type')
        
        if msg_type == 'player_update':
            # Update player position
            data = message.get('data', {})
            if client_id in self.game_state['players']:
                if 'x' in data:
                    self.game_state['players'][client_id]['x'] = data['x']
                if 'y' in data:
                    self.game_state['players'][client_id]['y'] = data['y']
                
                # Broadcast update
                self.broadcast_game_update()
        
        elif msg_type == 'cannon_pickup':
            # Process cannon pickup
            cannon_id = message.get('cannon_id')
            if cannon_id in self.game_state['cannons']:
                cannon = self.game_state['cannons'][cannon_id]
                player = self.game_state['players'][client_id]
                
                # Assign cannon to player
                cannon['controlled_by'] = client_id
                player['has_cannon'] = True
                player['cannon_id'] = cannon_id
                
                # Broadcast pickup
                self.broadcast_message('cannon_pickup', {
                    'cannon_id': cannon_id,
                    'player_id': client_id
                })
        
        elif msg_type == 'cannon_shoot':
            # Process cannon shot
            target_x = message.get('target_x', 0)
            target_y = message.get('target_y', 0)
            
            # Create projectile
            proj_id = f"proj_{time.time()}"
            projectile = {
                'id': proj_id,
                'x': self.game_state['players'][client_id]['x'],
                'y': self.game_state['players'][client_id]['y'],
                'dx': 10,
                'dy': 10,
                'damage': 10,
                'radius': 5,
                'color': (255, 0, 0),
                'owner_id': client_id,
                'can_bounce': False,
                'bounces': 0
            }
            
            self.game_state['projectiles'][proj_id] = projectile
            
            # Broadcast shot
            self.broadcast_message('cannon_shot', {
                'projectile': projectile
            })
        
        elif msg_type == 'ping':
            # Respond with pong
            self.send_message(client_id, 'pong', {})
    
    def send_init_message(self, client_id):
        """Send initial game state to a client"""
        if client_id not in self.clients:
            return
        
        init_message = {
            'type': 'init',
            'data': {
                'client_id': client_id,
                'map_width': 1000,
                'map_height': 700,
                'obstacles': self.game_state['obstacles'],
                'players': self.game_state['players'],
                'cannons': list(self.game_state['cannons'].values()),
                'projectiles': list(self.game_state['projectiles'].values()),
                'powerups': list(self.game_state['powerups'].values())
            }
        }
        
        try:
            self.clients[client_id].sendall(json.dumps(init_message).encode('utf-8'))
        except Exception as e:
            print(f"Mock server error sending init: {e}")
    
    def broadcast_game_update(self):
        """Broadcast game state to all clients"""
        update = {
            'type': 'game_update',
            'data': {
                'players': self.game_state['players'],
                'cannons': list(self.game_state['cannons'].values()),
                'projectiles': list(self.game_state['projectiles'].values()),
                'powerups': list(self.game_state['powerups'].values()),
                'sudden_death': False,
                'sudden_death_timer': 120
            }
        }
        
        self.broadcast_message('game_update', update)
    
    def broadcast_message(self, msg_type, data):
        """Broadcast a message to all clients"""
        message = {
            'type': msg_type,
            'data': data
        }
        
        message_json = json.dumps(message).encode('utf-8')
        
        for client_id, client_socket in list(self.clients.items()):
            try:
                client_socket.sendall(message_json)
            except Exception as e:
                print(f"Mock server error broadcasting to {client_id}: {e}")
                # Remove client on error
                if client_id in self.clients:
                    del self.clients[client_id]
    
    def send_message(self, client_id, msg_type, data):
        """Send a message to a specific client"""
        if client_id not in self.clients:
            return False
        
        message = {
            'type': msg_type,
            'data': data
        }
        
        try:
            self.clients[client_id].sendall(json.dumps(message).encode('utf-8'))
            return True
        except Exception as e:
            print(f"Mock server error sending to {client_id}: {e}")
            # Remove client on error
            if client_id in self.clients:
                del self.clients[client_id]
            return False
    
    def add_cannon(self, cannon_id="test_cannon", x=500, y=350):
        """Add a test cannon to the game state"""
        cannon = {
            'id': cannon_id,
            'x': x,
            'y': y,
            'type': 'RAPID',
            'shots_left': 10,
            'damage': 10,
            'speed': 350,
            'cooldown': 0.3,
            'radius': 5,
            'color': (255, 0, 0),
            'controlled_by': None,
            'spawn_time': time.time(),
            'use_timer': 0,
            'last_shot_time': 0
        }
        
        self.game_state['cannons'][cannon_id] = cannon
        return cannon
    
    def add_powerup(self, powerup_id="test_powerup", x=200, y=200, powerup_type="HEALTH"):
        """Add a test powerup to the game state"""
        powerup = {
            'id': powerup_id,
            'x': x,
            'y': y,
            'type': powerup_type,
            'radius': 10,
            'color': (0, 255, 0) if powerup_type == 'HEALTH' else (255, 255, 0)
        }
        
        self.game_state['powerups'][powerup_id] = powerup
        return powerup
    
    def stop(self):
        """Stop the mock server"""
        self.running = False
        
        # Close all client sockets
        for client_socket in self.clients.values():
            try:
                client_socket.close()
            except:
                pass
        
        # Close server socket
        try:
            self.socket.close()
        except:
            pass

# Mock pygame for testing
class MockPygame:
    print("--- test_client.py: Inside MockPygame class definition ---")
    """Mock for pygame module"""
    def __init__(self):
        self.events = []
        self.pressed_keys = {}
        self.K_LEFT = pygame.K_LEFT
        self.K_RIGHT = pygame.K_RIGHT
        self.K_UP = pygame.K_UP
        self.K_DOWN = pygame.K_DOWN
        self.K_a = pygame.K_a
        self.K_d = pygame.K_d
        self.K_w = pygame.K_w
        self.K_s = pygame.K_s
        self.K_e = pygame.K_e
        self.K_SPACE = pygame.K_SPACE
        self.QUIT = pygame.QUIT
        self.KEYDOWN = pygame.KEYDOWN
        self.KEYUP = pygame.KEYUP
        
        # Mock display
        self.display = MagicMock()
        self.display.set_mode.return_value = MagicMock()
        self.display.set_caption = MagicMock()
        self.display.update = MagicMock()
        
        # Mock Surface
        self.Surface = MagicMock()
        self.Surface.return_value = MagicMock()
        self.Surface.return_value.get_rect.return_value = MagicMock()
        
        # Mock font
        self.font = MagicMock()
        self.font.SysFont.return_value = MagicMock()
        self.font.SysFont.return_value.render.return_value = MagicMock()
        self.font.SysFont.return_value.render.return_value.get_width.return_value = 100
        
        # Mock time
        self.time = MagicMock()
        self.time.Clock.return_value = MagicMock()
        self.time.Clock.return_value.tick.return_value = 16
        self.time.Clock.return_value.get_time.return_value = 16
        
        # Mock mouse
        self.mouse = MagicMock()
        self.mouse.get_pos.return_value = (500, 350)
        
        # Mock draw
        self.draw = MagicMock()
    
    def add_event(self, event_type, **kwargs):
        """Add an event to the event queue"""
        event = MagicMock()
        event.type = event_type
        for key, value in kwargs.items():
            setattr(event, key, value)
        self.events.append(event)
    
    def get_events(self):
        """Get all events from the queue"""
        events = self.events
        self.events = []
        return events
    
    def set_pressed_keys(self, keys):
        """Set the pressed keys"""
        self.pressed_keys = keys
    
    def key_get_pressed(self):
        """Get pressed keys"""
        return self.pressed_keys
    
    def init(self):
        """Mock pygame.init()"""
        pass
    
    def quit(self):
        """Mock pygame.quit()"""
        pass

print("--- test_client.py: Defined MockPygame ---")

class TestGameClient(unittest.TestCase):
    print("--- test_client.py: Inside TestGameClient class definition ---")

    @classmethod
    def setUpClass(cls):
        print("--- test_client.py: Running TestGameClient.setUpClass ---")
        """Set up the test environment"""
        # Mock pygame helper instance
        cls.mock_pygame_helper = MockPygame() # Renamed for clarity
        
        # Create mock server
        cls.mock_server = MockServer(port=5557)
        cls.mock_server.start()
        
        # Add some test game objects
        cls.mock_server.add_cannon()
        cls.mock_server.add_powerup()
        
        # Wait for server to start
        time.sleep(1)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment"""
        if hasattr(cls, 'mock_server'):
            cls.mock_server.stop()
    
    def setUp(self):
        """Set up before each test"""
        # Start the patch manually
        self.pygame_patcher = patch('client.client.pygame')
        mock_pygame = self.pygame_patcher.start()
        self.addCleanup(self.pygame_patcher.stop) # Ensure patch stops after test

        # Configure the actual mock object (mock_pygame) using our helper (self.mock_pygame_helper)
        mock_pygame.init.side_effect = self.mock_pygame_helper.init
        mock_pygame.quit.side_effect = self.mock_pygame_helper.quit
        mock_pygame.display = self.mock_pygame_helper.display
        mock_pygame.Surface = self.mock_pygame_helper.Surface
        mock_pygame.font = self.mock_pygame_helper.font
        mock_pygame.time = self.mock_pygame_helper.time
        mock_pygame.mouse = self.mock_pygame_helper.mouse
        mock_pygame.draw = self.mock_pygame_helper.draw
        mock_pygame.event.get.side_effect = self.mock_pygame_helper.get_events
        mock_pygame.key.get_pressed.side_effect = self.mock_pygame_helper.key_get_pressed
        mock_pygame.QUIT = self.mock_pygame_helper.QUIT
        mock_pygame.KEYDOWN = self.mock_pygame_helper.KEYDOWN
        mock_pygame.KEYUP = self.mock_pygame_helper.KEYUP
        mock_pygame.K_LEFT = self.mock_pygame_helper.K_LEFT
        mock_pygame.K_RIGHT = self.mock_pygame_helper.K_RIGHT
        mock_pygame.K_UP = self.mock_pygame_helper.K_UP
        mock_pygame.K_DOWN = self.mock_pygame_helper.K_DOWN
        mock_pygame.K_a = self.mock_pygame_helper.K_a
        mock_pygame.K_d = self.mock_pygame_helper.K_d
        mock_pygame.K_w = self.mock_pygame_helper.K_w
        mock_pygame.K_s = self.mock_pygame_helper.K_s
        mock_pygame.K_e = self.mock_pygame_helper.K_e
        mock_pygame.K_SPACE = self.mock_pygame_helper.K_SPACE
        
        # Create patch for get_player_name to avoid input prompts during tests
        # Use patch as a context manager here for simplicity
        with patch('client.client.GameClient.get_player_name', return_value="TestPlayer"):
            self.client = GameClient(server_address='127.0.0.1', port=5557)
            # The GameClient will now use the mocked pygame configured above
            self.client.window = mock_pygame.display.set_mode.return_value
        
        # Set client to not actually run the game loop
        self.client.running = False
    
    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'client'):
            self.client.disconnect()
    
    def test_client_connection(self):
        """Test client connection to server"""
        print("--- test_client.py: Running test_client_connection ---")
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        self.assertTrue(self.client.connected)
        self.assertIsNotNone(self.client.client_id)
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Client should have received init message
        self.assertIn(self.client.client_id, self.client.players)
        self.assertIsNotNone(self.client.local_player)
    
    def test_client_player_movement(self):
        """Test client player movement handling"""
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Set up mock key presses for movement
        self.mock_pygame_helper.set_pressed_keys({
            self.mock_pygame_helper.K_RIGHT: True,
            self.mock_pygame_helper.K_d: True
        })
        
        # Store initial position
        initial_x = self.client.local_player.x
        initial_y = self.client.local_player.y
        
        # Process input
        self.client.handle_input()
        
        # Player should have moved right
        self.assertGreater(self.client.local_player.x, initial_x)
        self.assertEqual(self.client.local_player.y, initial_y)
        
        # Test vertical movement
        self.mock_pygame_helper.set_pressed_keys({
            self.mock_pygame_helper.K_DOWN: True,
            self.mock_pygame_helper.K_s: True
        })
        
        # Update stored position
        initial_x = self.client.local_player.x
        initial_y = self.client.local_player.y
        
        # Process input
        self.client.handle_input()
        
        # Player should have moved down
        self.assertEqual(self.client.local_player.x, initial_x)
        self.assertGreater(self.client.local_player.y, initial_y)
    
    def test_cannon_pickup(self):
        """Test cannon pickup functionality"""
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Move player to cannon position
        self.client.local_player.x = 500
        self.client.local_player.y = 350
        self.client.send_update()
        
        # Add a cannon pickup event
        self.mock_pygame_helper.add_event(self.mock_pygame_helper.KEYDOWN, key=self.mock_pygame_helper.K_e)
        
        # Process input to pick up cannon
        with patch('client.client.GameClient.try_pickup_cannon') as mock_pickup:
            self.client.handle_input()
            mock_pickup.assert_called_once()
        
        # Test the actual pickup function
        cannon_id = next(iter(self.mock_server.game_state['cannons'].keys()))
        with patch('socket.socket.sendall') as mock_sendall:
            self.client.try_pickup_cannon()
            mock_sendall.assert_called()
            # Check that the sent message contains the cannon_id
            args = mock_sendall.call_args[0][0]
            self.assertIn(b'cannon_pickup', args)
            self.assertIn(cannon_id.encode(), args)
    
    def test_cannon_shooting(self):
        """Test cannon shooting functionality"""
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Give player a cannon
        self.client.local_player.has_cannon = True
        self.client.local_player.cannon_id = "test_cannon"
        
        # Add a cannon shoot event
        self.mock_pygame_helper.add_event(self.mock_pygame_helper.KEYDOWN, key=self.mock_pygame_helper.K_SPACE)
        
        # Process input to shoot cannon
        with patch('client.client.GameClient.try_shoot_cannon') as mock_shoot:
            self.client.handle_input()
            mock_shoot.assert_called_once()
        
        # Test the actual shoot function
        with patch('socket.socket.sendall') as mock_sendall:
            self.client.try_shoot_cannon(500, 350)
            mock_sendall.assert_called()
            # Check that the sent message has the correct type
            args = mock_sendall.call_args[0][0]
            self.assertIn(b'cannon_shoot', args)
    
    def test_message_handling(self):
        """Test client message handling"""
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Test adding a game message
        self.client.add_message("Test message")
        self.assertEqual(len(self.client.messages), 1)
        self.assertEqual(self.client.messages[0]['text'], "Test message")
        
        # Test message timeout
        self.client.message_timeout = 0.1
        time.sleep(0.2)
        self.client.update_messages()
        self.assertEqual(len(self.client.messages), 0)
    
    def test_ping(self):
        """Test ping-pong functionality"""
        # Connect to mock server
        self.assertTrue(self.client.connect_to_server())
        
        # Give time for initial message processing
        time.sleep(1)
        
        # Test ping-pong
        with patch('time.time', side_effect=[100.0, 100.1]):
            self.client.ping_sent_time = 100.0
            self.client.handle_server_message({
                'type': 'pong',
                'data': {}
            })
            self.assertEqual(self.client.latency_ms, 100)

print("--- test_client.py: End of module execution ---")
