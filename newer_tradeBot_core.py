from . import api
from . import storage
from . import discord

import time
import logging
from datetime import date

class TradeBot():
	def __init__(self, testMode=False, resetBalance=False, daemon=False, verbose=False, baseAmount=1000.0):
		# Log
		logLevel = logging.INFO
		logFormat = "%(asctime)s %(levelname)s %(name)s: %(message)s"
		if daemon:
			logFile = "logs/trader_{}.log".format(date.today())
			logging.basicConfig(filename=logFile, format=logFormat, level=logLevel)
		else:
			logging.basicConfig(format=logFormat, level=logLevel)
		
		self._l = logging.getLogger("Trader")
		self._l.setLevel(logLevel)
		
		# Discord
		self.discord = discord.DiscordBot()
		self.discord.notify(":thought_balloon: Trader Started!")

		self.lastCycle = 0
		self.testMode = testMode
		self.verbose = verbose

		# Connect to exchange
		self.trader = api.TradeApi()
		if self.trader.binanceConnect():
			self._l.info("CONNECTED to Binance")
		
		# Storage
		self.stor = storage.Storage()
		self.tradeFee = self.stor.getFee("binance")
		
		# Get symbols to trade
		symbolList = self.loadTradeSymbolList()
		if not symbolList:
			self._l.error("No symbols found to trade! Analyze first...")
			return
		
		msg = "Trading symbols: {}".format(", ".join(symbolList))
		self._l.info(msg)
		self.discord.notify(msg)

		# Test mode OR Live mode
		if testMode:
			self._l.info("Setting cached balances...")
			self.stor.loadBalance()
			if resetBalance or not self.stor.getBalances():
				self._l.info("Resetting balances...")
				self.stor.resetBalance(symbolList)
				self.stor.setBalance(self.gblConf("baseSymbol"), baseAmount)
				self.stor.saveBalance()
		else:
			# Set symbols balance from exchange
			self._l.info("Setting live balances...")
			balance = self.trader.getBalance()
			for symbol in symbolList:
				if symbol in balance["free"]:
					self.stor.setBalance(symbol, balance["free"][symbol])
			self.stor.saveBalance()
		
		msg = "Current Balances: " + " | ".join(self.stor.getBalancesInfo())
		self._l.info(msg)
		self.discord.notify(msg)
	
	def timeToSec(self, strTime):
		suffixes = {"s":1, "m":60, "h":3600, "d":86400}
		for sfx in suffixes:
			if strTime[-1] == sfx:
				return int(strTime[:-1]) * suffixes[sfx]
		return int(strTime)
	
	def coin(self, symbol):
		return symbol.split("/")[0]
	
	def fiat(self, symbol):
		return symbol.split("/")[1]
	
	def gblConf(self, key):
		return self.stor.gblConf(key)
	
	def loadTradeSymbolData(self):
		return self.stor.loadSymbols()
	
	def loadTradeSymbolList(self):
		tradeSymbols = self.loadTradeSymbolData()
		if tradeSymbols is None:
			return []
		
		symList = []
		for mrkt in tradeSymbols["symbol"]:
			for symbol in mrkt.split("/"):
				if symbol not in symList:
					symList.append(symbol)
		
		return symList
	
	def getCandles(self, symbol, maxCandles=50):
		return self.trader.getCandles(symbol, self.gblConf("longCandle"), maxCandles)
	
	def getCandleStatus(self, candles):
		currPrice = candles["close"].iloc[-1]
		currOpen = candles["open"].iloc[-1]
		cdlDir = 1 if currPrice > currOpen else -1
		
		# Extend "open" search to revious candles
		for i in range(2, len(candles)+1):
			if cdlDir > 0 and candles["open"].iloc[-i] >= currOpen:
				break

			if cdlDir < 0 and candles["open"].iloc[-i] <= currOpen:
				break
			
			currOpen = candles["open"].iloc[-i]

		return cdlDir, currOpen, currPrice
	
	def getVolumeStatus(self, candles, bars=2):
		lastBar = candles["volume"].iloc[-bars]
		for i in range(1, bars+1)[::-1]:
			if lastBar < candles["volume"].iloc[-i]:
				return False

			if candles["close"].iloc[-i] < candles["open"].iloc[-i]:
				return False
			
			lastBar = candles["volume"].iloc[-i]
		
		return True
	
	def getSymbolEntry(self, symbol):
		return self.stor.getEntry(symbol)
	
	def hasSymbolEntry(self, symbol):
		return self.stor.hasEntry(symbol)

	def updateBalance(self, symbolList, valueList, entry, setAbsolute=False):
		if setAbsolute:
			self.stor.setBalance(symbolList[0], valueList[0])
			self.stor.setBalance(symbolList[1], valueList[1])
		else:
			self.stor.addBalance(symbolList[0], valueList[0])
			self.stor.addBalance(symbolList[1], valueList[1])

		self.stor.setEntry(symbolList[0], entry)
		self.stor.saveBalance()

		coinBlc = self.stor.getBalance(symbolList[0])
		fiatBlc = self.stor.getBalance(symbolList[1])
		balances = "{}: {} | {}: {}".format(symbolList[0], coinBlc, symbolList[1], fiatBlc)
		
		if entry != 0.0:
			self._l.info(" ** New Entry: {} at {}".format(symbolList[0], entry))
		else:
			self._l.info(" ** New Exit: {}".format(symbolList[0]))
		self._l.info(" ** Balance updated: "+balances)
		
	def buy(self, symbol, price, totalCost):
		# TODO: Make sure it's still possible to place order if price changes
		
		#Check for free balance
		coin, fiat = symbol.split("/")
		fiatBalance = self.stor.getBalance(fiat)
		if self.stor.getBalance(fiat) < totalCost:
			msg = "\n".join([
				"There isn't enough balance to buy {}".format(symbol),
				"Fiat balance: {} | Requested: {}".format(fiatBalance, totalCost)
			])
			self._l.error(msg)
			return {"success":False, "msg":msg}
		
		amount = self.gblConf("totalCost") / price / (1 + self.tradeFee)
		
		# Buy
		if not self.testMode:
			balances = self.trader.buy(symbol, amount)
			if balances is None:
				msg = "Failed to buy {} !".format(symbol)
				self._l.error(msg)
				return {"success":False, "msg":msg}
			
			self.updateBalance(
				[coin, fiat],
				[balances[fiat]["free"], balances[coin]["free"]],
				price,
				setAbsolute=True
			)
			
		else:
			self.updateBalance(
				[coin, fiat],
				[amount, -totalCost],
				price,
				setAbsolute=False
			)
		
		msg = "{0} Bought at {1}\nBalance: {2:.3f}".format(coin, price, self.stor.getBalance(coin))
		return {"success": True, "msg": msg}
	
	def sell(self, symbol, price, totalCost=0):
		#Check for free balance
		coin, fiat = symbol.split("/")
		coinBalance = self.stor.getBalance(coin)
		if totalCost == 0: 
			amount = coinBalance # Sell all
		else:
			amount = self.gblConf("totalCost") / price # Sell amount for cost
			if amount > coinBalance:
				msg = "\n".join([
					"There isn't enough balance to sell {}".format(symbol),
					"Coin balance: {} | Requested: {}".format(coinBalance, amount)
				])
				self._l.error(msg)
				return {"success": False, "msg":msg}
		
		# Sell
		if not self.testMode:
			balances = self.trader.sell(symbol, amount)
			if balances is None:
				msg = "Failed to sell {} !".format(symbol)
				self._l.error(msg)
				return {"success": False, "msg":msg}
			
			self.updateBalance(
				[coin, fiat],
				[balances[coin]["free"], balances[fiat]["free"]],
				0.0,
				setAbsolute=True
			)
			
		else:
			cost = amount * price / (1 + self.tradeFee)
			self.updateBalance(
				[coin, fiat],
				[-amount, cost],
				0.0,
				setAbsolute=False
			)
		
		msg = "{0} Sold at {1}\nBalance: {2:.2f}".format(coin, price, self.stor.getBalance(fiat))
		return {"success": True, "msg": msg}
	
	def tradeLoop(self):
		self._l.info("Trading!")
		interval = self.timeToSec(self.gblConf("shortCandle")) # 5min/1min?

		while True:
			if self.lastCycle > time.time() - interval:
				time.sleep(1)
				continue
			
			self.lastCycle = time.time()

			# Trade symbols in list
			symbols = self.stor.loadSymbols(cache=True)
			for symbol in symbols["symbol"]:
				symbolData = symbols.query("symbol == '{}'".format(symbol))
				
				# Data
				avgUp = symbolData["avgUp"].iloc[0]
				avgDown = symbolData["avgDown"].iloc[0]
				candles = self.getCandles(symbol)
				volumeValid = self.getVolumeStatus(candles)
				sDir, sOpen, sPrice = self.getCandleStatus(candles)
				
				if self.verbose:
					self._l.info("{}: Dir={}, Open={}, Close={}".format(symbol, sDir, sOpen, sPrice))

				# Logic
				if self.hasSymbolEntry(self.coin(symbol)):
					entryChange = sPrice / self.getSymbolEntry(self.coin(symbol)) - 1.0
					if sDir > 0 and entryChange > avgUp * 0.8: # Exit
						self._l.info(" ** Selling...")
						res = self.sell(symbol, sPrice) # Sell ALL
						self.discord.notify(res["msg"], icon=":green_circle:")
					
					elif sDir < 0 and entryChange < avgDown * self.gblConf("sellLossMult"): # Fail
						self._l.info(" ** Selling FLOP...")
						res = self.sell(symbol, sPrice) # Sell ALL
						self.discord.notify(res["msg"], icon=":red_circle:")
				
				else:
					candleChange = sPrice / sOpen - 1.0
					if sDir < 0 and candleChange < avgDown * 0.8: # Enter
					#if volumeValid: # Enter
						self._l.info(" ** Buying...")
						res = self.buy(symbol, sPrice, self.gblConf("totalCost"))
						self.discord.notify(res["msg"], icon=":blue_circle:")
			
			# Exit symbols not in list
			symbols = self.stor.getObsoleteSymbols(cache=True)
			for symbol in symbols:
				# Data
				candles = self.getCandles(symbol)
				sDir, sOpen, sPrice = self.getCandleStatus(candles)
				if self.verbose:
					self._l.info("{}: Dir={}, Open={}, Close={}".format(symbol, sDir, sOpen, sPrice))

				# Logic
				if self.hasSymbolEntry(self.coin(symbol)):
					entryChange = sPrice / self.getSymbolEntry(self.coin(symbol)) - 1.0
					if sDir > 0 and entryChange > self.tradeFee * 2.0:
						self._l.info(" ** Selling obsolete...")
						res = self.sell(symbol, sPrice) # Sell ALL
						self.discord.notify(res["msg"], icon=":yellow_circle:")
			
			if self.verbose:
				self._l.info("-----")