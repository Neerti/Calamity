import libtcodpy as libtcod
import json
import ConfigParser
import textwrap
import CONSTANTS
def random_choice_index(chances):  #choose one option from list of chances, returning its index
	#the dice will land on some number between 1 and the sum of the chances
	dice = libtcod.random_get_int(0, 1, sum(chances))

	#go through all chances, keeping the sum so far
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w

		#see if the dice landed in the part that corresponds to this choice
		if dice <= running_sum:
			return choice
		choice += 1

def random_choice(chances_dict):
	#choose one option from dictionary of chances, returning its key
	chances = chances_dict.values()
	strings = chances_dict.keys()

	return strings[random_choice_index(chances)]

def get_config(config, target, false_return=None):
	if config.has_key(str(target)):
		data = config[str(target)]
		return data
	else:
		return false_return

def roll_dice(die):
	'''
	this function simulates rolling hit dies and returns the resulting 
	nbr of hitpoints. Hit dies are specified in the format xdy where
	x indicates the number of times that a die (d) with y sides is 
	thrown. For example 2d6 means rolling 2 six sided dices.
	Arguments
		hitdie - a string in hitdie format
	Returns
		integer number of a result
	'''
	#interpret the hitdie string
	d_index = die.lower().index('d')
	nbr_of_rolls = int(die[0:d_index])
	dice_size = int(die[d_index + 1:])
	#roll the dice
	role_count = 0
	result = 0
	while role_count <= nbr_of_rolls:
		role_count += 1
		result += libtcod.random_get_int(0, 1, dice_size)
	return result
