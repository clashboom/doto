import cgi
import webapp2

from google.appengine.api import users


form = """
  <html>
  	<body>
  		<form action="/sign" method="post">
  			<div>
  				<textarea name="content" rows="10" cols="30"></textarea>
  			</div>
            <div>
                <input type="submit" value="Sign Guestbook" />
            </div>
  		</form>
  	</body>
  </html>
"""

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(form)

class Guestbook(webapp2.RequestHandler):
    def post(self):
        self.response.out.write('<html><body>You wrote: <pre>')
        self.response.out.write(cgi.escape(self.request.get('content')))
        self.response.out.write('</pre></body></html>')


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/sign', Guestbook)],
                                debug=True)