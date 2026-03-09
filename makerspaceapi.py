import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import logging
import settings

logger = logging.getLogger(__name__)

def _display_tz():
    tz_name = getattr(settings, 'DISPLAY_TIMEZONE', 'Europe/Berlin')
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning('Unknown DISPLAY_TIMEZONE %r, falling back to Europe/Berlin', tz_name)
        return ZoneInfo('Europe/Berlin')

class Transaction:
    def __init__(self, desc, value, date):
        self.desc = desc
        self.value = value
        tz = _display_tz()
        # date may be a UNIX timestamp (int/float) or ISO string
        if isinstance(date, (int, float)):
            self.date = datetime.fromtimestamp(date, tz=timezone.utc).astimezone(tz)
        else:
            try:
                dt = datetime.fromisoformat(str(date))
                if dt.tzinfo is None:
                    # treat naive datetimes from API as UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                self.date = dt.astimezone(tz)
            except Exception:
                self.date = datetime.fromtimestamp(0, tz=timezone.utc).astimezone(tz)

    def getDate(self):
        return self.date
    def getValue(self):
        return self.value
    def getDesc(self):
        return self.desc
    def toString(self):
        return "%s  %s  %6.2f" % (self.date.strftime('%d.%m.%y %H:%M'), self.desc, self.value)

class MakerSpaceAPI:
    _api_url   = 'http://localhost:8000'
    _api_token = ''

    @classmethod
    def configure(cls, api_url, api_token):
        cls._api_url   = api_url.rstrip('/')
        cls._api_token = api_token

    @staticmethod
    def _headers():
        return {'Authorization': f'Bearer {MakerSpaceAPI._api_token}'}

    @staticmethod
    def _base():
        return f'{MakerSpaceAPI._api_url}/api/v1'

    @staticmethod
    def ping():
        '''
        Check the public health endpoint to verify all actions can be processed.
        Does not verify that the used token is still valid!
        '''
        try:
            r = requests.get(
                f'{MakerSpaceAPI._api_url}/api/health',
                timeout=3,
            )
            return r.ok
        except requests.RequestException:
            return False
    
    def __init__(self, target, uid = 0):
        self._target = target
        self._uid = 0
        if isinstance(uid, (list, bytes, bytearray)):
            for i in uid:
                self._uid <<= 8
                self._uid += i
        else:
            self._uid = uid
        self._pin = None
    
    def changeTarget(self, target):
        self._target = target
    
    def getTarget(self):
        return self._target

    def isAdmin(self):
        '''Return True if this user has a PIN set (i.e. is a treasurer).'''
        if not self._uid:
            return False
        try:
            r = requests.get(
                f'{MakerSpaceAPI._base()}/users/nfc/{self._uid}',
                headers=MakerSpaceAPI._headers(),
                timeout=5,
            )
            if r.ok:
                return r.json().get('has_pin', False)
        except requests.RequestException:
            logger.exception('isAdmin check failed')
        return False

    def checkPin(self, pin):
        '''Verify the PIN against the API. Returns True only if the PIN is correct.'''
        self._pin = pin
        try:
            r = requests.post(
                f'{MakerSpaceAPI._base()}/bankomat/verify-pin',
                headers=MakerSpaceAPI._headers(),
                json={'nfc_id': self._uid, 'pin': pin},
                timeout=5,
            )
            return r.ok
        except requests.RequestException:
            logger.exception('checkPin failed')
            return False
    
    def getAdminName(self):
        if not self._uid:
            return None
        try:
            r = requests.get(
                f'{MakerSpaceAPI._base()}/users/nfc/{self._uid}',
                headers=MakerSpaceAPI._headers(),
                timeout=5,
            )
            if r.ok:
                return r.json().get('name') or str(self._uid)
        except requests.RequestException:
            logger.exception('getAdminName failed')
        return None

    def withdrawValue(self, value):
        '''Payout (withdraw) from a booking target. Requires PIN set via checkPin().'''
        try:
            r = requests.post(
                f'{MakerSpaceAPI._base()}/bankomat/payout',
                headers=MakerSpaceAPI._headers(),
                json={
                    'nfc_id':      self._uid,
                    'pin':         self._pin or '',
                    'target_slug': self._target,
                    'amount':      value,
                    'note':        f'Auszahlung zur Überweisung auf Bankkonto',
                },
                timeout=5,
            )
            if r.ok:
                return True
            logger.error('withdrawValue failed: %s %s', r.status_code, r.text)
            return False
        except requests.RequestException:
            logger.exception('withdrawValue failed')
            return False
    
    def getTotal(self):
        try:
            r = requests.get(
                f'{MakerSpaceAPI._base()}/bankomat/targets',
                headers=MakerSpaceAPI._headers(),
                timeout=5,
            )
            if r.ok:
                for t in r.json():
                    if t.get('slug') == self._target:
                        value = float(t.get('balance', 0))
                        return value
        except requests.RequestException:
            logger.exception('getTotal failed')
        return 0
    
    def addValue(self, value : float) -> bool:
        '''Record cash into a target (no user balance change — e.g. donations, card sales).'''
        if value is None or value <= 0:
            return False
        try:
            r = requests.post(
                f'{MakerSpaceAPI._base()}/bankomat/target-topup',
                headers=MakerSpaceAPI._headers(),
                json={'target_slug': self._target, 'amount': value},
                timeout=5,
            )
            if r.ok:
                self.getTotal()  # update MQTT sensors
                return True
            logger.error('addValue (target-topup) failed: %s %s', r.status_code, r.text)
            return False
        except requests.RequestException:
            logger.exception('addValue failed for source %s, value %.2f', self.source, value)
            return False

    def getCardValue(self) -> bool:
        try:
            r = requests.get(
                f'{MakerSpaceAPI._base()}/users/nfc/{self._uid}',
                headers=MakerSpaceAPI._headers(),
                timeout=5,
            )
            if r.ok:
                return round(float(r.json().get('balance', 0)), 2)
            return None
        except requests.RequestException:
            logger.exception('getCardValue failed')
            return None

    def addCardValue(self, value : float) -> float:
        '''Top up user account and record in nfckasse booking target.'''
        logger.info('Adding %.2f to nfckasse account uid %d', value, self._uid)
        if value is None or value <= 0:
            return False
        try:
            r = requests.post(
                f'{MakerSpaceAPI._base()}/bankomat/topup',
                headers=MakerSpaceAPI._headers(),
                json={
                    'nfc_id':      self._uid,
                    'amount':      value,
                    'target_slug': 'nfckasse',
                },
                timeout=5,
            )
            if r.ok:
                return round(float(r.json().get('balance', 0)), 2)
            logger.error('addValue (topup) failed: %s %s', r.status_code, r.text)
            return None
        except requests.RequestException:
            logger.exception('addValue failed')
            return None

    def transfer(self, value, destcard):
        '''Transfer balance to another card. destcard is raw bytes from NFC reader.'''
        dest_uid = 0
        for b in destcard:
            dest_uid <<= 8
            dest_uid += b

        if dest_uid == self._uid:
            logger.info('Transfer to same account stopped')
            return 1

        src_val = self.getValue()
        if src_val is None or value > src_val:
            return -1

        try:
            r = requests.post(
                f'{MakerSpaceAPI._base()}/bankomat/transfer',
                headers=MakerSpaceAPI._headers(),
                json={
                    'from_nfc_id': self._uid,
                    'to_nfc_id':   dest_uid,
                    'amount':      value,
                },
                timeout=5,
            )
            if r.ok:
                logger.info('Transfer successful')
                return 0
            if r.status_code == 404:
                logger.info('Destination account not found')
                return 2
            if r.status_code == 402:
                return -1
            logger.error('Transfer failed: %s %s', r.status_code, r.text)
            return 3
        except requests.RequestException:
            logger.exception('transfer failed')
            return 3

    def getTransactions(self, offset=0):
        try:
            limit = 4
            r = requests.get(
                f'{MakerSpaceAPI._base()}/bankomat/transactions/{self._uid}',
                headers=MakerSpaceAPI._headers(),
                params={'limit': limit + offset},
                timeout=5,
            )
            if not r.ok:
                return []
            all_tx = r.json()
            transactions = []
            for tx in all_tx[offset:offset + limit]:
                tx_type = tx.get('type', '')
                amount  = float(tx.get('amount', 0))
                date    = tx.get('created_at', 0)
                if tx_type == 'purchase':
                    desc = tx.get('note') or 'Kauf'
                elif tx_type in ('topup', 'booking_target_topup'):
                    desc = 'Aufladung'
                elif tx_type in ('transfer_out', 'transfer_in'):
                    desc = 'Überweisung'
                else:
                    desc = tx.get('note') or tx_type or 'Unbekannt'
                transactions.append(Transaction(desc, amount, date))
            return transactions
        except requests.RequestException:
            logger.exception('getTransactions failed')
            return []
