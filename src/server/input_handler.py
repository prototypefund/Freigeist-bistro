#!/usr/bin/env python3

import threading, time, os, asyncio, sys
from bluetooth_handler import BluetoothHandler
from order_handler import OrderHandler
from keyboard_handler import KeyboardHandler
from serial_handler import SerialHandler
from actions import Action

class InputHandler(threading.Thread):

	def __init__(self, verbose, bluetooth, fakeData, setupTags, websocket, recipeHandler):
		super().__init__()

		self.websocket = websocket
		self.recipeHandler = recipeHandler
		
		# initialize threads
		self.orderHandler = OrderHandler(self.recipeHandler, verbose, fakeData, websocket)
		self.orderHandler.start()
		self.keyboardHandler = KeyboardHandler()
		self.keyboardHandler.start()
		self.serialHandler = SerialHandler()
		self.serialHandler.start()

		# nothing to send yet
		self.message = ""
		self.afterStartup = True

		self.setupTags = setupTags
		self.bluetoothHandler = False
		if bluetooth:
			self.bluetoothHandler = BluetoothHandler()
		else:
			print("No Bluetooth available");
	

	def setupBluetooth(self):

		# Walk through all our ingredients
		# and wait until there is a tag being moved.
		# This tag will be assigned to the ingredient.
		self.bluetoothHandler.beginSetup()
		for i in self.recipeHandler.ingredients():
			print("setup",i)
			self.message = {
				"setup": 1,
				"recipe": "",
				"waiting": 0,
				"ingredients": {
					i: "use"
				}
			}
			self.message["action"] = Action.BT_SETUP

			self.sendMessageWithMsg(message=self.message)
			waitForTag = True
			while waitForTag:
				if self.bluetoothHandler.receivedNewInput():
					mac_address = self.bluetoothHandler.selection()
					self.bluetoothHandler.setupTag(i, mac_address)
					waitForTag = False

				time.sleep(.1)

		# Setup ready
		self.bluetoothHandler.setupReady()
		self.message = {
			"recipe": "",
			"waiting": 0,
			"ingredients": {}
		}
		self.message["action"] = Action.BT_READY

		self.sendMessageWithMsg(message=self.message)

	def run(self):

		#needed for async events (like sending via websocket) that don't need to be awaited
		asyncio.set_event_loop(asyncio.new_event_loop())

		if self.bluetoothHandler and self.setupTags:
			self.setupBluetooth()

		# check user inputs and evaluate which action to take
		# will run infinetly and wait for inputs

		while True:
			
			# for some reason keyboardInterrupts always reach bluetooththread first
			if self.bluetoothHandler and self.bluetoothHandler.btThread.isAlive() == False:
				print("bluetooththread quit, exiting")
				os._exit(1)

			if not self.recipeHandler.currentRecipe():
				self.nextRecipe()

			if self.bluetoothHandler and self.bluetoothHandler.receivedNewInput():
				self.handleBluetoothInput()

			if self.keyboardHandler.receivedNewInput():
				self.handleKeyboardInput()

			if self.serialHandler.receivedNewInput():
				self.handleSerialInput()

			time.sleep(.1)

	def nextRecipe(self):
		if (self.orderHandler.waiting() or self.afterStartup):
			print("next recipe")
			self.afterStartup = False
			self.recipeHandler.selectRecipe(self.orderHandler.nextDish())
			self.printStatus()
			self.sendMessage(Action.NEXT_ORDER)
		elif (self.recipeHandler.currentRecipe()):
			print("resetting recipe")
			self.recipeHandler.selectRecipe("")
			self.printStatus()
			self.sendMessage(Action.NEXT_ORDER)

	def nextIngredients(self):
		self.recipeHandler.getNextIngredients()
		self.printStatus()
		self.sendMessage(Action.NEXT_INGREDIENT)


	def handleOrderInput(self):
		self.assembleMessage(Action.NEXT_ORDER)

	def handleSerialInput(self):
		self.serialHandler.resetInputFlag()
		event = self.serialHandler.getButtonEvent()
		print("Received button event: " + str(event))

		if(event[0] == "0" and event[1] == "D"):
			self.nextIngredients()
		if(event[0] == "1" and event[1] == "D"):
			self.nextRecipe()
		if(event[0] == "2" and event[1] == "D"):
			self.orderHandler.reset()
		if(event[0] == "3" and event[1] == "D"):
			pass
		if(event[0] == "4" and event[1] == "D"):
			pass
		if(event[0] == "5" and event[1] == "D"):
			pass

	def handleKeyboardInput(self):
		userInput = self.keyboardHandler.getInput()

		if userInput in self.recipeHandler.ingredients():
			# entered a valid ingredient
			print("- ", userInput)
			self.recipeHandler.useIngredient(userInput)
			self.sendMessage(Action.NEXT_INGREDIENT)

		elif userInput in self.recipeHandler.dishes():
			# entered a valid dish
			self.orderHandler.appendToOrderQueue({
				"sauce": userInput,
				"name": userInput,
				"extras": ["+ Parmesan"],
				"recipe": self.recipeHandler.getRecipe(userInput) + ["Parmesan"] + self.recipeHandler.getDecorationFor(userInput),
				"preparation": self.recipeHandler.getPreparationFor(userInput)
			})

			self.sendMessage(Action.NEW_ORDER)

		elif userInput == "+":
			# go to next recipe
			self.nextRecipe()

		elif userInput == "status":
			self.printStatus()

		elif userInput == "setup":
			if self.bluetoothHandler:
				self.setupBluetooth()
			else:
				print("No bluetooth to set up")

		elif userInput == "reset":
			# go back to zero
			print("Resetting program...")
			self.recipeHandler.reset()
			self.orderHandler.reset()
			self.sendMessage(Action.CLEAR_QUEUE)

		elif userInput == "exit":
			os._exit(1)

		else:
			print("Unbekannte Eingabe: " + userInput)


	def handleBluetoothInput(self):
		selected = self.bluetoothHandler.selection()

		if selected in self.recipeHandler.currentIngredients():
			self.sendMessage(Action.NEXT_INGREDIENT)

		if selected in self.recipeHandler.ingredients():
			# entered a valid ingredient
			print("- ", selected)
			self.recipeHandler.useIngredient(selected)

			#self.assembleMessage(Action.NEXT_INGREDIENT)

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

	def assembleMessage(self, action):
		# assemble the message to be sent to the web browser
		# it takes the form of a JSON object looking something like this:
		# {
		#	recipe: "Antipasti"
		#	waiting: 4
		#	ingredients: {
		#		banana: "neutral",
		#		tomato: "success",
		#		basil: "error",
		#		...
		#	}
		# }

		if action != Action.CLEAR_QUEUE:
			self.message = {
				"recipe": self.recipeHandler.currentRecipe(),
				"extras": self.recipeHandler.currentExtras(),
				"preparation": self.recipeHandler.currentPreparation(),
				"waiting": self.orderHandler.waiting(),
				"ingredients": {},
				"action": action.value
			}

			# if the recipe is finished, blink for a bit and reset
			if self.recipeHandler.isReady():
				self.message["recipe"] = ""
				self.message["extras"] = ""
				self.message["preparation"] = ""
				for i in self.recipeHandler.ingredients():
					self.message["ingredients"][i] = "ready" #blinking
				self.recipeHandler.selectRecipe("")
				self.orderHandler.orderSQLInterface.recipeReady()
				if self.bluetoothHandler:
					self.bluetoothHandler.resetSelection()

				#time.sleep(5)
			else:
				self.message["ingredients"] = self.recipeHandler.getIngredientStatus()
				self.message["error"] = self.recipeHandler.getError()

		else:
			self.message = {
				"action": action
			}


		# modifying the message so that javascript in the browser can understand it:
		return str(self.message).replace("'",'"')

	def sendMessage(self, action):
		loop = asyncio.get_event_loop()
		task = loop.create_task(self.websocket.sendMessage(self.assembleMessage(action)))
		loop.run_until_complete(task)

	def sendMessageWithMsg(self, message):
		loop = asyncio.get_event_loop()
		task = loop.create_task(self.websocket.sendMessage(message))
		loop.run_until_complete(task)

	def reboot(self):
		print("restarting")
		time.sleep(1)
		asyncio.set_event_loop(asyncio.new_event_loop())
		# notify the frontends to restart in 10 s and then so long until the server is back again
		self.sendMessage(Action.RESTART)
		os.system('reboot')
		#os.execv(sys.executable, ['python'] + sys.argv)
