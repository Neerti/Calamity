#!/usr/bin/python

#Load this module to access the global constants

#actual size of the window
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 60
 
#size of the map portion shown on-screen
CAMERA_WIDTH = 128
CAMERA_HEIGHT = 48

#size of the map
MAP_WIDTH = 160
MAP_HEIGHT = 80
 
#sizes and coordinates relevant for the GUI
LOG_WIDTH = 160
LOG_HEIGHT = 50

PANEL_WIDTH = 30
PANEL_HEIGHT = 50
PANEL_X = 128

BAR_WIDTH = 30
LOG_Y = SCREEN_HEIGHT - LOG_HEIGHT 
MSG_X = 1
MSG_WIDTH = LOG_WIDTH - 1
MSG_HEIGHT = LOG_Y - 2
INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
LEVEL_SCREEN_WIDTH = 40

#parameters for dungeon generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 50
 
#spell values
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_RANGE = 8
CONFUSE_NUM_TURNS = 10
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25
 
#experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
 
 
FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not
TORCH_RADIUS = 10
 
LIMIT_FPS = 20  #20 frames-per-second maximum