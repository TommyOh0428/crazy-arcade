import pygame
from pygame.locals import *
import sys

pygame.init()

window = pygame.display.set_mode((1000, 700))

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            print("game terminated")
            pygame.quit()
            sys.exit()
    pygame.display.update()