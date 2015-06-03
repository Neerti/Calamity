#!/usr/bin/python
#
# libtcod python tutorial
#
 
import libtcodpy as libtcod
import CONSTANTS
import math
import textwrap
import shelve
import json
import ConfigParser

from helpers import *
from spells import *
 
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
TORCH_RADIUS = 8
 
LIMIT_FPS = 20  #20 frames-per-second maximum

 
 
color_dark_wall = libtcod.Color(28, 28, 28)
color_dark_ground = libtcod.Color(88, 88, 88)
color_light_wall = libtcod.Color(97, 56, 11)
color_light_ground = libtcod.Color(200, 180, 50)

class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked

		#all tiles start unexplored
		self.explored = False

		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Rect:
	#a rectangle on the map. used to characterize a room.
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h

	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)

	def intersect(self, other):
		#returns true if this rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
				self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, player_stats=None, player_skills=None, item=None, equipment=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.always_visible = always_visible
		self.fighter = fighter
		if self.fighter:  #let the fighter component know who owns it
			self.fighter.owner = self

		self.ai = ai
		if self.ai:  #let the AI component know who owns it
			self.ai.owner = self

		self.item = item
		if self.item:  #let the Item component know who owns it
			self.item.owner = self

		self.equipment = equipment
		if self.equipment:  #let the Equipment component know who owns it
			self.equipment.owner = self

			#there must be an Item component for the Equipment component to work properly
			self.item = Item()
			self.item.owner = self
		
		self.player_stats = player_stats
		if player_stats:
			self.player_stats.owner = self
		
		self.player_skills = player_skills
		if player_skills:
			self.player_skills.owner = self
	
	def is_player(self):
		if self is player:
			return True
		return False

	def move(self, dx, dy):
		#move by the given amount, if the destination is not blocked
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy

	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)

		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)

	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile.
		global objects
		objects.remove(self)
		objects.insert(0, self)

	def draw(self):
		#only show if it's visible to the player
		if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored):
			(x, y) = to_camera_coordinates(self.x, self.y)

			if x is not None:
				#set the color and then draw the character that represents this object at its position
				libtcod.console_set_default_foreground(con, self.color)
				libtcod.console_put_char(con, x, y, self.char, libtcod.BKGND_NONE)

	def clear(self):
		#erase the character that represents this object
		(x, y) = to_camera_coordinates(self.x, self.y)
		if x is not None:
			libtcod.console_put_char(con, x, y, ' ', libtcod.BKGND_NONE)


class Fighter:
	tick_total = 0
	#combat-related properties and methods (monster, player, NPC).
	def __init__(self, hp, defense, power, xp, death_function=None, species='Humanoid', evade = 10, block = 0, accuracy = 12):
		self.base_max_hp = hp
		self.hp = hp
		self.base_defense = defense
		self.base_evade = evade
		self.base_block = block
		self.base_power = power
		self.base_accuracy = accuracy
		self.xp = xp
		self.death_function = death_function
		self.species = species

	@property
	def power(self):  #return actual power, by summing up the bonuses from all equipped items
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus

	@property
	def accuracy(self):  #return actual accuracy, by summing up the bonuses from all equipped items and average of str and agi.
		stat_bonus = 0 #Monsters have no stats.
		if self.owner.is_player():
			stats = self.owner.player_stats
			stat_bonus = (stats.strength + stats.agility) / 2
		bonus = sum(equipment.accuracy_bonus for equipment in get_all_equipped(self.owner))
		return self.base_accuracy + stat_bonus + bonus

	@property
	def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defense + bonus
	
	@property
	def evade(self): #Return actual evade stat, by summing up bonuses from equipment and skills.
		skill_bonus = 0 
		if self.owner.is_player(): #Monsters don't use skills, so we need to check if it's a player.
			skill_bonus = self.owner.player_skills.skills['Dodge']
		bonus = sum(equipment.evade_bonus for equipment in get_all_equipped(self.owner))
		return self.base_evade + skill_bonus + bonus

	@property
	def block(self):  #Return actual block stat, by summing up bonuses from equipment and skills.
		if get_equipped_in_slot('left hand') == None: #No shield means no blocking.
			return 0
		skill_bonus = 0
		if self.owner.is_player(): #Monsters don't use skills, so we need to check if it's a player.
			skill_bonus = self.owner.player_skills.skills['Shields']
		bonus = sum(equipment.block_bonus for equipment in get_all_equipped(self.owner))
		return self.base_block + skill_bonus + bonus

	@property
	def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items as well as the current level.
		level_bonus = 0
		if self.owner.is_player():
			level_bonus = int(11.0 * (player.level / 2.0))
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + level_bonus + bonus

	def attack(self, target):
		damage = self.power

		if damage > 0:
			#make the target take some damage
			target.fighter.take_damage(damage, attacker = self)
	
	def accuracy_roll(self):
		return

	def take_damage(self, damage, attacker=None, piercing=0):
		if attacker:
			message(attacker.owner.name.title() + ' attacks ' + self.owner.name.title() + '.')
		
		was_evaded = self.evade_roll(attacker)
		if was_evaded:
			return
		was_blocked = self.block_roll(attacker)
		if was_blocked:
			return
		
		if piercing == 0:
			damage = self.armor_roll(damage)
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
			if self.owner is player:
				txt_color = libtcod.orange
			else:
				txt_color = libtcod.white
			message(self.owner.name.title() + ' is hit for ' + str(damage) + ' hit points.', txt_color, False)

			#check for death. if there's a death function, call it
			if self.hp <= 0:
				self.hp = 0 #So we don't go negative
				function = self.death_function
				if function is not None:
					function(self.owner)

				if self.owner != player:  #yield experience to the player
					player.fighter.xp += self.xp
	
	def armor_roll(self, damage):
		#a slightly less simple formula for attack damage
		armor_reduction = libtcod.random_get_int(0, 0, self.defense) #Roll a number, up to our combined armor value.
		damage -= armor_reduction #Reduce damage by how high we rolled.
		if damage <= 0: #If we completely negated the attack, let everyone know.
			message(self.owner.name.title() + "'s defenses compltely absorb the attack.", libtcod.grey, False)
		print self.owner.name + ' rolled ' + str(armor_reduction) + '.'
		return damage
	
	def evade_roll(self, attacker):
		if attacker:
			to_hit = attacker.owner.fighter.accuracy
			evade = self.evade
			
			if evade <= 0:
				return False #Don't bother rolling if we can never dodge
			
			to_hit_dice = libtcod.random_get_int(0, 0, to_hit)
			evade_dice_1 = libtcod.random_get_int(0, 0, evade)
			evade_dice_2 = libtcod.random_get_int(0, 0, evade)
			evade_dice = (evade_dice_1 + evade_dice_2) / 2
			if to_hit_dice >= evade_dice:
				return False #We failed to dodge.
			if evade_dice - to_hit_dice <= evade * 0.2:
				message(self.owner.name.title() + ' barely dodges the attack.', libtcod.grey, False)
			else:
				message(self.owner.name.title() + ' dodges the attack.', libtcod.grey, False)
			return True #We succeeded in dodging
		return
	
	def block_roll(self, attacker):
		to_hit = attacker.owner.fighter.accuracy
		shields = self.block
		
		if shields <= 0:
			return False #Don't bother rolling if we can never block.
		
		to_hit_dice = libtcod.random_get_int(0, 0, to_hit)
		block_dice_1 = libtcod.random_get_int(0, 0, shields)
		block_dice_2 = libtcod.random_get_int(0, 0, shields)
		block_dice = (block_dice_1 + block_dice_2) / 2
		if to_hit_dice >= block_dice:
			return False #We failed to block.
		if block_dice - to_hit_dice <= shields * 0.2:
			message(self.owner.name.title() + ' barely blocks the attack.', libtcod.grey, False)
		else:
			message(self.owner.name.title() + ' blocks the attack.', libtcod.grey, False)
		return True
		

	def heal(self, amount):
		#heal by the given amount, without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
	
	def adjust_max_hp(self, amount):
		self.max_hp = self.max_hp + amount

	def adjust_hp(self, amount):
		self.hp = self.hp + amount

	def adjust_all_hp(self, amount):
		self.max_hp = self.max_hp + amount
		self.hp = self.hp + amount
	
	def tick(self):
		if self.tick_total is None:
			self.tick_total = 0
		self.tick_total += 1
		self.autoheal()
		if self.owner.player_stats:
			self.owner.player_stats.autorecharge()
	
	def autoheal(self):
		if self.tick_total % (20) == 0:
			self.heal(1)
		

def do_after(target, delay):
	if target is None or delay is None:
		return 0
	start_tick = target.fighter.tick_total
	end_tick = target.fighter.tick_total + delay
	
	while not libtcod.console_is_window_closed():
		if target.fighter.tick_total >= end_tick:
			break
	
	
	'''
	while target.fighter.tick_total is not end_tick:
		pass
	'''
	return True

class PlayerStats: #Anything we want to track on the player specifically goes here
	def __init__(self, strength, agility, intelligence, oxygen, energy=0):
		self.base_strength = strength
		self.base_agility = agility
		self.base_intelligence = intelligence
		self.base_max_oxygen = oxygen
		self.oxygen = oxygen
		self.base_max_energy = energy
		self.energy = energy

	@property
	def strength(self):  #return actual strength, by summing up the bonuses from all equipped items
		bonus = sum(equipment.strength_bonus for equipment in get_all_equipped(self.owner))
		return self.base_strength + bonus

	@property
	def agility(self):  #return actual agility, by summing up the bonuses from all equipped items
		bonus = sum(equipment.agility_bonus for equipment in get_all_equipped(self.owner))
		return self.base_agility + bonus

	@property
	def intelligence(self):  #return actual intelligence, by summing up the bonuses from all equipped items
		bonus = sum(equipment.intelligence_bonus for equipment in get_all_equipped(self.owner))
		return self.base_intelligence + bonus

	@property
	def max_oxygen(self):  #return actual max_oxygen, by summing up the bonuses from all equipped items
		bonus = sum(equipment.oxygen_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_oxygen + bonus
	
	@property
	def max_energy(self):  #return actual max_energy, by summing up the bonuses from all equipped items
		bonus = sum(equipment.energy_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_energy + bonus

	def breathe(self, amount):
		#Reduce the oxygen by amount.
		if player.player_stats.race == 'Synthetic' or player.player_stats.race == 'Diona':
			return
		player.player_stats.oxygen -= amount
		#Check if we should suffocate.
		if self.oxygen <= 0:
			self.oxygen = 0 #so we don't go negative
			player.fighter.take_damage(5)

	def restore_oxygen(self, amount):
		#replenish the oxygen tank by amount
		self.oxygen += amount
		if self.oxygen > self.max_oxygen:
			self.oxygen = self.max_oxygen
	
	def adjust_max_oxygen(self, amount):
		self.max_oxygen = self.max_oxygen + amount

	def adjust_oxygen(self, amount):
		self.oxygen = self.oxygen + amount

	def adjust_all_oxygen(self, amount):
		self.max_oxygen = self.max_oxygen + amount
		self.oxygen = self.oxygen + amount
	
	def drain_energy(self, amount):
		self.energy -= amount
		if self.energy <= 0:
			self.energy = 0
	
	def recharge(self, amount):
		self.energy += amount
		if self.energy > self.max_energy:
			self.energy = self.max_energy

	def adjust_max_energy(self, amount):
		self.max_energy = self.max_energy + amount

	def adjust_all_energy(self, amount):
		self.max_energy = self.max_energy + amount
		self.energy = self.energy + amount

	def autorecharge(self):
		if self.owner.fighter.tick_total % (20) == 0:
			self.recharge(1)

	def change_race(self, race):
		self.race = race
	
	def change_title(self, title):
		self.title = title
	
	def adjust_strength(self, amount):
		self.strength = self.strength + amount

	def adjust_agility(self, amount):
		self.agility = self.agility + amount

	def adjust_intelligence(self, amount):
		self.intelligence = self.intelligence + amount

class PlayerSkills():
	skills = {}
	def __init__(self):
		self.skills = {
				'Command' : 0,
				'Fighting' : 0,
				'Armor' : 0,
				'Dodge' : 0,
				'Shields' : 0,
				'Stealth' : 0,
				'Unarmed Combat' : 0,
				'Short Blades' : 0,
				'Long Blades' : 0,
				'Blunt Weapons' : 0,
				'Axes' : 0,
				'Ballistics' : 0,
				'Energy' : 0,
				'Crossbow' : 0,
				'Throwing' : 0,
				'EVA' : 0,
				'Construction' : 0,
				'Electrical Engineering' : 0,
				'Heavy Machinery' : 0,
				'Complex Devices' : 0,
				'Info Tech' : 0,
				'Chemistry' : 0,
				'Medicine' : 0
				}
	def list_skills(self): #debug
		skills = self.skills
		for skill in skills:
			skills[skill] = skills[skill] + 1
			print skill
			print skills[skill]
			message(skill + ' is at level ' + str(skills[skill]) + '.', libtcod.cyan)



class BasicMonster:
	#AI for a basic monster.
	def take_turn(self):
		#a basic monster takes its turn. if you can see it, it can see you
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)

			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)
		monster.fighter.tick()

class ConfusedMonster:
	#AI for a temporarily confused monster (reverts to previous AI after a while).
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns

	def take_turn(self):
		if self.num_turns > 0:  #still confused...
			#move in a random direction, and decrease the number of turns confused
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1

		else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)
		self.owner.fighter.tick()

class Item:
	#an item that can be picked up and used.
	def __init__(self, use_function=None, stackable=False):
		self.use_function = use_function
		self.stackable = stackable
		self.stack = [self]
		
	def stacksize(self):
		return len(self.stack)

	def pick_up(self):
		#add to the player's inventory and remove from the map        
		if self.stackable:
			#check for existing stack
			existingindex = inventory_find(self.owner.name)
			if existingindex == -1:
				#No stack found, check if there is room in inventory to begin a new stack  
				if len(inventory) >= 26:
					message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
				else:
					#create a new stack
					inventory.append(self.owner)
					objects.remove(self.owner)
					message('You picked up a ' + self.owner.name + '!', libtcod.green)
			else:
				#add to existing stack
				existing_stack = inventory[existingindex]
				existing_stack.item.stack.append(self.owner)
				objects.remove(self.owner)
				message('You now have ' + str(existing_stack.item.stacksize()) + ' ' + self.owner.name + 's!', libtcod.green)
		else:
			if len(inventory) >= 26:
				message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
			else:
				inventory.append(self.owner)
				objects.remove(self.owner)
				message('You picked up a ' + self.owner.name + '!', libtcod.green)

				#special case: automatically equip, if the corresponding equipment slot is unused
				equipment = self.owner.equipment
				if equipment and get_equipped_in_slot(equipment.slot) is None:
					equipment.equip()

	def drop(self):
		#special case: if the object has the Equipment component, dequip it before dropping
		if self.owner.equipment:
			self.owner.equipment.dequip()

		if self.stackable and self.stacksize() > 1:
			#Drop 1 item of the stack
			dropobject = self.stack.pop()
			dropobject.x = player.x
			dropobject.y = player.y
			objects.append(dropobject)
			message('You dropped a ' + dropobject.name + '. (' + str(self.stacksize()) + ' remaining)', libtcod.yellow)
		else:
			#add to the map and remove from the player's inventory. also, place it at the player's coordinates
			objects.append(self.owner)
			inventory.remove(self.owner)
			self.owner.x = player.x
			self.owner.y = player.y
			message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

	def use(self):
		#special case: if the object has the Equipment component, the "use" action is to equip/dequip
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return

		#just call the "use_function" if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				if self.stackable and self.stacksize() > 1:
					self.stack.pop()
					message('You used a ' + self.owner.name + '. (' + str(self.stacksize()) + ' remaining)', libtcod.yellow)
				else:
					inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
 
class Equipment:
	#an object that can be equipped, yielding bonuses. automatically adds the Item component.
	def __init__(self, slot, power_bonus=0, accuracy_bonus=0, defense_bonus=0, evade_bonus=0, block_bonus=0,
						max_hp_bonus=0,strength_bonus=0, agility_bonus=0, intelligence_bonus=0, oxygen_bonus=0, energy_bonus=0):
		self.power_bonus = power_bonus
		self.accuracy_bonus = accuracy_bonus
		self.defense_bonus = defense_bonus
		self.evade_bonus = evade_bonus
		self.block_bonus = block_bonus
		self.max_hp_bonus = max_hp_bonus
		self.strength_bonus = strength_bonus
		self.agility_bonus = agility_bonus
		self.intelligence_bonus = intelligence_bonus
		self.oxygen_bonus = oxygen_bonus
		self.energy_bonus = energy_bonus

		self.slot = slot
		self.is_equipped = False

	def toggle_equip(self):  #toggle equip/dequip status
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()

	def equip(self, suppress_msg=False):
		#if the slot is already being used, dequip whatever is there first
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()

		#equip object and show a message about it
		self.is_equipped = True
		if suppress_msg is not True:
			message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

	def dequip(self, suppress_msg=False):
		#dequip object and show a message about it
		if not self.is_equipped: return
		self.is_equipped = False
		if suppress_msg is not True:
			message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
 

def get_equipped_in_slot(slot):  #returns the equipment in a slot, or None if it's empty
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None

def get_equipped_name_in_slot(slot):  #returns the name of the equiped item, if it exists.
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.name
	return 'nothing'
 
def get_all_equipped(obj):  #returns a list of equipped items
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return []  #other objects have no equipment
 
 
def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True

	#now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False
 
def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
 
def create_h_tunnel(x1, x2, y):
	global map
	#horizontal tunnel. min() and max() are used in case x1>x2
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
 
def create_v_tunnel(y1, y2, x):
	global map
	#vertical tunnel
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
 
def make_map(algor=None):
	global map, objects, stairs

	#the list of objects with just the player
	objects = [player]

	#fill map with "blocked" tiles
	map = [[ Tile(True)
			 for y in range(MAP_HEIGHT) ]
		   for x in range(MAP_WIDTH) ]

	rooms = []
	num_rooms = 0
	
	if algor == 'old' or algor == None:
		for r in range(MAX_ROOMS):
			#random width and height
			w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
			h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
			#random position without going out of the boundaries of the map
			x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
			y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

			#"Rect" class makes rectangles easier to work with
			new_room = Rect(x, y, w, h)

			#run through the other rooms and see if they intersect with this one
			failed = False
			for other_room in rooms:
				if new_room.intersect(other_room):
					failed = True
					break

			if not failed:
				#this means there are no intersections, so this room is valid

				#"paint" it to the map's tiles
				create_room(new_room)

				#add some contents to this room, such as monsters
				place_objects(new_room)

				#center coordinates of new room, will be useful later
				(new_x, new_y) = new_room.center()

				if num_rooms == 0:
					#this is the first room, where the player starts at
					player.x = new_x
					player.y = new_y
				else:
					#all rooms after the first:
					#connect it to the previous room with a tunnel

					#center coordinates of previous room
					(prev_x, prev_y) = rooms[num_rooms-1].center()

					#draw a coin (random number that is either 0 or 1)
					if libtcod.random_get_int(0, 0, 1) == 1:
						#first move horizontally, then vertically
						create_h_tunnel(prev_x, new_x, prev_y)
						create_v_tunnel(prev_y, new_y, new_x)
					else:
						#first move vertically, then horizontally
						create_v_tunnel(prev_y, new_y, prev_x)
						create_h_tunnel(prev_x, new_x, new_y)

				#finally, append the new room to the list
				rooms.append(new_room)
				num_rooms += 1

		#create stairs at the center of the last room
		stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
		objects.append(stairs)
		stairs.send_to_back()  #so it's drawn below the monsters

def place_objects(room):

	place_monsters(room)
	place_items(room)

def place_monsters(room):
	#maximum number of monsters per room
	max_monsters = from_dungeon_level([[1, 1], [2, 4], [3, 6]])

	#chance of each monster
	monster_chances = {}
	for monster_name in config.get('lists', 'monster list').split(', '):
		chance_table = json.loads(config.get(monster_name, 'chance'))
		monster_chances[monster_name] = from_dungeon_level(chance_table)



	# remember unique monsters
	uniques = []

	#choose random number of monsters
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)

	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			# choose a random monster
			choice = random_choice(monster_chances)
			
			# load the monster data from the config
			monster = dict(config.items(choice))
			
			# do not create multiple unique monsters
			if monster['unique'] == 'True':
				if choice in uniques:
					continue
				else:
					uniques.append(choice)
			
			
			# build the monster components (hp, defense, power, xp, death_function=None, species='Humanoid', evade = 10, block = 0, accuracy = 12):
			fighter_component = Fighter(
				hp=int(monster['hp']),
				defense=int(monster['defense']),
				power=int(monster['power']),
				xp=int(monster['xp']),
				death_function=globals().get(monster['death_function'], None),
				species = str(get_config(monster, 'species', 'Humanoid')),
				evade = int(get_config(monster, 'evade', '10')),
				block = int(get_config(monster, 'block', '0')),
				accuracy = int(get_config(monster, 'accuracy', '12')))
				
			# this gets a class object by name
			ai_class = globals().get(monster['ai_component'])
			
			# and this instanstiates it if not None
			ai_component = ai_class and ai_class() or None
			
			# finally we assemble the monster object
			monster = Object(x, y, monster['char'], choice,
				libtcod.Color(*tuple(json.loads(monster['color']))),
				blocks=True, fighter=fighter_component, ai=ai_component)
			objects.append(monster)
			print 'Placed a ' + choice + ' at ' + str(x) + ',' + str(y) + '.'

def place_items(room):

	#chance of each item (by default they have a chance of 0 at level 1, which then goes up)
	item_chances = {}
	for item_name in config.get('lists', 'item list').split(', '):
		chance_table = json.loads(config.get(item_name, 'chance'))
		item_chances[item_name] = from_dungeon_level(chance_table)

	#maximum number of items per room
	max_items = from_dungeon_level([[1, 1], [2, 4]])

	#choose random number of items
	num_items = libtcod.random_get_int(0, 0, max_items)

	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			choice = random_choice(item_chances)

			# load the item data from the config
			item = dict(config.items(choice))

			#First, we need to determine if it's an item or equipment.
			item_component = None
			equipment_component = None

			if item['type'] == 'item':
				#build the item component, using
				#(self, use_function=None, stackable=False)
				item_component = Item(
					stackable=bool(item['stackable']),
					use_function=globals().get(item['use_function'], None))
			elif item['type'] == 'equipment':
				#build the equipment component, using
				#(self, slot, power_bonus=0, accuracy_bonus=0, defense_bonus=0, evade_bonus=0, block_bonus=0, max_hp_bonus=0,strength_bonus=0, agility_bonus=0, intelligence_bonus=0, oxygen_bonus=0, energy_bonus=0):
				equipment_component = Equipment(
					slot=str(item['slot']), #We want an error to occur if slot is empty
					power_bonus = int(get_config(item, 'power', 0)), #get_config() lets us not need to define every single stat on an item in the config file
					accuracy_bonus = int(get_config(item, 'accuracy', 0)),
					defense_bonus = int(get_config(item, 'defense', 0)),
					evade_bonus = int(get_config(item, 'evade', 0)),
					block_bonus = int(get_config(item, 'block', 0)),
					max_hp_bonus = int(get_config(item, 'max_hp', 0)),
					strength_bonus = int(get_config(item, 'strength', 0)),
					agility_bonus = int(get_config(item, 'agility', 0)),
					intelligence_bonus = int(get_config(item, 'intelligence', 0)),
					oxygen_bonus = int(get_config(item, 'oxygen', 0)))
			else:
				#We probably messed up if this happens.
				print 'WARN: Made an item without any components.'
			
			# finally we assemble the object
			#Reminder: Here are the inputs we can fill, if we so choose.
			#(x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, player_stats=None, item=None, equipment=None)
			item = Object(x, y, item['char'], choice,
				libtcod.Color(*tuple(json.loads(item['color']))),
				blocks=False, item=item_component, equipment=equipment_component)
			objects.append(item)
			print 'Placed a ' + choice + ' at ' + str(x) + ',' + str(y) + '.'
			item.send_to_back()  #items appear below other objects
			item.always_visible = True  #items are visible even out-of-FOV, if in an explored area



def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)

	#render the background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
								 name + ': ' + str(value) + '/' + str(maximum))


def get_names_under_mouse():
	global mouse

	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	(x, y) = (camera_x + x, camera_y + y)  #from screen to map coordinates

	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

	names = ', '.join(names)  #join the names, separated by commas
	return names.title()

def move_camera(target_x, target_y):
	global camera_x, camera_y, fov_recompute

	#new camera coordinates (top-left corner of the screen relative to the map)
	x = target_x - CAMERA_WIDTH / 2  #coordinates so that the target is at the center of the screen
	y = target_y - CAMERA_HEIGHT / 2

	#make sure the camera doesn't see outside the map
	if x < 0: x = 0
	if y < 0: y = 0
	if x > MAP_WIDTH - CAMERA_WIDTH - 1: x = MAP_WIDTH - CAMERA_WIDTH - 1
	if y > MAP_HEIGHT - CAMERA_HEIGHT - 1: y = MAP_HEIGHT - CAMERA_HEIGHT - 1

	if x != camera_x or y != camera_y: fov_recompute = True

	(camera_x, camera_y) = (x, y)

def to_camera_coordinates(x, y):
	#convert coordinates on the map to coordinates on the screen
	(x, y) = (x - camera_x, y - camera_y)

	if (x < 0 or y < 0 or x >= CAMERA_WIDTH or y >= CAMERA_HEIGHT):
		return (None, None)  #if it's outside the view, return nothing

	return (x, y)

def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute

	move_camera(player.x, player.y)

	if fov_recompute:
		#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		libtcod.console_clear(con)

		#go through all tiles, and set their background color according to the FOV
		for y in range(CAMERA_HEIGHT):
			for x in range(CAMERA_WIDTH):
				(map_x, map_y) = (camera_x + x, camera_y + y)
				visible = libtcod.map_is_in_fov(fov_map, map_x, map_y)

				wall = map[map_x][map_y].block_sight
				if not visible:
					#if it's not visible right now, the player can only see it if it's explored
					if map[map_x][map_y].explored:
						if wall:
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
						else:
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
				else:
					#it's visible
					if wall:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
					#since it's visible, explore it
					map[map_x][map_y].explored = True

	#draw all objects in the list, except the player. we want it to
	#always appear over all other objects! so it's drawn later.
	for object in objects:
		if object != player:
			object.draw()
	player.draw()

	#blit the contents of "con" to the root console
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)


	#prepare to render the GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	libtcod.console_clear(log)

	#print the game messages, one line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(log, color)
		libtcod.console_print_ex(log, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1

	#show the player's stats
	libtcod.console_set_default_foreground(panel, libtcod.yellow)
	libtcod.console_print_ex(panel, 1, 1, libtcod.BKGND_NONE, libtcod.LEFT, player.name)
	libtcod.console_print_ex(panel, 1, 2, libtcod.BKGND_NONE, libtcod.LEFT, str(player.player_stats.title))
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, str(player.player_stats.race))
	libtcod.console_set_default_foreground(panel, libtcod.white)
	bar_y = 4
	render_bar(1, bar_y, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
			libtcod.dark_red, libtcod.darkest_red)
	bar_y += 2
	render_bar(1, bar_y, BAR_WIDTH, 'XP', player.fighter.xp, LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR,
			libtcod.green, libtcod.darker_green)
	bar_y += 2
	#This assumes the player is a non-synth.
	if player.player_stats.max_energy != 0:
		render_bar(1, bar_y, BAR_WIDTH, 'Energy', player.player_stats.energy, player.player_stats.max_energy,
				libtcod.darker_yellow, libtcod.darkest_yellow)
		bar_y += 2
	if player.player_stats.max_oxygen != 0:
		render_bar(1, bar_y, BAR_WIDTH, 'Oxy', player.player_stats.oxygen, player.player_stats.max_oxygen,
			libtcod.light_blue, libtcod.darker_blue)
		bar_y += 2

	yellow_text_y = 12
	yellow_text_left_x = 8
	yellow_text_right_x = 22
	libtcod.console_set_default_foreground(panel, libtcod.yellow) # Stats

	libtcod.console_print_ex(panel, PANEL_WIDTH / 2, yellow_text_y, libtcod.BKGND_NONE, libtcod.CENTER, '--Status--')
	yellow_text_y += 1
	libtcod.console_set_default_foreground(panel, libtcod.green)
	libtcod.console_print_ex(panel, PANEL_WIDTH / 2, yellow_text_y, libtcod.BKGND_NONE, libtcod.CENTER, 'Ideal')#NYI
	libtcod.console_set_default_foreground(panel, libtcod.yellow)
	yellow_text_y += 3

	libtcod.console_print_ex(panel, PANEL_WIDTH / 2, yellow_text_y, libtcod.BKGND_NONE, libtcod.CENTER, '--Statistics--')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Where:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Level:')
	yellow_text_y += 2
	
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Armor:')
	libtcod.console_print_ex(panel, yellow_text_right_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Str:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Evade:')
	libtcod.console_print_ex(panel, yellow_text_right_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Agi:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Block:')
	libtcod.console_print_ex(panel, yellow_text_right_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Int:')
	yellow_text_y += 2
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Money:')
	libtcod.console_print_ex(panel, yellow_text_right_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Time:')
	yellow_text_y += 2

	libtcod.console_print_ex(panel, PANEL_WIDTH / 2, yellow_text_y, libtcod.BKGND_NONE, libtcod.CENTER, '--Equipped Items--')
	yellow_text_y += 1
	
	libtcod.console_set_default_foreground(panel, libtcod.green) # Equipment
	#Also, yes, we're using yellow_text_y for green text.

	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'R Hand:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'L Hand:')
	yellow_text_y += 2
	
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Suit:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Exosuit:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Head:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Eyes:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Neck:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Belt:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Back:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Gloves:')
	yellow_text_y += 1
	libtcod.console_print_ex(panel, yellow_text_left_x, yellow_text_y, libtcod.BKGND_NONE, libtcod.RIGHT, 'Feet:')
	yellow_text_y += 1

	
	white_text_y = 17
	white_text_left_x = yellow_text_left_x + 2
	white_text_right_x = yellow_text_right_x + 2
	
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, 'Asteroid : ' + str(dungeon_level))
	white_text_y += 1
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.level))
	white_text_y += 2
	
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.fighter.defense))
	libtcod.console_print_ex(panel, white_text_right_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.player_stats.strength))
	white_text_y += 1
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.fighter.evade))
	libtcod.console_print_ex(panel, white_text_right_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.player_stats.agility))
	white_text_y += 1
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.fighter.block))
	libtcod.console_print_ex(panel, white_text_right_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.player_stats.intelligence))
	white_text_y += 2
	libtcod.console_print_ex(panel, white_text_right_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, str(player.fighter.tick_total))
	libtcod.console_print_ex(panel, white_text_left_x, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, "0") #NYI
	white_text_y += 3
	

	
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('right hand'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('left hand'))
	white_text_y += 2

	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('suit'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('exosuit'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('head'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('eyes'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('neck'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('belt'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('back'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('gloves'))
	white_text_y += 1
	libtcod.console_print_ex(panel, 10, white_text_y, libtcod.BKGND_NONE, libtcod.LEFT, get_equipped_name_in_slot('feet'))
	white_text_y += 2
	libtcod.console_set_default_foreground(panel, libtcod.yellow)
	libtcod.console_print_ex(panel, PANEL_WIDTH / 2, white_text_y, libtcod.BKGND_NONE, libtcod.CENTER, '--Abilities--')

	#display names of objects under the mouse
	libtcod.console_set_default_foreground(log, libtcod.light_gray)
	libtcod.console_print_ex(log, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

	#blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, PANEL_WIDTH, PANEL_HEIGHT, 0, PANEL_X, 0)

	#blit the contents of "log" to the root console
	libtcod.console_blit(log, 0, 0, LOG_WIDTH, LOG_HEIGHT, 0, 0, SCREEN_HEIGHT - LOG_Y)

def rest():
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.')
		player_action = 'didnt-take-turn'
	for obj in objects:
		if libtcod.map_is_in_fov(fov_map, obj.x, obj.y) and obj.fighter and obj is not player: #Suspend resting early if a monster is seen.
			message('There is a ' + str(obj.name) + ' nearby!',libtcod.red)
			player_action = 'didnt-take-turn'
		else:
			player_action = None
		

def player_move_or_attack(dx, dy):
	global fov_recompute

	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy

	#try to find an attackable object there
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break

	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
		player.player_stats.breathe(2) #Fighting is physically demanding.
	else:
		if not is_blocked(player.x + dx, player.y + dy): #Check if we can move into the new cell.
			player.move(dx, dy)
			fov_recompute = True
			player.player_stats.breathe(1)
		else: #Don't waste a turn if we bumped into a wall.
			return 'didnt-take-turn'
	player.fighter.tick()
	

def menu(header, options, width, transparency=0.7, return_string=False):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height

	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)

	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1

	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, transparency)

	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)

	if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen)

	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options):
		if return_string is True:
			return options[index]
		return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = []
		for itemobject in inventory:
			text = itemobject.name
			#show additional information, in case of a stack of items
			if itemobject.item and itemobject.item.stackable and itemobject.item.stacksize() > 1:
				text = str(itemobject.item.stacksize()) + ' ' + text + 's'
			#show additional information, in case it's equipped
			if itemobject.equipment and itemobject.equipment.is_equipped:
				text = text + ' (on ' + itemobject.equipment.slot + ')'
			options.append(text)

	index = menu(header, options, INVENTORY_WIDTH)

	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item

def inventory_find(itemname):
	#returns first index of item or -1 if the item is not found
	itemindex = -1
	for item in inventory:
		if item.name == itemname:
			itemindex = inventory.index(item)
	return itemindex

def msgbox(text, width=50):
	menu(text, [], width)  #use menu() as a sort of "message box"

def confirm_input():
	while not libtcod.console_is_window_closed():
		message("Uppercase [Y]es or [N]o, please.",libtcod.cyan)
		libtcod.console_flush()
		libtcod.console_clear(0)
		key = libtcod.console_wait_for_keypress(True)
		key_char = chr(key.c)
		if key_char == 'Y':
			return True
		elif key_char == 'N':
			return False
		else: #We need an answer!
			continue

def text_input():
	timer = 0
	x = 0
	window_x = 1
	window_y = SCREEN_HEIGHT - 1
	command = ''
	libtcod.console_print_ex(0, window_x-1, window_y, libtcod.BKGND_NONE, libtcod.LEFT, '>')
	libtcod.console_set_char_foreground(0, window_x-1, window_y, libtcod.white)
	while not libtcod.console_is_window_closed():

		key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)
		
		timer += 1
		if timer % (LIMIT_FPS // 4) == 0:
			if timer % (LIMIT_FPS // 2) == 0:
				timer = 0
				libtcod.console_set_char(0,  window_x+x,  window_y, "_")
				#libtcod.console_set_fore(0, x, 0, libtcod.white)
				libtcod.console_set_char_foreground(0, window_x+x, window_y, libtcod.white)
			else:
				libtcod.console_set_char(0, window_x+x,  window_y, " ")
				#libtcod.console_set_fore(0, x, 0, libtcod.white)
				libtcod.console_set_char_foreground(0, window_x+x, window_y, libtcod.white)
		
		if key.vk == libtcod.KEY_BACKSPACE and x > 0:
			libtcod.console_set_char(0, window_x+x,  window_y, " ")
			#libtcod.console_set_fore(0, x, 0, libtcod.white)
			libtcod.console_set_char_foreground(0, window_x+x, window_y, libtcod.white)
			command = command[:-1]
			x -= 1
		elif key.vk == libtcod.KEY_ENTER:
			break
		elif key.vk == libtcod.KEY_ESCAPE:
			command = ""
			break
		elif key.c > 0:
			letter = chr(key.c)
			libtcod.console_set_char(0, window_x+x, window_y, letter)  #print new character at appropriate position on screen
			#libtcod.console_set_fore(0, x, 0, libtcod.white)  #make it white or something
			libtcod.console_set_char_foreground(0, window_x+x, window_y, libtcod.white)
			command += letter  #add to the string
			x += 1

		libtcod.console_flush()

	libtcod.console_clear(0)
	print command
	return command

def handle_keys():
	global key

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game

	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		elif key.vk == libtcod.KEY_KP5:
			player.player_stats.breathe(1)
			player.fighter.tick()
			pass  #do nothing ie wait for the monster to come to you
		else:
			#test for other keys
			key_char = chr(key.c)

			if key_char == 'g':
				#pick up an item
				for object in objects:  #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break

			if key_char == 'i':
				#show the inventory; if an item is selected, use it
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()

			if key_char == 'd':
				#show the inventory; if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()

			if key_char == 'c':
				#show character information
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
					   '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
					   '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

			if key_char == '<':
				#go down stairs, if the player is on them
				if stairs.x == player.x and stairs.y == player.y:
					next_level()

			if key_char == 'r':
				#start resting until health/energy are full
				rest()

			if key_char == 'w':
				text_input()
			
			if key_char == '`':
				choice = text_input()
				if choice == 'reveal map':
					global map
					for x in range(0, MAP_WIDTH):
						for y in range(0, MAP_HEIGHT):
							map[x][y].explored = True
					global fov_recompute
					fov_recompute = True
					message('Revealing the current map\'s tiles.')
				
				elif choice == 'unreveal map':
					global map
					for x in range(0, MAP_WIDTH):
						for y in range(0, MAP_HEIGHT):
							map[x][y].explored = False
					global fov_recompute
					fov_recompute = True
					message('Unexploring the current map\'s tiles.')
				
				elif choice == 'heal':
					player.fighter.heal(player.fighter.max_hp)
					message('Health restored to full.')
				
				elif choice == 'xp':
					player.fighter.xp += 500
					message('XP granted.')
				
				elif choice == 'skills':
					player.player_skills.list_skills()
					message('Skills printed to console.')
				
				elif choice == 'adjust energy':
					amount = text_input()
					player.player_stats.recharge(int(amount))
					message('Energy adjusted by ' + str(amount) + '.')
				
				elif choice == 'test confirm':
					option = confirm_input()
					libtcod.console_wait_for_keypress(True)
					message('confirm_input() returned ' + str(option) + '.')
				
				elif choice == 'fireball':
					cast_fireball()

				
				else:
					message('Unknown command.')
				return 'didnt-take-turn'


			if key_char == '?':
				msgbox('Use the arrow keys or numpad to move.\
				\npress [i] to view your inventory.')
			
			return 'didnt-take-turn'

def message(new_msg, color = libtcod.white, append = True, ):
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]

		#add the new line as a tuple, with the text and the color
		if append:
			game_msgs.append( (line, color) )
		else: #We want multiple messages on the same line, if possible.
			if game_msgs:
				new_msg = game_msgs.pop()
				if color == libtcod.white and new_msg[1] is not color:
					color = new_msg[1]
				new_msg = new_msg[0]
				
				game_msgs.append( (new_msg + '  ' + line, color) )
			else: #We have an empty list
				game_msgs.append( (line, color) )

def check_level_up():
	#see if the player's experience is enough to level-up
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#it is! level up and ask to raise some stats
		player.level += 1
		player.fighter.xp -= level_up_xp

		message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)

		choice = None
		while choice == None:  #keep asking until a choice is made
			choice = menu('Level up! Choose a stat to raise:\n',
						  ['Strength (+1 strength, from ' + str(player.player_stats.strength) + ')',
						   'Agility (+1 agility, from ' + str(player.player_stats.agility) + ')',
						   'Intelligence (+1 intelligence, from ' + str(player.player_stats.intelligence) + ')'], LEVEL_SCREEN_WIDTH)

		if choice == 0:
			player.player_stats.strength += 1
		elif choice == 1:
			player.player_stats.agility += 1
		elif choice == 2:
			player.player_stats.intelligence += 1



def player_death(player):
	#the game ended!
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'

	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.dark_red

def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be
	#attacked and doesn't move
	message('The ' + monster.name + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.yellow)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def target_tile(max_range=None):
	global key, mouse
	#return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
	# track the position of keyboard targeting
	target_x, target_y = (player.x, player.y)
	target_col = libtcod.console_get_char_background(con, target_x, target_y)
	while not libtcod.console_is_window_closed():
		#render the screen. this erases the inventory and shows the names of objects under the mouse.
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
		render_all()

		# replace the previous background
		# so that if we return it does not leave artifacts on screen
		libtcod.console_set_char_background(con, target_x, target_y, target_col, flag=libtcod.BKGND_SET)

		(x, y) = (mouse.cx, mouse.cy)

		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)  #cancel if the player right-clicked or pressed Escape

		#accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
				(max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)

		if (key.vk in (libtcod.KEY_ENTER, libtcod.KEY_KPENTER) and
			libtcod.map_is_in_fov(fov_map, target_x, target_y) and
				(max_range is None or
				player.distance(target_x, target_y) <= max_range)):
			return (target_x, target_y)

		# move targeting reticule
		target_keys = {
					libtcod.KEY_KP4: (-1, +0),
					libtcod.KEY_KP6: (+1, +0),
					libtcod.KEY_KP2: (+0, +1),
					libtcod.KEY_KP8: (+0, -1),
					libtcod.KEY_KP7: (-1, -1),
					libtcod.KEY_KP9: (+1, -1),
					libtcod.KEY_KP1: (-1, +1),
					libtcod.KEY_KP3: (+1, +1),
					'h': (-1, +0),
					'l': (+1, +0),
					'j': (+0, +1),
					'k': (+0, -1),
					'y': (-1, -1),
					'u': (+1, -1),
					'b': (-1, +1),
					'n': (+1, +1),
					}
		
		direction = None
		if key.vk in target_keys.keys():
			direction = target_keys[key.vk]
		elif chr(key.c) in target_keys:
			direction = target_keys[chr(key.c)]
		
		if direction:
			# replace the previous background
			libtcod.console_set_char_background(con, target_x, target_y,target_col, flag=libtcod.BKGND_SET)
			# move the reticule: adjust current position by target_keys offset
			target_x += direction[0]
			target_y += direction[1]
			# get the new background
			target_col = libtcod.console_get_char_background(con, target_x, target_y)

		# draw the targeting reticule
		libtcod.console_set_char_background(con, target_x, target_y, libtcod.dark_flame, flag=libtcod.BKGND_SET)

def target_monster(max_range=None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x, y) = target_tile(max_range)
		if x is None:  #player cancelled
			return None

		#return the first clicked monster, otherwise continue looping
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def closest_monster(max_range):
	#find closest enemy, up to a maximum range, and in the player's FOV
	closest_enemy = None
	closest_dist = max_range + 1  #start with (slightly more than) maximum range

	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between this object and the player
			dist = player.distance_to(object)
			if dist < closest_dist:  #it's closer, so remember it
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def cast_heal():
	global player
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'

	message('You rub regenerative membrane on your wounds, and watch them close up before your eyes!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)

def cast_oxygen():
	#fill the player's oxygen tank
	if player.player_stats.oxygen == player.player_stats.max_oxygen:
		message('Your main oxygen tank is already full', libtcod.red)
		return 'cancelled'

	if player.player_stats.oxygen + 300 >= player.player_stats.max_oxygen:
		message('You decide to not refill your main oxygen tank, as it lacks sufficent capacity to hold the air you would\'ve introduced.', libtcod.red)
		return 'cancelled'

	message('You connect the new tank to your main one, turn a valve, and watch as the gague changes.', libtcod.light_violet)
	player.player_stats.restore_oxygen(300)

def cast_lightning():
	#find closest enemy (inside a maximum range) and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:  #no enemy found within maximum range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'

	#zap it!
	message('A lighting bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
			+ str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_fireball():
	#ask the player for a target tile to throw a fireball at
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

	for obj in objects:  #damage every fighter in range, including the player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)

def cast_confuse():
	#ask the player for a target to confuse
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'

	#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster  #tell the new component who owns it
	message('The eyes of the ' + monster.name + ' look vacant, as they start to stumble around!', libtcod.light_green)

def from_dungeon_level(table):
	#returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0

def save_game():
	#open a new empty shelve (possibly overwriting an old one) to write the game data
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)  #index of player in objects list
	file['stairs_index'] = objects.index(stairs)  #same for the stairs
	file['inventory'] = inventory
	file['abilities'] = abilities
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['dungeon_level'] = dungeon_level
	file.close()
 
def load_game():
	#open the previously saved shelve and load the game data
	global map, objects, player, stairs, inventory, game_msgs, game_state, dungeon_level, abilities

	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]  #get index of player in objects list and access it
	stairs = objects[file['stairs_index']]  #same for the stairs
	inventory = file['inventory']
	abilities = file['abilities']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	dungeon_level = file['dungeon_level']
	file.close()

	initialize_fov()
	message('Welcome back '+ player.name + '!', libtcod.green)

def new_game(player_name='John Doe',player_race='Human',player_title='Xenoarchelogist'):
	global player, game_msgs, game_state, dungeon_level

	#make a new player character
	new_player(player_name,player_race,player_title)

	#generate map (at this point it's not drawn to the screen)
	dungeon_level = 1
	make_map()
	initialize_fov()

	game_state = 'playing'


	#create the list of game messages and their colors, starts empty
	game_msgs = []

	#a warm welcoming message!
	message('Welcome '+ player.name + '!', libtcod.green)
	if player.player_stats.max_oxygen != 0:
		message('You enable your internal air supply and descend into the hollowed asteroid...', libtcod.yellow)
	else: #It makes no sense to turn on internals if we don't need them.
		message('You descend into the hollowed asteroid...', libtcod.yellow)


def new_player(player_name,player_race,player_title):
	global player, inventory, abilities
	
	#create object representing the player
	fighter_component = Fighter(hp=15, defense=0, power=2, xp=0, death_function=player_death)
	stats_component = PlayerStats(strength=8, agility=8, intelligence=8, oxygen=1000)
	skills_component = PlayerSkills()
	player = Object(0, 0, '@', player_name, libtcod.white, blocks=True, fighter=fighter_component, player_stats=stats_component, player_skills=skills_component)

	player.level = 1
	
	player.player_stats.change_race(player_race)
	player.player_stats.change_title(player_title)
	
	inventory = []
	abilities = []

	#Handle race bonuses
	if player_race is 'Tajaran':
		print 'meow'
		player.fighter.adjust_all_hp(-2)
		player.player_stats.adjust_agility(1)
		player.player_stats.adjust_strength(-1)
		
		#TODO: Add unarmed combat bonus
	
	if player_race is 'Unathi':
		print 'hiss'
		player.fighter.adjust_all_hp(6)
		player.player_stats.adjust_agility(-1)
		player.player_stats.adjust_strength(1)
		
		#TODO: Add ability to butcher corpses for food.
	
	if player_race is 'Skrell':
		print 'warble'
		player.fighter.adjust_all_hp(-2)
		player.player_stats.adjust_agility(-1)
		player.player_stats.adjust_intelligence(1)
		
		#TODO: Add increased breathing factor, free breathing in water, resist toxins
	
	if player_race is 'Synthetic':
		print 'beep'
		player.fighter.species = 'Synthetic'
		player.player_stats.adjust_all_oxygen(-player.player_stats.max_oxygen) #Remove all the oxygen completely.
		player.player_stats.adjust_all_energy(500)
		player.fighter.adjust_all_hp(20)
		player.fighter.base_defense += 3
		return
	
	if player_race is 'Diona':
		print 'creak'
		player.fighter.adjust_all_hp(24)
		player.player_stats.adjust_agility(-2)
		
		#TODO: Add light dependance, faster health regeneration
		

	#Handle profession bonuses
	if player_title is 'Xenoarchelogist' or player_title is 'Miner':
		#initial equipment: a pickaxe
		equipment_component = Equipment(slot='right hand', power_bonus=1, defense_bonus=1)
		obj = Object(0, 0, 'T', 'pickaxe', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True

	if player_title is 'Miner':
		#Miners are tougher, and so they start with more health and strength, but less of everything else.
		player.fighter.adjust_all_hp(8)
		
		player.player_stats.adjust_strength(2)
		player.player_stats.adjust_agility(-1)
		player.player_stats.adjust_intelligence(-1)
		
	
	if player_title is 'Security Officer':
		#initial equipment: a stunbaton
		equipment_component = Equipment(slot='right hand', power_bonus=2)
		obj = Object(0, 0, '|', 'stunbaton', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		player.player_stats.adjust_strength(1)
		player.player_stats.adjust_agility(-1)
	
	if player_title is 'Engineer':
		#initial equipment: a wrench
		equipment_component = Equipment(slot='right hand', power_bonus=1)
		obj = Object(0, 0, 'Y', 'wrench', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		#Engineers start with extra oxygen
		equipment_component = Equipment(slot='back', oxygen_bonus=500)
		obj = Object(0, 0, '0', 'O2 tank', libtcod.blue, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		player.player_stats.oxygen = player.player_stats.max_oxygen #a hack so the engi's oxygen starts full.
		
		player.player_stats.adjust_intelligence(1)
	
	if player_title is 'Scientist':
		#initial equipment: a wrench
		equipment_component = Equipment(slot='right hand', power_bonus=1)
		obj = Object(0, 0, 'Y', 'wrench', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		player.player_stats.adjust_strength(-2)
		player.player_stats.adjust_agility(-1)
		player.player_stats.adjust_intelligence(3)

	if player_title is 'Medical Doctor':
		#initial equipment: a wrench
		equipment_component = Equipment(slot='right hand', power_bonus=1)
		obj = Object(0, 0, 'Y', 'wrench', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		item_component = Item(use_function=cast_heal)
		item = Object(0, 0, '+', 'medical kit', libtcod.green, item=item_component)
		inventory.append(obj)
		item.always_visible = True
		
		player.player_stats.adjust_strength(1)
		player.player_stats.adjust_intelligence(1)
	
	if player_title is 'Roboticist':
		#initial equipment: a wrench
		equipment_component = Equipment(slot='right hand', power_bonus=1)
		obj = Object(0, 0, 'Y', 'wrench', libtcod.grey, equipment=equipment_component)
		inventory.append(obj)
		equipment_component.equip(True)
		obj.always_visible = True
		
		player.player_stats.adjust_agility(-1)
		player.player_stats.adjust_intelligence(1)

	#Everyone gets these.
	equipment_component = Equipment(slot='exosuit', defense_bonus=1)
	obj = Object(0, 0, 'H', 'voidsuit', libtcod.grey, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip(True)
	obj.always_visible = True

	equipment_component = Equipment(slot='head', defense_bonus=1)
	obj = Object(0, 0, 'H', 'space helmet', libtcod.grey, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip(True)
	obj.always_visible = True

	equipment_component = Equipment(slot='suit')
	obj = Object(0, 0, 'S', 'jumpsuit', libtcod.grey, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip(True)
	obj.always_visible = True

	equipment_component = Equipment(slot='feet')
	obj = Object(0, 0, 'b', 'shoes', libtcod.grey, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip(True)
	obj.always_visible = True

def next_level():
	#advance to the next level
	global dungeon_level
	message('You take a moment to rest, and recover your strength.', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%

	dungeon_level += 1
	message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
	make_map()  #create a fresh new level!
	initialize_fov()
 
def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True

	#create the FOV map, according to the generated map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
 
def play_game():
	global camera_x, camera_y, key, mouse
	global skip_turns

	player_action = None
	mouse = libtcod.Mouse()
	key = libtcod.Key()

	(camera_x, camera_y) = (0, 0)

	while not libtcod.console_is_window_closed():
		#render the screen
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()

		libtcod.console_flush()

		#erase all objects at their old locations, before they move
		for object in objects:
			object.clear()

		check_level_up()
	
		#handle keys and exit game if needed
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break

		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()

def main_menu():
	#libtcod.console_flush()
	libtcod.console_clear(0)
	while not libtcod.console_is_window_closed():

		#show the game's title, and some credits!
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
								 'CALAMITY')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Neerti')

		#show options and wait for the player's choice
		choice = menu('', ['Play a new game', 'Continue', 'Quit'], 24,1)

		if choice == 0:  #new game
			#new_game()
			#play_game()
			character_generation()
		if choice == 1:  #load last game
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2:  #quit
			break

def character_generation(player_name='John Doe',player_race='Human',player_title='Xenoarchelogist'):
	player_name
	player_race
	player_title
	#libtcod.console_flush()
	libtcod.console_clear(0)
	while not libtcod.console_is_window_closed():

		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,'Character Generation')

		#show options and wait for the player's choice
		libtcod.console_wait_for_keypress(True)
		choice = menu('', ['Play now', 'Change name', 'Change race', 'Change class', 'Return to menu'], 24, 1)

		if choice == 0:  #start with default stuff
			new_game(player_name,player_race,player_title)
			play_game()
			break
		if choice == 1:  #Ask for a name
			player_name = name_menu()
#			break
		elif choice == 2: #Open the race menu
			player_race = race_menu()
#			break
		elif choice == 3: #Open the class menu
			player_title = title_menu()
#			break
		elif choice == 4: #go back to menu
			main_menu()
			break

def race_menu():
	libtcod.console_wait_for_keypress(True)
	choice = menu('Choose your race.', ['Human', 'Tajaran', 'Unathi', 'Skrell', 'Synthetic'], 24, 1, return_string=True)
	return choice

def title_menu():
	libtcod.console_wait_for_keypress(True)
	choice = menu('Choose your profession.', ['Xenoarchelogist', 'Miner', 'Security Officer', 'Engineer', 'Medical Doctor', 'Roboticist', 'Cyberneticist', 'Assistant'], 24, 1, return_string=True)
	return choice

def name_menu():
	libtcod.console_set_default_foreground(0, libtcod.light_yellow)
	libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,'Please type your character\'s name, then press enter when finished.')
	choice = text_input()
	return choice

if __name__ == '__main__':
	#libtcod.console_set_custom_font('arial12x12.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
	libtcod.console_set_custom_font('terminal8x12_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
	libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Calamity', False)
	libtcod.sys_set_fps(LIMIT_FPS)
	con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
	panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
	log = libtcod.console_new(LOG_WIDTH, LOG_HEIGHT)

	config = ConfigParser.ConfigParser()
	config.read('dungeons.conf')

	main_menu()