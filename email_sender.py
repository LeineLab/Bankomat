from smtplib import SMTP
from email.mime.text import MIMEText
import user_config

class emailSender:
	def report(self, amount, name, target):
		try:
			text = 'Es wurde soeben eine Abschöpfung in Höhe von %.2f Euro für %s von %s vorgenommen.' % (amount, target, name)
			msg = MIMEText(text, 'plain')
			msg['Subject'] = 'Abschöpfung'
			msg['From'] = user_config.SMTP_SENDER
			smtp = SMTP(user_config.SMTP_HOST, 587)
			smtp.ehlo()
			smtp.starttls()
			smtp.ehlo()
			smtp.login(user_config.SMTP_USERNAME, user_config.SMTP_PASSWORD)
			success = False
			try:
				smtp.sendmail(user_config.SMTP_SENDER, [user_config.SMTP_RECEIVER], msg.as_string())
				success = True
			finally:
				smtp.quit()
				return success
		except:
			return False

if __name__ == '__main__':
	e = emailSender()
	e.report(0, 'test', 'testmail')
