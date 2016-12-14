import webapp2
from google.appengine.api import users
from google.appengine.api import images
from google.appengine.ext import ndb
import jinja2
import os
import json
from datetime import datetime, timedelta
import sys

#need to check, some of the curr_user has been overrided due to the nick name so need to come up with new variable that has fixed email for them (transfer page has this prob)

class User(ndb.Model):
	email = ndb.StringProperty()
	amount = ndb.IntegerProperty()
	curr_code = ndb.StringProperty(default = '')
	transaction_history = ndb.StringProperty(repeated=True)
	nickname = ndb.StringProperty()
	image = ndb.BlobProperty()
	
class Code(ndb.Model):
	five_codes = ndb.StringProperty(repeated=True)
	ten_codes = ndb.StringProperty(repeated =True)					#can try JsonProperty to create a dictionary
	twenty_codes = ndb.StringProperty(repeated = True)
	fifty_codes = ndb.StringProperty(repeated = True)

class Vendor(ndb.Model):
	name = ndb.StringProperty()
	email = ndb.StringProperty()
	amount = ndb.IntegerProperty()
	site = ndb.StringProperty()
	transaction_history = ndb.StringProperty(repeated=True)
	
def user_key():
	return ndb.Key('user', 1)
	
def code_key():
	return ndb.Key('code',1)

	
JINJA_ENVIRONMENT = jinja2.Environment(				
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
	
#leaving code here (not in any handler) causes it to only be run when the app is updated

class MainHandler(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()			#check if the user is logged in
		if user:
			user_query = User.query(ancestor=user_key())			#query for User objects inside user_key()
			curr_user = user_query.filter(User.email==user.email())				#filter out current user's User object
			curr_user = curr_user.fetch(1)										#fetch to get a list with the current user's User object
			if not curr_user:						#first users of app, curr_user is empty
				curr_user = User(parent=user_key())								
				curr_user.email = user.email()					#create a new User object in user_key()and set email = current user and amount 0
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]						#get the curr_user object
			curr_transaction_history = []
			for i in curr_user.transaction_history:				#get curr_user's transaction history (stored as an array of json strings)
				curr_transaction_history.append(json.loads(i))
			login_url = users.create_logout_url("/")
			template = JINJA_ENVIRONMENT.get_template('index.html')
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())				#generates QR code using google charts API that links to the transfer page with the current user's email appended (to be read as a get value later)
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			template_values = {
				'login_url' : login_url,
				'mymoney' : curr_user.amount,
				'curr_user' : curr_user.email,
				'user_code_url' : user_code_url,
				'curr_transaction_history' : curr_transaction_history,
				'user_image': user_image
			}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
			self.response.out.write(template.render(template_values))
		else:							#if user is not logged in, redirect to log in page along with login url back to this page
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
class CreateCode(webapp2.RequestHandler):				#adds new prepaid codes to datastore
	def get(self):
		template = JINJA_ENVIRONMENT.get_template('usercode.html')
		user = users.get_current_user()
		if not user:			# not logged in, redirect to login page that will bring them back to main page
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
		elif users.is_current_user_admin():				#if user is admin of app
			self.response.out.write("""<form action="" method= "post"> 
							<select name="amount">
								<option value="10"> $10 </option>
								<option value="50"> $50 </option>
							</select>
							<p> Code: </p>
							<textarea name="code" placeholder="Enter code"></textarea>
							<br>
							<input type="submit"/>
						</form>""")
		else:		#if logged in but not admin
			self.redirect('/')
	def post(self):						#receives code values and processes them to datastore
		template = JINJA_ENVIRONMENT.get_template('usercode.html')
		user = users.get_current_user()
		if not user:						#if not logged in, go to login page with login link that directs back to main page
			login_text = "Log In"
			login_url = users.create_login_url('/createcode')
			template_values = {
				'login_text':login_text,
				'login_url': login_url
				}
			self.response.out.write(template.render(template_values))
		elif users.is_current_user_admin():
			new_code = self.request.get('code')
			if new_code:
				amount = self.request.get('amount')						#gets whether this is 10 or 50 dollar code
				code_query=Code.query(ancestor=code_key())				#queries of the code object (there should be only 1)
				code = code_query.fetch(1)
				if code:												#checks of there's currently a code object (may have been deleted/ new/etc reasons)
					code = code[0]
					if int(amount) == 10:								#if want to add new denominations, just need to add another (value)_codes StringProperty(repeated=True)  and add corresponding elif to this
						code.ten_codes.append(new_code)
					elif int(amount) == 50:
						code.fifty_codes.append(new_code)
				else:
					code=Code(parent=code_key())						#creates a new code object in code_key() if there isn't any
					if int(amount) == 10:								#if want to add new denominations, just need to add another (value)_codes StringProperty(repeated=True)  and add corresponding elif to this
						code.ten_codes = [new_code]
					elif int(amount) == 50:
						code.fifty_codes = [new_code]
				code.put()												#updates/creates the new code oject in datastore
				self.redirect('/createcode')							
		else:								#if logged in, redirect to main page
			self.redirect('/')
class ReceiveCredits(webapp2.RequestHandler):
    def get(self):
		approved = self.request.get('approval')								#to see if they approved adding the credits to this account
		code_query=Code.query(ancestor=code_key())
		code = code_query.fetch(1)											#fetching Code object from code_key()
		if code:
			code = code[0]
			ten_codes = code.ten_codes
			fifty_codes = code.fifty_codes
		else:
			ten_codes = []
			fifty_codes = []
		user = users.get_current_user()
		card_id = self.request.get('id')									#gets the specific prepaid card code
		if user:
			user_query = User.query(ancestor=user_key())					#getting the current user's object
			curr_user = user_query.filter(User.email==user.email())
			curr_user = curr_user.fetch(1)
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			login_url = users.create_logout_url('/receivecredits?id={0}'.format(card_id))
			if approved:													#checks if transaction is approved or not
				template = JINJA_ENVIRONMENT.get_template('topupApproved.html')		#this is after top up is approved
				curr_amount = curr_user.amount
				card_id = curr_user.curr_code
				if card_id in ten_codes:
					curr_amount += 10
					amount = 10
				elif card_id in fifty_codes:
					curr_amount += 50
					amount = 50
				else:
					amount = 0
				if card_id in ten_codes or card_id in fifty_codes:
					if len(curr_user.transaction_history) >= 50:
						del (curr_user.transaction_history[0])
						curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from Prepaid Card".format(str(amount)), "Prepaid Card", amount]))
					else:
						curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from Prepaid Card".format(str(amount)), "Prepaid Card", amount]))
				curr_user.amount = curr_amount
				curr_user.put()
				template_values = {
					'login_url' : login_url,
					'amount' : amount,
					'curr_user': curr_user.email,
					'curr_time': str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)),
					'curr_description': "Received {0} from Prepaid Card".format(str(amount)),
					'ten_codes': ten_codes,
					'fifty_codes': fifty_codes,
					'card_id': card_id,
					'user_code_url': user_code_url,
					'user_image': user_image
					}
				if curr_user.nickname:
					template_values['curr_user'] = curr_user.nickname
			else:
				template = JINJA_ENVIRONMENT.get_template('topup.html')
				if card_id in ten_codes:
					amount = 10
					curr_user.curr_code = str(card_id)
					curr_user.put()
				elif card_id in fifty_codes:
					amount = 50
					curr_user.curr_code = str(card_id)
					curr_user.put()
				else:
					amount = 0
				template_values = {
					'login_url' : login_url,
					'curr_user': curr_user.email, 
					'amount': amount,
					'ten_codes': ten_codes, 
					'fifty_codes': fifty_codes,
					'card_id': card_id,
					'user_code_url': user_code_url,
					'user_email': curr_user.email,
					'user_image': user_image
					}
				if curr_user.nickname:
					template_values['curr_user'] = curr_user.nickname
			curr_transaction_history = []		#need to be after transaction complete to sohw latest transaction
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			template_values['curr_transaction_history'] = curr_transaction_history				#adds the current_transaction history and (in the next line) the QR code link to the template_values
			template_values['user_code_url'] = user_code_url
			self.response.out.write(template.render(template_values))
			if approved:
				if card_id in ten_codes:
					code.ten_codes.remove(str(card_id))
				elif card_id in fifty_codes:
					code.fifty_codes.remove(str(card_id))
				code.put()
		else:
			card_id = self.request.get('id')
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/receivecredits?id=' + card_id)
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
class Transfer(webapp2.RequestHandler):			#need add login page
	def get(self):							#need to have a transaction id so that when the user pays, we can check the amount paid and the vendor that was paid and see if it tallies with the vendor's info which can be accessed using the ID
		recipient_email = self.request.get("user")
		user = users.get_current_user()
		if user:
			template = JINJA_ENVIRONMENT.get_template('transfer.html')
			login_url = users.create_logout_url('/transfer')
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			recipient_object = user_query.filter(User.email==recipient_email)
			recipient_object = recipient_object.fetch(1)
			if not recipient_object:
				recipient_object = User(parent=user_key())
				recipient_object.email = recipient_email
				recipient_object.amount = 0
			else:
				recipient_object = recipient_object[0]
			if recipient_object.nickname:
				recipient_details = "{0} ({1})".format(recipient_object.nickname, recipient_email)
			else:
				recipient_details = recipient_email
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			login_url = users.create_logout_url('/transfer')
			template_values = {
				'login_url': login_url,
				'user_code_url': user_code_url,
				'curr_transaction_history' : curr_transaction_history,
				'curr_user': curr_user.email,
				'recipient': recipient_email,
				'recipient_details': recipient_details,
				'user_code_url': user_code_url,
				'user_image': user_image
			}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
			self.response.out.write(template.render(template_values))
		else:
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/transfer')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))

	def post(self):					#should try to double check if the user really wants to send to this person
		user = users.get_current_user()
		template = JINJA_ENVIRONMENT.get_template('transferApproved.html')
		if user:
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			login_url = users.create_logout_url('/transfer')
			recipient_email = self.request.get("recipient")				#even if another person manages to guess this, it is pointless since they can only change who they are transferring to and not who is transferring, look at comment below
			amount = self.request.get("amount")								#pointless to change as well
			if not amount:
				amount = 0
			amount = int(amount)
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			recipient_query = User.query(ancestor=user_key())
			recipient = recipient_query.filter(User.email==recipient_email)
			recipient = recipient.fetch(1)
			if not recipient:
				recipient = User(parent=user_key())
				recipient.email = recipient_email
				recipient.amount = 0
			else:
				recipient = recipient[0]
			if curr_user.email == recipient.email or curr_user.amount<amount or amount<=0:
				template_values = {
					'login_url': login_url,
					'curr_user_email': curr_user.email,
					'curr_user_amount': curr_user.amount,
					'recipient_email': recipient.email,
					'amount': amount,
					'user_code_url': user_code_url,
					'curr_user': curr_user.email,
					'user_image': user_image}
			else:
				if len(curr_user.transaction_history) >= 50:
					del (curr_user.transaction_history[0])
					curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Paid ${0} to {1}".format(str(amount), recipient.email), recipient.email, amount]))
				else:
					curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Paid ${0} to {1}".format(str(amount), recipient.email)], recipient.email, amount))
				if len(recipient.transaction_history) >= 10:
					del (recipient.transaction_history[0])
					recipient.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from {1}".format(str(amount), curr_user.email), curr_user.email, amount]))
				else:
					recipient.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from {1}".format(str(amount), curr_user.email), curr_user.email, amount]))
				template_values = {
					'login_url': login_url,
					'curr_user_email': curr_user.email,
					'curr_user_amount': curr_user.amount,
					'amount': amount,
					'curr_user': curr_user.email,
					'curr_time': str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)),
					'user_code_url': user_code_url,
					'curr_description': "Paid ${0} to {1}".format(str(amount), recipient.email),
					'user_image': user_image
					}
				recipient.amount += amount
				curr_user.amount -= amount
				if curr_user.nickname:
					template_values['curr_user'] = curr_user.nickname
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			template_values['curr_transaction_history'] = curr_transaction_history
			self.response.out.write(template.render(template_values))
			recipient.put()
			curr_user.put()
		else:
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/transfer')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
			
class UserPay(webapp2.RequestHandler):		#userpay and userpayFailed html files need to be redone with the new template, need to change the balance tab name as well
	def get(self):
		user = users.get_current_user()
		vendor = self.request.get('vendor')
		amount = self.request.get('amount')
		template = JINJA_ENVIRONMENT.get_template('userpay.html')
		if user:
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			login_url = users.create_logout_url('/userpay')
			template_values = {
				'login_url': login_url,
				'vendor': vendor,
				'amount': amount,
				'curr_transaction_history': curr_transaction_history,
				'user_code_url': user_code_url,
				'curr_user': curr_user.email,
				'user_image': user_image
				}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
			self.response.out.write(template.render(template_values))
		else:			#need to maintain the data so that users after logging in don't have to change
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/userpay')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
		
	def post(self):
		user = users.get_current_user()
		if user:
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			login_url = users.create_login_url('/')
			curr_vendor = self.request.get('vendor')
			amount = self.request.get('amount')
			template = JINJA_ENVIRONMENT.get_template('userpayFailed.html')
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			vendor_query = Vendor.query()
			vendor = vendor_query.filter(Vendor.name==curr_vendor)				#user email is fixed to the person who has logged in
			vendor = vendor.fetch(1)
			template_values = {
				'curr_transaction_history': curr_transaction_history,
				'login_url': login_url,
				'curr_user': curr_user.email,
				'user_code_url': user_code_url,
				'user_image': user_image
			}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
			if int(curr_user.amount) < int(amount):
				template_values['main_body'] = "You do not have sufficient funds for this transaction"
				self.response.out.write(template.render(template_values))
			else:
				if not vendor:
					template_values['main_body'] = "This vendor does not exist"
					self.response.out.write(template.render(template_values))
				else:
					vendor = vendor[0]
					vendor.amount += int(amount)
					curr_user.amount -= int(amount)
					if len(curr_user.transaction_history) >= 50:
						del (curr_user.transaction_history[0])
						curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Paid ${0} to {1}".format(str(amount), vendor.name), vendor.name, amount]))
					else:
						curr_user.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Paid ${0} to {1}".format(str(amount), vendor.name), vendor.name, amount]))
					if len(vendor.transaction_history) >= 10:
						del (vendor.transaction_history[0])
						vendor.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from {1}".format(str(amount), curr_user.email), curr_user.email, amount]))
					else:
						vendor.transaction_history.append(json.dumps([str(datetime.strptime(str(datetime.now())[:19], "%Y-%m-%d %H:%M:%S")+timedelta(hours=8)), "Received ${0} from {1}".format(str(amount), curr_user.email), curr_user.email, amount]))
					vendor.put()
					curr_user.put()
					vendor_query = Vendor.query()
					vendor = vendor_query.filter(Vendor.name==curr_vendor)				#user email is fixed to the person who has logged in
					vendor = vendor.fetch(1)[0]
					self.redirect('https://' + str(vendor.site)+ "?approved=True")
		else:
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/userpay')
			template_values = {
				'login_url': login_url}
			self.response.out.write(template.render(template_values))
			
class About(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			template = JINJA_ENVIRONMENT.get_template('about.html')
			login_url = users.create_logout_url('/about')
			curr_user = user.email()
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			template_values = {
				'login_url': login_url,
				'curr_user': curr_user.email,
				'curr_transaction_history': curr_transaction_history,
				'user_code_url': user_code_url,
				'user': user,
				'user_image': user_image}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
		else:
			template = JINJA_ENVIRONMENT.get_template('about.html')
			login_url = users.create_login_url('/about')
			template_values = {
				'login_url': login_url,
				'user': user}
		self.response.out.write(template.render(template_values))
		
class Settings(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			template = JINJA_ENVIRONMENT.get_template('settings.html')
			login_url = users.create_logout_url('/about')
			curr_user = user.email()
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if curr_user.image:
				user_image = "/image?image="+curr_user.key.urlsafe()
			else:
				user_image = "/pictures/default_user.jpg"
			curr_transaction_history = []
			for i in curr_user.transaction_history:
				curr_transaction_history.append(json.loads(i))
			user_code_url = "https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl=cashitsg.appspot.com/transfer?user={0}&choe=UTF-8".format(user.email())
			template_values = {
				'login_url': login_url,
				'curr_user': curr_user.email,
				'curr_transaction_history': curr_transaction_history,
				'user_code_url': user_code_url,
				'user': user,
				'user_image': user_image}
			if curr_user.nickname:
				template_values['curr_user'] = curr_user.nickname
				template_values['curr_nickname'] = curr_user.nickname
		else:
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/settings')
			curr_user = ""
			template_values = {
				'login_url': login_url,
				'curr_user': curr_user,
				'user': user}
		self.response.out.write(template.render(template_values))
	def post(self):		#need to change if new settings are added
		user = users.get_current_user()
		if user:
			new_name = self.request.get("nickname")
			new_image = str(images.resize(self.request.get("newImage"),200,200))		#can't seem to add an exception for this
			user_query = User.query(ancestor=user_key())
			curr_user = user_query.filter(User.email==user.email())				#user email is fixed to the person who has logged in
			curr_user = curr_user.fetch(1)
			if not curr_user:
				curr_user = User(parent=user_key())
				curr_user.email = user.email()
				curr_user.amount = 0
			else:
				curr_user = curr_user[0]
			if new_name: 		#can be if else since if one is submitted then won't get the other
				curr_user.nickname = new_name
			elif new_image:
				curr_user.image = new_image
			curr_user.put()
			self.redirect('/settings')
		else:
			template = JINJA_ENVIRONMENT.get_template('login.html')
			login_url = users.create_login_url('/settings')
			curr_user = ""
			template_values = {
				'login_url': login_url,
				'curr_user': curr_user,
				'user': user}
			self.response.out.write(template.render(template_values))

class Image(webapp2.RequestHandler):
	def get(self):
		user_key = ndb.Key(urlsafe=self.request.get('image'))
		user = user_key.get()
		self.response.headers['Content-Type'] = 'image'
		self.response.out.write(user.image)
			
app = webapp2.WSGIApplication([
	('/', MainHandler),
    ('/receivecredits', ReceiveCredits),
	('/createcode', CreateCode),
	('/transfer', Transfer),
	('/userpay', UserPay),
	('/about', About),
	('/settings', Settings),
	('/image', Image)
], debug=True)