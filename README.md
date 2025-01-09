# Pocket Option Trading Bot
Bot for autotrade in [Pocket Option]()


### After authorization:
- set timeframe as `15 sec`
- set time as `15 sec`

### Information
Bot connects to websocket and receives signals every half a second from PO.
To make it more convenient, I simplify data to 1 second so that to use seconds
everywhere. After each change of currency, the screen reloads. It is to cut
unwanted signals from previous currencies.

### Pocket Option trading bot Martingale
`finmartbot.py` - Martingale trading. The default strategy is pretty simple. If the previous candles are red, the bot makes 'put' order. And 'call' otherwise. You can see a current Martingale stack in the console (Martingale stack). For example, Martingale stack [1, 3, 9] means that if you order $1 and lose, the next order will be $3, then $9, and will be reset to $1. You can change `MARTINGALE stack`.



### FAQ
`Is it free?`
Yes, the bot is fully free and you can use it without any payments.

`Is it profitable?`
No, my greedy friend. Sometimes, you can have profitable days, but you will lose all your money in the long run.

`What's the purpose of the Bot then?`
The goal of the bot is to strengthen your Python programming skills, motivating you with the illusory opportunity to get rich.

### Links
[Pocket Option registration link]()

[Telegram]()

[YouTube]()

### Donations
If you want to thank the author for his amazing work:

or

send your BTC here: ``
