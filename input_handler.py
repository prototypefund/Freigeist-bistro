#!/usr/bin/env python3

import threading, time, os
from recipe_handler import RecipeHandler
from bluetooth_handler import BluetoothHandler
from order_handler import OrderHandler
from keyboard_handler import KeyboardHandler

class InputHandler(threading.Thread):

	def __init__(self, verbose, bluetooth):
		# let python do the threading magic
		super().__init__()

		self.recipeHandler = RecipeHandler()
		self.orderHandler = OrderHandler(verbose)
		self.orderHandler.start()
		self.keyboardHandler = KeyboardHandler()
		self.keyboardHandler.start()

		self.bluetoothHandler = False
		if bluetooth:
			self.bluetoothHandler = BluetoothHandler()

		# nothing to send yet
		self.newMessage = False

	def run(self):
		# check user inputs and evaluate which action to take
		# will run infinetly and wait for inputs

		while True:
			if not self.recipeHandler.currentRecipe():
				self.nextRecipe()

			if self.bluetoothHandler and self.bluetoothHandler.receivedNewInput():
				self.handleBluetoothInput()

			if self.keyboardHandler.receivedNewInput():
				self.handleKeyboardInput()

			if self.orderHandler.receivedNewInput():
				self.handleOrderInput()

			time.sleep(.1)

	def nextRecipe(self):
		if (self.orderHandler.waiting()):
			self.recipeHandler.selectRecipe(self.orderHandler.nextDish())
			self.printStatus()
			self.assembleMessage()
		elif (self.recipeHandler.currentRecipe()):
			self.recipeHandler.selectRecipe("")
			self.printStatus()
			self.assembleMessage()

	def handleOrderInput(self):
		self.assembleMessage()

	def handleKeyboardInput(self):
		userInput = self.keyboardHandler.getInput()

		if userInput in self.recipeHandler.ingredients():
			# entered a valid ingredient
			print("- ", userInput)
			self.recipeHandler.useIngredient(userInput)
			self.assembleMessage()

		elif userInput in self.recipeHandler.dishes():
			# entered a valid dish
			self.orderHandler.waitinglist.append(userInput)
			self.assembleMessage()

		elif userInput == "+":
			# go to next recipe
			self.nextRecipe()

		elif userInput == "status":
			self.printStatus()

		elif userInput == "reset":
			# go back to zero
			print("Resetting program...")
			self.recipeHandler.reset()
			self.orderHandler.reset()
			self.assembleMessage()

		elif userInput == "exit":
			os._exit(1)

		else:
			print("Unbekannte Eingabe: " + userInput)


	def handleBluetoothInput(self):
		selected = self.bluetoothHandler.selection()

		if selected in self.recipeHandler.ingredients():
			# entered a valid ingredient
			print("- ", selected)
			self.recipeHandler.useIngredient(selected)
			self.assembleMessage()

		else:
			# everything else
			print("Unbekannte Eingabe: " + selected)

		print("")
		# wait for 100ms to save resources
		time.sleep(.1)

	def printStatus(self):
		print("\n> Current Recipe: ",
			self.recipeHandler.currentRecipe(),
			self.recipeHandler.currentIngredients(),
			"///", self.orderHandler.waiting(),
			"in waiting list\n")

	def assembleMessage(self):
		# assemble the message to be sent to the web browser
		# it takes the form of a JSON object looking something like this:
		# {
		#	banana: "neutral",
		#	tomato: "success",
		#	basil: "error",
		#	...
		# }

		self.message = {
			"recipe": self.recipeHandler.currentRecipe(),
			"waiting": self.orderHandler.waiting(),
			"ingredients": {}
		}

		# if the recipe is finished, blink for a bit and reset
		if self.recipeHandler.isReady():
			self.message["recipe"] = ""
			for i in self.recipeHandler.ingredients():
				self.message["ingredients"][i] = "blink" #blinking
			self.recipeHandler.selectRecipe("")
			self.newMessage = True
			return

		# iterating through all our available ingredients
		for i in self.recipeHandler.ingredients():
			if i in self.recipeHandler.currentIngredients():
				if self.recipeHandler.usedIngredients().count(i) == 1:
					# we used a required ingredient exactly once
					self.message["ingredients"][i] = "neutral" #grey

				elif self.recipeHandler.usedIngredients().count(i) > 1:
					# we tried using a required ingredients multiple times
					self.message["ingredients"][i] = "error" #red

				else:
					# we still need to use an ingredient
					self.message["ingredients"][i] = "success" #green

			else:
				if i in self.recipeHandler.usedIngredients():
					# not required but tried to use it
					self.message["ingredients"][i] = "error" #red

				else:
					# not required and not used
					self.message["ingredients"][i] = "neutral" #grey

		self.newMessage = True

	def getMessage(self):
		# distributing the message to the outer world
		self.newMessage = False
		# modifying the message so that javascript in the browser can understand it:
		return str(self.message).replace("'",'"')
		