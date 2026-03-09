# Bankomat user_config - copy to user_config.py and fill in your values

# MakerSpaceAPI connection
API_URL   = 'http://localhost:8000'
API_TOKEN = ''  # Bearer token for this bankomat device (from MakerSpaceAPI admin)

ACCOUNT_TARGET  = 'nfckasse'
DONATION_TARGET = 'donations'
CARDS_TARGET    = 'cards'

# NV9/NV10 bill acceptor serial port
NV9_10_USBPORT = '/dev/ttyUSB0'

# Optional guest card UID (raw bytes or None)
GUEST_UID = None

# SMTP data for email alerts
SMTP_USERNAME    = ''
SMTP_PASSWORD    = ''
SMTP_HOST        = ''
SMTP_SENDER      = ''
SMTP_RECEIVER    = ''

# Timezone for displaying transaction timestamps (IANA timezone name)
DISPLAY_TIMEZONE = 'Europe/Berlin'

# Test UID for manual testing (list of bytes, e.g. [0x04, 0xAB, 0xCD, 0xEF])
UID_TEST = [0, 0, 0, 0]
