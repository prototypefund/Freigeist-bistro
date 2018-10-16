from flask import Flask
from flask_restful import Resource, Api
import threading, os, json
from order_sql_interface import OrderSQLInterface
from flask_cors import CORS

#the server that's responsible for handling user interactions from the dashboard
class WebServer(threading.Thread):
	def __init__(self, inputHandler):
		super().__init__()
		self.app = Flask(__name__)
		self.api = Api(self.app)
		CORS(self.app)
		self.dbPath = os.path.dirname(os.path.abspath(__file__))+'/recipes.db'
		self.orderSQLInterface = OrderSQLInterface(self.dbPath)
		self.inputHandler = inputHandler

		@self.app.route('/orders', methods=['GET'])
		def get_orders():
			#return all orders
			orders = self.orderSQLInterface.getOrderQueue()
			order_names = [order["order"] for order in orders]
			#print(order_names)
			#return "hallo"
			return json.dumps({"order_names": order_names})

		@self.app.route('/order', methods=['POST'])
		def post():
			self.inputHandler.orderHandler.addMealPreparation(...,...)
			return 'hello world'

		@self.app.route('/prepared_orders', methods=['GET'])
		def get_prepared_orders():
			#return all prepared orders
			orders = self.orderSQLInterface.getOrderQueue()
			order_names = [order["order"] for order in orders]
			#print(order_names)
			#return "hallo"
			return json.dumps({"order_names": order_names})

	def run(self):
		#for debug mode the flask server must run on the main thread
		self.app.run(debug=False)


