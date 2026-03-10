# Bankomat - cash selfservice

[NFCKasse](https://github.com/LeineLab/NFCKasse) was meant to be a standalone project in the beginning.
Replace the open cash box for drinks with a tracable bookkeeping solution while maintaining privacy.
But after a while the cash to QR-code exchange was a bit annoying, so this project was born.

Bankomat – or in the case of LeineLab: the ScheineLab – is the solution to properly observed cash transactions.

## Features
- Top up cards to use in conjunction with NFCKasse to buy drinks, snacks or what ever you'd like to offer
- Accept donations – still the easiest way for many people, currently no feature for donation statements
- Buy a new NFC card
- Scroll through transactions associated with scanned card
- Transfer money between NFC card accounts
- Add treasurers, that can open the "safe" to withdraw the cash
- Accept coins and notes

## Menu
3 phyical buttons:
- Dontate -> accepts notes + coins
- Buy card -> accept coins to dispense a card
- Guest -> Top up the guest account

When scanning a NFC-Tag:
- 1 NFC account
  - 5 Top up account
    - Insert coins/notes, press OK
  - 6 Transactions
    - Shows a scrollable list of transactions
    - Pressing OK opens transaction details (date/price)
    - Return to list with Cancel
  - 7 Transfer
    - Input amount to transfer, confirm with OK, scan tag to transfer to
  - 8 Withdraw (Treasurer only)
- 3 Withdraw donations (Treasurer only)
- 4 Withdraw card purchases (Treasurer only)

Withdrawal opens the door to count money, the exact amount taken needs to be entered and confirmed, close door again.

## MAterial
- Raspberry Pi (we're using a 3B, but from B+ on any will do)
- NV9 USB note acceptor (off ebay, less than half the price)
- HX-913 up to HX-918 coin acceptor depending on how many different coins you need
- PN532 NFC reader (I2C)
- 20x4 LCD + PCF8547 Port-Expander
- 4x4 Keypad
- 3 buttons with backlight (not really necessary, depending on the features you want)
- Servo (for card dispensal)
- Electromagenetic lock (NC, opened by pulse, with feedback; could be a mechanic lock as well)
