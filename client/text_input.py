"""
text_input.py

This module provides a simple text input handler for Pygame, allowing users to input text with a blinking cursor.
"""

import pygame
from pygame.locals import *

class TextInput:
    WHITE = (255, 255, 255)
    """A simple text input handler for pygame"""
    def __init__(self, font=None, max_length=20, font_color=WHITE, antialias=True):
        self.font = font if font else pygame.font.SysFont(None, 32)
        self.text = ""
        self.max_length = max_length
        self.font_color = font_color
        self.antialias = antialias
        self.active = True
        self.surface = None
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_interval = 0.5
        self.update_surface()
    
    def update(self, events, dt):
        for event in events:
            if event.type == KEYDOWN and self.active:
                if event.key == K_BACKSPACE:
                    self.text = self.text[:-1]
                elif event.key == K_RETURN:
                    return True  
                elif len(self.text) < self.max_length and event.unicode.isprintable():
                    self.text += event.unicode
                
                self.update_surface()
    
        self.cursor_timer += dt
        if self.cursor_timer >= self.cursor_blink_interval:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible
            self.update_surface()
                
        return False
    
    def update_surface(self):
        base_text = self.font.render(self.text, self.antialias, self.font_color)
        
        if self.cursor_visible and self.active:
            # cursor at end of text
            cursor_pos = self.font.size(self.text)[0]
            cursor_height = self.font.get_height()
            width = max(base_text.get_width() + 2, cursor_pos + 2)
            self.surface = pygame.Surface((width, cursor_height), pygame.SRCALPHA)
            self.surface.blit(base_text, (0, 0))
            
            pygame.draw.line(
                self.surface, 
                self.font_color, 
                (cursor_pos, 2), 
                (cursor_pos, cursor_height - 2), 
                2
            )
        else:
            self.surface = base_text
        
    def get_surface(self):
        return self.surface
    
    def get_text(self):
        return self.text